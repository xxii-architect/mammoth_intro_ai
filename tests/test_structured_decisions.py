import asyncio
import json
from types import SimpleNamespace

import pytest

from mammoth_os.agent_loop import (
    AgentRun,
    AgentRunner,
    RunStore,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)
from mammoth_os.agent_loop.decisions import decision_schema, parse_structured_decision
from mammoth_os.llm_client import FallbackAdapter
from mammoth_os.openai_adapter import OpenAIAdapter


def envelope(action="answer", tool=None, args_json="{}", final="Answer", **overrides):
    return json.dumps({
        "action": action, "reasoning": "Public summary.", "plan": [],
        "tool": tool, "args_json": args_json, "final": final, **overrides,
    })


def collect(stream):
    async def drain():
        return [event async for event in stream]
    return asyncio.run(drain())


def cloud(model="gpt-4o-mini", base_url=None, structured_decisions=True, responses=None):
    calls = []
    queued = list(responses or [envelope()])
    adapter = OpenAIAdapter({
        "model": model, "base_url": base_url, "api_key": "test",
        "structured_decisions": structured_decisions,
    })

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            model=model, choices=[SimpleNamespace(
                message=SimpleNamespace(content=queued.pop(0)), finish_reason="stop",
            )],
        )

    adapter._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return adapter, calls


def runner(tmp_path, adapter):
    registry = ToolRegistry()
    invoked = []
    for name, tier, admin in [("read", "read", False), ("execute", "exec", False), ("host", "read", True)]:
        registry.register(ToolSpec(
            name=name, tier=tier, admin_only=admin, description=name,
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
            handler=lambda args, ctx: invoked.append(args) or {"status": "ok"},
        ))
    return AgentRunner(registry, lambda: adapter, RunStore(tmp_path / "runs")), invoked


def test_schema_only_contains_authorized_tool_names():
    schema = decision_schema(["read", "read", "execute"])
    assert schema["properties"]["tool"]["enum"] == [None, "execute", "read"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert parse_structured_decision(envelope(), [])["final"] == "Answer"
    assert parse_structured_decision(envelope("finalize", final=None), [])["final"] is None


@pytest.mark.parametrize("text", [
    envelope("tool", "host", '{"query":"x"}', None),
    envelope("tool", "read", "[]", None),
    envelope("tool", "read", "not JSON", None),
    envelope("tool", "read", '{"query":NaN}', None),
    envelope("tool", "read", '{"query":"safe","query":"different"}', None),
    envelope("tool", "read", "{}", "Conflicting answer"),
    envelope("answer", "read"),
    envelope("answer", args_json='{"extra":1}'),
    envelope("answer", final=""),
    envelope("finalize", final="Unexpected"),
    envelope("unknown"),
    envelope(plan=["x"] * 13),
    envelope(plan=[{"title": "bad"}]),
    envelope(reasoning="x" * 1201),
    envelope(extra="not allowed"),
    'prose ' + envelope(),
    envelope().replace('"action": "answer"', '"action": "tool", "action": "answer"'),
])
def test_invalid_structured_envelopes_are_never_prose_fallbacks(text):
    assert parse_structured_decision(text, ["read"]) is None


def test_openai_strict_schema_is_used_and_ordinary_generate_is_unchanged():
    adapter, calls = cloud(responses=[envelope(), "Ordinary SDK answer"])
    result = asyncio.run(adapter.generate_completion(
        "JSON", decision_json=True, decision_schema=decision_schema(["read"]),
    ))
    assert result.decision_protocol == "json_schema"
    fmt = calls[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["properties"]["tool"]["enum"] == [None, "read"]
    assert asyncio.run(adapter.generate("hello")) == "Ordinary SDK answer"
    assert "response_format" not in calls[1]


@pytest.mark.parametrize("model,base,enabled,expected", [
    ("gpt-4.1-mini", None, True, "json_schema"),
    ("gpt-4o-mini", None, False, "json_object"),
    ("deepseek-chat", "https://api.deepseek.com/v1", True, "json_object"),
    ("gpt-4o-mini", "https://custom.example/v1", True, "text"),
    ("gpt-5-mini", None, True, "text"),
    ("gpt-4o-unverified", None, True, "json_object"),
])
def test_capability_selection_is_conservative(model, base, enabled, expected):
    adapter, calls = cloud(model, base, enabled)
    result = asyncio.run(adapter.generate_completion("JSON", decision_json=True, decision_schema=decision_schema([])))
    assert result.decision_protocol == expected
    assert calls[0].get("response_format", {}).get("type", "text") == expected


def test_structured_tool_uses_registry_and_retains_approval(tmp_path):
    adapter, calls = cloud(responses=[
        envelope("tool", "execute", '{"query":"x"}', None),
        envelope(final="Verified observations."),
    ])
    agent, invoked = runner(tmp_path, adapter)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="Execute")
    ctx = ToolContext(user_id="u")
    events = collect(agent.start(run, ctx))
    assert events[-1].type == "run.awaiting_approval"
    assert invoked == []
    assert "host" not in calls[0]["response_format"]["json_schema"]["schema"]["properties"]["tool"]["enum"]
    resumed = collect(agent.resume(run, ctx, approval_id=run.pending_approval["id"], approved=True))
    assert invoked == [{"query": "x"}]
    assert resumed[-1].type == "run.completed"
    assert run.reply == "Verified observations."


def test_bad_arguments_repair_before_approval_or_tool_execution(tmp_path):
    adapter, calls = cloud(responses=[
        envelope("tool", "execute", '{"query":123}', None),
        envelope(final="I need a valid query."),
    ])
    agent, invoked = runner(tmp_path, adapter)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="Execute")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert invoked == []
    assert not any(e.type in {"approval.requested", "tool.call"} for e in events)
    assert run.steps == 1
    assert "expected string" in calls[1]["messages"][0]["content"]
    assert events[-1].type == "run.completed"


