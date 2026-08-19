"""Embeddable ATLAS FAB SDK surface for developers integrating MammothOS."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from mammoth_os.atlas_session import ATLASSession
from mammoth_os.llm_client import get_llm_client


def _run_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("AtlasFAB blocking methods cannot run inside an active event loop. Use the async variant instead.")


@dataclass(slots=True)
class AtlasFABConfig:
    """Configuration for embedding the ATLAS tutoring loop inside another product."""

    user_id: str = "workspace:default"
    adapter: str = ""
    model: str = ""
    audience: str = "developer"
    mode: str = "tutor"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def llm_config(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {}
        if self.adapter:
            config["MAMMOTH_LLM_ADAPTER"] = self.adapter
        if self.model:
            config["model"] = self.model
        return config


class AtlasFAB:
    """Small public SDK for embedding ATLAS lesson and code workflows."""

    contract_version = "v1"

    def __init__(self, config: Optional[AtlasFABConfig] = None, session: Optional[ATLASSession] = None):
        self.config = config or AtlasFABConfig()
        self.session = session or ATLASSession(user_id=self.config.user_id)

    def start_lesson(
        self,
        topic: str,
        *,
        module_idx: int = 0,
        lesson_idx: int = 0,
        exercise_count: int = 1,
        use_llm: Optional[bool] = None,
        difficulty: str = "beginner",
        learner_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        resolved_context = dict(self.config.metadata.get("learner_context") or {})
        if learner_context:
            resolved_context.update(learner_context)
        return self.session.start_lesson(
            topic,
            module_idx=module_idx,
            lesson_idx=lesson_idx,
            exercise_count=exercise_count,
            use_llm=use_llm,
            difficulty=difficulty,
            learner_context=resolved_context or None,
        )

    def status(self) -> Dict[str, Any]:
        return self.session.status()

    def next_lesson(self, lesson_idx_delta: int = 1) -> Dict[str, Any]:
        return self.session.next_lesson(lesson_idx_delta=lesson_idx_delta)

    async def submit_async(
        self,
        *,
        files: Optional[Dict[str, str]] = None,
        solution_code: str = "",
        solution_filename: str = "solution.py",
    ) -> Dict[str, Any]:
        payload = dict(files or {})
        if solution_code and solution_filename not in payload:
            payload[solution_filename] = solution_code
        if not payload:
            raise ValueError("submit_async requires files or solution_code.")
        return await self.session.submit(payload)

    def submit(
        self,
        *,
        files: Optional[Dict[str, str]] = None,
        solution_code: str = "",
        solution_filename: str = "solution.py",
    ) -> Dict[str, Any]:
        return _run_blocking(
            self.submit_async(
                files=files,
                solution_code=solution_code,
                solution_filename=solution_filename,
            )
        )

    async def generate_and_test_async(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resolved = {"source": "atlas_fab", "audience": self.config.audience, "mode": self.config.mode}
        if context:
            resolved.update(context)
        return await self.session.generate_and_test(prompt, context=resolved)

    def generate_and_test(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return _run_blocking(self.generate_and_test_async(prompt, context=context))

    def runtime_state(self) -> Dict[str, Any]:
        client = get_llm_client(self.config.llm_config())
        describe = getattr(client, "describe_runtime_state", None)
        if callable(describe):
            state = describe()
        else:
            state = {
                "primary_provider": type(client).__name__.replace("Adapter", "").lower(),
                "model": str(getattr(client, "model", "unknown")),
            }
        return {
            "contract_version": self.contract_version,
            "product_surface": "atlas_fab",
            "user_id": self.config.user_id,
            "audience": self.config.audience,
            "mode": self.config.mode,
            **state,
        }
