"""
Mammoth OS — CommunityEngineAgent
Generates community challenges, shared missions, group prompts, and
leaderboard-driven engagement tasks for Mammoth OS and True XXII Supply.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


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
            "group_size": 1 | 5 | 20 | "open",
            "team_context": "crew alpha",
            "learner_context": "Week 3",
            "engagement_goal": "share progress",
        }
        """
        theme = str(payload.get("theme", "mindset")).strip() or "mindset"
        difficulty = str(payload.get("difficulty", "easy")).strip() or "easy"
        group_size = payload.get("group_size", "open")
        team_context = str(payload.get("team_context") or "").strip() or None
        learner_context = str(payload.get("learner_context") or "").strip() or None
        engagement_goal = str(payload.get("engagement_goal") or "").strip() or None
        learner_signals = self._normalize_list(payload.get("learner_signals") or payload.get("signals"))

        challenge = self._generate_challenge(theme, difficulty, team_context, learner_context, engagement_goal)
        prompt = self._generate_prompt(theme, team_context, learner_context)
        reward = self._generate_reward(difficulty, group_size, learner_signals)
        social = self._generate_social_callout(group_size, team_context)

        return {
            "agent": "community_engine",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "theme": theme,
            "difficulty": difficulty,
            "group_size": group_size,
            "team_context": team_context,
            "learner_context": learner_context,
            "engagement_goal": engagement_goal,
            "challenge": challenge,
            "prompt": prompt,
            "reward": reward,
            "social_callout": social,
            "engagement_checkpoints": self._build_checkpoints(theme, difficulty, group_size, engagement_goal),
            "context_summary": self._build_context_summary(theme, difficulty, team_context, learner_context, learner_signals),
            "next_actions": self._build_next_actions(theme, difficulty, group_size, learner_signals),
            "tags": self._build_tags(theme, difficulty, team_context, learner_context, learner_signals),
            "signal_confidence": self._estimate_confidence(theme, difficulty, learner_signals),
        }

    def _normalize_list(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        result: List[str] = []
        for entry in value:
            text = str(entry or "").strip()
            if text:
                result.append(text)
        return list(dict.fromkeys(result))

    def _generate_challenge(
        self,
        theme: str,
        difficulty: str,
        team_context: str | None,
        learner_context: str | None,
        engagement_goal: str | None,
    ) -> str:
        base = f"A {difficulty} community challenge focused on {theme}."
        context_bits = [bit for bit in [team_context, learner_context, engagement_goal] if bit]
        context_line = f" Context: {' | '.join(context_bits)}." if context_bits else ""

        if theme == "fieldcraft":
            return (
                f"{base} Everyone completes a small outdoor task today — identify a plant, track an animal sign, "
                f"or note a terrain feature.{context_line}"
            )

        if theme == "wildlife":
            return (
                f"{base} Each person documents one wildlife sighting or sign. Share photos, sketches, or notes."
                f"{context_line}"
            )

        if theme == "ai_learning":
            return (
                f"{base} Everyone builds one tiny AI workflow or solves one small coding problem. "
                f"Share your result with the group.{context_line}"
            )

        return (
            f"{base} Reflect on one thing you learned today and post a short sentence about it. "
            f"Keep it honest and grounded.{context_line}"
        )

    def _generate_prompt(self, theme: str, team_context: str | None, learner_context: str | None) -> str:
        context = team_context or learner_context
        if theme == "fieldcraft":
            return f"What outdoor skill made you more capable today{f' in {context}' if context else ''}?"
        if theme == "wildlife":
            return f"What animal signs did you notice today that you normally overlook{f' in {context}' if context else ''}?"
        if theme == "ai_learning":
            return f"What part of today’s AI lesson clicked for you in a new way{f' in {context}' if context else ''}?"
        return f"What’s one thing you learned today that surprised you{f' in {context}' if context else ''}?"

    def _generate_reward(self, difficulty: str, group_size: Any, learner_signals: List[str]) -> Dict[str, Any]:
        base_xp = {"hard": 40, "medium": 25}.get(difficulty, 10)
        group_bonus = 5 if group_size == "open" else 10 if isinstance(group_size, int) and group_size > 5 else 3
        signal_bonus = min(10, len(learner_signals) * 2)
        return {
            "xp_bonus": base_xp + group_bonus + signal_bonus,
            "streak_bonus": 2 if difficulty == "hard" else 1 if difficulty == "medium" else 0,
            "group_bonus": group_bonus,
        }

    def _generate_social_callout(self, group_size: Any, team_context: str | None) -> str:
        context = f" for {team_context}" if team_context else ""
        if group_size == "open":
            return f"Open challenge{context} — anyone can join. Share your progress and hype each other up."
        if isinstance(group_size, int) and group_size <= 5:
            return f"Small crew challenge{context} — keep each other accountable and share your wins."
        if isinstance(group_size, int) and group_size > 5:
            return f"Group challenge for {group_size} people{context} — post updates and celebrate progress together."
        return f"Community challenge{context} — share your results with the Mammoth Crew."

    def _build_checkpoints(self, theme: str, difficulty: str, group_size: Any, engagement_goal: str | None) -> List[str]:
        checkpoints = [
            f"Post one update that matches the {theme} challenge.",
            "React to at least one other member's progress.",
            "Capture one lesson learned before closing the loop.",
        ]
        if engagement_goal:
            checkpoints.insert(1, f"Make sure the post moves the engagement goal forward: {engagement_goal}.")
        if difficulty == "hard" or (isinstance(group_size, int) and group_size > 5):
            checkpoints.append("Include one measurable result or artifact.")
        return checkpoints[:4]

    def _build_context_summary(
        self,
        theme: str,
        difficulty: str,
        team_context: str | None,
        learner_context: str | None,
        learner_signals: List[str],
    ) -> str:
        context_bits = [bit for bit in [team_context, learner_context] if bit]
        context_text = " / ".join(context_bits) if context_bits else "no extra context"
        signal_text = f" signals: {', '.join(learner_signals)}" if learner_signals else ""
        return f"{theme} / {difficulty} / {context_text}{signal_text}"

    def _build_next_actions(
        self,
        theme: str,
        difficulty: str,
        group_size: Any,
        learner_signals: List[str],
    ) -> List[str]:
        actions = [
            "Publish the challenge in the active community channel.",
            "Set a measurable engagement checkpoint before the next review.",
        ]
        if "needs_examples" in learner_signals:
            actions.append("Add one example post so members know what good looks like.")
        if difficulty == "hard":
            actions.append("Keep the ask short so the group can respond quickly.")
        if isinstance(group_size, int) and group_size > 5:
            actions.append("Assign one person to summarize the best responses.")
        return actions[:4]

    def _build_tags(
        self,
        theme: str,
        difficulty: str,
        team_context: str | None,
        learner_context: str | None,
        learner_signals: List[str],
    ) -> List[str]:
        tags = [theme, difficulty]
        if team_context:
            tags.append(team_context.replace(" ", "_"))
        if learner_context:
            tags.append(learner_context.replace(" ", "_"))
        tags.extend(learner_signals)
        return list(dict.fromkeys(tag.lower().replace(" ", "_") for tag in tags if tag))

    def _estimate_confidence(self, theme: str, difficulty: str, learner_signals: List[str]) -> float:
        confidence = 0.65
        if theme in {"fieldcraft", "ai_learning", "wildlife"}:
            confidence += 0.05
        if difficulty == "easy":
            confidence += 0.04
        elif difficulty == "hard":
            confidence -= 0.03
        confidence -= min(0.08, len(learner_signals) * 0.02)
        return round(max(0.45, min(0.95, confidence)), 2)
