import asyncio
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import api_server
import mammoth_os.atlas_session as session_module
from mammoth_os.agents.curriculum_agent import CurriculumAgent, LessonAuthoringError
from mammoth_os.agents.curriculum_validation_v2 import validate_curriculum
from mammoth_os.curriculum_library import prepare_curriculum, save_curriculum, list_curricula
from mammoth_os.learner_model import build_learner_context, build_lesson_plan, set_onboarding_profile
from mammoth_os.learner_model import update_learner_model
from mammoth_os.tutor_delivery import curriculum_readiness


@pytest.fixture(autouse=True)
def bypass_outline_for_legacy_lesson_tests(monkeypatch):
    async def existing_outline(self, curriculum, *args):
        return curriculum
    monkeypatch.setattr(CurriculumAgent, "_plan_curriculum", existing_outline)


@pytest.fixture
def course():
    lesson = {
        "lesson_id": "lesson-one", "title": "Python variables", "source": "authored",
        "summary": "Store a value and inspect changes.", "estimated_minutes": 20,
        "content": " ".join([
            "A Python variable is a name that refers to a value. Start by opening a Python interpreter and entering age = 25. "
            "The equals sign assigns the value on its right to the name on its left. It does not ask whether two values are equal. "
            "When you enter print(age), Python looks up the name and displays its current value. Choose names that describe the information they hold. "
            "Next enter age = age + 1. Python first reads the current value, adds one, and assigns the result back to the same name. "
            "Printing age now displays 26. The name remains the same while the value it refers to has changed. "
            "A second example uses temperature = 18. Add two degrees by assigning temperature = temperature + 2, then print the result. "
            "You should see 20. Trace each assignment before running it and compare your prediction with the actual result. "
            "If you accidentally use an undefined name, check its spelling and ensure the earlier assignment ran. "
            "For guided practice, assign a starting score, increase it by five, and explain the output in your own words. "
            "This lesson prepares you to combine named values into expressions and later use conditions to make decisions."
        ]),
        "objectives": ["Assign a named value", "Explain reassignment"],
        "teaching_points": ["Assignment binds a name to a value.", "Names describe the data being stored.", "Reassignment updates the value associated with a name."],
        "examples": ["age = 25; age = age + 1 produces 26.", "temperature = 18; temperature = temperature + 2 produces 20."],
    }
    second = deepcopy(lesson)
    second["lesson_id"] = "lesson-two"
    second["title"] = "Python expressions"
    second["content"] = "Expressions combine Python values. " + second["content"]
    return {"curriculum_id": "course-one", "subject": "Python", "title": "Python foundations",
            "modules": [{"module_id": "module-one", "title": "Foundations", "lessons": [lesson, second]}]}


def test_whole_course_is_invalid_when_one_lesson_fails(course):
    course["modules"][0]["lessons"][0]["content"] = "Thin introduction..."
    valid, validation = validate_curriculum(course)
    assert not valid
    assert validation["summary"]["valid_lessons"] == 1
    assert not curriculum_readiness(course)["ready"]


def test_readiness_rejects_template_truncation_duplicates_and_claimed_success(course):
    assert curriculum_readiness(course)["ready"]
    course["quality"] = {"ready": True}
    course["modules"][0]["lessons"][1] = deepcopy(course["modules"][0]["lessons"][0])
    quality = prepare_curriculum(course)["quality"]
    assert not quality["ready"]
    assert any("unique" in error for error in quality["lessons"][1]["errors"])
    assert any("duplicates" in error for error in quality["lessons"][1]["errors"])
    course["modules"][0]["lessons"][0]["source"] = "template"
    assert not curriculum_readiness(course)["lessons"][0]["ready"]


