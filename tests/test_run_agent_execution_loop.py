import asyncio

import api_server
import mammoth_os.agent_registry as agent_registry_mod


class _DummyManifest:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.name = agent_id
        self.status = "IDLE"
        self.capabilities = []
        self.level = 1
        self.endpoint = "internal://demo"
        self.last_heartbeat = None
        self.metadata = {}


class _DummyRegistry:
    async def get_agent(self, agent_id: str):
        return _DummyManifest(agent_id)


def test_run_agent_execution_loop_retries_until_contract_passes(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", _DummyRegistry())

    attempts = {"count": 0}

    def fake_registry_run_agent(agent_name, payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {"status": "ok", "summary": "happy to help"}
        return {
            "status": "ok",
            "summary": "Captured browser execution with replay-ready output.",
            "execution": {"stage": "verify", "passed": True},
        }

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "browse_web",
                "agent_id": "browser_agent",
                "payload": {"prompt": "https://example.com"},
                "execution_policy": {"max_attempts": 2},
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["status"] == "ok"
    assert response["result"]["execution_loop"]["verification"]["passed"] is True
    assert len(response["result"]["execution_loop"]["attempts"]) == 2
    assert attempts["count"] == 2


def test_run_agent_execution_loop_marks_failed_when_output_stays_generic(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", _DummyRegistry())
    monkeypatch.setattr(api_server, "registry_run_agent", lambda agent_name, payload: "happy to help")

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "lesson_coaching",
                "agent_id": "tutor_agent",
                "payload": {"prompt": "Coach me"},
                "execution_policy": {"max_attempts": 1, "required_fields": ["status"]},
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["status"] == "error"
    verification = response["result"]["execution_loop"]["verification"]
    assert verification["passed"] is False
    failed_checks = {item["name"] for item in verification["failed_checks"]}
    assert "structured_output" in failed_checks
