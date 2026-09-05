# mammoth_os/agents/field_ops_agent.py
"""
FieldOpsAgent — Elite Business Operations Intelligence

Analyzes operational context and delivers prioritized, actionable field
intelligence for True XXII Supply and small business operators.
No templates. No guessing. Real LLM reasoning on every run.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Union

from .base_agent import BaseAgent

logger = logging.getLogger("mammoth.agents.field_ops")


SYSTEM_PROMPT = """You are an elite field operations intelligence officer embedded with True XXII Supply —
a small business operator in Boise, Idaho specializing in native plants, outdoor gear, and homesteading supplies.

Your role: read operational situations fast, cut through noise, and deliver sharp, prioritized action intelligence.

Rules:
- Every answer is SPECIFIC to the query. Never use generic filler.
- Priorities must be ranked by impact-to-effort ratio.
- Actions must be executable — specific enough that someone can start in the next hour.
- Think like a seasoned operator, not a consultant.

Respond in this exact JSON structure:
{
  "situation_summary": "2-sentence sharp read of the operational landscape based on the query",
  "priorities": [
    {
      "rank": 1,
      "priority": "Priority name (concise)",
      "rationale": "Why this is the #1 priority RIGHT NOW — specific reason",
      "action": "Exact action to take — who, what, how",
      "timeline": "Today / This week / Within 48 hours / etc.",
      "success_metric": "Specific, observable indicator that this is done",
      "effort": "Low / Medium / High"
    },
    {
      "rank": 2,
      "priority": "...",
      "rationale": "...",
      "action": "...",
      "timeline": "...",
      "success_metric": "...",
      "effort": "..."
    },
    {
      "rank": 3,
      "priority": "...",
      "rationale": "...",
      "action": "...",
      "timeline": "...",
      "success_metric": "...",
      "effort": "..."
    }
  ],
  "immediate_win": "ONE specific action executable in the next 48 hours that creates real momentum — be concrete",
  "blockers": ["Specific blocker 1 that could stall execution", "Blocker 2 if any"],
  "risks": ["Risk 1 — what could go wrong and why", "Risk 2 if any"],
  "operator_note": "Straight talk from one operator to another — what would you do if this were your business right now"
}

Return ONLY the JSON. No preamble. No explanation outside the JSON.
"""


class FieldOpsAgent(BaseAgent):
    """Elite business field operations intelligence agent. Real LLM calls on every run."""

    name = "FieldOpsAgent"

    def run(self, prompt: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        prompt_text, context = self._parse_input(prompt)
        if not prompt_text:
            return self._error_response("No operational query provided — give me something to work with.")
        try:
            return self._run_async(self._generate_intel(prompt_text, context))
        except Exception as exc:
            logger.error(f"FieldOpsAgent run failed: {exc}")
            return self._error_response(str(exc))

    def execute_action(
        self, action_type: str, target: str, details: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = dict(details or {})
        if "prompt" not in payload:
            payload["prompt"] = str(target or "").strip()
        return {**self.run(payload), "action": action_type, "target": target}

    async def _generate_intel(
        self, prompt_text: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client
        client = get_llm_client()
        context_block = ""
        if context:
            context_block = f"\n\nAdditional context provided:\n{json.dumps(context, indent=2)}"
        user_message = f"Field ops query: {prompt_text}{context_block}"
        raw = await client.generate(
            f"{SYSTEM_PROMPT}\n\n{user_message}",
            max_tokens=2048,
            temperature=0.3,
        )
        parsed = self._extract_json(raw)
        priorities = parsed.get("priorities", [])
        confidence = round(
            min(0.95, 0.65 + len(priorities) * 0.06 + (0.05 if parsed.get("immediate_win") else 0)),
            2,
        )
        return {
            "status": "ok",
            "agent": self.name,
            "mode": "business_ops_intel",
            "artifact_type": "field_ops",
            "prompt": prompt_text,
            "situation_summary": parsed.get("situation_summary", ""),
            "priorities": priorities,
            "immediate_win": parsed.get("immediate_win", ""),
            "blockers": parsed.get("blockers", []),
            "risks": parsed.get("risks", []),
            "operator_note": parsed.get("operator_note", ""),
            "confidence": confidence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": (
                f"Field ops intel: {len(priorities)} prioritized actions — "
                f"{priorities[0]['priority'] if priorities else 'see analysis'}."
            ),
            "quality_flags": ["llm_synthesized", "business_context_aware", "prompt_responsive"],
        }

    @staticmethod
    def _parse_input(prompt: Any):
        if isinstance(prompt, dict):
            text = str(
                prompt.get("prompt")
                or prompt.get("task")
                or prompt.get("query")
                or prompt.get("content")
                or ""
            ).strip()
            ctx = prompt.get("context") or {}
        else:
            text = str(prompt or "").strip()
            ctx = {}
        return text, ctx

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        text = str(raw or "").strip()
        # Strip markdown code fences (deepseek wraps JSON in ```json...```)
        import re as _re
        text = _re.sub(r"```(?:json)?\s*", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "situation_summary": text[:400] if text else "Unable to parse response.",
            "priorities": [],
            "risks": [],
            "blockers": [],
        }

    @staticmethod
    def _error_response(message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "agent": "FieldOpsAgent",
            "mode": "business_ops_intel",
            "artifact_type": "field_ops",
            "summary": f"FieldOpsAgent could not complete: {message}",
            "priorities": [],
            "confidence": 0.0,
            "quality_flags": ["error"],
        }

    @staticmethod
    def _run_async(coro):
        """Safe sync->async bridge. Handles both running and fresh event loops."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
