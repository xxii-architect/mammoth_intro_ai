"""
Mammoth OS — FieldOpsAgent
Generates hands-on field exercises, wildlife observations, terrain challenges,
and practical survival tasks for Monday fieldwork and learning modules.
"""

from typing import Dict, Any


class FieldOpsAgent:
    """
    Produces rugged, outdoors-focused practice tasks.
    Designed for True XXII Supply's fieldwork identity.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "topic": "navigation",
            "environment": "forest",
            "difficulty": "easy" | "medium" | "hard"
        }
        """
        topic = payload.get("topic", "general fieldcraft")
        environment = payload.get("environment", "outdoors")
        difficulty = payload.get("difficulty", "easy")

        mission = self._generate_mission(topic, environment, difficulty)
        skill_focus = self._skill_focus(topic)
        checklist = self._generate_checklist(topic, environment)

        return {
            "agent": "field_ops",
            "topic": topic,
            "environment": environment,
            "difficulty": difficulty,
            "mission": mission,
            "skill_focus": skill_focus,
            "checklist": checklist,
        }

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _generate_mission(self, topic: str, environment: str, difficulty: str) -> str:
        """
        Creates a field mission based on topic + environment + difficulty.
        """
        base = f"Head into the {environment} and complete a {difficulty} {topic} exercise."

        if topic.lower() == "navigation":
            return (
                f"{base} Choose a landmark, plot a bearing, and travel to it without "
                f"checking your phone. Log obstacles and terrain changes."
            )

        if topic.lower() == "plant identification":
            return (
                f"{base} Locate three plants you can positively identify. "
                f"Record leaf structure, scent, habitat, and any medicinal or survival uses."
            )

        if topic.lower() == "wildlife tracking":
            return (
                f"{base} Find fresh tracks or signs. Document gait, direction, "
                f"feeding behavior, and any nearby water sources."
            )

        if topic.lower() == "firecraft":
            return (
                f"{base} Gather tinder, kindling, and fuel. Build a stable fire lay "
                f"and note moisture levels, wind direction, and ignition success."
            )

        return (
            f"{base} Perform a practical field task and record observations "
            f"that relate to real-world survival or outdoors skills."
        )

    def _skill_focus(self, topic: str) -> str:
        """
        Provides the core skill being trained.
        """
        mapping = {
            "navigation": "Situational awareness + bearing discipline",
            "plant identification": "Pattern recognition + ecological literacy",
            "wildlife tracking": "Movement analysis + environmental reading",
            "firecraft": "Resource assessment + controlled ignition",
        }
        return mapping.get(topic.lower(), "General fieldcraft fundamentals")

    def _generate_checklist(self, topic: str, environment: str) -> Dict[str, bool]:
        """
        Returns a simple checklist of field tasks.
        """
        if topic.lower() == "navigation":
            return {
                "selected_landmark": False,
                "plotted_bearing": False,
                "terrain_notes_recorded": False,
                "distance_estimated": False,
            }

        if topic.lower() == "plant identification":
            return {
                "three_plants_found": False,
                "leaf_structure_noted": False,
                "habitat_logged": False,
                "medicinal_value_checked": False,
            }

        if topic.lower() == "wildlife tracking":
            return {
                "tracks_found": False,
                "direction_logged": False,
                "behavior_inferred": False,
                "water_sources_noted": False,
            }

        if topic.lower() == "firecraft":
            return {
                "tinder_collected": False,
                "kindling_prepared": False,
                "fire_lay_built": False,
                "ignition_attempted": False,
            }

        return {
            "observation_made": False,
            "notes_recorded": False,
            "environment_assessed": False,
        }
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
