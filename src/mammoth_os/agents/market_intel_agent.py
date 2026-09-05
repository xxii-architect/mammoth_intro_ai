# mammoth_os/agents/market_intel_agent.py
"""
MarketIntelAgent — Elite Real-Time Market Intelligence

Delivers structured competitive analysis, trend identification, demand signals,
and strategic white-space mapping. Grounded in live web data via DuckDuckGo
and Wikipedia before synthesis by LLM.

Zero hardcoded templates. Every report generated fresh against the actual query.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union

from .base_agent import BaseAgent

logger = logging.getLogger("mammoth.agents.market_intel")


SYSTEM_PROMPT = """You are an elite market intelligence analyst embedded with True XXII Supply —
a Boise, Idaho small business specializing in native plants, outdoor gear, and homesteading supplies.

Your role: read market signals, map the competitive landscape, and surface the strategic openings
that a sharp operator can act on this week. Think like an intelligence officer, not a PowerPoint consultant.

Rules:
- Specific beats generic. Name real competitor types, real trends, real demand signals.
- Idaho/Boise market specificity earns a bonus. Generic "market forces" language loses points.
- Every strategic move must be executable by a small operator with limited budget.
- If web context is provided, incorporate it. Don't ignore it.

Respond in this exact JSON structure:
{
  "market_summary": "2-3 sentences — the sharpest read of the current market landscape relevant to the query",
  "key_trends": [
    {
      "trend": "Trend name — concise and specific",
      "signal": "What data point, behavior, or event is driving this right now",
      "opportunity": "Specific way True XXII Supply can capitalize — no fluff",
      "urgency": "Now / 3-6 months / Long-term"
    },
    {
      "trend": "...",
      "signal": "...",
      "opportunity": "...",
      "urgency": "..."
    },
    {
      "trend": "...",
      "signal": "...",
      "opportunity": "...",
      "urgency": "..."
    }
  ],
  "competitive_landscape": [
    {
      "competitor": "Competitor name, type, or category — be specific to Boise/Idaho when possible",
      "strengths": "What they genuinely do well that makes them a real threat",
      "gaps": "Where they fall short — the actual opening True XXII Supply can exploit",
      "threat_level": "Low / Medium / High"
    },
    {
      "competitor": "...",
      "strengths": "...",
      "gaps": "...",
      "threat_level": "..."
    },
    {
      "competitor": "...",
      "strengths": "...",
      "gaps": "...",
      "threat_level": "..."
    }
  ],
  "demand_signals": [
    "Signal 1 — specific observable demand indicator",
    "Signal 2",
    "Signal 3"
  ],
  "white_space": "The specific, defensible gap in the market that True XXII Supply is best positioned to own — one paragraph, be bold",
  "strategic_moves": [
    "Move 1 — specific action this week to capitalize on market conditions, with estimated cost",
    "Move 2 — medium-term move (next 30 days)",
    "Move 3 — positioning play that builds long-term advantage"
  ],
  "risks": [
    "Risk 1 — external market risk with specific mitigation",
    "Risk 2"
  ],
  "confidence_note": "Honest 1-sentence note on data quality and what would sharpen this analysis"
}