def test_library_persists_exact_course_and_does_not_overwrite_corruption(course, tmp_path):
    path = tmp_path / "library.json"
    saved = save_curriculum(path, course)
    assert saved["curriculum"]["quality"]["ready"]
    assert list_curricula(path)[0]["curriculum"]["modules"] == course["modules"]
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        save_curriculum(path, course)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_profile_level_is_not_overridden_by_fast_pacing(tmp_path):
    state = {}
    model = set_onboarding_profile(state, user_id="learner", storage_path=str(tmp_path),
                                   onboarding={"experience_level": "beginner", "preferred_pacing": "challenge"})
    assert build_learner_context(model)["recommended_difficulty"] == "beginner"
    model["onboarding"]["experience_level"] = "expert"
    assert build_lesson_plan({"learner_model": model}, "Python")["difficulty"] == "expert"
    model["recent_outcomes"] = [{"passed": False}, {"passed": False}]
    assert build_learner_context(model)["recommended_difficulty"] == "advanced"
    model["onboarding"]["experience_level"] = "intermediate"
    model["mastery"] = {"python": 0.8}
    model["recent_outcomes"] = [{"passed": True}] * 3
    assert build_learner_context(model)["recommended_difficulty"] == "advanced"
    with pytest.raises(ValueError):
        set_onboarding_profile(user_id="learner", storage_path=str(tmp_path), onboarding={"experience_level": "unlimited"})
    model["recent_outcomes"] = [{"passed": True, "topic": "python", "concept": "python"}] * 3
    assert build_lesson_plan({"learner_model": model}, "Nutrition")["difficulty"] == "intermediate"
    model["onboarding"]["experience_level"] = "beginner"
    model["mastery"] = {"python": 0.95}
    model["recent_outcomes"] = [{"passed": True, "topic": "python", "concept": "python"}] * 9
    assert build_lesson_plan({"learner_model": model}, "Python")["difficulty"] == "expert"


def test_subject_extraction_handles_actual_nutrition_request():
    agent = CurriculumAgent(None)
    prompt = "generate a curriculum for Nutritional Science-Nutrition macronutrients micronutrients and diet optimization basics for a beginner with a thorough introduction please!"
    assert agent._extract_subject(prompt) == "Nutritional Science-Nutrition macronutrients micronutrients and diet optimization basics"
    assert agent._extract_subject({"prompt": prompt}) == agent._extract_subject(prompt)


def test_generation_failure_returns_honest_draft_without_provider_errors(monkeypatch):
    agent = CurriculumAgent(None)
    monkeypatch.setattr(agent, "_load_from_mammoth_supabase", lambda *args: None)
    monkeypatch.setattr(agent, "_inject_chunks_into_lessons", lambda curriculum: curriculum)
    async def broken(*args, **kwargs):
        raise RuntimeError("insufficient_quota secret diagnostic")
    monkeypatch.setattr(agent, "_author_lesson_with_llm", broken)
    result = agent.run("Create a curriculum for Python")
    assert result["status"] == "ok"
    assert result["quality"]["status"] == "draft"
    assert result["validation"]["valid"] is False
    assert "insufficient_quota" not in str(result)
    assert all(item["code"] == "provider_or_runtime_error" for item in result["curriculum"]["generation_diagnostics"])
    assert all(not lesson["content"] for module in result["curriculum"]["modules"] for lesson in module["lessons"])


def test_authored_lesson_uses_profile_and_strips_reasoning(monkeypatch, course):
    import json
    import mammoth_os.agents.curriculum_agent as module
    captured = {}
    payload = course["modules"][0]["lessons"][0]
    class Client:
        async def generate(self, prompt, **kwargs):
            captured.update({"prompt": prompt, **kwargs})
            return "<think>Private model draft reasoning.</think>" + json.dumps(payload)
    monkeypatch.setattr(module, "get_llm_client", lambda: Client())
    agent = CurriculumAgent(None)
    result = asyncio.run(agent._author_lesson_with_llm(
        {**payload, "source": "template"}, subject="Python",
        module_title="Foundations", curriculum_title="Python foundations",
        learner_context={"recommended_difficulty": "expert", "goals": ["Review tradeoffs"]},
    ))
    assert result["difficulty"] == "expert"
    assert "Private model" not in result["content"]
    assert "Private model" in result["reasoning_trace"]
    assert '"recommended_difficulty": "expert"' in captured["prompt"]
    assert "define vocabulary before using it" in captured["prompt"]
    assert "Worked examples" in captured["prompt"]
    assert captured["max_tokens"] == 3200
    assert captured["response_format"] == {"type": "json_object"}


