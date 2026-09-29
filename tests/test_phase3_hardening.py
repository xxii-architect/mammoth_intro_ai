import asyncio

from mammoth_os.agents.coding_agent import CodingAgent
from mammoth_os.agents.curriculum_agent import CurriculumAgent
from mammoth_os.agents.planner_agent import PlannerAgent


def test_curriculum_agent_validates_generated_curriculum():
    agent = CurriculumAgent(router=None)
    result = agent.run("Create a lesson track for lesson")
    curriculum = result["curriculum"]

    assert "validation" in curriculum
    assert "validation_valid" in curriculum
    assert "quality_flags" in result
    assert "validation_gate_active" in result["quality_flags"]


def test_planner_agent_normalizes_underestimated_lesson_durations():
    agent = PlannerAgent(router=None)
    curriculum = {
        "modules": [
            {
                "module_id": "m1",
                "title": "Foundations",
                "lessons": [
                    {
                        "lesson_id": "l1",
                        "title": "Variables",
                        "content": "This lesson explains variables with a detailed step-by-step example. " * 6,
                        "estimated_minutes": 2,
                    },
                    {
                        "lesson_id": "l2",
                        "title": "Functions",
                        "content": "This lesson covers functions with examples. " * 5,
                        "estimated_minutes": 2,
                    },
                ],
            }
        ]
    }
    plan = asyncio.run(agent.create_plan("Learn Python basics", {"curriculum": curriculum}))

    assert plan["tasks"]
    assert all(task["estimated_minutes"] >= 10 for task in plan["tasks"])
    assert plan["estimated_duration_sec"] >= 60 * sum(task["estimated_minutes"] for task in plan["tasks"])


def test_coding_agent_rejects_placeholder_test_output(monkeypatch, tmp_path):
    import mammoth_os.sandbox_runner as sandbox_runner

    def fake_run_code(**kwargs):
        return {
            "passed": True,
            "stdout": "OK: test_placeholder.py::test_ok",
            "stderr": "TODO: replace this placeholder output",
            "returncode": 0,
            "method": "stub",
        }

    monkeypatch.setattr(sandbox_runner, "run_code", fake_run_code)

    project = tmp_path / "demo"
    project.mkdir()
    (project / "test_placeholder.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = asyncio.run(CodingAgent(router=None).run_tests(str(project)))

    assert result["passed"] is False
    assert "Placeholder or fabricated test output detected" in result["stderr"]
