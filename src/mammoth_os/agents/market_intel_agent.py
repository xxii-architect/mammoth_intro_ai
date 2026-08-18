"""
Mammoth OS — MarketIntelAgent
Generates structured market intelligence briefings with source-aware signals.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


class MarketIntelAgent:
    """
    Produces structured market intelligence briefings.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "topic": "AI engineering",
            "focus": "job market" | "tools" | "trends",
            "depth": "quick" | "full",
            "sources": [{"label": "...", "summary": "..."}],
        }
        """
        topic = str(payload.get("topic", "technology")).strip() or "technology"
        focus = str(payload.get("focus", "trends")).strip() or "trends"
        depth = str(payload.get("depth", "quick")).strip() or "quick"
        sources = self._normalize_sources(payload.get("sources") or payload.get("evidence"))

        summary = self._generate_summary(topic, focus, depth, sources)
        signals = self._generate_signals(topic, focus, sources)
        confidence = self._estimate_confidence(topic, focus, depth, sources, signals)
        action = self._generate_action(topic, focus, depth, signals)

        return {
            "agent": "market_intel",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "focus": focus,
            "depth": depth,
            "summary": summary,
            "signals": signals,
            "signal_confidence": confidence,
            "action": action,
            "sources": sources,
            "opportunities": self._build_opportunities(topic, focus, signals),
            "risks": self._build_risks(topic, focus, signals),
            "next_actions": self._build_next_actions(topic, focus, depth, confidence),
        }

    def _normalize_sources(self, sources: Any) -> List[Dict[str, str]]:
        if not sources:
            return [
                {
                    "label": "Direct prompt",
                    "summary": "No external source data supplied; using prompt-driven synthesis.",
                }
            ]

        normalized: List[Dict[str, str]] = []
        for source in sources if isinstance(sources, list) else [sources]:
            if isinstance(source, dict):
                label = str(source.get("label") or source.get("name") or "Source").strip()
                summary = str(source.get("summary") or source.get("quote") or source.get("value") or "").strip()
                if not summary:
                    continue
                normalized.append({"label": label or "Source", "summary": summary[:240]})
            else:
                summary = str(source).strip()
                if summary:
                    normalized.append({"label": "Source", "summary": summary[:240]})

        return normalized or [
            {
                "label": "Direct prompt",
                "summary": "No external source data supplied; using prompt-driven synthesis.",
            }
        ]

    def _generate_summary(self, topic: str, focus: str, depth: str, sources: List[Dict[str, str]]) -> str:
        source_hint = f"using {len(sources)} source(s)" if sources else "with no external sources"
        if topic.lower() == "ai engineering":
            if focus == "job market":
                return (
                    f"AI engineering hiring keeps moving toward systems integration, model orchestration, and "
                    f"product-minded delivery {source_hint}."
                )
            if focus == "tools":
                return (
                    f"Tooling is consolidating around orchestration, retrieval, and deployment layers {source_hint}."
                )
            return (
                f"AI engineering is stabilizing into a production discipline centered on reliability, "
                f"evaluation, and deployment {source_hint}."
            )

        if topic.lower() == "software engineering":
            return (
                f"Software engineering remains focused on AI-assisted delivery, cloud-native execution, and "
                f"practical production skills {source_hint}."
            )

        if depth == "full":
            return (
                f"{topic} shows a mix of stable demand and selective growth, with the strongest value in "
                f"repeatable execution, measurable outcomes, and clear differentiation {source_hint}."
            )

        return (
            f"{topic} shows steady movement toward practical skills, adaptability, and deployment readiness {source_hint}."
        )

    def _generate_signals(self, topic: str, focus: str, sources: List[Dict[str, str]]) -> Dict[str, Any]:
        topic_lower = topic.lower()
        base = {
            "topic": topic,
            "focus": focus,
            "trend_strength": "medium",
            "source_count": len(sources),
            "source_quality": "mixed" if len(sources) > 1 else "single",
        }

        if topic_lower == "ai engineering":
            base.update(
                {
                    "skill_shift": "multi-agent systems > standalone models",
                    "tooling": "orchestration layers, retrieval, and deployment pipelines",
                    "demand": "high for practical builders",
                    "trend": "production reliability and evaluation discipline",
                }
            )
        elif topic_lower == "software engineering":
            base.update(
                {
                    "skill_shift": "AI-assisted coding becoming standard",
                    "tooling": "cloud-native stacks + automation",
                    "demand": "strong for full-stack generalists",
                    "trend": "copilots integrated into workflows",
                }
            )
        else:
            base.update(
                {
                    "skill_shift": "practical execution valued over theory",
                    "tooling": "stable ecosystems and repeatable delivery",
                    "demand": "steady",
                    "trend": "incremental innovation",
                }
            )

        return base

    def _estimate_confidence(
        self,
        topic: str,
        focus: str,
        depth: str,
        sources: List[Dict[str, str]],
        signals: Dict[str, Any],
    ) -> float:
        confidence = 0.62
        confidence += min(0.16, len(sources) * 0.04)
        if depth == "full":
            confidence += 0.05
        if focus in {"job market", "tools"}:
            confidence += 0.03
        if signals.get("trend_strength") == "medium":
            confidence += 0.04
        if topic.lower() in {"ai engineering", "software engineering"}:
            confidence += 0.05
        return round(min(0.95, confidence), 2)

    def _generate_action(self, topic: str, focus: str, depth: str, signals: Dict[str, Any]) -> str:
        if topic.lower() == "ai engineering":
            if focus == "job market":
                return "Build one small multi-agent workflow and document the result as evidence."
            if focus == "tools":
                return "Compare two orchestration stacks and note which integration surface is easiest to ship."
            return "Document one deployed AI system and extract the repeatable pattern it uses."

        if topic.lower() == "software engineering":
            return "Refactor one small project using AI-assisted tooling and capture the workflow."

        if depth == "full":
            return f"Turn the strongest signal in {topic} into one concrete validation step."
        return f"Identify one practical skill in {topic} you can apply immediately."

    def _build_opportunities(self, topic: str, focus: str, signals: Dict[str, Any]) -> List[str]:
        opportunities = [
            f"Leverage the strongest {focus} signal to prioritize the next experiment.",
            "Translate the trend into a measurable workflow or artifact.",
        ]
        if signals.get("skill_shift"):
            opportunities.append(f"Build around the shift toward {signals['skill_shift']}.")
        if topic.lower() == "ai engineering":
            opportunities.append("Pair model integration with a deployment or evaluation loop.")
        return opportunities[:4]

    def _build_risks(self, topic: str, focus: str, signals: Dict[str, Any]) -> List[str]:
        risks = [
            "Assuming the trend is broader than the evidence supports.",
            "Overweighting hype without a repeatable validation path.",
        ]
        if focus == "job market":
            risks.append("Treating role titles as a proxy for actual daily work.")
        if signals.get("source_quality") == "single":
            risks.append("Single-source conclusions are more fragile.")
        return risks[:4]

    def _build_next_actions(self, topic: str, focus: str, depth: str, confidence: float) -> List[str]:
        actions = [
            "Validate the signal against one additional source or data point.",
            "Write one sentence about the practical implication for your workflow.",
        ]
        if depth == "full":
            actions.append("Capture a small evidence table with sources, signal strength, and caveats.")
        if confidence < 0.75:
            actions.append("Keep the conclusion tentative until the next verification pass.")
        return actions[:4]
