from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from .reasoning_agent_v2_upgrade import (
    _extract_error_pattern_enhanced,
    _socratic_questions_enhanced,
    _micro_lesson_enhanced,
    _estimate_confidence_enhanced,
)


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
        """Extract error pattern using enhanced v2 detection logic.
        
        v2 upgrade: Supports 16 error categories instead of 8, with better
        heuristic detection for edge cases like recursion, timeout, memory.
        """
        return _extract_error_pattern_enhanced(context)

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
        """Generate Socratic questions tailored to error type.
        
        v2 upgrade: Uses enhanced error pattern detection with 16 categories
        and pattern-specific guidance for better learner alignment.
        """
        return _socratic_questions_enhanced(pattern, problem)

    def _micro_lesson(self, pattern: str) -> str:
        """Generate pattern-specific micro-lessons.
        
        v2 upgrade: Supports 16 error categories with targeted guidance
        for syntax, logic, runtime, and performance errors.
        """
        return _micro_lesson_enhanced(pattern)

    def _estimate_confidence(self, steps: List[str], pattern: str) -> float:
        """Estimate confidence using enhanced pattern clarity assessment.
        
        v2 upgrade: Takes context into account with clearer patterns having
        higher baseline confidence scores.
        """
        # Use enhanced confidence estimation with default context
        return _estimate_confidence_enhanced(pattern, has_context=bool(steps))

    def _quality_score(self, prompt: str, reasoning: Dict[str, Any]) -> float:
        """Reward clarity, specificity, and actionable guidance in reasoning output."""
        score = 0.45
        problem = self._normalize_problem(prompt)
        if problem:
            score += 0.15
        if reasoning.get("error_pattern"):
            score += 0.1
        if reasoning.get("socratic_questions"):
            score += 0.1
        if reasoning.get("micro_lesson"):
            score += 0.1
        confidence = float(reasoning.get("confidence") or 0.0)
        if confidence >= 0.7:
            score += 0.1
        if reasoning.get("steps"):
            score += 0.1
        return round(min(score, 0.99), 2)

    def _verification_checks(self, prompt: str, reasoning: Dict[str, Any]) -> List[str]:
        """Offer a compact verification loop so the model stays grounded and testable."""
        checks: List[str] = []
        if not self._normalize_problem(prompt):
            checks.append("Clarify the target behavior before troubleshooting.")
        else:
            checks.append("Confirm the smallest failing condition before changing broader logic.")
        if reasoning.get("error_pattern"):
            checks.append(f"Validate the {reasoning.get('error_pattern')} pattern against one real example.")
        if reasoning.get("socratic_questions"):
            checks.append("Answer the first Socratic question with a concrete testable hypothesis.")
        if reasoning.get("micro_lesson"):
            checks.append("Apply the micro-lesson to one boundary case before widening the fix.")
        return checks[:4]

    def reason(self, problem: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload_context = dict(context or {})
        pattern = self._extract_error_pattern(payload_context)
        payload_context["error_pattern"] = pattern
        sub_problems = self.decompose(problem)
        steps = [self._infer(sub_problem, payload_context) for sub_problem in sub_problems]
        answer = " ".join(step for step in steps if step)
        reasoning = {
            "answer": answer,
            "steps": steps,
            "confidence": self._estimate_confidence(steps, pattern),
            "sub_problems": sub_problems,
            "error_pattern": pattern,
            "socratic_questions": self._socratic_questions(pattern, self._normalize_problem(problem)),
            "micro_lesson": self._micro_lesson(pattern),
        }
        reasoning["quality_score"] = self._quality_score(problem, reasoning)
        reasoning["verification_checks"] = self._verification_checks(problem, reasoning)
        reasoning["recommended_next_step"] = (
            reasoning.get("verification_checks", ["Test the narrowest hypothesis."])[0]
            if reasoning.get("verification_checks")
            else "Test the narrowest hypothesis."
        )
        return reasoning

    def _build_reasoning_summary(self, prompt: str, reasoning: Dict[str, Any]) -> str:
        answer = str(reasoning.get("answer") or "").strip()
        if answer:
            return answer[:220] + ("..." if len(answer) > 220 else "")
        if prompt:
            return f"Reason through the problem: {prompt[:200]}"
        return "Check the narrowest failing condition before making a broader change."

    def _build_quality_flags(self, prompt: str, reasoning: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        if not self._normalize_problem(prompt):
            flags.append("missing_problem")
        if float(reasoning.get("confidence") or 0) < 0.7:
            flags.append("low_confidence")
        if not reasoning.get("socratic_questions"):
            flags.append("missing_socratic_guidance")
        if not reasoning.get("micro_lesson"):
            flags.append("missing_micro_lesson")
        return flags or ["clear_guidance"]

    def run(self, payload: Any) -> Dict[str, Any]:
        normalized = self._normalize_payload(payload)
        prompt = normalized.get("problem", "")
        reasoning = self.reason(prompt, normalized.get("context", {}))
        status = "ok" if self._normalize_problem(prompt) else "needs_context"
        quality_flags = self._build_quality_flags(prompt, reasoning)
        reasoning_summary = self._build_reasoning_summary(prompt, reasoning)
        return {
            "status": status,
            "agent": self.name,
            "mode": normalized.get("mode", "default"),
            "prompt": prompt,
            "summary": reasoning_summary,
            "quality_flags": quality_flags,
            "quality_score": reasoning.get("quality_score"),
            "verification_checks": reasoning.get("verification_checks", []),
            "recommended_next_step": reasoning.get("recommended_next_step"),
            "reasoning": {
                **reasoning,
                "summary": reasoning_summary,
                "quality_flags": quality_flags,
            },
            "evidence": {
                "error_pattern": reasoning.get("error_pattern"),
                "confidence": reasoning.get("confidence"),
                "mode": normalized.get("mode", "default"),
            },
        }

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event.event_type == "REASONING_REQUEST":
            result = self.reason(event.payload["problem"], event.payload.get("context"))
            await self.emit_event("REASONING_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "ReasoningAgent shutting down.")
