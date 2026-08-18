"""
Mammoth OS — PlantTheSeedAgent
Generates foundational learning seeds tied to survival mindset and long-game thinking.
"""

from typing import Any, Dict, List


class PlantTheSeedAgent:
    """
    Generates seed insights for learning modules.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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
        topic = str(payload.get("topic", "learning")).strip() or "learning"
        context = str(payload.get("context") or "").strip() or None
        lesson_title = str(payload.get("lesson_title") or "").strip() or None
        module_title = str(payload.get("module_title") or "").strip() or None
        progress_score = self._coerce_progress(payload.get("progress_score"))
        next_focus = str(payload.get("next_focus") or "").strip()

        seed = self._generate_seed(topic, context, lesson_title, module_title)
        expansion = self._expand_seed(topic, context, lesson_title, module_title, progress_score)
        action = self._generate_action(topic, lesson_title, module_title, next_focus, progress_score)
        follow_up = self._follow_up_questions(topic, lesson_title, module_title, next_focus)
        tags = self._derive_tags(topic, lesson_title, module_title, next_focus, progress_score)

        return {
            "agent": "plant_the_seed",
            "status": "ok",
            "topic": topic,
            "context": context,
            "lesson_title": lesson_title,
            "module_title": module_title,
            "progress_score": progress_score,
            "seed": seed,
            "expansion": expansion,
            "action": action,
            "follow_up": follow_up,
            "tags": tags,
            "recommendations": self._build_recommendations(topic, lesson_title, module_title, next_focus, progress_score),
            "summary": self._build_summary(topic, lesson_title, module_title, progress_score, next_focus),
        }

    def _coerce_progress(self, value: Any) -> float:
        try:
            progress = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, progress))

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
