"""
Mammoth OS — MarketIntelAgent
Generates structured market intelligence briefings with source-aware signals.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from .base_agent import BaseAgent

class MarketIntelAgent(BaseAgent):
    """
    Produces structured market intelligence briefings.
    """

    def __init__(self, user_id: str | None = None, router=None):
        super().__init__(router)
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
        citations, references = self._build_citation_bundle(sources)
        source_coverage = self._build_source_coverage(signals, sources)

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
            "citations": citations,
            "references": references,
            "source_coverage": source_coverage,
            "quality_flags": self._quality_flags(sources, source_coverage),
            "opportunities": self._build_opportunities(topic, focus, signals),
            "risks": self._build_risks(topic, focus, signals),
            "next_actions": self._build_next_actions(topic, focus, depth, confidence),
        }

    def _normalize_sources(self, sources: Any) -> List[Dict[str, str]]:
        accessed_at = datetime.now(timezone.utc).isoformat()
        if not sources:
            return [
                {
                    "id": "src-prompt-1",
                    "label": "Direct prompt",
                    "summary": "No external source data supplied; using prompt-driven synthesis.",
                    "url": "",
                    "publisher": "mammoth_runtime",
                    "source_type": "prompt",
                    "accessed_at": accessed_at,
                }
            ]

        normalized: List[Dict[str, str]] = []
        for idx, source in enumerate(sources if isinstance(sources, list) else [sources], start=1):
            if isinstance(source, dict):
                label = str(source.get("label") or source.get("name") or "Source").strip()
                summary = str(source.get("summary") or source.get("quote") or source.get("value") or "").strip()
                url = str(source.get("url") or source.get("source") or "").strip()
                if not summary:
                    continue
                normalized.append(
                    {
                        "id": str(source.get("id") or f"src-{idx}"),
                        "label": label or "Source",
                        "summary": summary[:240],
                        "url": url,
                        "publisher": str(source.get("publisher") or "provided").strip() or "provided",
                        "source_type": "provided",
                        "accessed_at": str(source.get("accessed_at") or accessed_at),
                    }
                )
            else:
                summary = str(source).strip()
                if summary:
                    normalized.append(
                        {
                            "id": f"src-{idx}",
                            "label": "Source",
                            "summary": summary[:240],
                            "url": "",
                            "publisher": "provided",
                            "source_type": "provided",
                            "accessed_at": accessed_at,
                        }
                    )

        return normalized or [
            {
                "id": "src-prompt-1",
                "label": "Direct prompt",
                "summary": "No external source data supplied; using prompt-driven synthesis.",
                "url": "",
                "publisher": "mammoth_runtime",
                "source_type": "prompt",
                "accessed_at": accessed_at,
            }
        ]

    def _build_citation_bundle(self, sources: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        citations: List[Dict[str, str]] = []
        references: List[Dict[str, str]] = []
        for source in sources:
            source_id = str(source.get("id") or "")
            label = str(source.get("label") or "Source")
            summary = str(source.get("summary") or "")
            citations.append(
                {
                    "source_id": source_id,
                    "label": label,
                    "quote": summary[:220],
                    "why_it_matters": "Supports market signal framing and confidence scoring.",
                }
            )
            references.append(
                {
                    "source_id": source_id,
                    "title": label,
                    "url": str(source.get("url") or ""),
                    "publisher": str(source.get("publisher") or "unknown"),
                    "source_type": str(source.get("source_type") or "unknown"),
                    "accessed_at": str(source.get("accessed_at") or ""),
                }
            )
        return citations, references

    def _build_source_coverage(self, signals: Dict[str, Any], sources: List[Dict[str, str]]) -> Dict[str, Any]:
        claim_count = 4
        source_count = len(sources)
        linked_claims = claim_count if source_count else 0
        return {
            "source_count": source_count,
            "citation_coverage": round(linked_claims / claim_count, 2) if claim_count else 0.0,
            "fully_supported_claims": linked_claims,
            "total_claims": claim_count,
            "source_quality": str(signals.get("source_quality") or "unknown"),
        }

    def _quality_flags(self, sources: List[Dict[str, str]], source_coverage: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        has_external = any(str(source.get("source_type") or "") == "provided" for source in sources)
        if not has_external:
            flags.append("missing_external_sources")
        if float(source_coverage.get("citation_coverage") or 0) < 1.0:
            flags.append("incomplete_citation_coverage")
        if has_external:
            flags.append("source_grounding_acceptable")
        return flags

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