def test_full_course_accepts_requested_teaching_depth_and_twenty_minute_lessons(monkeypatch, course):
    import json
    import mammoth_os.agents.curriculum_agent as module

    agent = CurriculumAgent(None)
    monkeypatch.setattr(agent, "_load_from_mammoth_supabase", lambda *args: None)
    monkeypatch.setattr(agent, "_inject_chunks_into_lessons", lambda value: value)
    requested_titles = []

    class Client:
        async def generate(self, prompt, **kwargs):
            title = prompt.split("Lesson title seed: ", 1)[1].split("\n", 1)[0]
            requested_titles.append(title)
            lesson = deepcopy(course["modules"][0]["lessons"][0])
            lesson["title"] = title
            lesson["content"] = title + ". " + lesson["content"] + " " + lesson["content"]
            lesson["estimated_minutes"] = 20
            assert 350 <= len(lesson["content"].split()) <= 600
            return json.dumps(lesson)

    monkeypatch.setattr(module, "get_llm_client", lambda: Client())
    result = agent.run("Create a curriculum for Python")
    assert len(requested_titles) == 9
    assert result["quality"]["ready"], result["quality"]
    assert result["validation"]["valid"]
    assert result["curriculum"]["estimated_total_minutes"] == 180
    assert all(module["estimated_minutes"] == 60 for module in result["curriculum"]["modules"])
    assert not result["curriculum"].get("generation_warnings")
    assert all(lesson["status"] == "ready" and lesson["estimated_minutes"] == 20
               for item in result["curriculum"]["modules"] for lesson in item["lessons"])


def test_safe_authoring_diagnostics_distinguish_json_and_teaching_failures(monkeypatch, course):
    import json
    import mammoth_os.agents.curriculum_agent as module

    agent = CurriculumAgent(None)
    payload = deepcopy(course["modules"][0]["lessons"][0])
    class Client:
        async def generate(self, prompt, **kwargs):
            return json.dumps(payload)
    monkeypatch.setattr(module, "get_llm_client", lambda: Client())
    payload["content"] = "A thin Python outline."
    with pytest.raises(LessonAuthoringError) as failure:
        asyncio.run(agent._author_lesson_with_llm(
            {**payload, "source": "template"}, subject="Python", module_title="Foundations", curriculum_title="Python"))
    assert failure.value.code == "teaching_checks_failed"
    assert any("180 words" in issue for issue in failure.value.issues)
    monkeypatch.setattr(agent, "_load_from_mammoth_supabase", lambda *args: None)
    monkeypatch.setattr(agent, "_inject_chunks_into_lessons", lambda value: value)
    result = agent.run("Create a curriculum for Python")
    assert not result["quality"]["ready"]
    assert result["curriculum"]["generation_diagnostics"][0]["code"] == "teaching_checks_failed"
    assert "180 words" in result["curriculum"]["generation_warnings"][0]

    class InvalidClient:
        async def generate(self, prompt, **kwargs):
            return '{"content": "Truncated'
    monkeypatch.setattr(module, "get_llm_client", lambda: InvalidClient())
    result = agent.run("Create a curriculum for Python")
    assert result["curriculum"]["generation_diagnostics"][0]["code"] == "invalid_json"


def test_authoring_repairs_schema_once_without_relaxing_content_checks(monkeypatch, course):
    import json
    import mammoth_os.agents.curriculum_agent as module
    payload = deepcopy(course["modules"][0]["lessons"][0])
    prompts = []
    class Client:
        async def generate(self, prompt, **kwargs):
            prompts.append(prompt)
            return json.dumps({**payload, "content": {"Introduction": "wrong shape"}} if len(prompts) == 1 else payload)
    monkeypatch.setattr(module, "get_llm_client", lambda: Client())
    result = asyncio.run(CurriculumAgent(None)._author_lesson_with_llm(
        {**payload, "source": "template", "generation_warning": "Old failed draft"},
        subject="Python", module_title="Foundations", curriculum_title="Python"))
    assert len(prompts) == 2
    assert "top-level string" in prompts[1]
    assert result["authoring_attempts"] == 2
    assert result["status"] == "ready"
    assert "generation_warning" not in result


