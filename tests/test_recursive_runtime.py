import asyncio
import json

import pytest

from mammoth_os.agent_loop import AgentRun, AgentRunner, RunStore
from mammoth_os.agent_loop.tools import ToolContext, ToolRegistry, ToolSpec
from mammoth_os.llm_completion import Completion
from mammoth_os.recursive.runtime import RecursiveRuntime, recursive_limits


class Model:
    model = "fixture"

    def __init__(self, values, usage=True):
        self.values = list(values)
        self.prompts = []
        self.usage = usage

    async def generate_completion(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return Completion(json.dumps(self.values.pop(0)), finish_reason="stop",
                          usage={"total_tokens": 100} if self.usage else {})


PLAN = {"steps": ["Inspect the evidence."], "checks": ["Address uncertainty."]}
ANSWER = {"final": "A testable hypothesis."}
PASS = {"label": "pass", "reasons": ["Matches the request."], "suggestions": [], "confidence": 0.8}
UNCERTAIN = {**PASS, "label": "uncertain", "confidence": 0.1}
SYNTHESIS = {"answer": "A testable hypothesis, not a verified fact."}


def setup(tmp_path, values, *, registry=None, usage=True):
    model = Model(values, usage)
    store = RunStore(tmp_path)
    base = AgentRunner(registry or ToolRegistry(), lambda: model, store)
    run = AgentRun(AgentRun.new_id(), "tenant-a", "Explore a hypothesis.",
                   request={"recursive": recursive_limits(True)})
    ctx = ToolContext(user_id="tenant-a")
    return model, base, run, ctx


async def drain(runtime, *, initial=False, action=None):
    lease = runtime.reserve()
    return [event.to_dict() async for event in runtime.stream(lease, initial=initial, action=action)]


def test_full_production_roles_and_honest_usage(tmp_path):
    model, base, run, ctx = setup(tmp_path, [PLAN, ANSWER, PASS, SYNTHESIS])
    events = asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "completed"
    assert run.reply == SYNTHESIS["answer"]
    assert run.recursive["usage"]["tokens"] == 400
    assert len(model.prompts) == 4
    assert [e["type"] for e in events].count("run.completed") == 1
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert all(e["contract"] == "mammoth.run.v1" for e in events)
    assert "cache" not in run.public()["recursive"]
    assert events[-1]["data"]["fact_verification"] == "not_performed"


def test_failed_critique_replans_with_findings(tmp_path):
    fail = {**PASS, "label": "fail", "suggestions": ["Consider an alternative."]}
    model, base, run, ctx = setup(tmp_path, [PLAN, ANSWER, fail, PLAN, ANSWER, PASS, SYNTHESIS])
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "completed"
    assert "Consider an alternative." in model.prompts[3]
    assert run.recursive["iteration"] == 1
    assert run.recursive["usage"]["tokens"] == 700


def test_uncertainty_checkpoint_survives_reload_and_is_single_use(tmp_path):
    model, base, run, ctx = setup(tmp_path, [PLAN, ANSWER, UNCERTAIN, SYNTHESIS])
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "awaiting_approval"
    approval_id = run.pending_approval["id"]
    base.store = RunStore(tmp_path)
    saved = base.store.get(run.id, run.user_id)
    runtime = RecursiveRuntime(base, saved, ctx)
    lease = runtime.reserve()
    action = runtime.resolve(approval_id, True, "Retain the caveats.")

    async def resume():
        return [event async for event in runtime.stream(lease, action=action)]

    asyncio.run(resume())
    assert saved.status == "completed"
    assert len(model.prompts) == 4
    assert saved.recursive["usage"]["tokens"] == 400
    runtime = RecursiveRuntime(base, saved, ctx)
    lease = runtime.reserve()
    try:
        with pytest.raises(ValueError, match="No matching"):
            runtime.resolve(approval_id, True, "")
    finally:
        lease.close()


def test_human_rejection_does_not_synthesize(tmp_path):
    model, base, run, ctx = setup(tmp_path, [PLAN, ANSWER, UNCERTAIN])
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    runtime = RecursiveRuntime(base, run, ctx)
    lease = runtime.reserve()
    action = runtime.resolve(run.pending_approval["id"], False, "Need stronger evidence.")

    async def resume():
        return [event async for event in runtime.stream(lease, action=action)]

    asyncio.run(resume())
    assert run.status == "cancelled"
    assert len(model.prompts) == 3


@pytest.mark.parametrize("approved", [True, False])
def test_tool_approval_preserved_without_replaying_planner(tmp_path, approved):
    calls = []
    registry = ToolRegistry()

    async def handler(args, ctx):
        calls.append(args)
        return {"status": "ok"}

    registry.register(ToolSpec(name="controlled", description="Controlled action", tier="exec",
                               input_schema={"type": "object", "properties": {}}, handler=handler))
    model, base, run, ctx = setup(
        tmp_path, [PLAN, {"tool": "controlled", "args": {}}, ANSWER, PASS, SYNTHESIS], registry=registry)
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "awaiting_approval"
    assert calls == []
    approval_id = run.pending_approval["id"]
    base.store = RunStore(tmp_path)
    saved = base.store.get(run.id, run.user_id)
    runtime = RecursiveRuntime(base, saved, ctx)
    lease = runtime.reserve()
    action = runtime.resolve(approval_id, approved, "")

    async def resume():
        return [event async for event in runtime.stream(lease, action=action)]

    asyncio.run(resume())
    assert saved.status == "completed"
    assert calls == ([{}] if approved else [])
    assert sum("You are the planner role" in p for p in model.prompts) == 1
    assert saved.recursive["usage"]["tool_calls"] == (1 if approved else 0)
    assert saved.recursive["usage"]["tokens"] == 500


def test_missing_usage_is_explicit_failure(tmp_path):
    _, base, run, ctx = setup(tmp_path, [PLAN], usage=False)
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "failed"
    assert run.recursive["usage"]["accounting_status"] == "unavailable"
    assert run.recursive["stop_reason"] == "provider_usage_unavailable"
    assert not run.public()["can_continue"]


def test_iteration_leash_and_no_premature_success(tmp_path):
    fail = {**PASS, "label": "fail"}
    model, base, run, ctx = setup(tmp_path, [PLAN, ANSWER, fail, PLAN, ANSWER, fail])
    events = asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "failed"
    assert run.recursive["stop_reason"] == "max_iterations"
    assert not any(e["type"] == "run.completed" for e in events)
    assert len(model.prompts) == 6


def test_nonblocking_lease_rejects_competing_consumers(tmp_path):
    _, base, run, ctx = setup(tmp_path, [])
    first = RecursiveRuntime(base, run, ctx).reserve()
    try:
        with pytest.raises(ValueError, match="already active"):
            RecursiveRuntime(base, run, ctx).reserve()
    finally:
        first.close()
    RecursiveRuntime(base, run, ctx).reserve().close()


def test_token_ceiling_stops_before_provider_call(tmp_path):
    model, base, run, ctx = setup(tmp_path, [PLAN])
    run.request["recursive"]["max_tokens"] = 100
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert model.prompts == []
    assert run.status == "failed"
    assert run.recursive["stop_reason"] == "max_tokens"


def test_cancellation_during_model_call_retains_unknown_usage(tmp_path):
    model, base, run, ctx = setup(tmp_path, [PLAN])

    async def exercise():
        entered = asyncio.Event()

        async def stalled(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        model.generate_completion = stalled
        runtime = RecursiveRuntime(base, run, ctx)
        task = asyncio.create_task(drain(runtime, initial=True))
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert run.status == "partial"
        assert run.recursive["reservation"] > 0
        assert run.recursive["usage"]["accounting_status"] == "incomplete"
        RecursiveRuntime(base, run, ctx).reserve().close()

    asyncio.run(exercise())


def test_offline_echo_is_not_completed_analysis(tmp_path):
    model, base, run, ctx = setup(tmp_path, [])

    async def offline(*args, **kwargs):
        return Completion("[LOCAL_ADAPTER] echo", usage={"total_tokens": 1})

    model.generate_completion = offline
    events = asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "failed"
    assert not any(e["type"] == "run.completed" for e in events)
    assert "[LOCAL_ADAPTER]" not in run.reply


def test_public_role_fields_strip_private_reasoning(tmp_path):
    _, base, run, ctx = setup(tmp_path, [
        {"steps": ["<think>private planning</think>Inspect the evidence."]}, ANSWER,
        {**UNCERTAIN, "reasons": ["<think>private critique</think>Needs confirmation."]},
    ])
    asyncio.run(drain(RecursiveRuntime(base, run, ctx), initial=True))
    assert run.status == "awaiting_approval"
    assert "private" not in json.dumps(run.public())


def test_persistence_failure_does_not_hang_stream_or_retain_lease(tmp_path):
    model, base, run, ctx = setup(tmp_path, [PLAN])
    save = base.store.save
    broken = False

    async def generate(*args, **kwargs):
        nonlocal broken
        broken = True
        return Completion(json.dumps(PLAN), usage={"total_tokens": 100})

    def persist(value):
        if broken:
            raise OSError("Storage unavailable")
        save(value)

    model.generate_completion = generate
    base.store.save = persist

    async def exercise():
        with pytest.raises(OSError, match="Storage unavailable"):
            await asyncio.wait_for(drain(RecursiveRuntime(base, run, ctx), initial=True), 2)
        RecursiveRuntime(base, run, ctx).reserve().close()

    asyncio.run(exercise())


def test_recursive_live_cache_does_not_mask_another_workers_saved_state(tmp_path):
    _, base, run, _ = setup(tmp_path, [])
    run.recursive = {"contract": "mammoth.recursive.v1"}
    base.store.save(run)
    other_store = RunStore(tmp_path)
    other = other_store.get(run.id, run.user_id)
    other.status = "cancelled"
    other_store.save(other)
    assert base.store.get(run.id, run.user_id).status == "cancelled"


def test_approval_terminal_releases_lease_before_transport_closes(tmp_path):
    _, base, run, ctx = setup(tmp_path, [PLAN, ANSWER, UNCERTAIN])

    async def exercise():
        runtime = RecursiveRuntime(base, run, ctx)
        stream = runtime.stream(runtime.reserve(), initial=True)
        async for event in stream:
            if event.type == "run.awaiting_approval":
                # The client may leave this stream open while sending its decision.
                other = RecursiveRuntime(base, run, ctx)
                lease = other.reserve()
                try:
                    other.resolve(run.pending_approval["id"], True, "")
                finally:
                    lease.close()
                await stream.aclose()
                return
        pytest.fail("No human review gate")

    asyncio.run(exercise())


@pytest.mark.parametrize("value", [None, "yes", {"max_iterations": 4}, {"max_tokens": True},
                                 {"max_seconds": -1}, {"unlimited": True}])
def test_budget_input_is_strict(value):
    with pytest.raises(ValueError):
        recursive_limits(value)
