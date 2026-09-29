from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .budget import Budget, BudgetTracker
from .contracts import (
    Critique,
    Execution,
    HumanGateDecision,
    HumanGateRequest,
    Plan,
    RunnerContext,
    RunnerDeps,
    Synthesis,
)
from .leash_policy import DefaultLeashPolicy, LeashDecision, LeashPolicy
from .node import NodeCost, RecursiveNode
from .router import DefaultRouter, Router, RouterDecision


@dataclass
class RunnerConfig:
    budget: Budget = field(default_factory=Budget)
    abort_flag: Callable[[], bool] = lambda: False
    router: Router | None = None
    leash_policy: LeashPolicy | None = None

    def __post_init__(self) -> None:
        if not callable(self.abort_flag):
            raise TypeError("abort_flag must be callable")


@dataclass
class RunnerCheckpoint:
    node: RecursiveNode
    tracker: BudgetTracker
    trace: list[dict[str, Any]]
    iteration: int
    request: HumanGateRequest


class RecursiveMASRunner:
    """Bounded Planner -> Executor -> Critic -> Router loop.

    All callbacks are dependency-injected. The runner itself performs no
    network, filesystem, or provider operations.
    """

    def __init__(self, deps: RunnerDeps, config: RunnerConfig | None = None):
        self.deps = deps
        self.config = config or RunnerConfig()
        self.router = self.config.router or self.deps.router or DefaultRouter()
        self.leash_policy = self.config.leash_policy or self.deps.leash_policy or DefaultLeashPolicy()

    @staticmethod
    async def _invoke(callback, *args, timeout: float) -> tuple[Any, float]:
        started = time.monotonic()
        if inspect.iscoroutinefunction(callback):
            value = await asyncio.wait_for(callback(*args), timeout=timeout)
        else:
            value = await asyncio.wait_for(asyncio.to_thread(callback, *args), timeout=timeout)
            if inspect.isawaitable(value):
                value = await asyncio.wait_for(value, timeout=max(0.0, timeout - (time.monotonic() - started)))
        return value, time.monotonic() - started

    @staticmethod
    def _cost(result: Any, elapsed_seconds: float = 0.0) -> NodeCost:
        cost = NodeCost(
            tokens_used=getattr(result, "tokens", None),
            seconds_used=max(getattr(result, "seconds", 0.0), elapsed_seconds),
            tool_calls=getattr(result, "tool_calls", None),
        )
        return cost

    def _leash(self, node: RecursiveNode, tracker: BudgetTracker, iteration: int) -> LeashDecision:
        return self.leash_policy.evaluate(
            node,
            tracker,
            self.config.budget,
            iteration,
            bool(self.config.abort_flag()),
        )

    @staticmethod
    def _context(node: RecursiveNode, iteration: int) -> RunnerContext:
        return RunnerContext(
            task=node.goal,
            artifacts=dict(node.artifacts),
            depth=node.depth,
            iteration=iteration,
            trace_id=node.trace_id,
        )

    @staticmethod
    def _record(trace: list[dict[str, Any]], stage: str, status: str, **details: Any) -> None:
        trace.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "status": status,
            **details,
        })

    @staticmethod
    def _result(
        node: RecursiveNode,
        tracker: BudgetTracker,
        trace: list[dict[str, Any]],
        stop_reason: str | None,
        human_decision: HumanGateDecision | None = None,
        checkpoint: RunnerCheckpoint | None = None,
    ) -> dict[str, Any]:
        node.cost = NodeCost(tracker.tokens, tracker.seconds, tracker.tool_calls)
        return {
            "status": node.status,
            "stop_reason": stop_reason,
            "final_node": node,
            "trace": trace,
            "budget_used": {
                "tokens": tracker.tokens,
                "seconds": tracker.seconds,
                "tool_calls": tracker.tool_calls,
            },
            "human_decision": human_decision,
            "checkpoint": checkpoint,
        }

    @staticmethod
    def _matches_request(decision: HumanGateDecision, request: HumanGateRequest) -> bool:
        supplied = decision.request
        return (
            supplied.trace_id == request.trace_id
            and supplied.goal == request.goal
            and supplied.iteration == request.iteration
        )

    def _exceeded_budget(self, tracker: BudgetTracker) -> str | None:
        if tracker.tokens > self.config.budget.max_tokens:
            return "max_tokens"
        if tracker.seconds > self.config.budget.max_seconds:
            return "max_seconds"
        if tracker.tool_calls > self.config.budget.max_tool_calls:
            return "max_tool_calls"
        return None

    async def run(self, root: RecursiveNode) -> dict[str, Any]:
        if root.status != "pending":
            raise ValueError("run requires a pending node; resume paused runs with their checkpoint")
        tracker = BudgetTracker()
        trace: list[dict[str, Any]] = []
        current = root
        current.status = "running"
        current.trace_id = current.trace_id or str(uuid.uuid4())
        iteration = 0
        stop_reason: str | None = None
        human_decision: HumanGateDecision | None = None
        pending_request: HumanGateRequest | None = None

        def stop_if_leashed(stage: str) -> bool:
            nonlocal stop_reason
            leash = self._leash(current, tracker, iteration)
            if leash.should_stop:
                stop_reason = leash.stop_reason
                current.status = "stopped"
                self._record(trace, stage, "stopped", reason=stop_reason)
                return True
            return False

        def timeout_remaining() -> float:
            return max(0.0, self.config.budget.max_seconds - tracker.seconds)

        try:
            while True:
                if stop_if_leashed("preflight"):
                    break
                current.critique = None
                context = self._context(current, iteration)

                plan, elapsed = await self._invoke(self.deps.run_planner, context, timeout=timeout_remaining())
                if not isinstance(plan, Plan):
                    raise TypeError("run_planner must return Plan")
                current.artifacts["plan"] = plan.output
                plan_cost = self._cost(plan, elapsed)
                tracker.apply(plan_cost)
                self._record(trace, "planner", "completed", cost=plan_cost.__dict__.copy())
                if stop_if_leashed("after_planner"):
                    break

                execution, elapsed = await self._invoke(
                    self.deps.run_executor, plan, self._context(current, iteration), timeout=timeout_remaining()
                )
                if not isinstance(execution, Execution):
                    raise TypeError("run_executor must return Execution")
                current.artifacts["execution"] = execution.output
                execution_cost = self._cost(execution, elapsed)
                tracker.apply(execution_cost)
                self._record(trace, "executor", "completed", cost=execution_cost.__dict__.copy())
                if stop_if_leashed("after_executor"):
                    break

                critique, elapsed = await self._invoke(
                    self.deps.run_critic, execution, self._context(current, iteration), timeout=timeout_remaining()
                )
                if not isinstance(critique, Critique):
                    raise TypeError("run_critic must return Critique")
                current.critique = critique
                current.attempts += 1
                critique_cost = self._cost(critique, elapsed)
                tracker.apply(critique_cost)
                self._record(trace, "critic", "completed", label=critique.label, cost=critique_cost.__dict__.copy())
                leash = self._leash(current, tracker, iteration)
                route = self.router.route(current, leash)
                if not isinstance(route, RouterDecision):
                    raise TypeError("router must return RouterDecision")
                self._record(trace, "router", route.target, reason=route.stop_reason)

                if route.target == "stop":
                    stop_reason = route.stop_reason or "router_stop"
                    current.status = "stopped"
                    break

                if route.target == "human_gate":
                    request = HumanGateRequest(
                        execution=execution.output,
                        critique=critique,
                        goal=current.goal,
                        trace_id=current.trace_id,
                        iteration=iteration,
                    )
                    pending_request = request
                    if self.deps.run_human_gate is None:
                        current.status = "awaiting_human"
                        stop_reason = "human_gate_unconfigured"
                        self._record(trace, "human_gate", "paused", reason=stop_reason)
                        break
                    human_decision, elapsed = await self._invoke(
                        self.deps.run_human_gate,
                        request,
                        self._context(current, iteration),
                        timeout=timeout_remaining(),
                    )
                    if not isinstance(human_decision, HumanGateDecision):
                        raise TypeError("run_human_gate must return HumanGateDecision")
                    if not self._matches_request(human_decision, request):
                        raise ValueError("human gate decision does not match the pending request")
                    current.artifacts["human_gate"] = {
                        "status": human_decision.status,
                        "reason": human_decision.reason,
                    }
                    self._record(trace, "human_gate", human_decision.status, reason=human_decision.reason)
                    tracker.apply(NodeCost(seconds_used=elapsed))
                    if human_decision.status == "pause":
                        current.status = "awaiting_human"
                        stop_reason = "human_pause"
                        break
                    if human_decision.status == "reject":
                        current.status = "stopped"
                        stop_reason = "human_rejected"
                        break
                    route = RouterDecision("synthesizer")

                if route.target == "synthesizer":
                    if stop_if_leashed("before_synthesizer"):
                        break
                    synthesis, elapsed = await self._invoke(
                        self.deps.run_synthesizer,
                        self._context(current, iteration),
                        timeout=timeout_remaining(),
                    )
                    if not isinstance(synthesis, Synthesis):
                        raise TypeError("run_synthesizer must return Synthesis")
                    current.artifacts["final"] = synthesis.output
                    synthesis_cost = self._cost(synthesis, elapsed)
                    tracker.apply(synthesis_cost)
                    self._record(trace, "synthesizer", "completed", cost=synthesis_cost.__dict__.copy())
                    stop_reason = self._exceeded_budget(tracker)
                    current.status = "stopped" if stop_reason else "succeeded"
                    break

                if route.target != "planner":
                    raise ValueError(f"unsupported router target: {route.target!r}")
                next_iteration = iteration + 1
                if next_iteration >= self.config.budget.max_iterations:
                    current.status = "stopped"
                    stop_reason = "max_iterations"
                    self._record(trace, "iteration_guard", "stopped", reason=stop_reason)
                    break
                iteration = next_iteration

        except asyncio.CancelledError:
            current.status = "stopped"
            stop_reason = "cancelled"
            self._record(trace, "runner", "cancelled")
            raise
        except asyncio.TimeoutError:
            current.status = "stopped"
            stop_reason = "max_seconds"
            self._record(trace, "runner", "stopped", reason=stop_reason)
        except Exception as exc:
            current.status = "failed"
            stop_reason = "stage_error"
            self._record(
                trace,
                "runner",
                "failed",
                error_type=type(exc).__name__,
                error="Agent stage failed; inspect protected server logs.",
            )

        checkpoint = None
        if current.status == "awaiting_human" and pending_request is not None:
            checkpoint = RunnerCheckpoint(current, tracker, trace, iteration, pending_request)
        return self._result(current, tracker, trace, stop_reason, human_decision, checkpoint)

    async def resume(self, checkpoint: RunnerCheckpoint, decision: HumanGateDecision) -> dict[str, Any]:
        """Continue a paused run after an external authority supplies a decision.

        The caller is responsible for authenticating/authorizing the human. An
        approval resumes at synthesis and does not replay completed agent work.
        """
        if checkpoint.node.status != "awaiting_human":
            raise ValueError("checkpoint is not awaiting a human decision")
        if not self._matches_request(decision, checkpoint.request):
            raise ValueError("human gate decision does not match the checkpoint request")

        node = checkpoint.node
        tracker = checkpoint.tracker
        trace = checkpoint.trace
        human_decision = decision
        node.artifacts["human_gate"] = {"status": decision.status, "reason": decision.reason}
        self._record(trace, "human_gate", decision.status, reason=decision.reason)

        if decision.status == "pause":
            return self._result(node, tracker, trace, "human_pause", decision, checkpoint)
        if decision.status == "reject":
            node.status = "stopped"
            return self._result(node, tracker, trace, "human_rejected", decision)

        try:
            leash = self._leash(node, tracker, checkpoint.iteration)
            if leash.should_stop:
                node.status = "stopped"
                self._record(trace, "resume_preflight", "stopped", reason=leash.stop_reason)
                return self._result(node, tracker, trace, leash.stop_reason, decision)
            node.status = "running"
            synthesis, elapsed = await self._invoke(
                self.deps.run_synthesizer,
                self._context(node, checkpoint.iteration),
                timeout=max(0.0, self.config.budget.max_seconds - tracker.seconds),
            )
            if not isinstance(synthesis, Synthesis):
                raise TypeError("run_synthesizer must return Synthesis")
            node.artifacts["final"] = synthesis.output
            cost = self._cost(synthesis, elapsed)
            tracker.apply(cost)
            self._record(trace, "synthesizer", "completed", cost=cost.__dict__.copy())
            stop_reason = self._exceeded_budget(tracker)
            node.status = "stopped" if stop_reason else "succeeded"
            return self._result(node, tracker, trace, stop_reason, decision)
        except asyncio.CancelledError:
            node.status = "stopped"
            self._record(trace, "runner", "cancelled")
            raise
        except asyncio.TimeoutError:
            node.status = "stopped"
            self._record(trace, "runner", "stopped", reason="max_seconds")
            return self._result(node, tracker, trace, "max_seconds", decision)
        except Exception as exc:
            node.status = "failed"
            self._record(
                trace,
                "runner",
                "failed",
                error_type=type(exc).__name__,
                error="Agent stage failed; inspect protected server logs.",
            )
            return self._result(node, tracker, trace, "stage_error", decision)
