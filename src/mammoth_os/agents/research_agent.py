# mammoth_os/agents/research_agent.py
"""
ResearchAgent — Elite Grounded Research with LLM Synthesis

WHAT CHANGED vs. the original:
- Preserved 100% of the existing Wikipedia + DuckDuckGo web retrieval plumbing
- Replaced _build_findings() hardcoded claim templates with real LLM synthesis
- Replaced _generate_summary() hardcoded template with real LLM summary
- Added proper artifact_type="research" (fixes BUG 1 — no more "coding artifact" label)
- findings now render as structured prose + source-backed claims, not raw JSON
- Added "summarize" intent handling that is genuinely different from "research_curriculum"
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .base_agent import BaseAgent

logger = logging.getLogger("mammoth.agents.research")


RESEARCH_SYSTEM = """You are an elite research analyst embedded with True XXII Supply (Boise, Idaho).
You have been given a set of live web search results. Your job is to synthesize them into
a high-quality research brief — think intelligence officer briefing a decision-maker, not Wikipedia summary.

Rules:
- Ground every claim in the provided sources. If you add context from training knowledge, label it clearly.
- Cite sources by their [S1], [S2], etc. label where relevant.
- Idaho/Boise specificity earns extra points when it's relevant to the query.
- No filler. Every sentence must earn its place.

Respond in this exact JSON structure:
{
  "title": "Research brief title — sharp and specific to the actual query",
  "executive_summary": "3-4 sentences — the key insight a decision-maker needs immediately. Lead with the sharpest finding.",
  "findings": [
    {
      "heading": "Finding area — concise label",
      "content": "2-3 sentences of analysis grounded in the sources. Cite [S1], [S2] etc. inline.",
      "source_support": ["S1", "S2"]
    },
    {
      "heading": "...",
      "content": "...",
      "source_support": ["S2", "S3"]
    },
    {
      "heading": "...",
      "content": "...",
      "source_support": []
    }
  ],
  "key_facts": [
    "Fact 1 — specific, citable, one sentence [S1]",
    "Fact 2",
    "Fact 3"
  ],
  "knowledge_gaps": "What this research could NOT confirm — where a decision-maker should dig further",
  "recommended_next_steps": [
    "Actionable follow-up 1 — specific to True XXII Supply's situation",
    "Actionable follow-up 2"
  ],
  "confidence_assessment": "Honest 1-2 sentences on data quality and what would improve it"
}

Return ONLY the JSON. No preamble.
"""

SUMMARIZE_SYSTEM = """You are an expert summarizer and analyst embedded with True XXII Supply (Boise, Idaho).
You will be given a topic and supporting web context. Produce a sharp, decision-ready summary.

This is a SUMMARY task — not exhaustive research. The output should be:
- Concise (shorter than a full research brief)
- Action-oriented (what does this mean for an operator?)
- Clear and jargon-free

Respond in this exact JSON structure:
{
  "summary_title": "One sharp title capturing what was summarized",
  "tldr": "One sentence — the single most important takeaway",
  "key_points": [
    "Point 1 — specific, concrete, 1 sentence",
    "Point 2",
    "Point 3",
    "Point 4",
    "Point 5"
  ],
  "context": "2-3 sentences of background that make the key points make sense",
  "bottom_line": "What this means for True XXII Supply specifically — what should they do or know based on this summary",
  "caveats": "Any important limitations or 'but also consider' points"
}

Return ONLY the JSON. No preamble.
"""

CURRICULUM_SYSTEM = """You are an elite curriculum research analyst working with True XXII Supply (Boise, Idaho).
You have been given live web search results about an educational or learning topic.

Your job: surface the best curriculum structure, key concepts, recommended resources,
and a practical learning path. Think learning designer + subject expert.

Respond in this exact JSON structure:
{
  "topic": "Curriculum area — sharpened version of the query",
  "overview": "2-3 sentences — what this topic is and why it matters for the operator",
  "core_concepts": [
    {
      "concept": "Concept name",
      "description": "What it is and why it matters — 1-2 sentences",
      "difficulty": "Beginner / Intermediate / Advanced"
    },
    {
      "concept": "...",
      "description": "...",
      "difficulty": "..."
    }
  ],
  "learning_path": [
    {
      "phase": "Phase 1: ...",
      "focus": "What to learn / build in this phase",
      "duration": "Estimated time",
      "milestones": ["Milestone A", "Milestone B"]
    },
    {
      "phase": "Phase 2: ...",
      "focus": "...",
      "duration": "...",
      "milestones": []
    }
  ],
  "recommended_resources": [
    {
      "resource": "Resource name or type",
      "why": "Why this specific resource for this topic",
      "cost": "Free / Paid / Varies"
    }
  ],
  "practical_application": "How True XXII Supply can apply this curriculum to real operations — concrete and specific",
  "estimated_mastery_time": "Realistic estimate to functional competency"
}

