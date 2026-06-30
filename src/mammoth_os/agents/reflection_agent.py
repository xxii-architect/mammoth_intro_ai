"""
Mammoth OS — ReflectionAgent
Generates structured learning reflections, mindset prompts, and personal growth insights.
"""

from typing import Dict, Any
from datetime import datetime


class ReflectionAgent:
    """
    Produces reflective prompts and insights to reinforce learning.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "topic": "Week 1",
            "lesson_title": "Intro to AI",
            "difficulty": "easy" | "medium" | "hard"
        }
        """
        topic = payload.get("topic", "learning")
        lesson_title = payload.get("lesson_title", None)
        difficulty = payload.get("difficulty", "medium")

        prompt = self._generate_prompt(topic, lesson_title)
        insight = self._generate_insight(topic, difficulty)
        action = self._generate_action(topic)

        return {
            "agent": "reflection",
            "timestamp": datetime.utcnow().isoformat(),
            "topic": topic,
            "lesson_title": lesson_title,
            "difficulty": difficulty,
            "prompt": prompt,
            "insight": insight,
            "action": action,
        }

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _generate_prompt(self, topic: str, lesson_title: str | None) -> str:
        """
        Reflection prompt — short, introspective, actionable.
        """
        if lesson_title:
            return (
                f"Think back on '{lesson_title}'. What part of the lesson felt most "
                f"surprising or unexpectedly clear once you saw it?"
            )

        return (
            f"What is one thing about {topic} that feels less intimidating now "
            f"than it did yesterday?"
        )

    def _generate_insight(self, topic: str, difficulty: str) -> str:
        """
        Provides a mindset insight based on difficulty.
        """
        if difficulty == "easy":
            return (
                f"Early wins in {topic} matter. They build confidence and momentum. "
                f"Small victories compound faster than you expect."
            )

        if difficulty == "hard":
            return (
                f"Struggle is a signal, not a setback. Hard lessons in {topic} "
                f"are where your long-term growth actually begins."
            )

        return (
            f"Steady progress in {topic} is more important than perfect execution. "
            f"Consistency beats intensity."
        )

    def _generate_action(self, topic: str) -> str:
        """
        Gives the user a small reflective action.
        """
        return (
            f"Write one sentence that captures what {topic} taught you today. "
            f"Keep it honest, simple, and grounded."
        )
