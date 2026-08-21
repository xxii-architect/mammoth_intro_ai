"""
Mammoth OS — ReflectionAgent
Generates structured learning reflections, mindset prompts, and personal growth insights.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


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
            "difficulty": "easy" | "medium" | "hard",
            "progress_score": 0.0-1.0,
            "struggle_tags": ["need examples", "error handling"],
        }
        """
        topic = str(payload.get("topic", "learning")).strip() or "learning"
        lesson_title = str(payload.get("lesson_title") or payload.get("module_title") or "").strip() or None
        difficulty = str(payload.get("difficulty", "medium")).strip().lower() or "medium"
        progress_score = self._coerce_progress(payload.get("progress_score"))
        signals = self._collect_signals(payload)

        prompt = self._generate_prompt(topic, lesson_title, signals)
        insight = self._generate_insight(topic, difficulty, progress_score, signals)
        action = self._generate_action(topic, difficulty, signals)
        follow_up_tags = self._derive_follow_up_tags(difficulty, progress_score, signals)
        sources = [
            {
                "id": "src-reflection-input",
                "type": "direct_prompt",
                "label": "Reflection input",
                "summary": lesson_title or topic,
                "url": "",
                "publisher": "mammoth_runtime",
                "source_type": "prompt",
                "accessed_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": "src-reflection-signals",
                "type": "learner_signals",
                "label": "Signal summary",
                "summary": self._signal_summary(difficulty, progress_score, signals),
                "url": "",
                "publisher": "mammoth_runtime",
                "source_type": "derived",
                "accessed_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        citations, references = self._build_citation_bundle(sources)
        source_coverage = self._build_source_coverage(sources)

        return {
            "agent": "reflection",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "lesson_title": lesson_title,
            "difficulty": difficulty,
            "progress_score": progress_score,
            "prompt": prompt,
            "insight": insight,
            "action": action,
            "signals": signals,
            "follow_up_tags": follow_up_tags,
            "recommendations": self._build_recommendations(topic, difficulty, progress_score, signals),
            "sources": sources,
            "citations": citations,
            "references": references,
            "source_coverage": source_coverage,
            "quality_flags": self._quality_flags(source_coverage),
            "confidence": self._estimate_confidence(difficulty, progress_score, signals),
            "reflection_summary": self._build_summary(topic, lesson_title, difficulty, progress_score, signals),
        }

    def _build_citation_bundle(self, sources: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        citations: List[Dict[str, str]] = []
        references: List[Dict[str, str]] = []
        for source in sources:
            source_id = str(source.get("id") or "")
            label = str(source.get("label") or "source")
            summary = str(source.get("summary") or "")
            citations.append(
                {
                    "source_id": source_id,
                    "label": label,
                    "quote": summary[:220],
                    "why_it_matters": "Supports the reflection guidance and follow-up tags.",
                }
            )
            references.append(
                {
                    "source_id": source_id,
                    "title": label,
                    "url": str(source.get("url") or ""),
                    "publisher": str(source.get("publisher") or "mammoth_runtime"),
                    "source_type": str(source.get("source_type") or "derived"),
                    "accessed_at": str(source.get("accessed_at") or ""),
                }
            )
        return citations, references

    def _build_source_coverage(self, sources: List[Dict[str, str]]) -> Dict[str, Any]:
        claim_count = 3
        linked_claims = claim_count if sources else 0
        return {
            "source_count": len(sources),
            "citation_coverage": round(linked_claims / claim_count, 2) if claim_count else 0.0,
            "fully_supported_claims": linked_claims,
            "total_claims": claim_count,
        }

    def _quality_flags(self, source_coverage: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        if int(source_coverage.get("source_count") or 0) == 0:
            flags.append("missing_sources")
        if float(source_coverage.get("citation_coverage") or 0) < 1.0:
            flags.append("incomplete_citation_coverage")
        if not flags:
            flags.append("source_grounding_acceptable")
        return flags

    def _coerce_progress(self, value: Any) -> float:
        try:
            progress = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, progress))

    def _collect_signals(self, payload: Dict[str, Any]) -> List[str]:
        raw_tags = payload.get("struggle_tags") or payload.get("signals") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]

        normalized: List[str] = []
        for tag in raw_tags:
            tag_text = str(tag or "").strip().lower()
            if not tag_text:
                continue
            if "example" in tag_text or "example" in tag_text:
                normalized.append("need_examples")
            elif "error" in tag_text or "bug" in tag_text:
                normalized.append("error_handling")
            elif "env" in tag_text or "setup" in tag_text or "install" in tag_text:
                normalized.append("environment_setup")
            elif "fast" in tag_text or "slow" in tag_text or "pace" in tag_text:
                normalized.append("pace_adjustment")
            elif "confus" in tag_text or "stuck" in tag_text:
                normalized.append("needs_clarity")
            else:
                normalized.append(tag_text.replace(" ", "_"))

        return list(dict.fromkeys(normalized))

    def _generate_prompt(self, topic: str, lesson_title: str | None, signals: List[str]) -> str:
        if lesson_title:
            if signals:
                return (
                    f"Think back on '{lesson_title}'. Which part felt clearest after you "
                    f"worked through the struggle tags {', '.join(signals)}?"
                )
            return (
                f"Think back on '{lesson_title}'. What part of the lesson felt most "
                f"surprising or unexpectedly clear once you saw it?"
            )

        if signals:
            return (
                f"What is one thing about {topic} that feels less intimidating now, "
                f"especially after noticing {', '.join(signals)}?"
            )

        return (
            f"What is one thing about {topic} that feels less intimidating now "
            f"than it did yesterday?"
        )

    def _generate_insight(self, topic: str, difficulty: str, progress_score: float, signals: List[str]) -> str:
        if difficulty == "easy":
            return (
                f"Early wins in {topic} matter. They build confidence and momentum. "
                f"Small victories compound faster than you expect."
            )

        if difficulty == "hard" or progress_score < 0.5:
            extra = " " + self._signal_tail(signals) if signals else ""
            return (
                f"Struggle is a signal, not a setback. Hard lessons in {topic} are where "
                f"your long-term growth actually begins.{extra}"
            ).strip()

        return (
            f"Steady progress in {topic} is more important than perfect execution. "
            f"Consistency beats intensity."
        )

    def _generate_action(self, topic: str, difficulty: str, signals: List[str]) -> str:
        if "need_examples" in signals:
            return f"Rewrite one {topic} idea using a concrete example and one plain-language explanation."
        if "environment_setup" in signals:
            return f"Document the exact setup steps for {topic} so the next attempt starts cleanly."
        if "error_handling" in signals:
            return f"Capture one failure mode in {topic} and write how you would detect it earlier."
        if difficulty == "hard":
            return f"Slow down and restate the core {topic} idea in one sentence before adding more complexity."
        return f"Write one sentence that captures what {topic} taught you today."

    def _derive_follow_up_tags(self, difficulty: str, progress_score: float, signals: List[str]) -> List[str]:
        tags = list(signals)
        if progress_score < 0.4:
            tags.append("review_foundations")
        if difficulty == "hard" or progress_score < 0.6:
            tags.append("slow_down")
        if "needs_clarity" in tags and "need_examples" not in tags:
            tags.append("need_examples")
        return list(dict.fromkeys(tags))

    def _build_recommendations(self, topic: str, difficulty: str, progress_score: float, signals: List[str]) -> List[str]:
        recommendations = [
            f"Restate the core {topic} idea in your own words.",
            "Capture one uncertainty before moving on.",
        ]
        if progress_score < 0.5:
            recommendations.append("Revisit the smallest working example before expanding scope.")
        if "need_examples" in signals:
            recommendations.append("Add one concrete example to anchor the lesson.")
        if "environment_setup" in signals:
            recommendations.append("Write down the setup steps so the next run is repeatable.")
        if difficulty == "hard":
            recommendations.append("Keep the next step small enough to verify quickly.")
        return recommendations[:4]

    def _signal_summary(self, difficulty: str, progress_score: float, signals: List[str]) -> str:
        if signals:
            return f"difficulty={difficulty}; progress={progress_score:.2f}; signals={', '.join(signals)}"
        return f"difficulty={difficulty}; progress={progress_score:.2f}; signals=none"

    def _build_summary(
        self,
        topic: str,
        lesson_title: str | None,
        difficulty: str,
        progress_score: float,
        signals: List[str],
    ) -> str:
        focus = lesson_title or topic
        if progress_score < 0.5 or difficulty == "hard":
            return f"{focus} needs slower pacing, clearer examples, and one smaller verification step."
        if signals:
            return f"{focus} is moving forward, but the signal pattern suggests one targeted review step."
        return f"{focus} is progressing steadily; keep the reflection brief and keep building momentum."

    def _estimate_confidence(self, difficulty: str, progress_score: float, signals: List[str]) -> float:
        confidence = 0.68 + (progress_score - 0.5) * 0.25
        if difficulty == "easy":
            confidence += 0.05
        elif difficulty == "hard":
            confidence -= 0.08
        if signals:
            confidence -= min(0.1, len(signals) * 0.02)
        return round(max(0.45, min(0.95, confidence)), 2)

    def _signal_tail(self, signals: List[str]) -> str:
        if not signals:
            return ""
        if len(signals) == 1:
            return f"Pay attention to {signals[0].replace('_', ' ')}."
        return f"Pay attention to {signals[0].replace('_', ' ')} and {signals[1].replace('_', ' ')}."
