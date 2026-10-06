import asyncio
import json
from copy import deepcopy

import pytest

from mammoth_os.agents.curriculum_agent import CurriculumAgent, LessonAuthoringError


def outline_for(course):
    rows = [lesson for module in course["modules"] for lesson in module["lessons"]]
    topics = ["Nutrition vocabulary", "Energy and balance", "Carbohydrates and fiber", "Protein and amino acids",
              "Fats and food sources", "Vitamins and minerals", "Reading food labels", "Dietary patterns", "Planning and reviewing meals"]
    return {"lessons": [
        {"lesson_id": row["lesson_id"], "title": topics[index], "subtopic": topics[index],
         "objectives": [f"Explain {topics[index]}", f"Apply {topics[index]} in practice"],
         "prerequisites": [rows[index - 1]["lesson_id"]] if index else []}
        for index, row in enumerate(rows)
    ]}


@pytest.fixture
def agent():
    return CurriculumAgent(None)


@pytest.fixture
def course(agent):
    return agent._build_template_curriculum("Nutrition", "nutrition", "now")


def install(monkeypatch, payload):
    class Client:
        def __init__(self):
            self.calls = []
        async def generate(self, prompt, **kwargs):
            self.calls.append(prompt)
            return json.dumps(payload)
    client = Client()
    monkeypatch.setattr("mammoth_os.agents.curriculum_agent.get_llm_client", lambda: client)
    return client


def test_outline_covers_distinct_topics_and_preserves_ids(agent, course, monkeypatch):
    planned = outline_for(course)
    client = install(monkeypatch, planned)
    result = asyncio.run(agent._plan_curriculum(course, "Nutrition", {"recommended_difficulty": "beginner"}))
    rows = [lesson for module in result["modules"] for lesson in module["lessons"]]
    assert [row["title"] for row in rows] == [row["title"] for row in planned["lessons"]]
    assert result["outline_status"] == "validated_structure"
    assert len(client.calls) == 1
    assert "every named part" in client.calls[0]


@pytest.mark.parametrize("defect", ["count", "future", "identity", "duplicate"])
def test_invalid_outline_is_rejected_before_authoring(agent, course, monkeypatch, defect):
    planned = outline_for(course)
    if defect == "count":
        planned["lessons"].pop()
    elif defect == "future":
        planned["lessons"][0]["prerequisites"] = ["nutrition-m3-l3"]
    elif defect == "identity":
        planned["lessons"][0]["lesson_id"] = "invented"
    else:
        planned["lessons"][1]["subtopic"] = planned["lessons"][0]["subtopic"]
    install(monkeypatch, planned)
    original = deepcopy(course)
    with pytest.raises(ValueError):
        asyncio.run(agent._plan_curriculum(course, "Nutrition", {}))
    assert course == original


def test_failed_outline_does_not_spend_on_nine_lessons(agent, course, monkeypatch):
    install(monkeypatch, {"lessons": []})
    monkeypatch.setattr(agent, "_author_lesson_with_llm", lambda *args, **kwargs: pytest.fail("No author calls after failed outline"))
    result = agent._enrich_curriculum_lessons(course, "Nutrition", {})
    assert result["generation_diagnostics"][0]["code"] == "sequence_planning_failed"
    assert all(not row.get("content") for module in result["modules"] for row in module["lessons"])


def test_authors_receive_real_sequence_and_navigation_is_manifest_derived(agent, course, monkeypatch):
    sequence = outline_for(course)["lessons"]
    lesson = {**sequence[0], "source": "template"}
    body = ("Nutrition vocabulary defines what energy, food, and nutrients mean before we compare dietary choices. " * 20).strip()
    payload = {**lesson, "summary": "Nutrition vocabulary.", "content": body,
               "estimated_minutes": 20, "teaching_points": ["Food provides energy.", "Nutrients have distinct roles.", "Dietary choices have context."],
               "examples": ["Example one: compare a food label step by step.", "Example two: distinguish energy from nutrient amounts."]}
    client = install(monkeypatch, payload)
    result = asyncio.run(agent._author_lesson_with_llm(lesson, subject="Nutrition", module_title="Foundations", curriculum_title="Nutrition", course_sequence=sequence))
    assert result["next_lesson_id"] == sequence[1]["lesson_id"]
    assert result["next_lesson_title"] == sequence[1]["title"]
    assert result["content"].endswith("Next lesson: Energy and balance.")
    assert "Vitamins and minerals" in client.calls[0]
    payload["content"] += "\n\nIn the next lesson we will cover vitamins."
    corrected = asyncio.run(agent._author_lesson_with_llm(lesson, subject="Nutrition", module_title="Foundations", curriculum_title="Nutrition", course_sequence=sequence))
    assert "cover vitamins" not in corrected["content"]
    assert corrected["content"].endswith("Next lesson: Energy and balance.")
    assert corrected["sequence_review"]["removed_forward_promises"]


def test_numerical_study_examples_must_be_labeled(agent):
    lesson = {"lesson_id": "n1", "title": "Nutrition studies"}
    body = ("Nutrition studies need careful comparison of methods, populations, and limitations before applying findings. " * 20).strip()
    payload = {"title": lesson["title"], "summary": "Evaluate evidence.", "content": body + "\n\nA study of 100 participants found a 40% improvement.",
               "objectives": ["Distinguish observations from causes"], "estimated_minutes": 20,
               "teaching_points": ["Comparisons require context.", "Associations are not causes.", "Population differences matter."],
               "examples": ["Trace an illustrative comparison with two groups.", "Identify alternative explanations in a scenario."]}
    with pytest.raises(LessonAuthoringError) as failure:
        agent._parse_authored_lesson(json.dumps(payload), lesson, subject="Nutrition")
    assert failure.value.code == "unsupported_study_claim"
    payload["content"] = body + "\n\nHypothetical example: a study of 100 participants found a 40% improvement."
    assert agent._parse_authored_lesson(json.dumps(payload), lesson, subject="Nutrition")["status"] == "ready"
