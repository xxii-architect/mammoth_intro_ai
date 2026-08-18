from mammoth_os.agents.reflection_agent import ReflectionAgent


def test_reflection_agent_personalizes_from_signals():
    agent = ReflectionAgent(user_id="learner-1")

    result = agent.run(
        {
            "topic": "ATLAS lessons",
            "lesson_title": "Intro to prompt debugging",
            "difficulty": "hard",
            "progress_score": 0.38,
            "struggle_tags": ["need examples", "error handling"],
        }
    )

    assert result["status"] == "ok"
    assert result["lesson_title"] == "Intro to prompt debugging"
    assert "need_examples" in result["signals"]
    assert "error_handling" in result["signals"]
    assert "review_foundations" in result["follow_up_tags"]
    assert result["confidence"] < 0.8
    assert "signatures" not in result
    assert "example" in result["action"].lower()


def test_reflection_agent_surfaces_summary_and_sources():
    agent = ReflectionAgent(user_id="learner-2")

    result = agent.run(
        {
            "topic": "UI scaffolding",
            "difficulty": "medium",
            "progress_score": 0.8,
        }
    )

    assert result["status"] == "ok"
    assert result["sources"]
    assert "difficulty=medium" in result["sources"][1]["summary"]
    assert result["reflection_summary"]
    assert result["recommendations"]
