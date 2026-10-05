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
import re
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

    async def _lookup_weather(self, prompt_text: str, context: Dict[str, Any]) -> Dict[str, Any] | None:
        """Live forecast only when the request names a place or coordinates; never guessed."""
        from mammoth_os.weather import default_weather, extract_place, weather_enabled

        if context.get("include_weather") is False or not weather_enabled():
            return None
        lat, lon = context.get("latitude"), context.get("longitude")
        place = str(context.get("location") or context.get("place") or "").strip() or None
        if place is None and (lat is None or lon is None):
            place = extract_place(prompt_text)
        if place is None and (lat is None or lon is None):
            return None
        try:
            if place is not None:
                return await asyncio.to_thread(default_weather().forecast, place, days=3)
            return await asyncio.to_thread(default_weather().forecast, None, latitude=float(lat), longitude=float(lon), days=3)
        except Exception as exc:  # weather is supplementary; never fail the mission over it
            logger.warning(f"FieldOpsAgent weather lookup failed: {exc}")
            return {"status": "error", "code": "unreachable", "error": "Weather provider could not be reached."}

    async def _generate_intel(
        self, prompt_text: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client
        from mammoth_os.weather import summarize_forecast

        client = get_llm_client()
        weather = await self._lookup_weather(prompt_text, context)
        weather_ok = bool(weather and weather.get("status") == "ok")
        llm_context = {k: v for k, v in context.items() if k not in {"latitude", "longitude", "include_weather"}}
        context_block = ""
        if llm_context:
            context_block = f"\n\nAdditional context provided:\n{json.dumps(llm_context, indent=2, default=str)}"
        if weather_ok:
            context_block += f"\n\nLive forecast (use it; do not invent other weather):\n{summarize_forecast(weather)}"
        user_message = f"Field ops query: {prompt_text}{context_block}"
        raw = await client.generate(
            user_message,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.3,
        )
        parsed = self._extract_json(raw)
        priorities = parsed.get("priorities", [])
        topic = str(context.get("topic") or self._extract_topic(prompt_text))
        environment = str(context.get("environment") or "unspecified")
        difficulty = str(context.get("difficulty") or self._extract_difficulty(prompt_text) or "medium").lower()
        hazards = context.get("hazards") if isinstance(context.get("hazards"), list) else []
        weather_hazards = list(weather.get("hazards") or []) if weather_ok else []
        hazard_count = len(hazards) + len(weather_hazards)
        risk_level = "high" if difficulty == "hard" or hazard_count >= 2 else "medium" if hazard_count else "low"
        equipment = ["map", "compass"] if "navigat" in topic.lower() else []
        safety_notes = [f"Hazard control: {hazard}." for hazard in hazards]
        safety_notes.extend(f"Weather hazard: {hazard}" for hazard in weather_hazards)
        abort_conditions = [f"Abort if {hazard} makes the route unsafe." for hazard in hazards]
        if weather_hazards:
            abort_conditions.append("Abort or reschedule if forecast weather hazards arrive earlier or stronger than expected.")
        if risk_level == "high" and not abort_conditions:
            abort_conditions.append("Abort if conditions exceed training or visibility limits.")
        mission = f"Complete a {difficulty} {topic} mission in {environment}. Confirm a bearing and report route status."
        confidence = round(
            min(0.95, 0.65 + len(priorities) * 0.06 + (0.05 if parsed.get("immediate_win") else 0)),
            2,
        )
        quality_flags = ["llm_synthesized", "business_context_aware", "prompt_responsive"]
        if weather_ok:
            quality_flags.append("live_weather")
        elif weather is not None:
            quality_flags.append("weather_unavailable")
        return {
            "status": "ok",
            "agent": self.name,
            "mode": "business_ops_intel",
            "artifact_type": "field_ops",
            "prompt": prompt_text,
            "topic": topic,
            "environment": environment,
            "difficulty": difficulty,
            "risk_level": risk_level,
            "mission": mission,
            "checklist": {"selected_landmark": False, "bearing_confirmed": False, "route_checked": False},
            "completion_criteria": ["Bearing recorded", "Landmark identified", "Route status reported"],
            "equipment": equipment,
            "safety_notes": safety_notes,
            "abort_conditions": abort_conditions,
            "approval_gate": {"requires_review": risk_level == "high", "reason": "high-risk field mission" if risk_level == "high" else "standard field mission"},
            "next_actions": ["Review hazards", "Confirm equipment", "Set an abort point"],
            "situation_summary": parsed.get("situation_summary", ""),
            "priorities": priorities,
            "immediate_win": parsed.get("immediate_win", ""),
            "blockers": parsed.get("blockers", []),
            "risks": parsed.get("risks", []),
            "operator_note": parsed.get("operator_note", ""),
            "weather": weather if weather_ok else ({"status": weather.get("status"), "code": weather.get("code"), "error": weather.get("error")} if weather else None),
            "forecast": [
                line[2:] if line.startswith("- ") else line
                for line in summarize_forecast(weather).splitlines()
                if not line.startswith("- Hazard:")
            ] if weather_ok else [],
            "confidence": confidence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": (
                f"Field ops intel: {len(priorities)} prioritized actions — "
                f"{priorities[0]['priority'] if priorities else 'see analysis'}."
            ),
            "quality_flags": quality_flags,
        }

    @staticmethod
    def _parse_input(prompt: Any):
        if isinstance(prompt, dict):
            text = str(
                prompt.get("prompt")
                or prompt.get("topic")
                or prompt.get("task")
                or prompt.get("query")
                or prompt.get("content")
                or ""
            ).strip()
            ctx = dict(prompt.get("context") or {})
            for key, value in prompt.items():
                if key not in {"prompt", "topic", "task", "query", "content", "context"}:
                    ctx.setdefault(key, value)
        else:
            text = str(prompt or "").strip()
            ctx = {
                "topic": FieldOpsAgent._extract_topic(text),
                "difficulty": FieldOpsAgent._extract_difficulty(text) or "medium",
            }
            environment = re.search(r"\bin\s+([a-z][a-z -]+?)(?:\s+conditions?)?$", text, re.IGNORECASE)
            if environment:
                ctx["environment"] = environment.group(1).strip()
        return text, ctx

    @staticmethod
    def _extract_topic(text: str) -> str:
        cleaned = re.sub(r"\b(easy|medium|hard)\b", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bin\s+[a-z][a-z -]+?(?:\s+conditions?)?$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip() or "field operations"

    @staticmethod
    def _extract_difficulty(text: str) -> str | None:
        match = re.search(r"\b(easy|medium|hard)\b", text, re.IGNORECASE)
        return match.group(1).lower() if match else None

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