Return ONLY the JSON. No preamble.
"""


class ResearchAgent(BaseAgent):
    """
    Elite grounded research agent. Retrieves real web data (Wikipedia + DuckDuckGo)
    and synthesizes findings via LLM. Handles research_curriculum, summarize,
    and general research intents distinctly.
    """

    name = "ResearchAgent"

    INTENT_MAP = {
        "research_curriculum": "curriculum",
        "summarize": "summarize",
        "research": "research",
    }

    def run(self, prompt: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        prompt_text, intent, context = self._parse_input(prompt)
        if not prompt_text:
            return self._error_response("No research topic provided.")
        try:
            return self._run_async(self._research_pipeline(prompt_text, intent, context))
        except Exception as exc:
            logger.error(f"ResearchAgent run failed: {exc}")
            return self._error_response(str(exc))

    def execute_action(
        self, action_type: str, target: str, details: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = dict(details or {})
        if "prompt" not in payload:
            payload["prompt"] = str(target or "").strip()
        payload.setdefault("intent", action_type)
        return {**self.run(payload), "action": action_type, "target": target}

    async def _research_pipeline(
        self, prompt_text: str, intent: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client
        client = get_llm_client()
        mode = self.INTENT_MAP.get(intent, "research")
        expanded_queries = self._expand_query(prompt_text)
        loop = asyncio.get_event_loop()
        all_sources, retrieval_errors = await loop.run_in_executor(
            None, self._retrieve_sources, expanded_queries
        )
        ranked = self._rank_sources(all_sources, prompt_text)
        top_sources = self._deduplicate(ranked)[:8]
        source_block = self._format_source_block(top_sources)
        if mode == "curriculum":
            system = CURRICULUM_SYSTEM
        elif mode == "summarize":
            system = SUMMARIZE_SYSTEM
        else:
            system = RESEARCH_SYSTEM
        ctx_block = ""
        if context:
            ctx_block = f"\n\nOperator context:\n{json.dumps(context, indent=2)}"
        user_message = (
            f"Research query: {prompt_text}\n"
            f"{source_block}"
            f"{ctx_block}"
        )
        raw = await client.generate(
            f"{system}\n\n{user_message}",
            max_tokens=3000,
            temperature=0.3,
        )
        parsed = self._extract_json(raw)
        normalized_sources = self._normalize_sources(top_sources)
        confidence = round(
            min(0.95,
                0.55
                + len(top_sources) * 0.07
                + (0.05 if len(top_sources) > 4 else 0)
                + (0.05 if mode == "research" and parsed.get("findings") else 0)
                + (0.05 if mode == "curriculum" and parsed.get("core_concepts") else 0)),
            2,
        )
        if mode == "curriculum":
            summary_text = (
                f"Curriculum research: {parsed.get('topic', prompt_text[:60])} — "
                f"{len(parsed.get('core_concepts', []))} concepts, "
                f"{len(parsed.get('learning_path', []))} learning phases"
            )
            result_fields = {
                "topic": parsed.get("topic", ""),
                "overview": parsed.get("overview", ""),
                "core_concepts": parsed.get("core_concepts", []),
                "learning_path": parsed.get("learning_path", []),
                "recommended_resources": parsed.get("recommended_resources", []),
                "practical_application": parsed.get("practical_application", ""),
                "estimated_mastery_time": parsed.get("estimated_mastery_time", ""),
            }
        elif mode == "summarize":
            summary_text = f"Summary: {parsed.get('tldr', prompt_text[:80])}"
            result_fields = {
                "summary_title": parsed.get("summary_title", ""),
                "tldr": parsed.get("tldr", ""),
                "key_points": parsed.get("key_points", []),
                "context": parsed.get("context", ""),
                "bottom_line": parsed.get("bottom_line", ""),
                "caveats": parsed.get("caveats", ""),
            }
        else:
            findings = parsed.get("findings", [])
            summary_text = (
                f"Research: {parsed.get('title', prompt_text[:60])} — "
                f"{len(findings)} findings from {len(top_sources)} sources"
            )
            result_fields = {
                "title": parsed.get("title", ""),
                "executive_summary": parsed.get("executive_summary", ""),
                "findings": findings,
                "key_facts": parsed.get("key_facts", []),
                "knowledge_gaps": parsed.get("knowledge_gaps", ""),
                "recommended_next_steps": parsed.get("recommended_next_steps", []),
                "confidence_assessment": parsed.get("confidence_assessment", ""),
            }
        return {
            "status": "ok",
            "agent": self.name,
            "mode": mode,
            "artifact_type": "research",
            "prompt": prompt_text,
            "intent": intent,
            **result_fields,
            "sources": normalized_sources,
            "sources_retrieved": len(top_sources),
            "retrieval_errors": retrieval_errors,
            "confidence": confidence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary_text,
            "quality_flags": (
                ["llm_synthesized", "web_grounded", "prompt_responsive"]
                if top_sources
                else ["llm_synthesized", "prompt_responsive", "low_source_coverage"]
            ),
        }

    def _retrieve_sources(
        self, queries: List[str]
    ) -> Tuple[List[Dict], List[str]]:
        sources: List[Dict] = []
        errors: List[str] = []
        for query in queries[:3]:
            wiki_hits, wiki_err = self._fetch_wikipedia(query)
            sources.extend(wiki_hits)
            if wiki_err:
                errors.append(wiki_err)
            ddg_hits, ddg_err = self._fetch_duckduckgo(query)
            sources.extend(ddg_hits)
            if ddg_err:
                errors.append(ddg_err)
        return sources, errors

    def _fetch_wikipedia(self, query: str) -> Tuple[List[Dict], Optional[str]]:
        results: List[Dict] = []
        try:
            search_url = (
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
                search_url,
                headers={"User-Agent": "MammothOS/1.0 ResearchAgent (research)"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                search_data = json.loads(resp.read().decode("utf-8", errors="replace"))
            hits = search_data.get("query", {}).get("search", [])
            page_titles = [h["title"] for h in hits[:2] if "title" in h]
            for title in page_titles:
                try:
                    extract_url = (
                        "https://en.wikipedia.org/w/api.php?"
                        + urllib.parse.urlencode({
                            "action": "query",
                            "prop": "extracts",
                            "exintro": True,
                            "explaintext": True,
                            "titles": title,
                            "format": "json",
                            "utf8": 1,
                        })
                    )
                    req = urllib.request.Request(
                        extract_url,
                        headers={"User-Agent": "MammothOS/1.0 ResearchAgent (research)"},
                    )
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        extract_data = json.loads(
                            resp.read().decode("utf-8", errors="replace")
                        )
                    pages = extract_data.get("query", {}).get("pages", {})
                    for page in pages.values():
                        extract = str(page.get("extract") or "").strip()
                        if extract and len(extract) > 50:
                            results.append({
                                "id": f"wiki-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                                "title": str(page.get("title") or title),
                                "snippet": extract[:800],
                                "source": "Wikipedia",
                                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                                "relevance_score": 0.0,
                            })
                except Exception:
                    pass
        except Exception as exc:
            return results, f"wikipedia: {exc}"
        return results, None

    def _fetch_duckduckgo(self, query: str) -> Tuple[List[Dict], Optional[str]]:
        results: List[Dict] = []
        try:
            encoded_q = urllib.parse.quote(query[:140])
            url = (
                f"https://api.duckduckgo.com/?q={encoded_q}"
                "&format=json&no_html=1&skip_disambig=1"
            )
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "MammothOS/1.0 ResearchAgent (research)"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            abstract = str(payload.get("AbstractText") or "").strip()
            if abstract:
                results.append({
                    "id": f"ddg-{hashlib.md5(abstract[:50].encode()).hexdigest()[:8]}",
                    "title": str(payload.get("Heading") or query[:60]),
                    "snippet": abstract[:700],
                    "source": "DuckDuckGo",
                    "url": str(payload.get("AbstractURL") or ""),
                    "relevance_score": 0.0,
                })
            for topic in (payload.get("RelatedTopics") or [])[:3]:
                text = str(topic.get("Text") or "").strip()
                if text and len(text) > 40:
                    results.append({
                        "id": f"ddg-{hashlib.md5(text[:50].encode()).hexdigest()[:8]}",
                        "title": "Related: " + text[:60],
                        "snippet": text[:400],
                        "source": "DuckDuckGo Related",
                        "url": str(topic.get("FirstURL") or ""),
                        "relevance_score": 0.0,
                    })
        except Exception as exc:
            return results, f"duckduckgo: {exc}"
        return results, None

    def _expand_query(self, query: str) -> List[str]:
        queries = [query]
        stops = {
            "the", "a", "an", "of", "and", "or", "in", "on", "at", "to",
            "for", "with", "from", "by", "is", "are", "was", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "shall", "what", "how", "why", "when", "where", "who",
        }
        keywords = [
            w for w in re.split(r"\W+", query.lower()) if w and w not in stops
        ]
        if keywords:
            keyword_query = " ".join(keywords[:6])
            if keyword_query != query.lower():
                queries.append(keyword_query)
        if "how to" in query.lower() or "tutorial" in query.lower():
            queries.append(f"{query} guide best practices")
        elif any(w in query.lower() for w in ["market", "industry", "trend"]):
            queries.append(f"{query} 2025 statistics overview")
        return list(dict.fromkeys(queries))[:3]

    @staticmethod
    def _rank_sources(sources: List[Dict], query: str) -> List[Dict]:
        query_words = set(re.split(r"\W+", query.lower()))
        def score(src: Dict) -> float:
            text = (src.get("title", "") + " " + src.get("snippet", "")).lower()
            words = set(re.split(r"\W+", text))
            overlap = len(query_words & words)
            base = overlap / max(len(query_words), 1)
            if src.get("source") == "Wikipedia":
                base += 0.05
            return base
        scored = [(score(s), s) for s in sources]
        scored.sort(key=lambda x: x[0], reverse=True)
        for sc, src in scored:
            src["relevance_score"] = round(sc, 3)
        return [src for _, src in scored]

    @staticmethod
    def _deduplicate(sources: List[Dict]) -> List[Dict]:
        seen: set = set()
        unique: List[Dict] = []
        for src in sources:
            snippet = src.get("snippet", "")
            fp = hashlib.md5(snippet[:120].encode()).hexdigest()
            if fp not in seen:
                seen.add(fp)
                unique.append(src)
        return unique

    @staticmethod
    def _format_source_block(sources: List[Dict]) -> str:
        if not sources:
            return "\n\nNo live web sources retrieved — synthesize from training knowledge and label clearly."
        lines = ["\n\nLive research sources (cite as [S1], [S2], etc.):"]
        for i, src in enumerate(sources, 1):
            lines.append(
                f"[S{i}] {src.get('source', 'Web')} — {src.get('title', '')}: "
                f"{src.get('snippet', '')[:500]}"
            )
        return "\n".join(lines)

    @staticmethod
    def _normalize_sources(sources: List[Dict]) -> List[Dict]:
        normalized = []
        for i, src in enumerate(sources, 1):
            title = str(src.get("title") or "Source").strip()
            snippet = str(src.get("snippet") or "").strip()
            url = str(src.get("url") or "").strip()
            normalized.append({
                "id": src.get("id") or f"src-{i}",
                "label": f"S{i}",
                "title": title,
                "excerpt": unicodedata.normalize("NFKC", snippet[:300]),
                "source": str(src.get("source") or "Web"),
                "url": url if url.startswith("http") else "",
                "relevance_score": src.get("relevance_score", 0.0),
            })
        return normalized

    @staticmethod
    def _parse_input(prompt: Any):
        if isinstance(prompt, dict):
            text = str(
                prompt.get("prompt")
                or prompt.get("topic")
                or prompt.get("task")
                or prompt.get("content")
                or ""
            ).strip()
            intent = str(prompt.get("intent") or prompt.get("mode") or "research").strip()
            ctx = prompt.get("context") or {}
        else:
            text = str(prompt or "").strip()
            intent = "research"
            ctx = {}
        return text, intent, ctx

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        text = str(raw or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "title": "Research Output",
            "executive_summary": text[:500] if text else "Unable to parse LLM response.",
            "findings": [],
            "key_facts": [],
            "key_points": [],
            "summary_title": "Summary",
            "tldr": text[:200] if text else "",
        }

    @staticmethod
    def _error_response(message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "agent": "ResearchAgent",
            "mode": "research",
            "artifact_type": "research",
            "summary": f"ResearchAgent could not complete: {message}",
            "findings": [],
            "sources": [],
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
