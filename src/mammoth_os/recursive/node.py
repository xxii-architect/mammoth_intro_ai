from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass
class NodeCost:
    tokens_used: int = 0
    seconds_used: float = 0.0
    tool_calls: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.tokens_used, bool) or not isinstance(self.tokens_used, int) or self.tokens_used < 0:
            raise ValueError("tokens_used must be a non-negative integer")
        if isinstance(self.tool_calls, bool) or not isinstance(self.tool_calls, int) or self.tool_calls < 0:
            raise ValueError("tool_calls must be a non-negative integer")
        if (
            isinstance(self.seconds_used, bool)
            or not isinstance(self.seconds_used, (int, float))
            or not isfinite(self.seconds_used)
            or self.seconds_used < 0
        ):
            raise ValueError("seconds_used must be finite and non-negative")


@dataclass
class RecursiveNode:
    id: str
    trace_id: str
    role: str
    goal: str
    depth: int = 0
    parent_id: str | None = None
    status: str = "pending"
    artifacts: dict[str, Any] = field(default_factory=dict)
    critique: Any = None
    attempts: int = 0
    cost: NodeCost = field(default_factory=NodeCost)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("node id is required")
        if not self.trace_id:
            raise ValueError("trace_id is required")
        if self.depth < 0:
            raise ValueError("depth must be non-negative")
        if not self.goal.strip():
            raise ValueError("node goal is required")