Return ONLY the JSON. No preamble. No explanation outside the JSON.
"""


class MarketIntelAgent(BaseAgent):
    """Elite market intelligence and competitive analysis agent."""

    name = "MarketIntelAgent"

    def run(self, prompt: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        prompt_text, context = self._parse_input(prompt)
        if not prompt_text:
            return self._error_response("No market query provided — describe what market or topic you want intel on.")
        try:
            return self._run_async(self._generate_intel(prompt_text, context))
        except Exception as exc:
            logger.error(f"MarketIntelAgent run failed: {exc}")
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
        loop = asyncio.get_event_loop()
        web_snippets, web_errors = await loop.run_in_executor(
            None, self._fetch_web_context, prompt_text
        )
        web_block = ""
        if web_snippets:
            web_block = "\n\nLive web context — incorporate into your analysis:\n"
            for s in web_snippets:
                web_block += f"[{s['source']} — {s['title']}]: {s['snippet']}\n"
        ctx_block = ""
        if context:
            ctx_block = f"\n\nAdditional operator context:\n{json.dumps(context, indent=2)}"
        user_message = (
            f"Market intelligence request: {prompt_text}"
            f"{web_block}"
            f"{ctx_block}"
        )
        raw = await client.generate(
            f"{SYSTEM_PROMPT}\n\n{user_message}",
            max_tokens=2800,
            temperature=0.35,
        )
        parsed = self._extract_json(raw)
        trends = parsed.get("key_trends", [])
        competitors = parsed.get("competitive_landscape", [])
        confidence = round(
            min(0.94,
                0.60
                + len(web_snippets) * 0.07
                + len(trends) * 0.04
                + len(competitors) * 0.03
                + (0.04 if parsed.get("white_space") else 0)),
            2,
        )
        return {
            "status": "ok",
            "agent": self.name,
            "mode": "market_intelligence",
            "artifact_type": "market_intel",
            "prompt": prompt_text,
            "market_summary": parsed.get("market_summary", ""),
            "key_trends": trends,
            "competitive_landscape": competitors,
            "demand_signals": parsed.get("demand_signals", []),
            "white_space": parsed.get("white_space", ""),
            "strategic_moves": parsed.get("strategic_moves", []),
            "risks": parsed.get("risks", []),
            "confidence_note": parsed.get("confidence_note", ""),
            "web_sources_used": len(web_snippets),
            "web_retrieval_errors": web_errors,
            "confidence": confidence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": (
                f"Market intel complete — {len(trends)} trends, "
                f"{len(competitors)} competitors, "
                f"{len(web_snippets)} live sources: {prompt_text[:80]}"
            ),
            "quality_flags": (
                ["llm_synthesized", "web_grounded", "prompt_responsive"]
                if web_snippets
                else ["llm_synthesized", "prompt_responsive", "no_live_web_data"]
            ),
        }

    def _fetch_web_context(self, query: str) -> Tuple[List[Dict], List[str]]:
        snippets: List[Dict] = []
        errors: List[str] = []
        try:
            encoded_q = urllib.parse.quote(query[:140])
            ddg_url = (
                f"https://api.duckduckgo.com/?q={encoded_q}"
                "&format=json&no_html=1&skip_disambig=1"
            )
            req = urllib.request.Request(
                ddg_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "MammothOS/1.0 MarketIntelAgent (research)",
                },
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            abstract = str(payload.get("AbstractText") or "").strip()
            if abstract:
                snippets.append({
                    "title": str(payload.get("Heading") or query[:60]),
                    "snippet": abstract[:600],
                    "source": "DuckDuckGo",
                })
            if len(abstract) < 100:
                topics = payload.get("RelatedTopics") or []
                for topic in topics[:2]:
                    text = str(topic.get("Text") or "").strip()
                    if text and len(text) > 40:
                        snippets.append({
                            "title": "Related: " + text[:60],
                            "snippet": text[:300],
                            "source": "DuckDuckGo Related",
                        })
        except Exception as exc:
            errors.append(f"duckduckgo: {exc}")
        try:
            wiki_url = (
                "https://en.wikipedia.org/w/api.php?"
                + urllib.parse.urlencode({
                    "action": "query",
                    "list": "search",
                    "srsearch": query[:120],
                    "srlimit": 3,
                    "format": "json",
                    "utf8": 1,
                })
            )
            req = urllib.request.Request(
                wiki_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "MammothOS/1.0 MarketIntelAgent (research)",
                },
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                wiki_data = json.loads(resp.read().decode("utf-8", errors="replace"))
            hits = wiki_data.get("query", {}).get("search", [])
            for hit in hits[:2]:
                title = str(hit.get("title") or "").strip()
                snippet = (
                    str(hit.get("snippet") or "")
                    .replace('<span class="searchmatch">', "")
                    .replace("</span>", "")
                    .strip()
                )
                if title and len(snippet) > 30:
                    snippets.append({
                        "title": title,
                        "snippet": snippet[:400],
                        "source": "Wikipedia",
                    })
        except Exception as exc:
            errors.append(f"wikipedia: {exc}")
        return snippets, errors

    @staticmethod
    def _parse_input(prompt: Any):
        if isinstance(prompt, dict):
            text = str(
                prompt.get("prompt")
                or prompt.get("query")
                or prompt.get("task")
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
            "market_summary": text[:400] if text else "Unable to parse LLM response.",
            "key_trends": [],
            "competitive_landscape": [],
            "demand_signals": [],
            "strategic_moves": [],
            "risks": [],
        }

    @staticmethod
    def _error_response(message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "agent": "MarketIntelAgent",
            "mode": "market_intelligence",
            "artifact_type": "market_intel",
            "summary": f"MarketIntelAgent could not complete: {message}",
            "key_trends": [],
            "competitive_landscape": [],
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
