"""
Mammoth OS — CommunityEngineAgent
Generates community challenges, shared missions, group prompts, and
leaderboard-driven engagement tasks for Mammoth OS and True XXII Supply.
"""

from typing import Any, Dict, List


class CommunityEngineAgent:
    """
    Produces structured community engagement tasks and group challenges.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Any) -> Dict[str, Any]:
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
        if isinstance(payload, dict):
            prompt = str(payload.get("prompt") or payload.get("theme") or "").strip()
            theme = self._normalize_theme(payload.get("theme", "mindset"))
            difficulty = self._normalize_difficulty(payload.get("difficulty", "easy"))
            group_size = self._normalize_group_size(payload.get("group_size", "open"))
            mode = str(payload.get("mode") or payload.get("format") or "challenge").strip() or "challenge"
            audience = str(payload.get("audience") or "community").strip() or "community"
            team_context = str(payload.get("team_context") or "").strip() or None
            learner_context = str(payload.get("learner_context") or "").strip() or None
            engagement_goal = str(payload.get("engagement_goal") or "").strip() or None
            learner_signals = self._normalize_list(payload.get("learner_signals") or payload.get("signals"))
            constraints = self._normalize_list(payload.get("constraints") or payload.get("guardrails"))
            approval_contract = self._normalize_contract(payload.get("approval_contract"))
        else:
            prompt = str(payload or "").strip()
            theme = self._infer_theme(prompt)
            difficulty = self._infer_difficulty(prompt)
            group_size = self._infer_group_size(prompt)
            mode = "challenge"
            audience = "community"
            team_context = None
            learner_context = None
            engagement_goal = None
            learner_signals = []
            constraints = []
            approval_contract = {}

        placeholder_reason = self._placeholder_reason(theme, team_context, learner_context)
        if placeholder_reason:
            return {
                "agent": "community_engine",
                "status": "needs_context",
                "structured_output_version": "v2",
                "approval_safe": True,
                "theme": theme,
                "difficulty": difficulty,
                "group_size": group_size,
                "mode": mode,
                "audience": audience,
                "team_context": team_context,
                "learner_context": learner_context,
                "engagement_goal": engagement_goal,
                "constraints": constraints,
                "approval_contract": approval_contract,
                "approval_gate": {"requires_review": False, "reason": "context required", "recommended_path": "add-real-community-context"},
                "challenge": "",
                "prompt": "",
                "reward": {"xp_bonus": 0, "streak_bonus": 0, "group_bonus": 0},
                "social_callout": "Provide the real team, challenge theme, or learner context before publishing.",
                "engagement_checkpoints": [],
                "context_summary": "needs_context",
                "next_actions": ["Add the real challenge theme or team context before publishing."],
                "tags": ["needs_context"],
                "signal_confidence": 0.45,
                "task_card": {
                    "title": "Community task: context needed",
                    "summary": "Add the real challenge theme or team context before publishing.",
                    "prompt": "",
                    "next_actions": ["Provide grounded challenge context"],
                    "tags": ["needs_context"],
                    "mode": mode,
                    "audience": audience,
                },
                "observability": {
                    "structured_output_version": "v2",
                    "theme": theme,
                    "difficulty": difficulty,
                    "group_size": group_size,
                    "mode": mode,
                    "audience": audience,
                    "signal_count": 0,
                    "checkpoint_count": 0,
                    "signal_confidence": 0.45,
                },
                "publish_preview": {"title": "Context required", "summary": placeholder_reason, "prompt": "", "reward": {}, "social_callout": ""},
            }

        challenge = self._generate_challenge(theme, difficulty, team_context, learner_context, engagement_goal)
        prompt = self._generate_prompt(theme, team_context, learner_context)
        reward = self._generate_reward(difficulty, group_size, learner_signals)
        social = self._generate_social_callout(group_size, team_context)
        checkpoints = self._build_checkpoints(theme, difficulty, group_size, engagement_goal)
        context_summary = self._build_context_summary(theme, difficulty, team_context, learner_context, learner_signals)
        next_actions = self._build_next_actions(theme, difficulty, group_size, learner_signals)
        tags = self._build_tags(theme, difficulty, team_context, learner_context, learner_signals)
        signal_confidence = self._estimate_confidence(theme, difficulty, learner_signals)
        approval_gate = self._approval_gate(group_size, difficulty, constraints)
        delivery_plan = self._delivery_plan(group_size, team_context)

        return {
            "agent": "community_engine",
            "status": "ok",
            "structured_output_version": "v2",
            "approval_safe": True,
            "theme": theme,
            "difficulty": difficulty,
            "group_size": group_size,
            "mode": mode,
            "audience": audience,
            "team_context": team_context,
            "learner_context": learner_context,
            "engagement_goal": engagement_goal,
            "constraints": constraints,
            "approval_contract": approval_contract,
            "approval_gate": approval_gate,
            "challenge": challenge,
            "prompt": prompt,
            "reward": reward,
            "social_callout": social,
            "engagement_checkpoints": checkpoints,
            "context_summary": context_summary,
            "delivery_plan": delivery_plan,
            "next_actions": next_actions,
            "tags": tags,
            "signal_confidence": signal_confidence,
            "task_card": {
                "title": f"Community task: {theme}",
                "summary": challenge,
                "prompt": prompt,
                "next_actions": next_actions[:2],
                "tags": tags[:4],
                "mode": mode,
                "audience": audience,
            },
            "observability": {
                "structured_output_version": "v2",
                "theme": theme,
                "difficulty": difficulty,
                "group_size": group_size,
                "mode": mode,
                "audience": audience,
                "signal_count": len(learner_signals),
                "checkpoint_count": len(checkpoints),
                "signal_confidence": signal_confidence,
            },
            "publish_preview": {
                "title": f"Community challenge: {theme}",
                "summary": challenge,
                "prompt": prompt,
                "reward": reward,
                "social_callout": social,
                "delivery_path": delivery_plan["primary_channel"],
            },
        }

    def _normalize_theme(self, value: Any) -> str:
        theme = str(value or "mindset").strip().lower()
        if theme in {"fieldcraft", "mindset", "wildlife", "ai_learning"}:
            return theme
        if self._is_placeholder(theme):
            return "unknown"
        return "mindset"

    def _normalize_difficulty(self, value: Any) -> str:
        difficulty = str(value or "easy").strip().lower()
        return difficulty if difficulty in {"easy", "medium", "hard"} else "easy"

    def _normalize_group_size(self, value: Any) -> Any:
        if isinstance(value, int):
            return max(1, value)
        text = str(value or "open").strip().lower()
        if text == "open":
            return "open"
        try:
            return max(1, int(text))
        except ValueError:
            return "open"

    def _infer_theme(self, prompt: str) -> str:
        lowered = str(prompt or "").lower()
        if "wildlife" in lowered or "animal" in lowered:
            return "wildlife"
        if "ai" in lowered or "code" in lowered:
            return "ai_learning"
        if "field" in lowered or "outdoor" in lowered or "survival" in lowered:
            return "fieldcraft"
        if self._is_placeholder(lowered.strip()):
            return "unknown"
        return "mindset"

    def _infer_difficulty(self, prompt: str) -> str:
        lowered = str(prompt or "").lower()
        if "hard" in lowered:
            return "hard"
        if "medium" in lowered:
            return "medium"
        return "easy"

    def _infer_group_size(self, prompt: str) -> Any:
        lowered = str(prompt or "").lower()
        if "open" in lowered or "public" in lowered:
            return "open"
        for token in lowered.replace("-", " ").split():
            if token.isdigit():
                return max(1, int(token))
        return "open"

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

    def _normalize_contract(self, value: Any) -> Dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return dict(value)
        return {"value": str(value)}

    def _approval_gate(self, group_size: Any, difficulty: str, constraints: List[str]) -> Dict[str, Any]:
        review_reasons: List[str] = []
        if group_size == "open":
            review_reasons.append("open enrollment challenge")
        elif isinstance(group_size, int) and group_size >= 10:
            review_reasons.append("large group coordination")
        if difficulty == "hard":
            review_reasons.append("high effort ask")
        if any("publish" in entry.lower() or "external" in entry.lower() or "brand" in entry.lower() for entry in constraints):
            review_reasons.append("external publishing constraint")
        return {
            "requires_review": bool(review_reasons),
            "reason": ", ".join(review_reasons) if review_reasons else "safe to publish directly",
            "recommended_path": "agent-console-approval" if review_reasons else "direct-delivery",
        }

    def _delivery_plan(self, group_size: Any, team_context: str | None) -> Dict[str, Any]:
        if group_size == "open":
            primary_channel = "community-feed"
        elif isinstance(group_size, int) and group_size <= 5:
            primary_channel = "small-crew-thread"
        else:
            primary_channel = "team-announcement"
        return {
            "primary_channel": primary_channel,
            "team_context": team_context,
            "operator_note": "Preview the prompt and reward block before posting if the challenge is public-facing.",
        }

    def _placeholder_reason(self, theme: str, team_context: str | None, learner_context: str | None) -> str | None:
        anchors = [theme, team_context, learner_context]
        populated = [str(anchor).strip() for anchor in anchors if str(anchor or "").strip()]
        if populated and all(self._is_placeholder(value) for value in populated):
            return "placeholder target provided"
        return None

    def _is_placeholder(self, value: str) -> bool:
        return value.strip().lower() in {"unknown", "tbd", "todo", "n/a", "none", "placeholder"}

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
