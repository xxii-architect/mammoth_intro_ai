from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class ReasoningAgent(BaseAgent):  # type: ignore
    """Reasoning layer for tutor hints, Socratic probes, and micro-lessons."""

    name = "ReasoningAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._engine_endpoint: Optional[str] = None

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def initialize(self) -> None:
        if hasattr(self, "get_config"):
            self._engine_endpoint = self.get_config("reasoning_engine_endpoint")

    def _normalize_payload(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            problem = payload.get("problem") or payload.get("prompt") or payload.get("topic") or ""
            context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            mode = payload.get("mode") or "default"
            return {"problem": str(problem), "context": context, "mode": str(mode)}
        if payload is None:
            return {"problem": "", "context": {}, "mode": "default"}
        return {"problem": str(payload), "context": {}, "mode": "default"}

    def _normalize_problem(self, problem: str) -> str:
        return re.sub(r"\s+", " ", str(problem or "")).strip()

    def _extract_error_pattern(self, context: Dict[str, Any]) -> str:
        tutor_result = context.get("tutor_result") if isinstance(context, dict) else None
        tutor_result = tutor_result if isinstance(tutor_result, dict) else {}
        adaptive = tutor_result.get("adaptive_signals") if isinstance(tutor_result.get("adaptive_signals"), dict) else {}
        fingerprint = str(adaptive.get("error_fingerprint") or "").strip().lower()
        if fingerprint:
            return fingerprint
        text = f"{tutor_result.get('message', '')} {tutor_result.get('error', '')}".lower()
        if "syntaxerror" in text:
            return "syntax_error"
        if "indentationerror" in text:
            return "indentation_error"
        if "assert" in text:
            return "assertion_error"
        if "importerror" in text or "modulenotfounderror" in text:
            return "import_error"
        if "typeerror" in text:
            return "type_error"
        if "nameerror" in text:
            return "name_error"
        if context.get("mode") == "coach":
            return "coaching_request"
        return "unknown"

    def decompose(self, problem: str) -> List[str]:
        normalized = self._normalize_problem(problem)
        if not normalized:
            return ["Clarify the learner's obstacle."]
        lowered = normalized.lower()
        if any(token in lowered for token in ["error", "failed", "failure", "exception", "assert", "syntax", "import"]):
            return [
                "Identify the failure pattern.",
                "Name the likely misconception.",
                "Select one safe next step.",
            ]
        return [
            "Restate the learner goal.",
            "Highlight one missing concept.",
            "Ask one guiding question.",
        ]

    def _infer(self, prompt: str, context: Dict[str, Any]) -> str:
        pattern = self._extract_error_pattern(context)
        lowered = self._normalize_problem(prompt).lower()
        if "failure pattern" in lowered:
            return f"Failure pattern detected: {pattern}. Focus only on this pattern during the next retry."
        if "misconception" in lowered or "missing concept" in lowered:
            if pattern in {"syntax_error", "indentation_error"}:
                return "The learner likely needs structure-first thinking. Rebuild the code skeleton before filling logic."
            if pattern == "assertion_error":
                return "The learner likely misread expected behavior. Revisit the expected output and one boundary case."
            return "The learner likely needs one prerequisite concept reinforced with a short example."
        if "guiding question" in lowered or "safe next step" in lowered:
            return "What is the smallest change you can test right now to confirm your assumption?"
        return "Keep the guidance short, testable, and focused on one behavior."

    def _socratic_questions(self, pattern: str, problem: str) -> List[str]:
        if pattern == "syntax_error":
            return [
                "Which line first breaks Python parsing, and what delimiter is missing?",
                "Can you run only that function after fixing indentation and syntax shape?",
            ]
        if pattern == "assertion_error":
            return [
                "What output does the test expect versus what your function returns now?",
                "Which edge case could explain that mismatch?",
            ]
        if pattern == "import_error":
            return [
                "Is the module path correct from the test runner's working directory?",
                "What is the smallest import statement that succeeds in isolation?",
            ]
        if pattern == "coaching_request":
            return [
                f"What is the first concrete checkpoint for: {problem[:90]}?",
                "How will you verify progress in under five minutes?",
            ]
        return [
            "What changed right before the failure appeared?",
            "What tiny experiment can confirm your next assumption?",
        ]

    def _micro_lesson(self, pattern: str) -> str:
        if pattern in {"syntax_error", "indentation_error"}:
            return "Micro-lesson: write a minimal passing structure first, then add one logic branch at a time."
        if pattern == "assertion_error":
            return "Micro-lesson: translate each failing assertion into plain language before changing implementation."
        if pattern in {"import_error", "name_error"}:
            return "Micro-lesson: confirm symbol/module visibility with a tiny isolated snippet before full test runs."
        if pattern == "type_error":
            return "Micro-lesson: annotate expected types, then print/inspect runtime values at the failing boundary."
        return "Micro-lesson: isolate one failing behavior and verify it with a single targeted check."

    def _estimate_confidence(self, steps: List[str], pattern: str) -> float:
        base = 0.68 if pattern == "unknown" else 0.75
        return round(min(0.98, base + (len(steps) * 0.06)), 2)

    def reason(self, problem: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload_context = dict(context or {})
        pattern = self._extract_error_pattern(payload_context)
        payload_context["error_pattern"] = pattern
        sub_problems = self.decompose(problem)
        steps = [self._infer(sub_problem, payload_context) for sub_problem in sub_problems]
        answer = " ".join(step for step in steps if step)
        return {
            "answer": answer,
            "steps": steps,
            "confidence": self._estimate_confidence(steps, pattern),
            "sub_problems": sub_problems,
            "error_pattern": pattern,
            "socratic_questions": self._socratic_questions(pattern, self._normalize_problem(problem)),
            "micro_lesson": self._micro_lesson(pattern),
        }

    def run(self, payload: Any) -> Dict[str, Any]:
        normalized = self._normalize_payload(payload)
        reasoning = self.reason(normalized["problem"], normalized.get("context", {}))
        return {
            "status": "ok",
            "agent": self.name,
            "mode": normalized.get("mode", "default"),
            "reasoning": reasoning,
            "prompt": normalized.get("problem", ""),
        }

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event.event_type == "REASONING_REQUEST":
            result = self.reason(event.payload["problem"], event.payload.get("context"))
            await self.emit_event("REASONING_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "ReasoningAgent shutting down.")