import asyncio

import api_server


def test_plan_execute_returns_plan_steps_with_progress(monkeypatch):
    async def fake_run_agent(body):
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
