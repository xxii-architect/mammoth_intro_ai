import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import api_server
from mammoth_os.agents.planner_agent import PlannerAgent
from mammoth_os.planning_quality import education_goal, software_goal, task_diagnostics


def task(**values):
    return {"task_id": "t1", "agent": "research", "title": "Identify prerequisites",
            "input": {"goal": "Find prerequisites"}, "depends_on": [], "estimated_minutes": 10, **values}


@pytest.mark.parametrize("profile", ["balanced", "atlas", "autonomous"])
@pytest.mark.parametrize("goal", [
    "Create a beginner Python curriculum with practical lessons",
    "Design an educational personal finance course covering market pricing",
    "Teach deployment operations and community publishing concepts",
    "Improve learning comprehension and practice",
])
def test_education_plans_do_not_add_operational_actions(goal, profile):
    steps = api_server._build_plan_steps(goal, profile)
    assert [step["agent_id"] for step in steps] == [
        "tutor_agent", "research_agent", "reflection_agent", "orchestrator",
    ]
    assert all(step["agent_id"] not in {
        "custodial_agent", "community_engine_agent", "market_intel_agent", "field_ops_agent",
    } for step in steps)


def test_educational_software_work_keeps_explicit_coding_step():
    steps = api_server._build_plan_steps("Implement the lesson UI component", "balanced")
    assert "coding-plan" in [step["id"] for step in steps]
    explicit = api_server._build_plan_steps("Build a learning app", "coding_only")
    assert len(explicit) == 1 and explicit[0]["agent_id"] == "coding_agent"
    operational = api_server._build_plan_steps("Deploy the platform and announce the launch", "autonomous")
    assert "custodial-check" in [step["id"] for step in operational]


@pytest.mark.parametrize("tasks", [
    [], [None], [task(input="wrong")], [task(depends_on="t2")],
    [task(depends_on=["t1"])], [task(depends_on=["unknown"])],
    [task(), task()], [task(title="")], [task(agent=["research"])],
    [task(input={"lesson": {}})], [task(), task(task_id="t2", depends_on=["t1", "t1"])],
])
def test_malformed_or_unsafe_task_graph_is_rejected(tasks):
    assert task_diagnostics(tasks)
    assert not PlannerAgent._valid_exec_tasks(tasks)


def test_valid_ordered_graph_and_curriculum_schema_remain_supported():
    assert not task_diagnostics([task(), task(task_id="t2", depends_on=["t1"])])
    assert not task_diagnostics([task(agent="tutor", input={"lesson": {"title": "Real lesson"}})], curriculum=True)


class Client:
    def __init__(self, raw):
        self.raw = raw
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append((prompt, kwargs))
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw


@pytest.mark.parametrize("raw", [
    "Research then deploy and publish to the community.",
    '[{"task_id":"t1","agent":"research","title":"Task","input":{"goal":"x"},"depends_on":[]}',
    json.dumps([task(title="")]),
    json.dumps([task(agent="community_engine")]),
    "[LOCAL_ADAPTER] no provider",
    RuntimeError("insufficient_quota"),
])
def test_bad_model_output_never_becomes_a_success_shaped_fallback(monkeypatch, raw):
    import mammoth_os.llm_client as llm
    client = Client(raw)
    monkeypatch.setattr(llm, "get_llm_client", lambda: client)
    plan = asyncio.run(PlannerAgent().create_plan("Design a learning curriculum"))
    assert plan["status"] == "failed"
    assert plan["tasks"] == [] and plan["estimated_duration_sec"] == 0
    assert "dag_validated" not in plan["quality_flags"]
    assert "insufficient_quota" not in json.dumps(plan)
    assert len(client.prompts) == 1


def test_reasoning_is_separate_from_valid_structured_plan(monkeypatch):
    import mammoth_os.llm_client as llm
    client = Client("<think>Private deliberation</think>" + json.dumps([task()]))
    monkeypatch.setattr(llm, "get_llm_client", lambda: client)
    plan = asyncio.run(PlannerAgent().create_plan("Design a learning curriculum"))
    assert plan["status"] == "planned" and len(plan["tasks"]) == 1
    assert "Private deliberation" not in json.dumps(plan["tasks"])
    assert plan["reasoning_trace"] == "Private deliberation"
    assert "community_engine" not in client.prompts[0][0]


def test_invalid_plan_endpoint_never_dispatches_or_records_success(monkeypatch):
    calls = []
    async def invalid(self, goal, constraints):
        return {"tasks": [task(title="")], "estimated_duration_sec": 600}
    monkeypatch.setattr(PlannerAgent, "create_plan", invalid)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: calls.append(kwargs))
    response = TestClient(api_server.app).post("/api/plan", json={"goal": "Design a lesson", "execute": True})
    assert response.status_code == 502
    assert response.json()["quality"]["ready"] is False
    assert response.json()["tasks"] == []
    assert not any(call.get("status") == "planned" for call in calls)


def test_failed_planner_run_is_not_ok(monkeypatch):
    async def invalid(self, goal, constraints):
        raise ValueError("Malformed response")
    monkeypatch.setattr(PlannerAgent, "_decompose_to_tasks", invalid)
    result = asyncio.run(PlannerAgent().run({"goal": "Teach Python"}))
    assert result["status"] == "failed" and result["valid"] is False


def test_empty_saved_curriculum_does_not_trigger_an_unrequested_model_plan(monkeypatch):
    async def forbidden(*args):
        raise AssertionError("An empty provided curriculum must not cause a model call")
    monkeypatch.setattr(PlannerAgent, "_llm_decompose", forbidden)
    plan = asyncio.run(PlannerAgent().create_plan("Teach Python", {"curriculum": {"modules": []}}))
    assert plan["status"] == "failed" and plan["tasks"] == []


def test_execution_endpoint_rejects_out_of_scope_education_agent(monkeypatch):
    async def operational(self, goal, constraints):
        return {"tasks": [task(agent="deploy")]}
    monkeypatch.setattr(PlannerAgent, "create_plan", operational)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    response = TestClient(api_server.app).post("/api/plan", json={"goal": "Design a lesson", "execute": True})
    assert response.status_code == 502 and response.json()["tasks"] == []


def test_valid_plan_endpoint_reports_actual_duration_and_separate_trace(monkeypatch):
    async def valid(self, goal, constraints):
        return {"status": "planned", "tasks": [task()], "estimated_duration_sec": 600,
                "reasoning_trace": "Consider the prerequisites."}
    monkeypatch.setattr(PlannerAgent, "create_plan", valid)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    response = TestClient(api_server.app).post("/api/plan", json={"goal": "Design a lesson"})
    assert response.status_code == 200
    assert response.json()["total_estimated_minutes"] == 10
    assert response.json()["reasoning_trace"] == "Consider the prerequisites."
    assert "reasoning_trace" not in response.json()["tasks"][0]["input"]


def test_education_preview_has_no_implicit_repository_or_operator_steps(monkeypatch):
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    response = asyncio.run(api_server.plan_execute({
        "objective": "Design a spaced repetition study workflow", "plan_profile": "autonomous", "dry_run": True,
    }))
    assert response["dry_run"] is True
    assert [step["agent_id"] for step in response["plan_steps"]] == [
        "tutor_agent", "research_agent", "reflection_agent", "orchestrator",
    ]


def test_goal_matching_does_not_confuse_building_curricula_with_software():
    assert education_goal("Build a Python curriculum")
    assert not software_goal("Build a Python curriculum")
    assert software_goal("Patch LessonsPage.jsx")
    assert not education_goal("Deploy operational services")
