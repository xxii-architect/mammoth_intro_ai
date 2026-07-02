"""
Mammoth OS — CommunityEngineAgent
Generates community challenges, shared missions, group prompts, and
leaderboard-driven engagement tasks for Mammoth OS and True XXII Supply.
"""

from typing import Dict, Any
from datetime import datetime


class CommunityEngineAgent:
    """
    Produces structured community engagement tasks and group challenges.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "theme": "fieldcraft" | "mindset" | "wildlife" | "ai_learning",
            "difficulty": "easy" | "medium" | "hard",
            "group_size": 1 | 5 | 20 | "open"
        }
        """
        theme = payload.get("theme", "mindset")
        difficulty = payload.get("difficulty", "easy")
        group_size = payload.get("group_size", "open")

        challenge = self._generate_challenge(theme, difficulty)
        prompt = self._generate_prompt(theme)
        reward = self._generate_reward(difficulty)
        social = self._generate_social_callout(group_size)

        return {
            "agent": "community_engine",
            "timestamp": datetime.utcnow().isoformat(),
            "theme": theme,
            "difficulty": difficulty,
            "group_size": group_size,
            "challenge": challenge,
            "prompt": prompt,
            "reward": reward,
            "social_callout": social,
        }

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _generate_challenge(self, theme: str, difficulty: str) -> str:
        """
        Creates a community challenge based on theme + difficulty.
        """
        base = f"A {difficulty} community challenge focused on {theme}."

        if theme == "fieldcraft":
            return (
                f"{base} Everyone completes a small outdoor task today — "
                f"identify a plant, track an animal sign, or note a terrain feature."
            )

        if theme == "wildlife":
            return (
                f"{base} Each person documents one wildlife sighting or sign. "
                f"Share photos, sketches, or notes."
            )

        if theme == "ai_learning":
            return (
                f"{base} Everyone builds one tiny AI workflow or solves one "
                f"small coding problem. Share your result with the group."
            )

        return (
            f"{base} Reflect on one thing you learned today and post a short "
            f"sentence about it. Keep it honest and grounded."
        )

    def _generate_prompt(self, theme: str) -> str:
        """
        Community discussion prompt.
        """
        if theme == "fieldcraft":
            return (
                "What’s one outdoor skill you practiced today that made you feel more capable?"
            )

        if theme == "wildlife":
            return (
                "What animal signs did you notice today that you normally overlook?"
            )

        if theme == "ai_learning":
            return (
                "What part of today’s AI lesson clicked for you in a new way?"
            )

        return (
            "What’s one thing you learned today that surprised you?"
        )

    def _generate_reward(self, difficulty: str) -> Dict[str, Any]:
        """
        Suggests XP or streak bonuses based on difficulty.
        """
        if difficulty == "hard":
            return {"xp_bonus": 40, "streak_bonus": 2}

        if difficulty == "medium":
            return {"xp_bonus": 25, "streak_bonus": 1}

        return {"xp_bonus": 10, "streak_bonus": 0}

    def _generate_social_callout(self, group_size: Any) -> str:
        """
        Creates a social callout message based on group size.
        """
        if group_size == "open":
            return (
                "Open challenge — anyone can join. Share your progress and hype each other up."
            )

        if isinstance(group_size, int) and group_size <= 5:
            return (
                f"Small crew challenge — keep each other accountable and share your wins."
            )

        if isinstance(group_size, int) and group_size > 5:
            return (
                f"Group challenge for {group_size} people — post your updates and "
                f"celebrate progress together."
            )

        return "Community challenge — share your results with the Mammoth Crew."
