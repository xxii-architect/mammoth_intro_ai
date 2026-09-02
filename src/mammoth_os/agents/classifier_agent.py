from __future__ import annotations

import re
from typing import Any, Dict, List

from .base_agent import BaseAgent


class ClassifierAgent(BaseAgent):# type: ignore
    """
    Classifies incoming requests and events into intents, routes them to
    the correct agent, and tags them with structured metadata labels.
    """

    name = "ClassifierAgent"

    _RULES = [
        ("guide", "mammoth_guide", ("guide", "sdk", "architecture", "walk me through", "tour")),
        ("coding", "coding", ("code", "debug", "refactor", "patch", "build", "test", "fix")),
        ("curriculum", "curriculum", ("curriculum", "course", "module", "syllabus", "roadmap")),
        ("tutoring", "tutor", ("lesson", "teach", "coach", "study", "practice")),
        ("community", "community_engine", ("community", "challenge", "crew", "engagement")),
        ("seed", "plant_the_seed", ("seed", "mindset", "habit", "foundation")),
        ("research", "research", ("research", "analyze", "market", "compare", "findings")),
    ]

    def __init__(self, router: Any = None):
        super().__init__(router)

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _labels_for(self, normalized: str) -> List[str]:
        lowered = normalized.lower()
        labels: List[str] = []
        if "atlas" in lowered:
            labels.append("atlas")
        if "repo" in lowered or "sdk" in lowered:
            labels.append("repo_context")
        if any(token in lowered for token in ("build", "test", "debug", "fix")):
            labels.append("execution")
        return labels

    async def classify(self, text: str) -> dict:
        normalized = self._normalize_text(text)
        lowered = normalized.lower()
        if not normalized:
            return {
                "intent": "unknown",
                "target_agent": "orchestrator_agent",
                "confidence": 0.32,
                "labels": ["needs_context"],
                "routing": {"reason": "empty request", "match_type": "none"},
                "summary": "Classification needs a concrete request before routing.",
            }

        for intent, target_agent, keywords in self._RULES:
            hits = [keyword for keyword in keywords if keyword in lowered]
            if hits:
                confidence = round(min(0.96, 0.62 + (len(hits) * 0.08)), 2)
                labels = list(dict.fromkeys([intent, *self._labels_for(normalized)]))
                return {
                    "intent": intent,
                    "target_agent": target_agent,
                    "confidence": confidence,
                    "labels": labels,
                    "routing": {"reason": f"matched keywords: {', '.join(hits[:3])}", "match_type": "keyword"},
                    "summary": f"Route to {target_agent} for {intent}-focused handling.",
                }

        return {
            "intent": "general",
            "target_agent": "orchestrator_agent",
            "confidence": 0.58,
            "labels": self._labels_for(normalized) or ["general"],
            "routing": {"reason": "fallback to orchestrator for mixed or broad requests", "match_type": "fallback"},
            "summary": "Route to the orchestrator for broader multi-step handling.",
        }

    async def route(self, classification: dict) -> str:
        """Return the target agent_id based on classification."""
        return classification.get("target_agent", "orchestrator_agent")

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            text = str(payload.get("text") or payload.get("prompt") or payload.get("message") or payload.get("topic") or "").strip()
        else:
            text = str(payload or "").strip()
        result = await self.classify(text)
        return {
            "status": "ok" if text else "needs_context",
            "agent": self.name,
            "text": text,
            "quality_flags": ["classified"] if text else ["missing_text"],
            **result,
        }

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "CLASSIFY_REQUEST":
            result = await self.classify(event.payload.get("text", ""))
            await self.emit_event("CLASSIFY_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "ClassifierAgent shutting down.")
