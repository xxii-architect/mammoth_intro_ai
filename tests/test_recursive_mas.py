import asyncio

import pytest

from mammoth_os.agents.adapters import HumanGateAdapter
from mammoth_os.recursive.adapter_bindings import build_runner_deps
from mammoth_os.recursive import (
    Budget,
    ConfidenceWeightedMergePolicy,
    Critique,
    Execution,
    HumanGateDecision,
    HumanGateRequest,
    NodeCost,
    Plan,
    RecursiveMASRunner,
    RecursiveNode,
    RunnerContext,
    RunnerConfig,
    RunnerDeps,
    Synthesis,
)


def make_root(depth=0):
    return RecursiveNode(id="root", trace_id="trace-1", role="root", goal="Build a safe plan", depth=depth)


def make_deps(*, critique=None, gate=None, calls=None, plan=None, execution=None, synthesis=None):
    calls = calls if calls is not None else []

    async def run_planner(context):
        calls.append("planner")
        return plan or Plan({"steps": [context.task]}, tokens=1, seconds=0.1, tool_calls=1)

    async def run_executor(current_plan, context):
        calls.append("executor")
        return execution or Execution({"result": "done"}, tokens=1, seconds=0.1, tool_calls=1)

    async def run_critic(current_execution, context):
        calls.append("critic")
        return critique or Critique("pass", confidence=0.95, tokens=1, seconds=0.1, tool_calls=1)

    async def run_synthesizer(context):
        calls.append("synthesizer")
        return synthesis or Synthesis({"answer": "complete"}, tokens=1, seconds=0.1, tool_calls=1)

    return RunnerDeps(
        run_planner=run_planner,
        run_executor=run_executor,
        run_critic=run_critic,
        run_synthesizer=run_synthesizer,
        run_human_gate=gate,
    ), calls


def test_runner_passes_through_synthesis_and_records_costs():
    deps, calls = make_deps()
    result = asyncio.run(RecursiveMASRunner(deps).run(make_root()))

    assert result["status"] == "succeeded"
    assert result["final_node"].artifacts["final"] == {"answer": "complete"}
    assert calls == ["planner", "executor", "critic", "synthesizer"]
    assert result["budget_used"] == {"tokens": 4, "seconds": pytest.approx(0.4), "tool_calls": 4}
    assert [entry["stage"] for entry in result["trace"]] == [
        "planner", "executor", "critic", "router", "synthesizer"
    ]


def test_runner_refuses_to_replay_a_completed_node():
    deps, calls = make_deps()
    runner = RecursiveMASRunner(deps)
    root = make_root()
    asyncio.run(runner.run(root))

    with pytest.raises(ValueError, match="pending node"):
        asyncio.run(runner.run(root))
    assert calls == ["planner", "executor", "critic", "synthesizer"]


def test_budget_exhaustion_prevents_the_next_agent_call():
    deps, calls = make_deps()
    result = asyncio.run(
        RecursiveMASRunner(deps, RunnerConfig(budget=Budget(max_tokens=1))).run(make_root())
    )

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "max_tokens"
    assert calls == ["planner"]
    assert result["budget_used"]["tokens"] == 1


def test_synthesis_over_budget_is_not_reported_as_success():
    deps, _ = make_deps(
        plan=Plan({}, tokens=0),
        execution=Execution({}, tokens=0),
        critique=Critique("pass", confidence=1.0, tokens=0),
        synthesis=Synthesis("done", tokens=2),
    )
    result = asyncio.run(
        RecursiveMASRunner(deps, RunnerConfig(budget=Budget(max_tokens=1))).run(make_root())
    )

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "max_tokens"
    assert result["final_node"].artifacts["final"] == "done"


def test_iteration_limit_bounds_failed_critique_retries():
    calls = []
    labels = iter(["fail", "fail"])

    async def run_planner(context):
        calls.append("planner")
        return Plan(context.task)

    async def run_executor(plan, context):
        calls.append("executor")
        return Execution({"attempt": context.iteration})

    async def run_critic(execution, context):
        calls.append("critic")
        return Critique(next(labels), confidence=0.8)

    deps = RunnerDeps(
        run_planner=run_planner,
        run_executor=run_executor,
        run_critic=run_critic,
        run_synthesizer=lambda context: Synthesis(None),
    )
    result = asyncio.run(
        RecursiveMASRunner(deps, RunnerConfig(budget=Budget(max_iterations=2))).run(make_root())
    )

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "max_iterations"
    assert calls == ["planner", "executor", "critic", "planner", "executor", "critic"]
    assert result["final_node"].attempts == 2


def test_abort_flag_prevents_any_agent_call():
    deps, calls = make_deps()
    result = asyncio.run(
        RecursiveMASRunner(deps, RunnerConfig(abort_flag=lambda: True)).run(make_root())
    )

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "kill_switch"
    assert calls == []


def test_depth_budget_stops_before_agents_run():
    deps, calls = make_deps()
    result = asyncio.run(
        RecursiveMASRunner(deps, RunnerConfig(budget=Budget(max_depth=1))).run(make_root(depth=2))
    )

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "max_depth"
    assert calls == []


def test_uncertain_critique_pauses_if_human_gate_missing():
    deps, calls = make_deps(critique=Critique("uncertain", confidence=0.1))
    result = asyncio.run(RecursiveMASRunner(deps).run(make_root()))

    assert result["status"] == "awaiting_human"
    assert result["stop_reason"] == "human_gate_unconfigured"
    assert "synthesizer" not in calls


