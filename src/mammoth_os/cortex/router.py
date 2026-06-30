"""
Mammoth OS — Cortex Router
Routes high-level intents to the appropriate agents via the AutonomousEngine.
"""

from typing import Any, Dict
from mammoth_os.autonomous_engine import AutonomousEngine # type: ignore


class CortexRouter:
    """
    Intent-based router for Mammoth OS.
    """

    def __init__(self, user_id: str | None = None):
        self.engine = AutonomousEngine(user_id=user_id)

    def route(self, intent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route an intent to the correct agent.

        Args:
            intent: High-level task type (e.g., 'plant_seed', 'field_ops').
            payload: Dict of task parameters.

        Returns:
            AutonomousEngine result dict.
        """
        agent_name = self._map_intent_to_agent(intent)
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
            "visual": "visual_engine",
            "community": "community_engine",
        }

        if intent not in intent_map:
            raise ValueError(f"Unknown intent: {intent}")

        return intent_map[intent]