def test_provider_failure_does_not_trigger_extra_authoring_spend(monkeypatch, course):
    import mammoth_os.agents.curriculum_agent as module
    calls = []
    class Client:
        async def generate(self, prompt, **kwargs):
            calls.append(prompt)
            raise RuntimeError("insufficient_quota private detail")
    monkeypatch.setattr(module, "get_llm_client", lambda: Client())
    with pytest.raises(RuntimeError):
        asyncio.run(CurriculumAgent(None)._author_lesson_with_llm(
            course["modules"][0]["lessons"][0], subject="Python", module_title="Foundations", curriculum_title="Python"))
    assert len(calls) == 1


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {"id": token, "email": f"{token}@example.test", "is_admin": False} if token in {"alice", "bob"} else None)
    monkeypatch.setattr(api_server, "_atlas_state_file_for_request", lambda: tmp_path / f"{api_server._current_request_user_id()}.json")
    states = {}
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: deepcopy(states.get(api_server._current_request_user_id(), {})))
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda state: states.update({api_server._current_request_user_id(): deepcopy(state)}))
    def hydrate(state, **kwargs):
        state["learner_model"] = {"onboarding": {"experience_level": "expert"}}
        state["learner_context"] = {"recommended_difficulty": "expert"}
    monkeypatch.setattr(api_server, "_hydrate_learner_state", hydrate)
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(session_module, "generate_exercises_for_lesson", lambda *args, **kwargs: [{"exercise_id": "practice", "prompt": "Explain variable assignment.", "starter_files": {}, "expected_test": "Explain assignment accurately."}])
    with TestClient(api_server.app) as test_client:
        yield test_client, states


def test_save_list_start_exact_curriculum_with_tenant_isolation(client, course):
    browser, states = client
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    assert browser.get("/api/atlas/curricula").status_code == 401
    assert browser.post("/api/atlas/curricula", headers=alice, json={"curriculum": course}).status_code == 200
    assert browser.get("/api/atlas/curricula", headers=bob).json()["curricula"] == []
    assert browser.post("/api/atlas/curricula/start", headers=bob, json={"curriculum_id": "course-one"}).status_code == 404
    response = browser.post("/api/atlas/curricula/start", headers=alice, json={"curriculum_id": "course-one"})
    assert response.status_code == 200, response.text
    assert states["alice"]["curriculum"]["modules"] == course["modules"]
    assert states["alice"]["lesson_id"] == "lesson-one"
    assert states["alice"]["lesson_plan"]["difficulty"] == "expert"
    assert "bob" not in states


def test_draft_can_be_saved_but_cannot_replace_active_lesson(client, course):
    browser, states = client
    states["alice"] = {"lesson_id": "existing-lesson"}
    headers = {"Authorization": "Bearer alice"}
    course["modules"][0]["lessons"][0]["content"] = "Thin intro..."
    saved = browser.post("/api/atlas/curricula", headers=headers, json={"curriculum": course})
    assert saved.status_code == 200
    assert not saved.json()["curriculum"]["quality"]["ready"]
    response = browser.post("/api/atlas/curricula/start", headers=headers, json={"curriculum_id": "course-one"})
    assert response.status_code == 409
    assert states["alice"]["lesson_id"] == "existing-lesson"


def test_malformed_curriculum_is_an_explicit_client_error(client, course):
    browser, _ = client
    course["modules"][0]["lessons"][0]["objectives"] = "not an array"
    assert browser.post("/api/atlas/curricula", headers={"Authorization": "Bearer alice"}, json={"curriculum": course}).status_code == 400


