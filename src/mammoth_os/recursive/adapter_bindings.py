from __future__ import annotations

from mammoth_os.agents.adapters import (
    CriticAdapter,
    ExecutorAdapter,
    HumanGateAdapter,
    PlannerAdapter,
    SynthesizerAdapter,
)
from .contracts import RunnerDeps
from .leash_policy import DefaultLeashPolicy, LeashPolicy
from .router import DefaultRouter, Router


def build_runner_deps(
    planner,
    executor,
    critic,
    synthesizer,
    human_gate=None,
    *,
    router: Router | None = None,
    leash_policy: LeashPolicy | None = None,
) -> RunnerDeps:
    """Bind role agents and explicit routing policies into runner dependencies."""
    return RunnerDeps(
        run_planner=PlannerAdapter(planner).run,
        run_executor=ExecutorAdapter(executor).run,
        run_critic=CriticAdapter(critic).run,
        run_synthesizer=SynthesizerAdapter(synthesizer).run,
        run_human_gate=HumanGateAdapter(human_gate).run,
        router=router or DefaultRouter(),
        leash_policy=leash_policy or DefaultLeashPolicy(),
    )
