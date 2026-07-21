import asyncio

from mammoth_os.agents.planner_agent import PlannerAgent
from mammoth_os.agents.curriculum_agent import CurriculumAgent
from mammoth_os.agent_registry import agent_registry, AgentManifest, AgentStatus


def test_decompose_to_tasks_and_ordering():
    planner = PlannerAgent(router=None)
    curriculum = CurriculumAgent(None).run("Physics: motion")
    tasks = asyncio.run(planner._decompose_to_tasks("Physics", {"curriculum": curriculum}))
    # Expect 3 modules * 3 lessons = 9 tasks
    assert len(tasks) == 9
    # Each task after the first should depend on the previous
    for i in range(1, len(tasks)):
        assert tasks[i]["depends_on"] == [tasks[i - 1]["task_id"]]

    # Register a 'tutor' agent so validate_plan can find it
    manifest = AgentManifest(
        agent_id="tutor",
        name="TutorAgent",
        version="0.1",
        capabilities=["tutor"],
        status=AgentStatus.ACTIVE,
        level=2,
        dependencies=[],
        endpoint="http://localhost",
    )
    asyncio.run(agent_registry.register(manifest))

    plan = {"plan_id": "p1", "goal": "Physics", "tasks": tasks}
    valid, diagnostics = asyncio.run(planner.validate_plan(plan))
    assert valid
    assert diagnostics == []


def test_validate_plan_detects_cycle_and_missing_agent():
    planner = PlannerAgent(router=None)
    # Create a cycle: A -> B -> A
    t1 = {"task_id": "A", "agent": "tutor", "input": {}, "depends_on": ["B"]}
    t2 = {"task_id": "B", "agent": "tutor", "input": {}, "depends_on": ["A"]}
    plan_cycle = {"plan_id": "p_cycle", "goal": "cycle", "tasks": [t1, t2]}
    valid_cycle, diagnostics_cycle = asyncio.run(planner.validate_plan(plan_cycle))
    assert not valid_cycle
    assert any("Cycle detected" in d for d in diagnostics_cycle)

    # Missing agent
    t3 = {"task_id": "C", "agent": "unknown_agent", "input": {}, "depends_on": []}
    plan_missing_agent = {"plan_id": "p_missing", "goal": "missing", "tasks": [t3]}
    ok_missing, diagnostics_missing = asyncio.run(planner.validate_plan(plan_missing_agent))
    assert not ok_missing
    assert any("Unknown agent" in d or "no agent" in d for d in diagnostics_missing)
