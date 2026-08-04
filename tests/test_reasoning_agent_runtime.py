import asyncio
from datetime import datetime, timezone

import api_server
import mammoth_os.agent_registry as agent_registry_mod
from mammoth_os.agents.reasoning_agent import ReasoningAgent


class DummyManifest:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.name = agent_id
        self.status = "IDLE"
        self.capabilities = []
        self.level = 1
        self.endpoint = "internal://demo"
        self.last_heartbeat = datetime.now(timezone.utc)
        self.metadata = {}


class DummyRegistry:
    async def get_agent(self, agent_id: str):
        return DummyManifest(agent_id)


def test_reasoning_agent_returns_structured_guidance():
    agent = ReasoningAgent(router=None)
    result = agent.run({
        "prompt": "My code failed the submission checks because an assertion is still failing.",
        "context": {"tutor_result": {"passed": False, "message": "AssertionError: expected 3 got 2"}},
        "mode": "tutor_hint",
    })

    assert result["status"] == "ok"
    assert result["agent"] == "ReasoningAgent"
    assert result["reasoning"]["answer"]
    assert result["reasoning"]["confidence"] >= 0.55
    assert result["reasoning"]["sub_problems"]
    assert result["reasoning"]["error_pattern"] == "assertion_error"
    assert result["reasoning"]["socratic_questions"]
    assert result["reasoning"]["micro_lesson"]


def test_run_agent_attaches_reasoning_hints_for_failed_tutor_output(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_create_approval_record", lambda *args, **kwargs: {"id": "approval-1", "target": "demo.py"})
    monkeypatch.setattr(api_server, "_build_operation_preview", lambda *args, **kwargs: "preview")
    monkeypatch.setattr(agent_registry_mod, "agent_registry", DummyRegistry())

    def fake_registry_run_agent(agent_name, payload):
        if agent_name == "tutor":
            return {"status": "ok", "passed": False, "message": "assertion failed"}
        if agent_name == "reasoning":
            assert payload["mode"] == "tutor_hint"
            return {
                "status": "ok",
                "agent": "ReasoningAgent",
                "reasoning": {"answer": "Try the next check", "confidence": 0.88, "steps": ["Check the boundary case"], "sub_problems": ["Boundary case"]},
            }
        raise AssertionError(f"unexpected agent: {agent_name}")

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "grade_submission",
                "payload": {"prompt": "Fix the failing checker"},
                "agent_id": "tutor_agent",
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["runtime_agent"] == "tutor"
    assert response["result"]["reasoning"]["agent"] == "ReasoningAgent"


def test_run_agent_attaches_reasoning_for_lesson_coaching(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", DummyRegistry())

    def fake_registry_run_agent(agent_name, payload):
        if agent_name == "tutor":
            return {"status": "ok", "agent": "TutorAgent", "mode": "coach", "topic": "Loops"}
        if agent_name == "reasoning":
            assert payload["mode"] == "coach"
            return {
                "status": "ok",
                "agent": "ReasoningAgent",
                "reasoning": {
                    "answer": "Guide with one checkpoint and one question.",
                    "confidence": 0.86,
                    "steps": ["Restate goal"],
                    "sub_problems": ["Restate goal"],
                    "error_pattern": "coaching_request",
                    "socratic_questions": ["What is the first checkpoint?"],
                    "micro_lesson": "Micro-lesson: isolate one checkpoint.",
                },
            }
        raise AssertionError(f"unexpected agent: {agent_name}")

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)
    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "lesson_coaching",
                "payload": {"prompt": "Coach me through loops"},
                "agent_id": "tutor_agent",
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["runtime_agent"] == "tutor"
    assert response["result"]["reasoning"]["reasoning"]["error_pattern"] == "coaching_request"