def test_next_uses_current_profile_and_retains_saved_lesson_content(client, course, monkeypatch):
    import mammoth_os.exercise_generator as generator
    browser, states = client
    alice = {"Authorization": "Bearer alice"}
    browser.post("/api/atlas/curricula", headers=alice, json={"curriculum": course})
    assert browser.post("/api/atlas/curricula/start", headers=alice, json={"curriculum_id": "course-one"}).status_code == 200
    calls = {}
    def generate(lesson, **kwargs):
        calls.update(kwargs)
        return [{"exercise_id": "practice-two", "prompt": "Explain expressions.", "starter_files": {}, "expected_test": "Explain accurately."}]
    monkeypatch.setattr(generator, "generate_exercises_for_lesson", generate)
    response = browser.post("/api/atlas/next", headers=alice, json={"override": True})
    assert response.status_code == 200, response.text
    assert calls["difficulty"] == "expert"
    assert states["alice"]["lesson_id"] == "lesson-two"
    assert states["alice"]["current_lesson"]["content"] == course["modules"][0]["lessons"][1]["content"]
    assert states["alice"]["current_exercise"]["exercise_id"] == "practice-two"
    assert states["alice"]["last_submission"] is None


def test_next_failure_does_not_change_active_lesson(client, course, monkeypatch):
    import mammoth_os.exercise_generator as generator
    browser, states = client
    alice = {"Authorization": "Bearer alice"}
    browser.post("/api/atlas/curricula", headers=alice, json={"curriculum": course})
    browser.post("/api/atlas/curricula/start", headers=alice, json={"curriculum_id": "course-one"})
    before = deepcopy(states["alice"])
    def broken(*args, **kwargs):
        raise RuntimeError("private provider diagnostic")
    monkeypatch.setattr(generator, "generate_exercises_for_lesson", broken)
    response = browser.post("/api/atlas/next", headers=alice, json={"override": True})
    assert response.status_code == 503
    assert "private provider" not in response.text
    assert states["alice"] == before


def test_sdk_starts_exact_course_and_keeps_level_on_next(monkeypatch, course):
    from mammoth_os.sdk import MammothMind
    calls = []
    def generate(lesson, **kwargs):
        calls.append(kwargs)
        return [{"exercise_id": lesson["lesson_id"] + "-exercise", "prompt": "Practice this lesson.", "starter_files": {}, "expected_test": "Explain clearly.", "submission_mode": "text"}]
    monkeypatch.setattr(session_module, "generate_exercises_for_lesson", generate)
    client = MammothMind(session=session_module.ATLASSession("sdk-learner"))
    snapshot = client.start_curriculum(course, difficulty="expert")
    assert snapshot["curriculum_id"] == course["curriculum_id"]
    assert snapshot["curriculum"]["modules"] == course["modules"]
    assert client.next_lesson()["lesson_id"] == "lesson-two"
    assert all(call["difficulty"] == "expert" for call in calls)


@pytest.mark.parametrize("meets_criteria", [True, False])
def test_grounded_assessment_uses_correctness_not_keyword_length(monkeypatch, course, meets_criteria):
    import json
    import mammoth_os.lesson_assessment as assessment
    criteria = [{"id": key, "met": meets_criteria, "feedback": "Explain how assignment changes the referenced value."} for key in ("concepts", "application", "reasoning")]
    class Client:
        async def generate(self, prompt, **kwargs):
            assert "Do not reward length or keyword repetition" in prompt
            return json.dumps({"score": 0.9, "criteria": criteria, "hint": "Trace the assignment and explain your prediction.", "safety_concern": False})
    monkeypatch.setattr(assessment, "get_llm_client", lambda: Client())
    result = asyncio.run(assessment.assess_text_response("Python variables because examples " * 20, course["modules"][0]["lessons"][0], {"prompt": "Explain assignment."}, "lesson-one"))
    assert result["passed"] is meets_criteria
    assert result["assessment_method"] == "lesson_grounded_model"
    assert result["mastery_evidence"] is True


def test_coverage_only_feedback_never_increases_mastery(tmp_path):
    result = {"passed": True, "mastery_evidence": False}
    for _ in range(9):
        model = update_learner_model("learner", lesson={"title": "Python"}, result=result, topic="Python", storage_path=str(tmp_path))
    assert model["mastery"]["python"] == 0.5
    assert build_learner_context(model, topic="Python")["recommended_difficulty"] == "beginner"
