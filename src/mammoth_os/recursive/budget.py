from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .node import NodeCost


@dataclass(frozen=True)
class Budget:
    max_depth: int = 2
    max_iterations: int = 4
    max_tokens: int = 50_000
    max_seconds: float = 60.0
    max_tool_calls: int = 50

    def __post_init__(self) -> None:
        if isinstance(self.max_depth, bool) or not isinstance(self.max_depth, int) or self.max_depth < 0:
            raise ValueError("max_depth must be a non-negative integer")
        if isinstance(self.max_iterations, bool) or not isinstance(self.max_iterations, int) or self.max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or self.max_tokens < 0:
            raise ValueError("max_tokens must be a non-negative integer")
        if isinstance(self.max_tool_calls, bool) or not isinstance(self.max_tool_calls, int) or self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be a non-negative integer")
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, (int, float))
            or not isfinite(self.max_seconds)
            or self.max_seconds < 0
        ):
            raise ValueError("max_seconds must be finite and non-negative")


@dataclass
class BudgetTracker:
    tokens: int = 0
    seconds: float = 0.0
    tool_calls: int = 0

    def apply(self, cost: NodeCost) -> None:
        self.tokens += cost.tokens_used
        self.seconds += cost.seconds_used
        self.tool_calls += cost.tool_calls
