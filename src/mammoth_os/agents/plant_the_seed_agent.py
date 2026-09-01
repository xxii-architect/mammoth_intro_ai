"""
Mammoth OS — PlantTheSeedAgent
Generates foundational learning seeds tied to survival mindset and long-game thinking.
"""

from typing import Any, Dict, List

from .base_agent import BaseAgent


class PlantTheSeedAgent(BaseAgent):
    """
    Generates seed insights for learning modules.
    """

    name = "PlantTheSeedAgent"

    def __init__(self, router: Any = None, user_id: str | None = None):
        if isinstance(router, str) and user_id is None:
            user_id = router
            router = None
        super().__init__(router)
        self.user_id = user_id

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    def run(self, payload: Any) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "topic": "AI engineering",
            "context": "Week 1",
            "lesson_title": "Intro to model routing",
            "module_title": "Routing foundations",
            "progress_score": 0.0-1.0,
            "next_focus": "examples",
        }
        """
        if isinstance(payload, dict):
            prompt = str(payload.get("prompt") or payload.get("topic") or "").strip()
            topic = str(payload.get("topic", "learning")).strip() or "learning"
            mode = str(payload.get("mode") or payload.get("focus") or "seed").strip() or "seed"
            audience = str(payload.get("audience") or "learner").strip() or "learner"
            context = str(payload.get("context") or "").strip() or None
            lesson_title = str(payload.get("lesson_title") or "").strip() or None
            module_title = str(payload.get("module_title") or "").strip() or None
            progress_score = self._coerce_progress(payload.get("progress_score"))
            next_focus = str(payload.get("next_focus") or "").strip()
            constraints = self._normalize_list(payload.get("constraints") or payload.get("guardrails"))
            approval_contract = self._normalize_contract(payload.get("approval_contract"))
        else:
            prompt = str(payload or "").strip()
            topic = self._infer_topic(prompt)
            mode = "seed"
            audience = "learner"
            context = self._infer_context(prompt)
            lesson_title = None
            module_title = None
            progress_score = 0.5
            next_focus = self._infer_next_focus(prompt)
            constraints = []
            approval_contract = {}

        missing_context_reason = self._missing_context_reason(topic, context, lesson_title, module_title)
        if missing_context_reason:
            return {
                "agent": "plant_the_seed",
                "status": "needs_context",
                "structured_output_version": "v2",
                "approval_safe": True,
                "topic": topic,
                "mode": mode,
                "audience": audience,
                "context": context,
                "lesson_title": lesson_title,
                "module_title": module_title,
                "progress_score": progress_score,
                "constraints": constraints,
                "approval_contract": approval_contract,
                "approval_gate": {"requires_review": False, "reason": "context required", "recommended_path": "provide-real-lesson-context"},
                "seed": "",
                "expansion": "",
                "action": "Provide the real lesson, module, or topic before generating a seed.",
                "follow_up": [
                    "What lesson or module should this seed attach to?",
                    "What specific concept needs the next small rep?",
                ],
                "tags": ["needs_context"],
                "recommendations": ["Replace stand-in targets like 'unknown' with the real lesson or module name."],
                "summary": "PlantTheSeedAgent needs a real lesson, module, or topic before it can generate a grounded seed.",
                "task_card": {
                    "title": "Plant the seed: context needed",
                    "mode": mode,
                    "audience": audience,
                    "summary": "Provide the real lesson, module, or topic before generating a seed.",
                    "next_action": "Add concrete learning context.",
                    "follow_up": ["Supply lesson/module context"],
                    "tags": ["needs_context"],
                },
                "observability": {
                    "structured_output_version": "v2",
                    "topic": topic,
                    "mode": mode,
                    "audience": audience,
                    "constraint_count": len(constraints),
                    "progress_bucket": "needs_context",
                },
                "evidence": [prompt or topic, missing_context_reason],
            }

        seed = self._generate_seed(topic, context, lesson_title, module_title)
        expansion = self._expand_seed(topic, context, lesson_title, module_title, progress_score)
        action = self._generate_action(topic, lesson_title, module_title, next_focus, progress_score)
        follow_up = self._follow_up_questions(topic, lesson_title, module_title, next_focus)
        tags = self._derive_tags(topic, lesson_title, module_title, next_focus, progress_score)
        recommendations = self._build_recommendations(topic, lesson_title, module_title, next_focus, progress_score)
        task_card = {
            "title": f"Plant the seed: {lesson_title or module_title or topic}",
            "mode": mode,
            "audience": audience,
            "summary": seed,
            "next_action": action,
            "follow_up": follow_up[:2],
            "tags": tags[:4],
        }
        observability = {
            "structured_output_version": "v2",
            "topic": topic,
            "mode": mode,
            "audience": audience,
            "constraint_count": len(constraints),
            "progress_bucket": "starter" if progress_score < 0.33 else "building" if progress_score < 0.66 else "refining",
        }

        return {
            "agent": "plant_the_seed",
            "status": "ok",
            "structured_output_version": "v2",
            "approval_safe": True,
            "topic": topic,
            "mode": mode,
            "audience": audience,
            "context": context,
            "lesson_title": lesson_title,
            "module_title": module_title,
            "progress_score": progress_score,
            "constraints": constraints,
            "approval_contract": approval_contract,
            "approval_gate": {"requires_review": False, "reason": "seed content is informational", "recommended_path": "direct-delivery"},
            "seed": seed,
            "expansion": expansion,
            "action": action,
            "follow_up": follow_up,
            "tags": tags,
            "recommendations": recommendations,
            "summary": self._build_summary(topic, lesson_title, module_title, progress_score, next_focus),
            "task_card": task_card,
            "observability": observability,
            "evidence": [seed, expansion, action],
        }

    def _infer_topic(self, prompt: str) -> str:
        cleaned = str(prompt or "").strip()
        return cleaned or "learning"

    def _infer_context(self, prompt: str) -> str | None:
        lowered = str(prompt or "").lower()
        for marker in ("week ", "module ", "lesson "):
            idx = lowered.find(marker)
            if idx >= 0:
                return str(prompt[idx:]).strip() or None
        return None

    def _infer_next_focus(self, prompt: str) -> str:
        lowered = str(prompt or "").lower()
        for keyword in ("examples", "practice", "review", "debugging", "testing"):
            if keyword in lowered:
                return keyword
        return ""

    def _missing_context_reason(
        self,
        topic: str,
        context: str | None,
        lesson_title: str | None,
        module_title: str | None,
    ) -> str | None:
        anchors = [topic, context, lesson_title, module_title]
        populated = [str(anchor).strip() for anchor in anchors if str(anchor or "").strip()]
        if populated and all(self._is_standin(value) for value in populated):
            return "stand-in target provided"
        return None

    def _is_standin(self, value: str) -> bool:
        return value.strip().lower() in {"unknown", "tbd", "n/a", "none"}

    def _coerce_progress(self, value: Any) -> float:
        try:
            progress = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, progress))

    def _normalize_list(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        items: List[str] = []
        for entry in value:
            text = str(entry or "").strip()
            if text:
                items.append(text)
        return list(dict.fromkeys(items))

    def _normalize_contract(self, value: Any) -> Dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return dict(value)
        return {"value": str(value)}

    def _generate_seed(
        self,
        topic: str,
        context: str | None,
        lesson_title: str | None,
        module_title: str | None,
    ) -> str:
        anchor = lesson_title or module_title or context or topic
        return f"Every step in {anchor} starts as a small seed: consistency."

    def _expand_seed(
        self,
        topic: str,
        context: str | None,
        lesson_title: str | None,
        module_title: str | None,
        progress_score: float,
    ) -> str:
        anchor = lesson_title or module_title or context or topic
        if progress_score < 0.5:
            return (
                f"{anchor} is still in the early growth stage. Keep the work tiny, visible, and repeatable so "
                f"the next rep compounds instead of overwhelming the learner."
            )
        return (
            f"In {anchor}, small daily reps compound the same way survival habits do. "
            f"You build mastery by planting tiny seeds every day, even when the weather is not ideal."
        )

    def _generate_action(
        self,
        topic: str,
        lesson_title: str | None,
        module_title: str | None,
        next_focus: str,
        progress_score: float,
    ) -> str:
        anchor = lesson_title or module_title or topic
        if next_focus:
            return f"Practice one {next_focus} step in {anchor} and keep it small enough to finish in five minutes."
        if progress_score < 0.5:
            return f"Rewrite the core {anchor} idea in one sentence and add one concrete example."
        return f"Write down one tiny {topic} skill you can practice today and make it hard to fail."

    def _follow_up_questions(
        self,
        topic: str,
        lesson_title: str | None,
        module_title: str | None,
        next_focus: str,
    ) -> List[str]:
        anchor = lesson_title or module_title or topic
        questions = [
            f"What is the smallest version of {anchor} that still proves the lesson works?",
            f"Which part of {topic} should be easier after one more rep?",
        ]
        if next_focus:
            questions.append(f"What would make the next {next_focus} step feel obvious instead of vague?")
        return questions[:3]

    def _derive_tags(
        self,
        topic: str,
        lesson_title: str | None,
        module_title: str | None,
        next_focus: str,
        progress_score: float,
    ) -> List[str]:
        tags = [topic.lower().replace(" ", "_")]
        if lesson_title:
            tags.append(lesson_title.lower().replace(" ", "_"))
        if module_title:
            tags.append(module_title.lower().replace(" ", "_"))
        if next_focus:
            tags.append(next_focus.lower().replace(" ", "_"))
        if progress_score < 0.5:
            tags.append("needs_foundation")
        return list(dict.fromkeys(tags))

    def _build_recommendations(
        self,
        topic: str,
        lesson_title: str | None,
        module_title: str | None,
        next_focus: str,
        progress_score: float,
    ) -> List[str]:
        anchor = lesson_title or module_title or topic
        recommendations = [
            f"Anchor the next step to {anchor}.",
            "Keep the scope small enough to verify immediately.",
        ]
        if next_focus:
            recommendations.append(f"Turn {next_focus} into one concrete practice step.")
        if progress_score < 0.5:
            recommendations.append("Use one example, one explanation, and one check for understanding.")
        return recommendations[:4]

    def _build_summary(
        self,
        topic: str,
        lesson_title: str | None,
        module_title: str | None,
        progress_score: float,
        next_focus: str,
    ) -> str:
        anchor = lesson_title or module_title or topic
        if progress_score < 0.5:
            return f"{anchor} needs a smaller, repeatable rep before the learner moves on."
        if next_focus:
            return f"{anchor} is ready for a focused next step around {next_focus}."
        return f"{anchor} is stable enough to keep compounding with one small daily rep."

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event.event_type == "PLANT_SEED_REQUEST":
            result = self.run(event.payload)
            await self.emit_event("PLANT_SEED_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "PlantTheSeedAgent shutting down.")