def test_hidden_tool_cannot_be_requested_even_if_provider_violates_schema(tmp_path):
    adapter, _ = cloud(responses=[envelope("tool", "host", '{"query":"x"}', None)] * 2)
    agent, invoked = runner(tmp_path, adapter)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="Read host")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert events[-1].type == "run.failed" and run.failure_code == "invalid_response"
    assert invoked == []


def test_structured_finalization_requests_plain_prose(tmp_path):
    adapter, calls = cloud(responses=[envelope("finalize", final=None), "Long-form prose answer"])
    agent, _ = runner(tmp_path, adapter)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="Explain thoroughly")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert events[-1].type == "run.completed"
    assert run.reply == "Long-form prose answer"
    assert "response_format" not in calls[1]
    assert calls[1]["max_tokens"] == 8192
    assert [call["decision_protocol"] for call in run.diagnostics] == ["json_schema", "text"]


def test_outage_fallback_selects_protocol_for_actual_provider(tmp_path):
    class Down:
        async def generate_completion(self, *args, **kwargs):
            raise RuntimeError("insufficient_quota")

    adapter, _ = cloud()
    chain = FallbackAdapter(Down(), adapter, primary_name="deepseek", fallback_name="openai")
    agent, _ = runner(tmp_path, chain)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="hi")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert events[-1].type == "run.completed"
    assert run.diagnostics[0]["decision_protocol"] == "json_schema"
    assert run.provider == "openai"


def test_schema_provider_error_is_explicit_not_silently_downgraded(tmp_path):
    adapter, _ = cloud()
    calls = []

    def unsupported(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("400 unsupported response_format json_schema")

    adapter._client.chat.completions.create = unsupported
    agent, _ = runner(tmp_path, adapter)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="hi")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert events[-1].type == "run.failed"
    assert "unsupported response_format" in events[-1].data["error"]
    assert len(calls) == 1
    assert calls[0]["response_format"]["type"] == "json_schema"


def test_schema_length_cutoff_never_executes_a_complete_looking_tool(tmp_path):
    adapter, _ = cloud(responses=[
        envelope("tool", "read", '{"query":"x"}', None), envelope(final="Recovered"),
    ])
    create = adapter._client.chat.completions.create
    count = 0

    def clipped(**kwargs):
        nonlocal count
        response = create(**kwargs)
        count += 1
        if count == 1:
            response.choices[0].finish_reason = "length"
        return response

    adapter._client.chat.completions.create = clipped
    agent, invoked = runner(tmp_path, adapter)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="hi")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert invoked == []
    assert events[-1].type == "run.completed"
    assert next(e for e in events if e.type == "run.recovering").data["code"] == "output_limit"


def test_openai_outage_can_fall_back_to_deepseek_compatibility(tmp_path):
    class Down:
        async def generate_completion(self, *args, **kwargs):
            raise RuntimeError("network timeout")

    adapter, calls = cloud(
        model="deepseek-chat", base_url="https://api.deepseek.com/v1",
        responses=['{"final":"Compatibility answer"}'],
    )
    chain = FallbackAdapter(Down(), adapter, primary_name="openai", fallback_name="deepseek")
    agent, _ = runner(tmp_path, chain)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="hi")
    events = collect(agent.start(run, ToolContext(user_id="u")))
    assert events[-1].type == "run.completed" and run.reply == "Compatibility answer"
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert run.diagnostics[0]["decision_protocol"] == "json_object"
    assert run.provider == "deepseek"