def test_human_pause_checkpoint_resumes_at_synthesis_without_replay():
    async def pause(request, context):
        return HumanGateDecision("pause", "Waiting for reviewer", request)

    deps, calls = make_deps(critique=Critique("uncertain", confidence=0.1), gate=pause)
    runner = RecursiveMASRunner(deps)
    paused = asyncio.run(runner.run(make_root()))

    assert paused["status"] == "awaiting_human"
    assert paused["checkpoint"] is not None
    assert calls == ["planner", "executor", "critic"]

    checkpoint = paused["checkpoint"]
    approval = HumanGateDecision("approve", "Approved", checkpoint.request)
    resumed = asyncio.run(runner.resume(checkpoint, approval))

    assert resumed["status"] == "succeeded"
    assert resumed["final_node"].artifacts["final"] == {"answer": "complete"}
    assert calls == ["planner", "executor", "critic", "synthesizer"]
    with pytest.raises(ValueError, match="not awaiting"):
        asyncio.run(runner.resume(checkpoint, approval))


def test_human_resume_rejects_a_decision_for_another_trace():
    async def pause(request, context):
        return HumanGateDecision("pause", "Waiting", request)

    deps, _ = make_deps(critique=Critique("uncertain", confidence=0.1), gate=pause)
    runner = RecursiveMASRunner(deps)
    paused = asyncio.run(runner.run(make_root()))
    checkpoint = paused["checkpoint"]
    wrong_request = HumanGateRequest(None, None, "another goal", trace_id="other", iteration=0)

    with pytest.raises(ValueError, match="does not match"):
        asyncio.run(runner.resume(checkpoint, HumanGateDecision("approve", "No", wrong_request)))


def test_human_approval_is_required_before_synthesis():
    async def approve(request, context):
        return HumanGateDecision("approve", "Reviewed", request)

    deps, calls = make_deps(critique=Critique("uncertain", confidence=0.1), gate=approve)
    result = asyncio.run(RecursiveMASRunner(deps).run(make_root()))

    assert result["status"] == "succeeded"
    assert result["human_decision"].status == "approve"
    assert result["final_node"].artifacts["human_gate"]["reason"] == "Reviewed"
    assert calls[-1] == "synthesizer"


def test_human_rejection_stops_without_synthesis():
    async def reject(request, context):
        return HumanGateDecision("reject", "Not approved", request)

    deps, calls = make_deps(critique=Critique("uncertain", confidence=0.1), gate=reject)
    result = asyncio.run(RecursiveMASRunner(deps).run(make_root()))

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "human_rejected"
    assert "synthesizer" not in calls


def test_stage_exception_fails_closed_and_is_traced():
    deps, _ = make_deps()

    async def broken_executor(plan, context):
        raise RuntimeError("executor unavailable")

    deps.run_executor = broken_executor
    result = asyncio.run(RecursiveMASRunner(deps).run(make_root()))

    assert result["status"] == "failed"
    assert result["stop_reason"] == "stage_error"
    assert result["trace"][-1]["error_type"] == "RuntimeError"
    assert "secret" not in result["trace"][-1]["error"]


def test_wall_clock_deadline_stops_slow_async_callback():
    calls = []

    async def slow_planner(context):
        calls.append("planner")
        await asyncio.sleep(0.05)
        return Plan({})

    deps, _ = make_deps(calls=calls)
    deps.run_planner = slow_planner
    result = asyncio.run(
        RecursiveMASRunner(deps, RunnerConfig(budget=Budget(max_seconds=0.01))).run(make_root())
    )

    assert result["status"] == "stopped"
    assert result["stop_reason"] == "max_seconds"
    assert calls == ["planner"]


def test_budget_rejects_invalid_limits_and_costs():
    with pytest.raises(ValueError):
        Budget(max_iterations=0)
    with pytest.raises(ValueError):
        NodeCost(tokens_used=-1)
    with pytest.raises(ValueError):
        Critique("pass", confidence=1.1)


def test_confidence_merge_is_stable_for_empty_and_tied_inputs():
    policy = ConfidenceWeightedMergePolicy()
    assert policy.merge([]).artifacts == {}

    first = make_root()
    first.critique = Critique("pass", confidence=0.8)
    first.artifacts["winner"] = "first"
    second = make_root()
    second.id = "second"
    second.critique = Critique("pass", confidence=0.8)
    second.artifacts["winner"] = "second"

    merged = policy.merge([first, second])
    assert merged.selected_node_id == "root"
    assert merged.artifacts["winner"] == "first"


def test_human_gate_adapter_defaults_to_pause_and_accepts_sync_handler():
    adapter = HumanGateAdapter()
    gate_request = HumanGateRequest(None, None, "goal")
    context = RunnerContext("goal", {}, 0, 0, "trace")
    paused = asyncio.run(adapter.run(gate_request, context))
    assert paused.status == "pause"

    def handler(gate_request, context):
        return HumanGateDecision("reject", "No", gate_request)

    rejected = asyncio.run(HumanGateAdapter(handler).run(gate_request, context))
    assert rejected.status == "reject"


def test_sync_role_agents_bind_and_run_without_blocking_contract_mismatch():
    class Planner:
        def run(self, *, task, context):
            return Plan(task)

    class Executor:
        def run(self, *, plan, context):
            return Execution({"plan": plan.output})

    class Critic:
        def run(self, *, execution, context):
            return Critique("pass", confidence=0.9)

    class Synthesizer:
        def run(self, *, context):
            return Synthesis(context.artifacts["execution"])

    deps = build_runner_deps(Planner(), Executor(), Critic(), Synthesizer())
    result = asyncio.run(RecursiveMASRunner(deps).run(make_root()))

    assert result["status"] == "succeeded"
    assert result["final_node"].artifacts["final"] == {"plan": "Build a safe plan"}
