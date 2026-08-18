from mammoth_os.agents.field_ops_agent import FieldOpsAgent


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
