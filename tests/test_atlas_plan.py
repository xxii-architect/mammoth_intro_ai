import asyncio

import api_server


def test_atlas_plan_creates_completed_plan(monkeypatch):
    state = {
        "topic": "Python basics",
        "current_lesson": {"title": "Functions", "lesson_id": "lesson-1"},
        "current_exercise": {"prompt": "Write a function that adds two numbers."},
    }
    saved = {}

    def fake_load_atlas_state():
        return state

    def fake_save_atlas_state(updated):
        saved["state"] = updated

    async def fake_run_agent(body):
        return {
            "status": "ok",
            "result": {"status": "ok", "output": body["payload"]["prompt"]},
            "intent": body["intent"],
            "agent_id": body["agent_id"],
            "task_id": "task-123",
        }

    monkeypatch.setattr(api_server, "_load_atlas_state", fake_load_atlas_state)
    monkeypatch.setattr(api_server, "_save_atlas_state", fake_save_atlas_state)
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: state)
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "run_agent", fake_run_agent)

    result = asyncio.run(api_server.atlas_plan({"plan_profile": "coding"}))

    assert result["status"] == "ok"
    assert result["plan"]["plan_status"] == "completed"
    assert result["plan"]["progress"]["total"] >= 4
    assert result["plan"]["progress"]["completed"] == result["plan"]["progress"]["total"]
    assert len(result["plan"]["plan_steps"]) >= 4
    assert result["plan"]["plan_profile"] == "coding"
    assert result["plan"]["coding_intent"] == "generate_code"
    assert result["plan"]["synthesis"]["learner_summary"]
    assert result["plan"]["synthesis"]["next_action"]
    assert saved["state"]["active_plan"]["plan_id"]
    assert saved["state"]["plan_history"][-1]["plan_id"] == result["plan"]["plan_id"]
    assert saved["state"]["plan_history"][-1]["coding_intent"] == "generate_code"
