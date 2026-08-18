from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent


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
