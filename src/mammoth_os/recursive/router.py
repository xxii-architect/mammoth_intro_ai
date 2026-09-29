from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .leash_policy import LeashDecision
from .node import RecursiveNode


RouteTarget = Literal["planner", "synthesizer", "human_gate", "stop"]


@dataclass(frozen=True)
class RouterDecision:
    target: RouteTarget
    stop_reason: str | None = None


class Router(Protocol):
    def route(self, node: RecursiveNode, leash: LeashDecision) -> RouterDecision: ...


class DefaultRouter:
    def __init__(self, human_gate_confidence_threshold: float = 0.3):
        if not 0.0 <= human_gate_confidence_threshold <= 1.0:
            raise ValueError("human_gate_confidence_threshold must be between 0 and 1")
        self.human_gate_confidence_threshold = human_gate_confidence_threshold

    def route(self, node: RecursiveNode, leash: LeashDecision) -> RouterDecision:
        if leash.should_stop:
            return RouterDecision("stop", leash.stop_reason)
        critique = node.critique
        if critique is None:
            return RouterDecision("planner")
        if critique.label == "pass":
            return RouterDecision("synthesizer")
        if critique.label == "uncertain" and critique.confidence < self.human_gate_confidence_threshold:
            return RouterDecision("human_gate")
        if critique.label in {"fail", "uncertain"}:
            return RouterDecision("planner")
        return RouterDecision("human_gate")
