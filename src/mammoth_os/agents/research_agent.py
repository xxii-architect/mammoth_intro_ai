# mammoth_os/agents/research_agent.py

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Tuple

from .base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    """Source-grounded research agent for structured, citation-backed reports."""

    name = "ResearchAgent"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: Any) -> Dict[str, Any]:
        request = self._normalize_request(prompt)
        objective = request["objective"]
        focus = request["focus"]

        external_sources, retrieval_errors = self._gather_external_sources(
            objective=objective,
            max_sources=request["max_sources"],
            allow_web_lookup=request["allow_web_lookup"],
            provided_sources=request["provided_sources"],
        )
        ranked_sources = self._rank_sources(objective, external_sources)
        contradiction_report = self._cross_source_contradictions(objective, ranked_sources)
        citations, references = self._build_citations_and_references(objective, focus, ranked_sources)
        findings = self._build_findings(objective, focus, ranked_sources)
        citation_coverage = self._citation_coverage(findings)
        quality_flags = self._quality_flags(ranked_sources, retrieval_errors, citation_coverage, contradiction_report)
        confidence = self._estimate_confidence(
            focus,
            objective,
            ranked_sources,
            citation_coverage,
            retrieval_errors,
            contradiction_report,
        )

        return {
            "status": "ok",
            "agent": self.name,
            "mode": "source_grounded_research_v2",
            "prompt": objective,
            "focus": focus,
            "summary": self._build_summary(objective, focus, external_sources),
            "research_questions": self._build_research_questions(objective, focus),
            "considerations": self._build_considerations(objective, focus),
            "next_actions": self._build_next_actions(focus),
            "findings": findings,
            "citations": citations,
            "references": references,
            "sources": ranked_sources,
            "ranked_sources": ranked_sources,
            "contradiction_report": contradiction_report,
            "source_coverage": {
                "source_count": len(ranked_sources),
                "citation_coverage": citation_coverage,
                "fully_supported_claims": int(round(citation_coverage * len(findings))) if findings else 0,
                "total_claims": len(findings),
            },
            "quality_flags": quality_flags,
            "confidence": confidence,
            "assumptions": self._build_assumptions(focus),
            "workflow_hints": {
                "needs_validation": "verify" in objective.lower() or "test" in objective.lower(),
                "supports_curriculum": "lesson" in objective.lower() or "curriculum" in objective.lower(),
                "supports_fieldwork": any(token in objective.lower() for token in ("survival", "plant", "field", "outdoor")),
                "web_lookup_enabled": request["allow_web_lookup"],
                "contradiction_scan_enabled": True,
            },
            "retrieval_errors": retrieval_errors,
        }

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        payload = dict(details or {})
        if "prompt" not in payload:
            payload["prompt"] = str(target or "").strip()
        return {
            **self.run(payload),
            "action": action_type,
            "target": target,
            "details": details,
        }

    def _normalize_request(self, prompt: Any) -> Dict[str, Any]:
        if isinstance(prompt, dict):
            objective = str(prompt.get("prompt") or prompt.get("objective") or prompt.get("topic") or "").strip()
            focus = str(prompt.get("focus") or self._infer_focus(objective)).strip().lower()
            max_sources = int(prompt.get("max_sources") or 5)
            allow_web_lookup = bool(prompt.get("allow_web_lookup", True))
            provided_sources = prompt.get("sources") if isinstance(prompt.get("sources"), list) else []
            return {
                "objective": objective or "current objective",
                "focus": focus or self._infer_focus(objective),
                "max_sources": max(1, min(8, max_sources)),
                "allow_web_lookup": allow_web_lookup,
                "provided_sources": provided_sources,
            }

        text = str(prompt or "").strip()
        parsed = self._parse_json_payload(text)
        if parsed:
            return self._normalize_request(parsed)

        objective = text or "current objective"
        return {
            "objective": objective,
            "focus": self._infer_focus(objective),
            "max_sources": 5,
            "allow_web_lookup": True,
            "provided_sources": [],
        }

    def _parse_json_payload(self, text: str) -> Dict[str, Any] | None:
        candidate = str(text or "").strip()
        if not candidate.startswith("{"):
            return None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _infer_focus(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if any(token in prompt_lower for token in ("lesson", "curriculum", "module", "learner")):
            return "curriculum"
        if any(token in prompt_lower for token in ("survival", "plant", "field", "navigation", "weather")):
            return "field_ops"
        if any(token in prompt_lower for token in ("gear", "compare", "market", "audience", "pricing")):
            return "market_intel"
        if any(token in prompt_lower for token in ("code", "build", "implement", "feature", "ui")):
            return "coding"
        return "general"

    def _gather_external_sources(
        self,
        *,
        objective: str,
        max_sources: int,
        allow_web_lookup: bool,
        provided_sources: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        normalized = self._normalize_provided_sources(provided_sources)
        errors: List[str] = []
        if len(normalized) >= max_sources or not allow_web_lookup:
            return normalized[:max_sources], errors

        needed = max_sources - len(normalized)
        web_sources, web_errors = self._lookup_web_sources(objective, needed)
        normalized.extend(web_sources)
        errors.extend(web_errors)
        if not normalized:
            normalized.append(self._build_prompt_source(objective))
        return normalized[:max_sources], errors

    def _build_prompt_source(self, objective: str) -> Dict[str, Any]:
        return {
            "id": "src-prompt-1",
            "title": "Prompt objective",
            "url": "",
            "snippet": objective[:600],
            "publisher": "mammoth_runtime",
            "source_type": "prompt",
            "accessed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _normalize_provided_sources(self, provided_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        accessed_at = datetime.now(timezone.utc).isoformat()
        for idx, source in enumerate(provided_sources):
            if not isinstance(source, dict):
                continue
            title = str(source.get("title") or source.get("label") or f"Provided Source {idx + 1}").strip()
            url = str(source.get("url") or source.get("source") or "").strip()
            snippet = str(source.get("snippet") or source.get("summary") or source.get("quote") or "").strip()
            if not snippet and not url:
                continue
            normalized.append(
                {
                    "id": f"src-provided-{idx + 1}",
                    "title": title or f"Provided Source {idx + 1}",
                    "url": url,
                    "snippet": snippet[:600],
                    "publisher": str(source.get("publisher") or source.get("domain") or "provided").strip() or "provided",
                    "source_type": "provided",
                    "accessed_at": str(source.get("accessed_at") or accessed_at),
                }
            )
        return normalized

    def _lookup_web_sources(self, objective: str, max_sources: int) -> Tuple[List[Dict[str, Any]], List[str]]:
        sources: List[Dict[str, Any]] = []
        errors: List[str] = []
        for fetcher in (self._fetch_wikipedia_summary, self._fetch_duckduckgo_summary):
            if len(sources) >= max_sources:
                break
            fetched, err = fetcher(objective)
            if fetched:
                sources.extend(fetched[: max_sources - len(sources)])
            if err:
                errors.append(err)
        return sources[:max_sources], errors

    def _fetch_wikipedia_summary(self, objective: str) -> Tuple[List[Dict[str, Any]], str | None]:
        query = urllib.parse.quote(objective[:120])
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "MammothOS/1.0 ResearchAgent"})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return [], f"wikipedia_http_error:{exc.code}"
        except urllib.error.URLError as exc:
            return [], f"wikipedia_network_error:{exc.reason}"
        except (TimeoutError, ValueError) as exc:
            return [], f"wikipedia_parse_error:{exc}"

        extract = str(payload.get("extract") or "").strip()
        content_urls = payload.get("content_urls") if isinstance(payload.get("content_urls"), dict) else {}
        desktop = content_urls.get("desktop") if isinstance(content_urls.get("desktop"), dict) else {}
        page_url = str(desktop.get("page") or "").strip()
        title = str(payload.get("title") or objective).strip() or objective
        if not extract:
            return [], "wikipedia_empty_extract"
        return (
            [
                {
                    "id": "src-web-wikipedia-1",
                    "title": title,
                    "url": page_url,
                    "snippet": extract[:600],
                    "publisher": "Wikipedia",
                    "source_type": "web",
                    "accessed_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            None,
        )

    def _fetch_duckduckgo_summary(self, objective: str) -> Tuple[List[Dict[str, Any]], str | None]:
        query = urllib.parse.quote(objective[:140])
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "MammothOS/1.0 ResearchAgent"})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return [], f"duckduckgo_http_error:{exc.code}"
        except urllib.error.URLError as exc:
            return [], f"duckduckgo_network_error:{exc.reason}"
        except (TimeoutError, ValueError) as exc:
            return [], f"duckduckgo_parse_error:{exc}"

        abstract = str(payload.get("AbstractText") or "").strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        heading = str(payload.get("Heading") or objective).strip()
        if not abstract:
            return [], "duckduckgo_empty_abstract"
        return (
            [
                {
                    "id": "src-web-duckduckgo-1",
                    "title": heading or objective,
                    "url": abstract_url,
                    "snippet": abstract[:600],
                    "publisher": "DuckDuckGo Instant Answer",
                    "source_type": "web",
                    "accessed_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            None,
        )

    def _build_findings(self, objective: str, focus: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        claim_stems = self._claim_templates(objective, focus)
        source_ids = [str(source.get("id") or "") for source in sources if source.get("id")]
        findings: List[Dict[str, Any]] = []
        for idx, claim in enumerate(claim_stems, start=1):
            linked = source_ids[: min(len(source_ids), 2)] if source_ids else []
            findings.append(
                {
                    "id": f"finding-{idx}",
                    "claim": claim,
                    "supporting_source_ids": linked,
                    "support_level": "strong" if len(linked) >= 2 else "moderate" if len(linked) == 1 else "unverified",
                }
            )
        return findings

    def _rank_sources(self, objective: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        objective_tokens = self._tokenize(objective)
        ranked: List[Dict[str, Any]] = []
        for source in sources:
            snippet = str(source.get("snippet") or "")
            title = str(source.get("title") or "")
            source_type = str(source.get("source_type") or "")
            publisher = str(source.get("publisher") or "")
            snippet_tokens = self._tokenize(f"{title} {snippet}")
            token_overlap = len(objective_tokens.intersection(snippet_tokens))
            token_denominator = max(1, len(objective_tokens))
            relevance = min(1.0, token_overlap / token_denominator)
            depth = min(1.0, len(snippet) / 260.0)
            authority = 0.65
            if source_type == "provided":
                authority = 0.85
            elif source_type == "web":
                authority = 0.76
            if publisher.lower() == "wikipedia":
                authority = max(authority, 0.8)
            score = round((relevance * 0.45) + (depth * 0.25) + (authority * 0.30), 4)
            ranked.append(
                {
                    **source,
                    "evidence_score": score,
                    "relevance_score": round(relevance, 4),
                    "depth_score": round(depth, 4),
                    "authority_score": round(authority, 4),
                    "matched_tokens": sorted(objective_tokens.intersection(snippet_tokens))[:12],
                }
            )
        ranked.sort(key=lambda item: float(item.get("evidence_score") or 0.0), reverse=True)
        return ranked

    def _cross_source_contradictions(self, objective: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        polarity_pairs = [
            ("increase", "decrease"),
            ("recommended", "not recommended"),
            ("safe", "unsafe"),
            ("effective", "ineffective"),
            ("required", "optional"),
            ("high", "low"),
        ]
        objective_tokens = self._tokenize(objective)
        source_tokens: Dict[str, Set[str]] = {}
        for source in sources:
            sid = str(source.get("id") or "")
            source_tokens[sid] = self._tokenize(
                f"{source.get('title') or ''} {source.get('snippet') or ''}"
            )

        contradictions: List[Dict[str, Any]] = []
        for idx, left in enumerate(sources):
            left_id = str(left.get("id") or "")
            left_tokens = source_tokens.get(left_id, set())
            if not left_tokens:
                continue
            left_goal_overlap = objective_tokens.intersection(left_tokens)
            for right in sources[idx + 1:]:
                right_id = str(right.get("id") or "")
                right_tokens = source_tokens.get(right_id, set())
                if not right_tokens:
                    continue
                right_goal_overlap = objective_tokens.intersection(right_tokens)
                if not left_goal_overlap and not right_goal_overlap:
                    continue
                for positive, negative in polarity_pairs:
                    has_pos_left = positive in left_tokens and negative not in left_tokens
                    has_neg_left = negative in left_tokens and positive not in left_tokens
                    has_pos_right = positive in right_tokens and negative not in right_tokens
                    has_neg_right = negative in right_tokens and positive not in right_tokens
                    if (has_pos_left and has_neg_right) or (has_neg_left and has_pos_right):
                        contradictions.append(
                            {
                                "term_pair": [positive, negative],
                                "left_source_id": left_id,
                                "right_source_id": right_id,
                                "left_label": str(left.get("title") or left_id),
                                "right_label": str(right.get("title") or right_id),
                            }
                        )
                        break

        total_pairs = max(1, math.comb(len(sources), 2) if len(sources) >= 2 else 1)
        contradiction_count = len(contradictions)
        alignment_score = round(max(0.0, 1.0 - (contradiction_count / total_pairs)), 2)
        status = "aligned"
        if contradiction_count > 0:
            status = "mixed"
        if contradiction_count >= 2:
            status = "contested"
        return {
            "status": status,
            "alignment_score": alignment_score,
            "contradiction_count": contradiction_count,
            "pairs_checked": total_pairs,
            "contradictions": contradictions[:8],
        }

    def _claim_templates(self, objective: str, focus: str) -> List[str]:
        base = [
            f"The core objective for '{objective}' should be framed as a measurable decision with explicit constraints.",
            "Any recommendation should separate observed evidence from assumptions and identify unresolved gaps.",
        ]
        if focus == "curriculum":
            base.append("Curriculum recommendations should map to learner checkpoints and retention-oriented examples.")
        elif focus == "field_ops":
            base.append("Field recommendations should prioritize safety conditions, abort criteria, and observable checkpoints.")
        elif focus == "market_intel":
            base.append("Market recommendations should include concrete demand signals and confidence caveats.")
        elif focus == "coding":
            base.append("Engineering recommendations should prefer small, testable changes tied to explicit validation.")
        else:
            base.append("General recommendations should remain scoped, testable, and source-attributed.")
        return base[:3]

    def _build_citations_and_references(
        self,
        objective: str,
        focus: str,
        sources: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        citations: List[Dict[str, Any]] = []
        references: List[Dict[str, Any]] = []
        for source in sources:
            sid = str(source.get("id") or "")
            title = str(source.get("title") or "Source").strip() or "Source"
            snippet = str(source.get("snippet") or "").strip()
            citations.append(
                {
                    "source_id": sid,
                    "label": title,
                    "quote": snippet[:220],
                    "why_it_matters": f"Supports the {focus} research direction for '{objective[:120]}'.",
                }
            )
            references.append(
                {
                    "source_id": sid,
                    "title": title,
                    "url": str(source.get("url") or "").strip(),
                    "publisher": str(source.get("publisher") or "unknown"),
                    "source_type": str(source.get("source_type") or "unknown"),
                    "accessed_at": str(source.get("accessed_at") or ""),
                }
            )
        return citations, references

    def _citation_coverage(self, findings: List[Dict[str, Any]]) -> float:
        if not findings:
            return 0.0
        supported = 0
        for finding in findings:
            links = finding.get("supporting_source_ids")
            if isinstance(links, list) and any(str(item).strip() for item in links):
                supported += 1
        return round(supported / len(findings), 2)

    def _quality_flags(
        self,
        sources: List[Dict[str, Any]],
        retrieval_errors: List[str],
        citation_coverage: float,
        contradiction_report: Dict[str, Any],
    ) -> List[str]:
        flags: List[str] = []
        external_source_count = len([source for source in sources if str(source.get("source_type") or "") in {"web", "provided"}])
        if external_source_count == 0:
            flags.append("missing_external_sources")
        if citation_coverage < 1.0:
            flags.append("incomplete_citation_coverage")
        if retrieval_errors:
            flags.append("retrieval_errors_present")
        if int(contradiction_report.get("contradiction_count") or 0) > 0:
            flags.append("cross_source_conflicts_detected")
        if float(contradiction_report.get("alignment_score") or 0) >= 0.8 and external_source_count >= 2:
            flags.append("cross_source_consensus_strong")
        if len(sources) >= 2:
            flags.append("evidence_ranked")
        if len(sources) >= 3 and citation_coverage >= 0.66:
            flags.append("source_grounding_acceptable")
        return flags

    def _estimate_confidence(
        self,
        focus: str,
        prompt: str,
        sources: List[Dict[str, Any]],
        citation_coverage: float,
        retrieval_errors: List[str],
        contradiction_report: Dict[str, Any],
    ) -> float:
        base = 0.56
        if focus == "curriculum":
            base += 0.08
        elif focus == "coding":
            base += 0.1
        elif focus == "market_intel":
            base += 0.08
        elif focus == "field_ops":
            base += 0.06
        base += min(0.22, len(sources) * 0.05)
        base += min(0.16, citation_coverage * 0.16)
        base += min(0.08, float(contradiction_report.get("alignment_score") or 0) * 0.08)
        if retrieval_errors:
            base -= min(0.12, len(retrieval_errors) * 0.04)
        contradiction_count = int(contradiction_report.get("contradiction_count") or 0)
        if contradiction_count:
            base -= min(0.14, contradiction_count * 0.05)
        if "verify" in prompt.lower() or "test" in prompt.lower():
            base += 0.04
        return round(min(0.97, max(0.35, base)), 2)

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        tokens = {token for token in re.findall(r"[a-z0-9]{3,}", str(text or "").lower())}
        return {token for token in tokens if token not in {"with", "from", "that", "this", "should", "could", "would"}}

    def _build_summary(self, prompt: str, focus: str, sources: List[Dict[str, Any]]) -> str:
        source_hint = f"{len(sources)} sourced reference(s)" if sources else "no external references yet"
        if focus == "curriculum":
            return f"Research brief for {prompt}: curriculum recommendations with {source_hint}."
        if focus == "field_ops":
            return f"Research brief for {prompt}: field-safe operational guidance with {source_hint}."
        if focus == "market_intel":
            return f"Research brief for {prompt}: market signal framing with {source_hint}."
        if focus == "coding":
            return f"Research brief for {prompt}: implementation-focused analysis with {source_hint}."
        return f"Research brief for {prompt}: scoped findings and references with {source_hint}."

    def _build_research_questions(self, prompt: str, focus: str) -> List[str]:
        base = [
            f"What is the concrete decision behind '{prompt}'?",
            "Which assumptions still need source-backed validation?",
        ]
        if focus == "curriculum":
            return base + ["Which source-backed checkpoint best predicts learner readiness?"]
        if focus == "field_ops":
            return base + ["Which environmental constraints have the strongest evidence impact?"]
        if focus == "market_intel":
            return base + ["Which demand signal is strongest across references, and which is weakest?"]
        if focus == "coding":
            return base + ["What is the smallest implementation path supported by evidence?"]
        return base + ["What measurable outcome should this research drive next?"]

    def _build_assumptions(self, focus: str) -> List[str]:
        assumptions = [
            "Source-backed claims should be preferred over uncited synthesis.",
            "Missing citations should be treated as unresolved evidence gaps.",
        ]
        if focus == "coding":
            assumptions.append("Validation-ready implementation steps are higher value than broad architecture speculation.")
        return assumptions

    def _build_considerations(self, prompt: str, focus: str) -> List[str]:
        base = [
            "Separate observed source signals from assumptions.",
            "Capture unresolved evidence gaps before final recommendations.",
        ]
        if focus == "curriculum":
            return base + ["Keep recommendations tied to learner progression and measurable checkpoints."]
        if focus == "field_ops":
            return base + ["Prioritize safety and abort criteria where source coverage is weak."]
        if focus == "market_intel":
            return base + ["Distinguish demand evidence from narrative or hype."]
        if focus == "coding":
            return base + ["Tie each recommendation to a concrete validation step."]
        return base + ["Keep the report concise, actionable, and source-attributed."]

    def _build_next_actions(self, focus: str) -> List[str]:
        mapping = {
            "curriculum": [
                "Map cited findings to lesson checkpoints.",
                "Draft a module update with source references inline.",
            ],
            "field_ops": [
                "Convert findings into a safety-first field checklist.",
                "Mark any unverified claims for operator review.",
            ],
            "market_intel": [
                "Turn top signal into a validation experiment.",
                "Add one additional source for weakest supported claim.",
            ],
            "coding": [
                "Translate findings into a smallest-viable patch plan.",
                "Define a targeted validation run per key claim.",
            ],
            "general": [
                "Publish a short report with references appendix.",
                "Queue follow-up research for unresolved evidence gaps.",
            ],
        }
        return mapping.get(focus, mapping["general"])
