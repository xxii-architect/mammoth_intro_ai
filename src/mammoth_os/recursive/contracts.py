from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, TypeVar


@dataclass
class Plan:
    output: Any
    tokens: int = 0
    seconds: float = 0.0
    tool_calls: int = 0


@dataclass
class Execution:
    output: Any
    tokens: int = 0
    seconds: float = 0.0
    tool_calls: int = 0


@dataclass
class Critique:
    label: Literal["pass", "fail", "uncertain"]
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    tokens: int = 0
    seconds: float = 0.0
    tool_calls: int = 0

    def __post_init__(self) -> None:
        if self.label not in {"pass", "fail", "uncertain"}:
            raise ValueError("critique label must be pass, fail, or uncertain")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("critique confidence must be between 0 and 1")


@dataclass
class Synthesis:
    output: Any
    tokens: int = 0
    seconds: float = 0.0
    tool_calls: int = 0


@dataclass
class HumanGateRequest:
    execution: Any
    critique: Critique | None
    goal: str
    trace_id: str = ""
    iteration: int = 0


@dataclass
class HumanGateDecision:
    status: Literal["pause", "approve", "reject"]
    reason: str
    request: HumanGateRequest

    def __post_init__(self) -> None:
        if self.status not in {"pause", "approve", "reject"}:
            raise ValueError("human gate status must be pause, approve, or reject")


@dataclass
class RunnerContext:
    task: str
    artifacts: dict[str, Any]
    depth: int
    iteration: int
    trace_id: str


T = TypeVar("T")
MaybeAwaitable = T | Awaitable[T]
PlannerCallback = Callable[[RunnerContext], MaybeAwaitable[Plan]]
ExecutorCallback = Callable[[Plan, RunnerContext], MaybeAwaitable[Execution]]
CriticCallback = Callable[[Execution, RunnerContext], MaybeAwaitable[Critique]]
SynthesizerCallback = Callable[[RunnerContext], MaybeAwaitable[Synthesis]]
HumanGateCallback = Callable[[HumanGateRequest, RunnerContext], MaybeAwaitable[HumanGateDecision]]


@dataclass
class RunnerDeps:
    run_planner: PlannerCallback
    run_executor: ExecutorCallback
    run_critic: CriticCallback
    run_synthesizer: SynthesizerCallback
    run_human_gate: HumanGateCallback | None = None
    router: Any = None
    leash_policy: Any = None
