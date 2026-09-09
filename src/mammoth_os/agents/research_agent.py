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

CRITICAL RULES:
- You MUST always populate the findings[] array with a minimum of 5 substantive findings.
- If retrieved sources contain insufficient data, synthesize findings from your expert knowledge. Label these with "source_type": "llm_synthesized".
- NEVER return an empty findings[] array. NEVER title the output "Unable to Assess" or "Source Gap Assessment" — always synthesize a useful answer.
- The summary field must be a direct, actionable answer to the user question — not a meta-commentary about source availability.
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

CRITICAL RULES:
- You MUST always populate the findings[] array with a minimum of 5 substantive findings.
- If retrieved sources contain insufficient data, synthesize findings from your expert knowledge. Label these with "source_type": "llm_synthesized".
- NEVER return an empty findings[] array. NEVER title the output "Unable to Assess" or "Source Gap Assessment" — always synthesize a useful answer.
- The summary field must be a direct, actionable answer to the user question — not a meta-commentary about source availability.
Return ONLY the JSON. No preamble.
"""


LONG_FORM_OUTLINE_SYSTEM = """You are a senior research director outlining a comprehensive 5,000-word research document.

You have been given a topic and supporting web sources. Structure this as a thorough, authoritative document with exactly 6 body sections.

Respond with this exact JSON structure:
{
  "title": "Sharp, specific document title — not generic",
  "abstract": "4-5 sentence abstract covering thesis, scope, key findings, and main takeaway",
  "sections": [
    {
      "heading": "Specific, informative section heading",
      "brief": "2-3 sentences on exactly what this section covers and the central argument it makes"
    }
  ],
  "conclusion_brief": "What the conclusion should synthesize — the so-what and call to action for the reader"
}

Rules:
- Create exactly 6 sections — logically ordered so each builds on the last
- Avoid generic headings like Introduction, Overview, Background, Summary
- Every heading must be specific to the actual topic being researched
- Sections should cover distinct angles: landscape, technical depth, data/evidence, implications, risks, future outlook
- Return ONLY valid JSON. No preamble, no explanation.
"""

LONG_FORM_SECTION_SYSTEM = """You are an expert research writer producing one section of a comprehensive research document.

Write 650-800 words of polished, flowing prose for this section. Use the provided web sources to ground your analysis.

Rules:
- Write in flowing paragraphs. No bullet points, no sub-headers, no numbered lists within the section.
- Cite sources inline as [S1], [S2] where relevant — keep it readable, not academic-heavy.
- Write for an intelligent business decision-maker: clear, precise, no jargon for its own sake.
- Every paragraph must advance the argument. No filler or throat-clearing sentences.
- Open with a strong topic sentence that immediately establishes what this section argues.
- Close with a bridging sentence that flows naturally toward the next idea.
- Do NOT include the section heading in your output — just the prose body paragraphs.
- Target 700 words — comprehensive but tight.

Return ONLY the prose text. No JSON, no labels, no preamble, no heading.
"""

LONG_FORM_CONCLUSION_SYSTEM = """You are an expert research writer writing the conclusion of a comprehensive research document.

You will receive the document topic, a conclusion brief, and the content of all body sections. Write a powerful 400-500 word conclusion.

Rules:
- Synthesize core insights across sections — do not just summarize each section in order.
- Drive toward a clear so-what: what should the reader actually do or think differently after reading this?
- Acknowledge genuine uncertainty or limitations honestly but briefly.
- End with a memorable, forward-looking closing statement — the last sentence should land with weight.
- Flowing prose only. No bullet points, no headers, no numbered lists.

Return ONLY the prose text. No JSON, no labels, no heading, no preamble.
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

