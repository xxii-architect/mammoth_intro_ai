"""
Mammoth OS — BrandVoiceAgent (P16: LLM-powered)
Rewrites / generates content in the True XXII Supply brand voice via LLM synthesis.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent
from mammoth_os.analysis_contract import generate_analysis, run_analysis_sync

logger = logging.getLogger("mammoth.agents.brand_voice")

BRAND_VOICE_SYSTEM = """You are the brand voice engine for True XXII Supply, a Boise Idaho tactical/outdoor gear company.

True XXII Supply identity:
- Voice: rugged, direct, empowering — a seasoned operator talking to a peer, not a marketer
- Philosophy: "Plant the Seed" — small daily actions compound into real capability and resilience  
- Core energy: "Don't get caught running with scissors. Stand your ground. Build your skills. Feel more alive than ever."
- Audience: outdoor operators, EDC enthusiasts, Boise/Idaho community, preppers, hunters, hikers
- Tone range: rugged (default), motivational, calm — never corporate, never fluffy, never generic

Mode instructions:
- rewrite: Rewrite provided content in True XXII voice. Keep the core message, transform the delivery completely.
- tagline: One sharp memorable tagline. Short. Punchy. Operator energy.
- caption: Social media caption. Hook first. Plant the Seed philosophy woven in naturally.
- stakeholder_summary: Business stakeholder summary. Clear, confident, grounded — zero corporate fluff.
- tutorial_copy: Instructional copy that feels like a skilled operator guiding a peer, not a dry manual.
- rewrite_with_constraints: Rewrite with supplied constraints honored exactly — no exceptions.

Respond in this exact JSON structure — no preamble, no explanation outside the JSON:
{
  "output": "The rewritten or generated content — full ready-to-use copy, not a placeholder",
  "summary": "One sentence: what changed and why it lands for the True XXII audience",
  "tone_notes": "Brief note on the specific tone choices made"
}"""


class BrandVoiceAgent(BaseAgent):
    """Rewrites or generates content in the True XXII Supply brand voice."""

    def __init__(self, router: Optional[Any] = None, user_id: str | None = None):
        if isinstance(router, str) and user_id is None:
            user_id = router
            router = None
        super().__init__(router)
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            payload = {"content": str(payload or ""), "mode": "rewrite", "tone": "rugged"}

        content     = str(payload.get("content") or payload.get("prompt") or payload.get("text") or "").strip()
        mode        = str(payload.get("mode",      "rewrite") or "rewrite").strip()
        tone        = str(payload.get("tone",      "rugged")  or "rugged").strip()
        audience    = str(payload.get("audience",  "general") or "general").strip()
        constraints = payload.get("constraints") or []
        if not isinstance(constraints, list):
            constraints = [str(constraints)] if str(constraints).strip() else []
        if not content or content.casefold() in {"unknown", "placeholder", "tbd"}:
            return self._failure("needs_context", "Provide real copy or a specific writing brief before generating content.")

        try:
            result = run_analysis_sync(self._llm_pipeline(content, mode, tone, audience, constraints))
        except Exception:
            logger.exception("BrandVoiceAgent generation failed")
            return self._failure("failed", "The copy could not be generated and validated. No template was substituted; retry with your original brief.")

        output_text  = result.get("output", "")     if isinstance(result, dict) else str(result)
        summary_text = result.get("summary", "")    if isinstance(result, dict) else str(output_text)[:220]
        tone_notes   = result.get("tone_notes", "") if isinstance(result, dict) else ""
        if mode == "stakeholder_summary":
            if "what changed" not in output_text.lower():
                output_text = f"What changed: {output_text.strip()}"
            if "guardrails" not in output_text.lower():
                guardrails = ", ".join(str(item) for item in constraints)
                if not guardrails:
                    guardrails = "Keep the workflow approval-safe and grounded in source material."
                output_text = f"{output_text}\n\nGuardrails: {guardrails}"

        return {
            "agent":      "brand_voice",
            "status":     "ok",
            "mode":       mode,
            "tone":       tone,
            "audience":   audience,
            "input":      content,
            "output":     output_text,
            "summary":    summary_text or str(output_text)[:220],
            "tone_notes": tone_notes,
            "reasoning_trace": result.get("trace", ""),
            "quality": {"status": "ok", "ready": True, "evidence_status": "interpretation",
                        "fact_verification": "not_performed"},
        }

    async def _llm_pipeline(
        self,
        content: str,
        mode: str,
        tone: str,
        audience: str,
        constraints: List[str],
    ) -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client
        client = get_llm_client()

        constraint_block = ""
        if constraints:
            constraint_block = "\n\nHard constraints (honor exactly):\n" + "\n".join(f"- {c}" for c in constraints)

        user_message = (
            f"Mode: {mode}\n"
            f"Tone: {tone}\n"
            f"Audience: {audience}\n"
            f"Content to process:\n{content or '(none provided — generate a representative sample for the given mode)'}"
            f"{constraint_block}"
        )
        return await generate_analysis(
            client, BRAND_VOICE_SYSTEM, user_message,
            text_fields=("output", "summary", "tone_notes"),
            max_tokens=1200,
            temperature=0.7,
        )

    @staticmethod
    def _failure(status: str, message: str) -> Dict[str, Any]:
        return {"agent": "brand_voice", "status": status, "summary": message, "output": "",
                "quality": {"status": status, "ready": False, "evidence_status": "unverified",
                            "fact_verification": "not_performed"}}
