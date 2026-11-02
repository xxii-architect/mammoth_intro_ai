from mammoth_os.agents.field_ops_agent import FieldOpsAgent
import json
import pytest


@pytest.fixture(autouse=True)
def generated_plan(monkeypatch):
    class Model:
        async def generate(self, prompt, **kwargs):
            return json.dumps({
                "situation_summary": "Plan a short supervised exercise with an explicit turn-back point.",
                "priorities": [{"rank": 1, "priority": "Choose a safe practice area.",
                    "rationale": "Avoid exceeding the team's current skill and visibility limits.",
                    "action": "Mark a short practice route and review it with a partner.",
                    "timeline": "Before departure.", "success_metric": "Both partners can identify the turn-back point.",
                    "effort": "Low."}],
                "immediate_win": "Agree on a turn-back point before beginning.",
                "blockers": [], "risks": ["Conditions may exceed the team's experience."],
                "operator_note": "This is a practice outline, not independent safety verification.",
            })
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())


def test_field_ops_agent_builds_structured_mission():
    agent = FieldOpsAgent(user_id="field-1")

    result = agent.run(
        {
            "topic": "navigation",
            "environment": "forest",
            "difficulty": "hard",
            "duration_minutes": 45,
            "hazards": ["low visibility", "wet ground"],
        }
    )

    assert result["status"] == "ok"
    assert result["risk_level"] == "high"
    assert result["checklist"]["selected_landmark"] is False
    assert "bearing" in result["mission"].lower()
    assert len(result["completion_criteria"]) == 3
    assert any("hazard" in note.lower() for note in result["safety_notes"])


def test_field_ops_agent_parses_prompt_strings():
    agent = FieldOpsAgent(user_id="field-2")

    result = agent.run("medium firecraft in desert conditions")

    assert result["status"] == "ok"
    assert result["topic"] == "firecraft"
    assert result["environment"] == "desert"
    assert result["difficulty"] == "medium"
    assert result["next_actions"]


def test_field_ops_agent_adds_equipment_and_abort_conditions():
    agent = FieldOpsAgent(user_id="field-3")

    result = agent.run({"topic": "navigation", "environment": "mountain", "difficulty": "hard", "hazards": ["low visibility", "loose rock", "storm"]})

    assert result["status"] == "ok"
    assert "map" in result["equipment"]
    assert result["approval_gate"]["requires_review"] is True
    assert any("abort" in condition.lower() for condition in result["abort_conditions"])
