"""
Mammoth OS — PlantTheSeedAgent
Generates foundational learning seeds tied to survival mindset and long‑game thinking.
"""

from typing import Dict, Any


class PlantTheSeedAgent:
    """
    Generates 'seed' insights for learning modules.
    Inspired by True XXII Supply's Plant the Seed brand pillar.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "topic": "AI engineering",
            "context": "Week 1",
        }
        """
        topic = payload.get("topic", "learning")
        context = payload.get("context", None)

        seed = self._generate_seed(topic)
        expansion = self._expand_seed(topic)
        action = self._generate_action(topic)

        return {
            "agent": "plant_the_seed",
            "topic": topic,
            "context": context,
            "seed": seed,
            "expansion": expansion,
            "action": action,
        }

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _generate_seed(self, topic: str) -> str:
        """
        The 'seed' is the core idea — short, punchy, memorable.
        """
        return f"Every skill in {topic} starts as a single seed: consistency."

    def _expand_seed(self, topic: str) -> str:
        """
        Expands the seed into a survival‑mindset insight.
        """
        return (
            f"In {topic}, small daily reps compound the same way survival habits do. "
            f"You don’t build mastery by waiting for perfect conditions — you build it "
            f"by planting tiny seeds every day, even when the weather isn’t ideal."
        )

    def _generate_action(self, topic: str) -> str:
        """
        Gives the user a small, actionable step.
        """
        return (
            f"Write down one tiny {topic} skill you can practice today. "
            f"Make it so small you can’t fail. That’s your seed."
        )
