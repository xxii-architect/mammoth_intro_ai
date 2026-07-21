from mammoth_os.agents.curriculum_agent import CurriculumAgent


def test_subject_extraction_colon():
    agent = CurriculumAgent(router=None)
    res = agent.run("Calculus: limits and continuity")
    assert res["status"] == "ok"
    assert res["curriculum"]["subject"].lower().startswith("calculus")


def test_subject_extraction_for_phrase():
    agent = CurriculumAgent(router=None)
    res = agent.run("A short course for Data Science.")
    assert res["status"] == "ok"
    assert res["curriculum"]["subject"].lower().startswith("data science")


def test_estimated_minutes_consistency():
    agent = CurriculumAgent(router=None)
    res = agent.run("Biology: cells")
    curriculum = res["curriculum"]
    total = curriculum["estimated_total_minutes"]
    sum_modules = sum(m["estimated_minutes"] for m in curriculum["modules"])
    assert total == sum_modules
