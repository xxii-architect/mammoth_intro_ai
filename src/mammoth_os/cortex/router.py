"""
Mammoth OS — Cortex Router
Routes high-level intents to the appropriate agents via the AutonomousEngine.
"""

from typing import Any, Dict
from mammoth_os.agents.autonomous_engine import AutonomousEngine
from mammoth_os.agents.research_agent import ResearchAgent # type: ignore


class CortexRouter:
    """
    Intent-based router for Mammoth OS.
    """

    def __init__(self, user_id: str | None = None):
        self.engine = AutonomousEngine(user_id=user_id)

    def route(self, intent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route an intent to the correct agent.

        Intent → agent_name via _map_intent_to_agent, then:
        1. Delegate to agent_registry.run_agent for all registered agents.
        2. Fall back to AutonomousEngine.run_task for legacy file-op tasks
           (create_file, write_file, apply_patch) that live outside the registry.
        """
        agent_name = self._map_intent_to_agent(intent)

        # ── Primary path: AGENTS registry ─────────────────────────────────
        _FILE_OPS = {"create_file", "write_file", "apply_patch"}
        if agent_name not in _FILE_OPS:
            try:
                from mammoth_os.agent_registry import run_agent as _reg_run  # type: ignore
                result = _reg_run(agent_name, payload)
                # run_agent may return a coroutine if the underlying agent is async
                import asyncio
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            import concurrent.futures
                            fut = asyncio.run_coroutine_threadsafe(result, loop)
                            result = fut.result(timeout=60)
                        else:
                            result = loop.run_until_complete(result)
                    except RuntimeError:
                        result = asyncio.run(result)
                return result
            except Exception as exc:
                return {"status": "error", "agent": agent_name, "error": str(exc)}

        # ── Fallback: AutonomousEngine for file-manipulation tasks ─────────
        return self.engine.run_task(agent_name, payload)

    def _map_intent_to_agent(self, intent: str) -> str:
        """
        Map high-level intents to agent registry names.
        """
        intent_map = {
            "plant_seed": "plant_the_seed",
            "field_ops": "field_ops",
            "market_intel": "market_intel",
            "reflection": "reflection",
            "brand_voice": "brand_voice",
            "community": "community_engine",

            # Research intents
            "research": "research",
            "research_long_form": "research",
            "research_curriculum": "research",
            "research_survival": "research",
            "research_plants": "research",
            "compare_gear": "research",
            "summarize": "research",

            "guide": "mammoth_guide",
            "mammoth_guide": "mammoth_guide",
            "classifier": "classifier",

            # Auth / identity
            "auth": "auth",
            "validate_token": "auth",
            "issue_token": "auth",

            # Build / deploy / ops
            "build": "build",
            "deploy": "deploy",
            "execute": "executor",
            "executor": "executor",

            # Config / database
            "config": "config_manager",
            "config_manager": "config_manager",
            "database": "database",
            "db": "database",
            "migrate": "database",

            # File / shell / snapshot
            "filesystem": "filesystem",
            "fs": "filesystem",
            "shell": "shell",
            "snapshot": "snapshot",

            # Memory / scheduler
            "memory": "memory",
            "remember": "memory",
            "scheduler": "scheduler",
            "schedule": "scheduler",

            # UI / vector store
            "ui_builder": "ui_builder",
            "build_ui": "ui_builder",
            "vector_store": "vector_store",
            "rag": "vector_store",
            "embed": "vector_store",
        }

        # Smart fallback: if intent not in map, check AGENTS dict directly
        if intent not in intent_map:
            try:
                from mammoth_os.agent_registry import AGENTS
                if intent in AGENTS:
                    return intent
            except Exception:
                pass
            raise ValueError(f"Unknown intent: {intent}")

        return intent_map[intent]
