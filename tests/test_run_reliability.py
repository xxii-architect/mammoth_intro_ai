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
from mammoth_os.llm_client import ContextualClient, FallbackAdapter
from mammoth_os.llm_completion import Completion
from mammoth_os.openai_adapter import OpenAIAdapter


class Model:
    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_completion(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return self.responses.pop(0)


def collect(stream):
    async def drain():
        return [event async for event in stream]
    return asyncio.run(drain())


def setup(tmp_path, model, **kwargs):
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="read", description="read", tier="read", input_schema={"type": "object"},
        handler=lambda args, ctx: {"status": "ok", "answer": "Saved evidence"},
    ))
    runner = AgentRunner(registry, lambda: model, RunStore(tmp_path / "runs"), **kwargs)
    run = AgentRun(id=AgentRun.new_id(), user_id="u", message="Explain the evidence")
    return runner, run, ToolContext(user_id="u")


def test_actual_length_cutoff_never_executes_even_valid_json(tmp_path):
    model = Model(
        Completion('{"tool":"read","args":{}}', finish_reason="length", usage={"total_tokens": 100}),
        Completion('{"final":"Recovered."}', finish_reason="stop"),
    )
    runner, run, ctx = setup(tmp_path, model, max_steps=1)
    events = collect(runner.start(run, ctx))
    assert not any(e.type == "tool.call" for e in events)
    assert events[-1].type == "run.completed"
    assert run.steps == 1
    assert run.diagnostics[0]["finish_reason"] == "length"
    assert run.diagnostics[0]["usage"]["total_tokens"] == 100
    assert next(e for e in events if e.type == "run.recovering").data["code"] == "output_limit"
    assert model.calls[0][1]["max_tokens"] == 4096
    assert model.calls[0][1]["decision_json"] is True


def test_separate_prose_finalization_retains_source_context(tmp_path):
    model = Model(Completion('{"tool":null,"final":null}'), Completion("Textbook-based answer"))
    runner, run, ctx = setup(tmp_path, model)
    run.request["extra_context"] = "Textbook.pdf, page 120: source evidence"
    events = collect(runner.start(run, ctx))
    assert events[-1].type == "run.completed"
    assert "page 120: source evidence" in model.calls[-1][0]
    assert model.calls[-1][1]["max_tokens"] == 8192
    assert model.calls[-1][1]["decision_json"] is False


@pytest.mark.parametrize("text", [
    '{"tool":"read","args":{},"final":"bad"}',
    '{"tool":["read"],"args":{}}',
    '{"tool":"read","args":[]}',
    '{"final":{"content":"bad"}}',
    "",
])
def test_invalid_shapes_never_call_tools_or_claim_completion(tmp_path, text):
    model = Model(Completion(text), Completion(text))
    runner, run, ctx = setup(tmp_path, model)
    events = collect(runner.start(run, ctx))
    assert events[-1].type == "run.failed"
    assert not any(e.type in {"tool.call", "run.completed"} for e in events)
    assert len(model.calls) == 2
    assert run.public()["can_continue"]


def test_continue_preserves_evidence_after_disk_reload(tmp_path):
    model = Model(
        Completion('{"tool":"read","args":{}}'),
        Completion("", finish_reason="length"),
        Completion("", finish_reason="length"),
        Completion('{"final":"Answer from saved evidence"}'),
    )
    runner, run, ctx = setup(tmp_path, model)
    events = collect(runner.start(run, ctx))
    assert events[-1].type == "run.partial"
    runner.store = RunStore(tmp_path / "runs")
    reloaded = runner.store.get(run.id, "u")
    assert reloaded is not None
    resumed = collect(runner.continue_run(reloaded, ctx))
    assert resumed[0].type == "run.continued"
    assert resumed[-1].type == "run.completed"
    assert "Saved evidence" in model.calls[-1][0]
    assert not any(e.type == "tool.call" for e in resumed)
    assert reloaded.continuations == 1
    assert [e["seq"] for e in reloaded.events] == list(range(1, len(reloaded.events) + 1))


