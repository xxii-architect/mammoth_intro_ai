from __future__ import annotations

import asyncio
import inspect
from typing import Any, Protocol

from mammoth_os.recursive.contracts import (
    Critique,
    Execution,
    HumanGateDecision,
    HumanGateRequest,
    Plan,
    RunnerContext,
    Synthesis,
)


async def _invoke_agent(method, *args, **kwargs):
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)
    result = await asyncio.to_thread(method, *args, **kwargs)
    return await result if inspect.isawaitable(result) else result


class PlannerLike(Protocol):
    def run(self, *, task: str, context: RunnerContext) -> Any: ...


class ExecutorLike(Protocol):
    def run(self, *, plan: Plan, context: RunnerContext) -> Any: ...


class CriticLike(Protocol):
    def run(self, *, execution: Execution, context: RunnerContext) -> Any: ...


class SynthesizerLike(Protocol):
    def run(self, *, context: RunnerContext) -> Any: ...


class PlannerAdapter:
    def __init__(self, agent: PlannerLike):
        self.agent = agent

    async def run(self, context: RunnerContext) -> Plan:
        return await _invoke_agent(self.agent.run, task=context.task, context=context)


class ExecutorAdapter:
    def __init__(self, agent: ExecutorLike):
        self.agent = agent

    async def run(self, plan: Plan, context: RunnerContext) -> Execution:
        return await _invoke_agent(self.agent.run, plan=plan, context=context)


class CriticAdapter:
    def __init__(self, agent: CriticLike):
        self.agent = agent

    async def run(self, execution: Execution, context: RunnerContext) -> Critique:
        return await _invoke_agent(self.agent.run, execution=execution, context=context)


class SynthesizerAdapter:
    def __init__(self, agent: SynthesizerLike):
        self.agent = agent

    async def run(self, context: RunnerContext) -> Synthesis:
        return await _invoke_agent(self.agent.run, context=context)


class HumanGateAdapter:
    def __init__(self, handler=None):
        self.handler = handler

    async def run(self, request: HumanGateRequest, context: RunnerContext) -> HumanGateDecision:
        if self.handler is None:
            return HumanGateDecision(
                status="pause",
                reason="No human gate handler configured.",
                request=request,
            )
        return await _invoke_agent(self.handler, request, context)