CRITICAL RULES:
- You MUST always populate the findings[] array with a minimum of 5 substantive findings.
- If retrieved sources contain insufficient data, synthesize findings from your expert knowledge. Label these with "source_type": "llm_synthesized".
- NEVER return an empty findings[] array. NEVER title the output "Unable to Assess" or "Source Gap Assessment" — always synthesize a useful answer.
- The summary field must be a direct, actionable answer to the user question — not a meta-commentary about source availability.
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
            if intent in ("research_long_form", "long_form_research"):
                return self._run_async(self._long_form_pipeline(prompt_text, context))
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
            "\n\n---\nIMPORTANT: Your entire response must be a single valid JSON object."
            " Start with {{ and end with }}. No preamble, no prose, no explanation outside the JSON."
            " Populate findings[] with at least 5 objects each having \"heading\", \"content\", \"source_support\" keys."
        )
        raw = await client.generate(
            user_message,
            system_prompt=system,
            max_tokens=4096,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        parsed = self._extract_json(raw)
        # ── nested-JSON rescue: LLM sometimes returns JSON inside executive_summary ──
        exec_val = parsed.get("executive_summary", "")
        if isinstance(exec_val, str):
            _es = exec_val.strip()
            # find outermost { } in exec_val (handles leading prose)
            _s = _es.find("{"); _e = _es.rfind("}")
            if _s != -1 and _e > _s:
                try:
                    import json as _jj
                    inner = _jj.loads(_es[_s:_e+1])
                    if isinstance(inner, dict) and (inner.get("findings") or inner.get("executive_summary")):
                        # fully replace parsed with inner when we have richer data
                        if parsed.get("_raw_unparsed") or not parsed.get("findings"):
                            parsed = inner
                        else:
                            for k, v in inner.items():
                                if not parsed.get(k):
                                    parsed[k] = v
                except Exception:
                    pass
        # ── findings rescue: if LLM omitted findings[], synthesize from executive_summary ──
        if not parsed.get("findings"):
            exec_sum = str(parsed.get("executive_summary") or "").strip()
            key_facts = parsed.get("key_facts") or []
            if exec_sum or key_facts:
                synth = []
                if exec_sum:
                    synth.append({"claim": exec_sum[:500], "source_type": "llm_synthesized", "source_ref": "S0"})
                for i, kf in enumerate(key_facts[:4], 1):
                    synth.append({"claim": str(kf)[:300], "source_type": "llm_synthesized", "source_ref": f"S{i}"})
                parsed["findings"] = synth
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


    # -- Long-Form Research Pipeline -----------------------------------------

    async def _generate_section(self, client, topic, source_block, section, idx):
        heading = section.get("heading", "Section " + str(idx + 1))
        brief = section.get("brief", "")
        nl = chr(10)
        user_msg = (
            "Document topic: " + topic + nl + nl
            + "Section " + str(idx + 1) + ": " + heading + nl
            + "Section brief: " + brief + nl + nl
            + source_block + nl + nl
            + "Write the full prose body for this section (650-800 words). "
            + "Do not include the heading -- just the body paragraphs."
        )
        try:
            prose = await client.generate(user_msg, system_prompt=LONG_FORM_SECTION_SYSTEM, max_tokens=1800, temperature=0.5)
            return {"heading": heading, "content": prose.strip(), "order": idx}
        except Exception as exc:
            logger.warning("Long-form section %d failed: %s", idx, exc)
            return {"heading": heading, "content": "[Section failed: " + str(exc) + "]", "order": idx}

    async def _long_form_pipeline(self, prompt_text, context):
        from mammoth_os.llm_client import get_llm_client
        client = get_llm_client()
        nl = chr(10)
        expanded_queries = self._expand_query(prompt_text)
        loop = asyncio.get_event_loop()
        all_sources, retrieval_errors = await loop.run_in_executor(None, self._retrieve_sources, expanded_queries)
        ranked = self._rank_sources(all_sources, prompt_text)
        top_sources = self._deduplicate(ranked)[:10]
        source_block = self._format_source_block(top_sources)
        ctx_block = ""
        if context:
            ctx_block = nl + nl + "Operator context:" + nl + json.dumps(context, indent=2)
        outline_msg = ("Research topic: " + prompt_text + nl + source_block + ctx_block + nl + nl + "Generate a 6-section document outline. Return ONLY valid JSON.")
        outline_raw = await client.generate(outline_msg, system_prompt=LONG_FORM_OUTLINE_SYSTEM, max_tokens=2048, temperature=0.3, response_format={"type": "json_object"})
        outline = self._extract_json(outline_raw)
        title = outline.get("title") or prompt_text
        abstract = outline.get("abstract") or ""
        sections_spec = outline.get("sections") or [{"heading": "Section " + str(i + 1), "brief": ""} for i in range(6)]
        conclusion_brief = outline.get("conclusion_brief") or ""
        section_tasks = [self._generate_section(client, prompt_text, source_block, sec, idx) for idx, sec in enumerate(sections_spec)]
        completed_sections = list(await asyncio.gather(*section_tasks))
        section_digest = (nl + nl).join("## " + s["heading"] + nl + s["content"][:400] + "..." for s in completed_sections)
        conclusion_msg = ("Document topic: " + prompt_text + nl + nl + "Conclusion brief: " + conclusion_brief + nl + nl + "Section contents:" + nl + section_digest + nl + nl + "Write the conclusion (400-500 words of flowing prose).")
        try:
            conclusion = (await client.generate(conclusion_msg, system_prompt=LONG_FORM_CONCLUSION_SYSTEM, max_tokens=1024, temperature=0.4)).strip()
        except Exception as exc:
            logger.warning("Conclusion failed: %s", exc); conclusion = ""
        normalized_sources = self._normalize_sources(top_sources)
        word_count = len(abstract.split()) + sum(len(s["content"].split()) for s in completed_sections) + len(conclusion.split())
        docx_filename = None
        try:
            docx_filename = self._generate_docx(title, abstract, completed_sections, conclusion, normalized_sources, prompt_text)
        except Exception as exc:
            logger.warning("DOCX skipped: %s", exc)
        return {"artifact_type": "long_form_research", "title": title, "abstract": abstract, "sections": completed_sections, "conclusion": conclusion, "sources": normalized_sources, "word_count": word_count, "docx_filename": docx_filename, "retrieval_errors": retrieval_errors or [], "executive_summary": abstract}

    def _generate_docx(self, title, abstract, sections, conclusion, sources, query):
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            import os as _os
            from datetime import datetime as _dt
            doc = Document()
            ns = doc.styles["Normal"]; ns.font.name = "Calibri"; ns.font.size = Pt(11)
            h = doc.add_heading(title, level=0); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in h.runs: run.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)
            meta = doc.add_paragraph(); meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
            mr = meta.add_run("MammothOS Research  " + chr(0xb7) + "  " + _dt.now().strftime("%B %d, %Y"))
            mr.font.size = Pt(10); mr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            doc.add_paragraph()
            nl = chr(10)
            if abstract:
                doc.add_heading("Abstract", level=2)
                ap = doc.add_paragraph(abstract)
                for run in ap.runs: run.font.italic = True
                doc.add_paragraph()
            for sec in sorted(sections, key=lambda s: s.get("order", 0)):
                doc.add_heading(sec["heading"], level=1)
                for para_text in sec["content"].split(nl + nl):
                    if para_text.strip(): doc.add_paragraph(para_text.strip())
                doc.add_paragraph()
            if conclusion:
                doc.add_heading("Conclusion", level=1)
                for para_text in conclusion.split(nl + nl):
                    if para_text.strip(): doc.add_paragraph(para_text.strip())
                doc.add_paragraph()
            if sources:
                doc.add_heading("Sources & References", level=1)
                for i, src in enumerate(sources, 1):
                    src_title = src.get("title") or src.get("label") or "Source " + str(i)
                    src_url = src.get("url") or src.get("source") or ""
                    doc.add_paragraph("[S" + str(i) + "] " + src_title + (" -- " + src_url if src_url else ""), style="List Number")
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:60].strip().replace(" ", "_")
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            filename = "mammoth_research_" + safe_title + "_" + ts + ".docx"
            out_dir = "/opt/mammothos/mammoth_intro_ai/generated_docs"
            _os.makedirs(out_dir, exist_ok=True); doc.save(_os.path.join(out_dir, filename))
            logger.info("DOCX saved: %s", filename); return filename
        except ImportError: logger.warning("python-docx not installed"); return None
        except Exception as exc: logger.error("DOCX error: %s", exc); return None

    def _fetch_duckduckgo(self, query: str) -> Tuple[List[Dict], Optional[str]]:
        """Scrape DuckDuckGo HTML search — no API key, returns real results."""
        import re as _re
        import hashlib as _hash
        results: List[Dict] = []
        try:
            encoded_q = urllib.parse.quote(query[:140])
            url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "identity",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            # Parse result titles, snippets, and urls from DDG HTML response
            titles   = _re.findall(r'class="result__a"[^>]*>([^<]{5,200})</', html)
            # Snippets may contain inner tags (<b> etc) — capture full innerHTML then strip
            raw_snips = _re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, _re.DOTALL)
            snippets  = [_re.sub(r'<[^>]+>', '', s).strip() for s in raw_snips]
            url_hits  = _re.findall(r'class="result__url"[^>]*>\s*([^\s<]{5,200})\s*</', html)
            for i, snippet in enumerate(snippets[:5]):
                snippet = snippet.strip()
                if not snippet or len(snippet) < 15:
                    continue
                title    = (titles[i].strip()    if i < len(titles)   else query[:60])
                url_hint = (url_hits[i].strip()  if i < len(url_hits) else "")
                results.append({
                    "id": f"ddg-{_hash.md5(snippet[:50].encode()).hexdigest()[:8]}",
                    "title": title[:120],
                    "snippet": snippet[:600],
                    "source": "DuckDuckGo",
                    "url": url_hint,
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
            text_raw = str(prompt or "").strip()
            # ── try JSON-string payload unwrap ────────────────────────────────
            if text_raw.startswith("{"):
                try:
                    import json as _jj
                    d = _jj.loads(text_raw)
                    if isinstance(d, dict):
                        text = str(
                            d.get("query") or d.get("topic") or d.get("prompt") or
                            d.get("task") or d.get("content") or ""
                        ).strip()
                        intent = str(d.get("intent") or d.get("mode") or "research").strip()
                        ctx = d.get("context") or {}
                        return text or text_raw, intent, ctx
                except Exception:
                    pass
            text = text_raw
            intent = "research"
            ctx = {}
        return text, intent, ctx

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        text = str(raw or "").strip()
        # Strip markdown code fences (deepseek wraps JSON in ```json...```)
        import re as _re
        text = _re.sub(r"```(?:json)?\s*", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            # ── truncation repair: close any unclosed arrays/objects ──────────
            try:
                stack = []
                in_str = False
                esc = False
                for ch in candidate:
                    if esc:
                        esc = False; continue
                    if ch == "\\" and in_str:
                        esc = True; continue
                    if ch == "\"":
                        in_str = not in_str; continue
                    if not in_str:
                        if ch in "{[":
                            stack.append("}" if ch == "{" else "]")
                        elif ch in "}]":
                            if stack and stack[-1] == ch:
                                stack.pop()
                repaired = candidate + "".join(reversed(stack))
                return json.loads(repaired)
            except Exception:
                pass
        return {
            "title": "Research Output",
            "executive_summary": text if text else "Unable to parse LLM response.",
            "_raw_unparsed": True,
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
