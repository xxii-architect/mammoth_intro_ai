"""Retrieval context and citation checks; these do not prove factual entailment."""
import re
from typing import Any

from mammoth_os import research_quality as rq

_REFERENCE = re.compile(r"\b(?:this|that|(?:the\s+)?current|(?:the\s+)?active)\s+(?:curriculum|lesson|course|topic)\b", re.IGNORECASE)


def resolve_research_query(prompt: str, context: dict[str, Any]) -> str:
    if not _REFERENCE.search(prompt):
        return prompt
    lesson = context.get("lesson") or context.get("lesson_context") or {}
    if not isinstance(lesson, dict):
        return prompt
    subject = str(lesson.get("subject") or lesson.get("curriculum_title") or lesson.get("title") or "").strip()
    if not subject:
        return prompt
    return subject[:300] + " " + _REFERENCE.sub("subject", prompt)


def relevant_evidence_sources(sources: list[dict], query: str) -> tuple[list[dict], list[dict]]:
    generic = {"research", "curriculum", "lesson", "course", "learning", "topic", "subject", "deeper", "dive", "beginner"}
    domain_query = " ".join(word for word in re.split(r"\W+", query) if word.casefold() not in generic)
    relevant, dropped = rq.filter_relevant_sources(sources, domain_query, min_strong=0)
    usable = []
    for source in relevant:
        if not str(source.get("snippet") or "").strip():
            dropped.append({**source, "drop_reason": "missing_excerpt"})
        else:
            usable.append(source)
    return usable, dropped


def link_findings(findings: Any, sources: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    source_by_label = {source["label"]: source for source in sources}
    linked, unverified, issues = [], [], []
    if not isinstance(findings, list):
        return [], [], ["Model findings must be a list."]
    for index, value in enumerate(findings):
        if not isinstance(value, dict):
            issues.append(f"Finding {index + 1} is not structured.")
            continue
        text = str(value.get("content") or value.get("claim") or "").strip()
        if not text:
            issues.append(f"Finding {index + 1} has no claim text.")
            continue
        evidence = []
        entries = value.get("evidence") if isinstance(value.get("evidence"), list) else []
        invalid = False
        for item in entries:
            if not isinstance(item, dict):
                invalid = True
                continue
            label = str(item.get("source_id") or "").strip()
            quote = str(item.get("quote") or "").strip()
            source = source_by_label.get(label)
            excerpt = str(source.get("snippet") or source.get("excerpt") or "") if source else ""
            normalized_quote = " ".join(quote.split()).casefold()
            if not source or len(normalized_quote) < 20 or normalized_quote not in " ".join(excerpt.split()).casefold():
                invalid = True
                continue
            if not rq.stems(text) & rq.stems(quote):
                invalid = True
                continue
            evidence.append({"source_id": label, "quote": quote, "url": source.get("url", ""), "title": source["title"]})
        cited = set(re.findall(r"\[(S\d+)\]", text))
        support = {label for label in value.get("source_support", []) if isinstance(label, str)} if isinstance(value.get("source_support"), list) else set()
        if (cited | support) - {item["source_id"] for item in evidence}:
            invalid = True
        row = {**value, "content": text, "evidence": evidence, "source_support": sorted({item["source_id"] for item in evidence})}
        if evidence and not invalid:
            row["evidence_status"] = "source_linked"
            linked.append(row)
        else:
            row["evidence_status"] = "unverified"
            row["source_support"] = []
            row["evidence"] = []
            row["content"] = re.sub(r"\[(?:S\d+|llm_synthesized)\]", "", text).strip()
            unverified.append(row)
            issues.append(f"Finding {index + 1} lacks valid matching source excerpts.")
    return linked, unverified, issues
