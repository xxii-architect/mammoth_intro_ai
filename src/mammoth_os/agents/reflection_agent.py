"""
Mammoth OS — ReflectionAgent
Generates structured learning reflections, mindset prompts, and personal growth insights.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
import logging

from .base_agent import BaseAgent
from mammoth_os.analysis_contract import run_analysis_sync, validate_analysis

logger = logging.getLogger("mammoth.agents.reflection")

REFLECTION_SYSTEM = """Analyze the learner's or user's actual situation with care and specificity.
Offer a considered interpretation, not a motivational speech or a diagnosis.

Rules:
- Separate the supplied observations from your interpretation and acknowledge missing information.
- Do not invent progress, struggle, emotions, lessons learned, or personal history.
- insight: a specific observation, a plausible alternative explanation, and what would distinguish them.
- action: one concrete, proportionate next step or small experiment based on this situation.
- prompt_question: one question that tests an assumption in this exact situation.
- No slogans, canned praise, brand persona, or 'consistency beats intensity' filler.
- No external sources were retrieved. Do not invent citations or claim factual verification.
- Explore analogies or speculative interpretations when useful, labeled as hypotheses,
  not facts about the user. An unpublished idea is not automatically a bad idea.
- Return concise public rationale, never private chain-of-thought.

Respond in this exact JSON only — no text outside the JSON:
{
  "prompt_question": "A question specific to the supplied situation",
  "insight": "A grounded interpretation with its uncertainty and a competing explanation",
  "action": "One concrete next step that can be checked"
}"""

class ReflectionAgent(BaseAgent):
    """
    Produces reflective prompts and insights to reinforce learning.
    """

    def __init__(self, user_id: str | None = None, router=None):
        super().__init__(router)
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

        free_text = str(payload.get("prompt") or "").strip()
        if free_text:
            topic = free_text

        generated = False
        trace = ""
        has_input = bool(payload.get("prompt") or payload.get("topic") or lesson_title or signals)
        try:
            if not has_input:
                raise ValueError("Reflection requires a situation")
            llm_out = self._run_async(self._llm_analyze(topic, lesson_title, difficulty, progress_score, signals))
            prompt = llm_out["prompt_question"]
            insight = llm_out["insight"]
            action = llm_out["action"]
            trace = llm_out["trace"]
            generated = True
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            logger.warning("Reflection generation failed (%s)", type(exc).__name__)
            prompt  = self._generate_prompt(topic, lesson_title, signals)
            insight = ""
            action  = self._generate_action(topic, difficulty, signals)
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
                "summary": "Routing hints (may include defaults, not measured performance): "
                + self._signal_summary(difficulty, progress_score, signals),
                "url": "",
                "publisher": "mammoth_runtime",
                "source_type": "derived",
                "accessed_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        citations, references = self._build_citation_bundle(sources)
        source_coverage = self._build_source_coverage(sources)

        reflection_summary = (
            f"{insight}\n\n**Question:** {prompt}\n\n**Next step:** {action}"
            if generated else
            "Reflection could not be generated. Any exercise below is a rule-based prompt, not an analyzed insight."
            if has_input else "Describe a situation or lesson you want to reflect on."
        )
        return {
            "agent": "reflection",
            "status": "ok" if generated else "failed" if has_input else "needs_context",
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
            "recommendations": [action] if generated else self._build_recommendations(topic, difficulty, progress_score, signals),
            "sources": sources,
            "citations": citations,
            "references": references,
            "source_coverage": source_coverage,
            "quality_flags": ["interpretation_not_fact_verified"] + ([] if generated else ["analysis_generation_failed"]),
            "quality": {
                "ready": generated,
                "evidence_status": "interpretation",
                "fact_verification": "not_performed",
                "issues": [] if generated else ["analysis_generation_failed"],
            },
            "generation_mode": "model" if generated else "unavailable",
            "trace": trace,
            "confidence": None,
            "summary": reflection_summary,           # standard contract key
            "reflection_summary": reflection_summary, # preserved for back-compat
        }

    async def _llm_analyze(
        self,
        topic: str,
        lesson_title,
        difficulty: str,
        progress_score: float,
        signals: List[str],
    ) -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client
        from mammoth_os.llm_completion import complete
        client = get_llm_client()
        signal_str = ", ".join(signals) if signals else "none"
        user_message = (
            f"Situation: {topic}\n"
            f"Lesson/module: {lesson_title or 'not specified'}\n"
            "Difficulty/progress defaults are routing hints, not observed learner performance.\n"
            f"Struggle signals: {signal_str}\n"
            f"Analyze this situation and return the JSON reflection."
        )
        completion = await complete(
            client,
            user_message,
            system_prompt=REFLECTION_SYSTEM,
            max_tokens=1500,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        if completion.finish_reason not in {"", "stop"}:
            raise ValueError("Reflection completion was not complete")
        return validate_analysis(completion.text, text_fields=("prompt_question", "insight", "action"))

    @staticmethod
    def _run_async(coro):
        return run_analysis_sync(coro)


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
                    "why_it_matters": "User input or derived routing signals; not independent factual support.",
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
        linked_claims = 0
        return {
            "source_count": len(sources),
            "external_source_count": 0,
            "evidence_status": "interpretation",
            "citation_coverage": round(linked_claims / claim_count, 2) if claim_count else 0.0,
            "fully_supported_claims": linked_claims,
            "total_claims": claim_count,
        }

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
            if "example" in tag_text:
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
        focus = lesson_title or topic
        signal_question = f" What example would clarify {', '.join(signals)}?" if signals else ""
        return f"What did you observe in {focus}, and what are you only assuming?{signal_question}"

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
