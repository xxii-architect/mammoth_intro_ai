import asyncio
import json

import pytest

from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent
from mammoth_os.llm_completion import Completion


def test_plant_the_seed_agent_uses_learning_context():
    agent = PlantTheSeedAgent(user_id="learner-1")

    result = agent.run(
        {
            "topic": "UI scaffolding",
            "context": "Module 2",
            "lesson_title": "Reusable dashboard shell",
            "module_title": "Layout foundations",
            "progress_score": 0.34,
            "next_focus": "examples",
        }
    )

    assert result["status"] == "ok"
    assert "Reusable dashboard shell" in result["seed"]
    assert "repeatable" in result["expansion"]
    assert "examples" in result["action"].lower()
    assert "needs_foundation" in result["tags"]
    assert result["follow_up"]
    assert result["recommendations"]


def test_plant_the_seed_agent_builds_progress_summary():
    agent = PlantTheSeedAgent(user_id="learner-2")

    result = agent.run({"topic": "ATLAS", "progress_score": 0.8})

    assert result["status"] == "ok"
    assert "compounding" in result["summary"]
    assert result["tags"][0] == "atlas"


def test_plant_the_seed_agent_rejects_placeholder_targets():
    agent = PlantTheSeedAgent(user_id="learner-3")

    result = agent.run({"topic": "unknown", "lesson_title": "unknown"})

    assert result["status"] == "needs_context"
    assert result["approval_gate"]["requires_review"] is False
    assert "real lesson" in result["summary"].lower()


def assessment():
    return {
        "idea_summary": "Simplify the interface palette.",
        "hypothesis": "Fewer accents improve visual hierarchy.",
        "verdict": "Prototype first",
        "verdict_rationale": "Compare a prototype with the current layout.",
        "validation_steps": [{
            "action": f"Check component {i}", "method": "Compare focus contrast",
            "cost": "$0", "timeline": "Day 1", "success_indicator": "Clear keyboard focus",
        } for i in range(3)],
        "first_3_actions": ["Inventory accents", "Build a prototype", "Check contrast"],
        "risks": [{"risk": "Ambiguous status", "severity": "Medium", "mitigation": "Keep status labels"}],
    }


def use_model(monkeypatch, responses):
    import mammoth_os.llm_client as clients
    calls = []

    class Model:
        async def generate_completion(self, prompt, **kwargs):
            calls.append((prompt, kwargs))
            return responses.pop(0)

    monkeypatch.setattr(clients, "get_llm_client", lambda: Model())
    return calls


def test_bad_json_has_no_verdict_raw_bleed_or_success(monkeypatch):
    calls = use_model(monkeypatch, [Completion('{"idea_summary":"cut')]*2)
    result = asyncio.run(PlantTheSeedAgent()._validate_idea("Simplify colors", {}))
    assert result["status"] == "error"
    assert result["quality"]["status"] == "failed"
    assert "verdict" not in result and "idea_summary" not in result
    assert "Needs more research" not in json.dumps(result)
    assert "cut" not in result["summary"]
    assert len(calls) == 2


def test_repair_is_bounded_and_prompt_scoped(monkeypatch):
    calls = use_model(monkeypatch, [Completion("bad"), Completion(json.dumps(assessment()))])
    result = asyncio.run(PlantTheSeedAgent()._validate_idea("Simplify colors", {"audience": "beginners"}))
    assert result["status"] == "ok"
    assert result["quality"]["attempts"] == 2
    assert result["confidence"] is None
    assert "validated" not in result["summary"].lower()
    assert "beginners" in calls[0][0]
    assert "True XXII Supply" not in calls[0][1]["system_prompt"]
    assert calls[0][1]["decision_json"] is True


@pytest.mark.parametrize("reason", ["length", "refusal"])
def test_finish_reason_prevents_false_assessment(monkeypatch, reason):
    responses = [Completion(json.dumps(assessment()), finish_reason=reason)] * 2
    calls = use_model(monkeypatch, responses)
    result = asyncio.run(PlantTheSeedAgent()._validate_idea("Palette", {}))
    assert result["status"] == "error"
    assert result["quality"]["issues"] == ["output_limit" if reason == "length" else "provider_refusal"]
    assert len(calls) == (2 if reason == "length" else 1)


@pytest.mark.parametrize("changes", [
    {"validation_steps": []}, {"first_3_actions": "wrong"}, {"risks": [1]},
    {"verdict": {}}, {"idea_summary": ""}, {"validation_steps": [{"action": "missing fields"}]*3},
])
def test_valid_json_with_invalid_shape_is_failed(monkeypatch, changes):
    payload = {**assessment(), **changes}
    use_model(monkeypatch, [Completion(json.dumps(payload))]*2)
    result = asyncio.run(PlantTheSeedAgent()._validate_idea("Palette", {}))
    assert result["status"] == "error"
    assert "confidence" not in result


def test_provider_exception_is_not_embedded_in_deliverable(monkeypatch):
    import mammoth_os.llm_client as clients

    def fail():
        raise RuntimeError("billing-provider-sensitive-detail")

    monkeypatch.setattr(clients, "get_llm_client", fail)
    result = PlantTheSeedAgent().run("Assess this palette")
    assert result["status"] == "error"
    assert result["quality"]["status"] == "failed"
    assert "billing-provider-sensitive-detail" not in json.dumps(result)