def test_continuation_is_bounded_and_cannot_start_twice(tmp_path):
    model = Model(*[Completion("") for _ in range(6)])
    runner, run, ctx = setup(tmp_path, model)
    collect(runner.start(run, ctx))
    stream = runner.continue_run(run, ctx)
    with pytest.raises(ValueError):
        runner.continue_run(run, ctx)
    collect(stream)
    collect(runner.continue_run(run, ctx))
    assert run.continuations == 2 and not run.public()["can_continue"]
    with pytest.raises(ValueError):
        runner.continue_run(run, ctx)
    assert len(model.calls) == 6


def test_continuation_checks_owner(tmp_path):
    runner, run, ctx = setup(tmp_path, Model(Completion(""), Completion("")))
    collect(runner.start(run, ctx))
    with pytest.raises(ValueError):
        runner.continue_run(run, ToolContext(user_id="other"))
    assert run.continuations == 0


def test_continuation_still_requires_execution_approval(tmp_path):
    model = Model(Completion(""), Completion(""), Completion('{"tool":"exec","args":{}}'))
    runner, run, ctx = setup(tmp_path, model)
    executed = []
    runner.registry.register(ToolSpec(
        name="exec", description="", tier="exec", input_schema={"type": "object"},
        handler=lambda args, ctx: executed.append(True) or {"status": "ok"},
    ))
    collect(runner.start(run, ctx))
    events = collect(runner.continue_run(run, ctx))
    assert events[-1].type == "run.awaiting_approval"
    assert executed == []


def test_refusal_does_not_retry_or_expose_private_reasoning(tmp_path):
    runner, run, ctx = setup(tmp_path, Model(Completion("", finish_reason="refusal")))
    events = collect(runner.start(run, ctx))
    assert events[-1].type == "run.failed"
    assert events[-1].data["code"] == "provider_refusal"
    assert not run.public()["can_continue"]
    assert len(run.diagnostics) == 1


def test_cancellation_during_model_call_prevents_tool_execution(tmp_path):
    model = Model(Completion('{"tool":"read","args":{}}'))
    runner, run, ctx = setup(tmp_path, model)
    generate = model.generate_completion

    async def cancelled(prompt, **kwargs):
        runner.cancel(run)
        return await generate(prompt, **kwargs)

    model.generate_completion = cancelled
    events = collect(runner.start(run, ctx))
    assert events[-1].type == "run.cancelled"
    assert not any(e.type == "tool.call" for e in events)


def test_cloud_metadata_and_text_contract_are_additive():
    calls = []
    response = SimpleNamespace(
        model="snapshot", choices=[SimpleNamespace(
            finish_reason="length", message=SimpleNamespace(content="", reasoning_content="PRIVATE")
        )], usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )

    def create(**kwargs):
        calls.append(kwargs)
        return response

    adapter = OpenAIAdapter({"api_key": "test", "model": "gpt-4o-mini"})
    adapter._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = asyncio.run(adapter.generate_completion("Return JSON", decision_json=True, max_tokens=4096))
    assert isinstance(result, Completion)
    assert result.text == ""
    assert result.finish_reason == "length"
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    assert result.model == "snapshot"
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["max_tokens"] == 4096
    assert asyncio.run(adapter.generate("hello")) == ""
    assert "response_format" not in calls[1]


def test_compatible_endpoint_is_not_assumed_to_support_json():
    calls = []
    adapter = OpenAIAdapter({"api_key": "test", "base_url": "https://custom.example/v1"})
    adapter._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: calls.append(kwargs) or SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
        )
    )))
    asyncio.run(adapter.generate_completion("JSON", decision_json=True))
    assert "response_format" not in calls[0]


def test_completion_metadata_survives_nested_fallback_and_context():
    class Broken:
        async def generate_completion(self, prompt, **kwargs):
            raise RuntimeError("insufficient_quota")

    model = Model(Completion("ok", finish_reason="stop", usage={"total_tokens": 5}))
    nested = FallbackAdapter(Broken(), model, primary_name="openai", fallback_name="ollama")
    outer = FallbackAdapter(Broken(), nested, primary_name="deepseek", fallback_name="openai")
    contextual = ContextualClient(outer, "Earlier context")
    result = asyncio.run(contextual.generate_completion("now"))
    assert result.usage == {"total_tokens": 5}
    assert outer.last_used_provider == "ollama"
    assert "Earlier context" in model.calls[0][0]
