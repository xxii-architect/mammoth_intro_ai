from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .budget import Budget, BudgetTracker
from .node import RecursiveNode


@dataclass(frozen=True)
class LeashDecision:
    should_stop: bool
    stop_reason: str | None = None


class LeashPolicy(Protocol):
    def evaluate(
        self,
        node: RecursiveNode,
        tracker: BudgetTracker,
        budget: Budget,
        iteration: int,
        abort: bool,
    ) -> LeashDecision: ...


class DefaultLeashPolicy:
    def evaluate(
        self,
        node: RecursiveNode,
        tracker: BudgetTracker,
        budget: Budget,
        iteration: int,
        abort: bool,
    ) -> LeashDecision:
        if abort:
            return LeashDecision(True, "kill_switch")
        if node.depth > budget.max_depth:
            return LeashDecision(True, "max_depth")
        if iteration >= budget.max_iterations:
            return LeashDecision(True, "max_iterations")
        if tracker.tokens >= budget.max_tokens:
            return LeashDecision(True, "max_tokens")
        if tracker.seconds >= budget.max_seconds:
            return LeashDecision(True, "max_seconds")
        if tracker.tool_calls >= budget.max_tool_calls:
            return LeashDecision(True, "max_tool_calls")
        return LeashDecision(False)
