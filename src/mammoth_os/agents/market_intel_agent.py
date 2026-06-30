"""
Mammoth OS — MarketIntelAgent
Generates strategic industry insights, trend summaries, and actionable intel
for AI engineering, software development, and technology markets.
"""

from typing import Dict, Any
from datetime import datetime


class MarketIntelAgent:
    """
    Produces structured market intelligence briefings.
    Designed for Mammoth OS weekly intel drops.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "topic": "AI engineering",
            "focus": "job market" | "tools" | "trends",
            "depth": "quick" | "full"
        }
        """
        topic = payload.get("topic", "technology")
        focus = payload.get("focus", "trends")
        depth = payload.get("depth", "quick")

        summary = self._generate_summary(topic, focus)
        signals = self._generate_signals(topic)
        action = self._generate_action(topic, focus)

        return {
            "agent": "market_intel",
            "timestamp": datetime.utcnow().isoformat(),
            "topic": topic,
            "focus": focus,
            "depth": depth,
            "summary": summary,
            "signals": signals,
            "action": action,
        }

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _generate_summary(self, topic: str, focus: str) -> str:
        """
        High-level briefing summary.
        """
        if topic.lower() == "ai engineering":
            if focus == "job market":
                return (
                    "AI engineering roles continue shifting toward multi-agent systems, "
                    "model integration, and applied ML. Companies prioritize engineers "
                    "who can build real products, not just model demos."
                )
            if focus == "tools":
                return (
                    "Tooling is consolidating around agent frameworks, vector databases, "
                    "Supabase backends, and orchestration layers. Practical integration "
                    "skills are outperforming pure research."
                )
            return (
                "AI engineering is stabilizing into a mature discipline focused on "
                "production reliability, agent autonomy, and real-world deployment."
            )

        if topic.lower() == "software engineering":
            return (
                "Software engineering continues trending toward AI-assisted development, "
                "full-stack autonomy, and cloud-native workflows. Practical builders "
                "remain in high demand."
            )

        return (
            f"The {topic} landscape shows steady movement with emphasis on practical "
            f"skills, adaptability, and real-world deployment."
        )

    def _generate_signals(self, topic: str) -> Dict[str, str]:
        """
        Key market signals — short, punchy indicators.
        """
        if topic.lower() == "ai engineering":
            return {
                "skill_shift": "Multi-agent systems > standalone models",
                "tooling": "Supabase + Python + orchestration layers",
                "demand": "High for practical builders",
                "trend": "Agent autonomy + production reliability",
            }

        if topic.lower() == "software engineering":
            return {
                "skill_shift": "AI-assisted coding becoming standard",
                "tooling": "Cloud-native stacks + automation",
                "demand": "Strong for full-stack generalists",
                "trend": "AI copilots integrated into workflows",
            }

        return {
            "skill_shift": "Practical experience valued over theory",
            "tooling": "Consolidation around stable ecosystems",
            "demand": "Steady",
            "trend": "Incremental innovation",
        }

    def _generate_action(self, topic: str, focus: str) -> str:
        """
        Actionable next step — something the user can do today.
        """
        if topic.lower() == "ai engineering":
            if focus == "job market":
                return (
                    "Build one small multi-agent workflow this week. "
                    "Practical demos outperform resumes."
                )
            if focus == "tools":
                return (
                    "Integrate a Supabase backend with a Python agent. "
                    "This is becoming a standard production pattern."
                )
            return (
                "Document one real-world AI system you use daily. "
                "Understanding deployed systems builds intuition."
            )

        if topic.lower() == "software engineering":
            return (
                "Refactor one small project using AI-assisted tooling. "
                "Modern workflows expect hybrid development."
            )

        return (
            f"Identify one practical skill in {topic} you can apply immediately. "
            f"Execution beats theory."
        )
