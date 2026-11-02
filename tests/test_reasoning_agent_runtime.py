import asyncio
import json
from datetime import datetime, timezone

import pytest
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


def test_reasoning_agent_returns_structured_guidance(monkeypatch):
    from mammoth_os.llm_client import LocalAdapter
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: LocalAdapter())
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
    assert result["generation_mode"] == "tutor_rules"
    assert result["quality"]["ready"] is False


def analysis_response():
    return {
        "answer": "Approval latency may come from competing polling requests, not a broken button.",
        "steps": ["Measure evidence fetch latency with polling enabled and disabled."],
        "assumptions": ["The approval request reaches the server; verify the request log."],
        "alternatives": ["A stale base can reject an otherwise responsive approval flow."],
        "recommended_next_step": "Compare the request timestamps for a single fresh approval.",
    }


def test_reasoning_analysis_is_not_tutor_boilerplate(monkeypatch):
    calls = []
    class Model:
        async def generate(self, prompt, **kwargs):
            calls.append((prompt, kwargs))
            return json.dumps(analysis_response())
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = ReasoningAgent().run({"prompt": "Is the approval button broken?"})
    assert result["status"] == "ok"
    assert result["generation_mode"] == "model"
    assert result["confidence"] is None
    assert result["quality"]["evidence_status"] == "interpretation"
    assert result["quality"]["fact_verification"] == "not_performed"
    assert result["answer"] in result["summary"]
    for key in ("assumptions", "alternatives", "steps"):
        assert result["reasoning"][key][0] in result["summary"]
    assert "micro_lesson" not in result["reasoning"]
    assert "learner likely" not in result["summary"]
    assert len(calls) == 1
    assert "0.85" not in calls[0][0]
    assert "primary sources first" in calls[0][1]["system_prompt"]


@pytest.mark.parametrize("response", [
    "[LOCAL_ADAPTER] prompt echo", "insufficient_quota provider failure",
    '{"answer": "A partial analysis."}', '{"answer": ["wrong type"]}',
])
def test_reasoning_never_replaces_failed_analysis_with_successful_templates(monkeypatch, response):
    class Model:
        async def generate(self, *args, **kwargs):
            return response
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = ReasoningAgent().run({"prompt": "Compare deployment approaches"})
    assert result["status"] == "failed"
    assert result["quality"]["ready"] is False
    assert not result["llm_enriched"]
    assert "analysis_generation_failed" in result["quality_flags"]
    assert "insufficient_quota" not in result["summary"]
    assert not result["reasoning"].get("micro_lesson")


def test_analysis_strips_reasoning_and_deduplicates_checks(monkeypatch):
    response = analysis_response()
    response["answer"] = "<think>private reasoning</think>" + response["answer"]
    response["steps"] *= 2
    class Model:
        async def generate(self, *args, **kwargs):
            return json.dumps(response)
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    async def call():
        return ReasoningAgent().run({"prompt": "Compare approval latency explanations"})
    result = asyncio.run(call())
    assert result["status"] == "ok"
    assert "private reasoning" not in result["summary"]
    assert "private reasoning" in result["trace"]
    assert len(result["reasoning"]["steps"]) == 1


def test_analysis_keeps_conversation_context_in_active_event_loop(monkeypatch):
    from mammoth_os.llm_client import conversation_context, current_conversation_context
    contexts = []
    class Model:
        async def generate(self, *args, **kwargs):
            contexts.append(current_conversation_context())
            return json.dumps(analysis_response())
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    async def call():
        with conversation_context("Earlier turn: compare polling and stale-base failures"):
            return ReasoningAgent().run({"prompt": "Which is more likely?"})
    assert asyncio.run(call())["status"] == "ok"
    assert contexts == ["Earlier turn: compare polling and stale-base failures"]


def test_truncated_valid_json_is_not_accepted_as_complete_analysis(monkeypatch):
    from mammoth_os.llm_completion import Completion
    class Model:
        async def generate_completion(self, *args, **kwargs):
            return Completion(text=json.dumps(analysis_response()), finish_reason="length")
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    assert ReasoningAgent().run({"prompt": "Compare options"})["status"] == "failed"


def test_provider_diagnostic_in_structured_output_is_not_advice(monkeypatch):
    response = analysis_response()
    response["answer"] = "insufficient_quota provider error"
    class Model:
        async def generate(self, *args, **kwargs):
            return json.dumps(response)
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = ReasoningAgent().run({"prompt": "Compare options"})
    assert result["status"] == "failed"
    assert "insufficient_quota" not in str(result)

def test_reasoning_model_can_enrich_tutor_without_losing_lesson_fields(monkeypatch):
    class Model:
        async def generate(self, *args, **kwargs):
            return json.dumps(analysis_response())
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = ReasoningAgent().run({
        "prompt": "Explain my failed assertion", "mode": "tutor_hint",
        "context": {"tutor_result": {"message": "AssertionError"}},
    })
    assert result["status"] == "ok"
    assert result["reasoning"]["micro_lesson"]
    assert result["reasoning"]["socratic_questions"]
    assert result["reasoning"]["error_pattern"] == "assertion_error"


def test_chat_renderer_keeps_analysis_and_evidence_labels():
    result = {"summary": "Evidence-specific answer.\n\n**Next step:** Compare timestamps."}
    assert api_server._render_chat_result({"output": result}) == result["summary"]
    for quality, expected in [
        ({"ready": True, "evidence_status": "interpretation"}, "interpretation"),
        ({"ready": True, "evidence_status": "source_linked"}, "source_linked"),
        ({"ready": False, "evidence_status": "interpretation"}, "unverified"),
    ]:
        metadata = api_server._build_chat_trust_metadata(
            provider="test", confidence=None, evidence_items=[{"quality": quality}],
            content=result["summary"],
        )
        assert metadata["evidence_status"] == expected
        assert metadata["fact_verification"] == "not_performed"
    mixed = api_server._build_chat_trust_metadata(
        provider="test", confidence=None, content=result["summary"],
        evidence_items=[
            {"quality": {"ready": True, "evidence_status": "source_linked"}},
            {"quality": {"ready": False, "evidence_status": "unverified"}},
        ],
    )
    assert mixed["evidence_status"] == "unverified"


def test_failed_analysis_cannot_pass_execution_contract():
    policy = api_server._execution_policy_for_run({}, {}, runtime_agent="reasoning")
    envelope = api_server._normalize_agent_output("reasoning", {
        "status": "failed", "summary": "A complete analysis could not be generated.",
        "quality": {"ready": False},
    })
    verification = api_server._verify_execution_contract(envelope, policy)
    assert not verification["passed"]
    assert any(check["name"] == "analysis_available" for check in verification["failed_checks"])


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
