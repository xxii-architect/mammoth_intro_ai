import asyncio

import api_server
import mammoth_os.agent_registry as agent_registry_mod


class DummyManifest:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.name = agent_id
        self.status = "IDLE"
        self.capabilities = []
        self.level = 1
        self.endpoint = "internal://demo"
        self.last_heartbeat = None
        self.metadata = {}


class DummyRegistry:
    async def get_agent(self, agent_id: str):
        return DummyManifest(agent_id)


def test_plan_execute_returns_plan_steps_with_progress(monkeypatch):
    calls = []

    async def fake_run_agent(body):
        calls.append(body)
        return {
            "status": "ok",
            "result": {"status": "ok", "output": body["payload"]["prompt"]},
            "intent": body["intent"],
            "agent_id": body["agent_id"],
            "task_id": "task-1",
        }

    monkeypatch.setattr(api_server, "run_agent", fake_run_agent)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0]})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)

    result = asyncio.run(
        api_server.plan_execute(
            {
                "objective": "Build a new ATLAS onboarding wizard",
                "plan_profile": "atlas",
                "approval_mode": False,
                "stop_on_failure": True,
            }
        )
    )

    assert result["status"] == "ok"
    assert result["plan_status"] == "completed"
    assert result["progress"]["total"] >= 4
    assert result["progress"]["completed"] == result["progress"]["total"]
    assert any(step["agent_id"] == "market_intel_agent" for step in result["plan_steps"])
    assert any(step["agent_id"] == "field_ops_agent" for step in result["plan_steps"])
    coding_call = next(body for body in calls if body["agent_id"] == "coding_agent")
    assert coding_call["intent"] == "summarize"
    assert coding_call["payload"]["coding_intent"] == "summarize"


def test_plan_execute_coding_only_profile_runs_just_coding_agent(monkeypatch):
    calls = []

    async def fake_run_agent(body):
        calls.append(body)
        return {
            "status": "ok",
            "result": {"status": "ok", "output": body["payload"]["prompt"]},
            "intent": body["intent"],
            "agent_id": body["agent_id"],
            "task_id": "task-coding-only",
        }

    monkeypatch.setattr(api_server, "run_agent", fake_run_agent)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0]})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)

    result = asyncio.run(
        api_server.plan_execute(
            {
                "objective": "Patch ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx in place",
                "plan_profile": "coding_only",
                "coding_intent": "patch_existing",
                "approval_mode": False,
                "stop_on_failure": True,
            }
        )
    )

    assert result["status"] == "ok"
    assert result["plan_profile"] == "coding_only"
    assert result["coding_intent"] == "patch_existing"
    assert len(result["plan_steps"]) == 1
    assert result["plan_steps"][0]["agent_id"] == "coding_agent"
    assert result["plan_steps"][0]["intent"] == "patch_existing"
    assert calls[0]["payload"]["files"] == ["ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx"]
    assert calls[0]["payload"]["context"]["target"] == "ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx"


def test_plan_execute_autonomous_profile_includes_community_and_custodial(monkeypatch):
    async def fake_run_agent(body):
        return {
            "status": "ok",
            "result": {"status": "ok", "output": body["payload"]["prompt"]},
            "intent": body["intent"],
            "agent_id": body["agent_id"],
            "task_id": "task-2",
        }

    monkeypatch.setattr(api_server, "run_agent", fake_run_agent)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0]})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)

    result = asyncio.run(
        api_server.plan_execute(
            {
                "objective": "Coordinate an autonomous release prep cycle",
                "plan_profile": "autonomous",
                "approval_mode": False,
                "stop_on_failure": True,
            }
        )
    )

    agent_ids = [step["agent_id"] for step in result["plan_steps"]]
    assert result["status"] == "ok"
    assert result["plan_status"] == "completed"
    assert "community_engine_agent" in agent_ids
    assert "custodial_agent" in agent_ids


def test_http_agent_routes_dispatch_to_registry(monkeypatch):
    calls = []

    def fake_registry_run_agent(agent_name, payload):
        calls.append((agent_name, payload))
        return {"status": "ok", "agent": agent_name, "payload": payload}

    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    atlas_result = asyncio.run(api_server.run_atlas_agent_endpoint("teach me the lesson plan"))
    coding_result = asyncio.run(api_server.run_coding_agent_endpoint({"prompt": "refactor the routes"}))

    assert atlas_result["status"] == "ok"
    assert atlas_result["runtime_agent"] == "tutor"
    assert coding_result["status"] == "ok"
    assert coding_result["runtime_agent"] == "coding"
    assert [name for name, _ in calls] == ["tutor", "coding"]


def test_run_agent_passes_explicit_coding_intent_to_registry(monkeypatch):
    calls = []

    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", DummyRegistry())

    def fake_registry_run_agent(agent_name, payload):
        calls.append((agent_name, payload))
        return {"status": "ok", "agent": agent_name, "payload": payload}

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "generate_code",
                "agent_id": "coding_agent",
                "payload": {
                    "prompt": "Patch ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx in place",
                    "coding_intent": "patch_existing",
                    "files": ["ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx"],
                    "target": "ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx",
                },
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["runtime_agent"] == "coding"
    assert calls[0][0] == "coding"
    assert calls[0][1]["intent"] == "patch_existing"
    assert calls[0][1]["context"]["coding_intent"] == "patch_existing"
    assert calls[0][1]["context"]["target"] == "ui\\mad-architecht-command-center\\src\\pages\\AgentPage.jsx"
