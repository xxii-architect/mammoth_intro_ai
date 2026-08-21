from mammoth_os.agents.curriculum_agent import CurriculumAgent
import asyncio


def test_run_generates_curriculum_structure():
    agent = CurriculumAgent(router=None)
    res = agent.run("Algebra: a short course")
    assert res["status"] == "ok"
    curriculum = res.get("curriculum")
    assert curriculum is not None
    assert "curriculum_id" in curriculum
    assert curriculum.get("subject") is not None
    assert isinstance(curriculum.get("modules"), list)
    assert len(curriculum.get("modules")) == 3
    for module in curriculum.get("modules"):
        assert isinstance(module.get("lessons"), list)
        assert len(module.get("lessons")) == 3


def test_execute_action_generate_calls_run():
    agent = CurriculumAgent(router=None)
    res = agent.execute_action("generate", target="", details={"prompt": "Python: basics"})
    assert res["status"] == "ok"
    curriculum = res["curriculum"]
    assert curriculum["subject"].lower().startswith("python")


def test_run_safe_inside_event_loop():
    agent = CurriculumAgent(router=None)

    async def _invoke():
        return agent.run("Python: event loop safe path")

    res = asyncio.run(_invoke())
    assert res["status"] == "ok"
