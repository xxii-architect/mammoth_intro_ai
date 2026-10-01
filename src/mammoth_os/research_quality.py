"""Research output hygiene: reasoning-leak stripping, source relevance, dedupe, completeness.

Pure functions only (no network, no model calls) so the research pipeline stays
testable without a provider and the same rules can be reused by other agents.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_REASONING_TAGS = ("think", "thinking", "reasoning", "reflection", "scratchpad")
_CLOSED_BLOCK_RE = re.compile(
    r"<(%s)\b[^>]*>.*?</\1\s*>" % "|".join(_REASONING_TAGS), re.IGNORECASE | re.DOTALL
)
_OPEN_TAG_RE = re.compile(r"<(%s)\b[^>]*>" % "|".join(_REASONING_TAGS), re.IGNORECASE)
_CLOSE_TAG_RE = re.compile(r"</(%s)\s*>" % "|".join(_REASONING_TAGS), re.IGNORECASE)

# Lines a model emits *about* the task rather than as part of the deliverable.
_PREAMBLE_RE = re.compile(
    r"^\s*(?:"
    r"(?:okay|ok|alright|sure|certainly|absolutely|of course|great)[,.!:]?\s.*"
    r"|(?:here(?:'s| is| are)\b).*:\s*"
    r"|(?:let me|let's|i'll|i will|i need to|i should|first,? i)\b.*"
    r"|(?:below is|the following is)\b.*:\s*"
    r")$",
    re.IGNORECASE,
)
_POSTAMBLE_RE = re.compile(
    r"^\s*(?:let me know\b.*|i hope (?:this|that)\b.*|feel free to\b.*|would you like\b.*\?"
    r"|\(?word count[:\s].*|\[?end of section\]?\.?)\s*$",
    re.IGNORECASE,
)

_TERMINAL_RE = re.compile(r"[.!?…\"'”’)\]]\s*$")
_SENTENCE_END_RE = re.compile(r"[.!?…][\"'”’)\]]*(?=\s|$)")

_STOPWORDS = frozenset(
    "the a an of and or in on at to for with from by is are was were be been being have has had do does did "
    "will would could should may might can shall what how why when where who which about into over under "
    "this that these those it its as than then vs versus i me my we our you your their they them".split()
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")
_DISAMBIGUATION_RE = re.compile(r"\bmay (?:also )?refer to\b|\(disambiguation\)|\bdisambiguation page\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Reasoning / meta-commentary stripping
# ---------------------------------------------------------------------------

def strip_reasoning(text: Any) -> Tuple[str, str]:
    """Remove model reasoning blocks and task meta-commentary.

    Returns ``(clean_text, trace)`` where ``trace`` holds the removed reasoning
    so it can be surfaced separately (never mixed into the deliverable).
    """
    raw = str(text or "")
    traces: List[str] = []

    def _collect(match: "re.Match[str]") -> str:
        inner = _OPEN_TAG_RE.sub("", _CLOSE_TAG_RE.sub("", match.group(0))).strip()
        if inner:
            traces.append(inner)
        return ""

    clean = _CLOSED_BLOCK_RE.sub(_collect, raw)

    # Dangling close tag: everything before it was reasoning.
    close = None
    for close in _CLOSE_TAG_RE.finditer(clean):
        pass
    if close is not None:
        head = _OPEN_TAG_RE.sub("", clean[: close.start()]).strip()
        if head:
            traces.append(head)
        clean = clean[close.end():]

    # Dangling open tag (output truncated mid-reasoning): drop the rest.
    opener = _OPEN_TAG_RE.search(clean)
    if opener:
        tail = clean[opener.end():].strip()
        if tail:
            traces.append(tail)
        clean = clean[: opener.start()]

    clean = _strip_meta_lines(clean.strip())
    return clean, "\n\n".join(traces).strip()


def _strip_meta_lines(text: str) -> str:
    lines = text.splitlines()
    # leading preambles (at most 2 lines, and only if real content follows)
    for _ in range(2):
        while lines and not lines[0].strip():
            lines.pop(0)
        if len(lines) > 1 and _PREAMBLE_RE.match(lines[0]) and len(lines[0]) < 200:
            lines.pop(0)
        else:
            break
    # trailing sign-offs
    for _ in range(2):
        while lines and not lines[-1].strip():
            lines.pop()
        if len(lines) > 1 and _POSTAMBLE_RE.match(lines[-1]):
            lines.pop()
        else:
            break
    return "\n".join(lines).strip()


def strip_echoed_heading(text: str, heading: str) -> str:
    """Drop a first line that just repeats the section heading."""
    if not text or not heading:
        return text
    lines = text.splitlines()
    first = re.sub(r"^[#*\s]+|[*:\s]+$", "", lines[0]).strip().lower()
    if first and first == heading.strip().lower():
        return "\n".join(lines[1:]).strip()
    return text


def clean_string_fields(value: Any) -> Any:
    """Recursively strip reasoning tags from every string in a parsed payload."""
    if isinstance(value, str):
        if _OPEN_TAG_RE.search(value) or _CLOSE_TAG_RE.search(value):
            return strip_reasoning(value)[0]
        return value
    if isinstance(value, list):
        return [clean_string_fields(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_string_fields(item) for key, item in value.items()}
    return value


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

def is_truncated(text: str) -> bool:
    stripped = (text or "").rstrip()
    return bool(stripped) and not _TERMINAL_RE.search(stripped)


def trim_to_last_sentence(text: str, *, min_keep_ratio: float = 0.5) -> Tuple[str, bool]:
    """Cut a truncated passage back to its last complete sentence.

    Returns ``(text, trimmed)``. If trimming would discard more than
    ``1 - min_keep_ratio`` of the text, the original is returned untouched.
    """
    stripped = (text or "").rstrip()
    if not is_truncated(stripped):
        return stripped, False
    ends = list(_SENTENCE_END_RE.finditer(stripped))
    if not ends:
        return stripped, False
    cut = ends[-1].end()
    if cut < len(stripped) * min_keep_ratio:
        return stripped, False
    return stripped[:cut].rstrip(), True


# ---------------------------------------------------------------------------
# Source relevance + entity disambiguation
# ---------------------------------------------------------------------------

def keywords(text: str) -> List[str]:
    return [tok for tok in _TOKEN_RE.findall(str(text or "").lower()) if tok not in _STOPWORDS and len(tok) > 1]


_SUFFIXES = ("ations", "ation", "ings", "ers", "ing", "ies", "ed", "es", "er", "ly", "s")


def stem(token: str) -> str:
    """Very light suffix stripping so "learners" and "learning" share a stem."""
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def stems(text: str) -> set:
    return {stem(tok) for tok in keywords(text)}


def entity_terms(query: str) -> List[List[str]]:
    """Quoted phrases and Capitalized multi-word names from the query, as token lists."""
    phrases = [match.strip() for match in re.findall(r"\"([^\"]{2,80})\"", query or "")]
    phrases += re.findall(r"\b(?:[A-Z][\w&'\-]*|[A-Z]{2,})(?:\s+(?:[A-Z][\w&'\-]*|[A-Z]{2,}|of|the|and|&))+\b", query or "")
    seen: List[List[str]] = []
    for phrase in phrases:
        toks = keywords(phrase)
        if len(toks) >= 2 and toks not in seen:
            seen.append(toks)
    return seen


def is_disambiguation(source: Dict[str, Any]) -> bool:
    return bool(_DISAMBIGUATION_RE.search(f"{source.get('title', '')} {source.get('snippet', '')[:300]}"))


def filter_relevant_sources(
    sources: Sequence[Dict[str, Any]],
    query: str,
    *,
    min_overlap: int = 1,
    min_strong: int = 2,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split sources into ``(kept, dropped)``.

    Always drops disambiguation pages. Sources sharing fewer than ``min_overlap``
    content keywords with the query are dropped only when at least
    ``min_strong`` on-topic sources exist; otherwise they are kept last and
    marked ``relevance: "weak"`` (related concepts often share no words). When the query names an entity (quoted
    phrase / multi-word proper noun), sources that don't mention it in full are
    demoted below those that do (never dropped: the entity may be a qualifier).
    User-provided sources are always kept.
    """
    query_terms = stems(query)
    entities = [[stem(tok) for tok in entity] for entity in entity_terms(query)]
    kept_scored: List[Tuple[float, int, Dict[str, Any]]] = []
    weak: List[Tuple[int, Dict[str, Any]]] = []
    dropped: List[Dict[str, Any]] = []
    for index, source in enumerate(sources or []):
        if not isinstance(source, dict):
            continue
        if source.get("source_type") == "provided":
            kept_scored.append((float("inf"), index, source))
            continue
        if is_disambiguation(source):
            dropped.append({**source, "drop_reason": "disambiguation_page"})
            continue
        text_terms = stems(f"{source.get('title', '')} {source.get('snippet', '')}")
        overlap = len(query_terms & text_terms) if query_terms else min_overlap
        if overlap < min_overlap:
            weak.append((index, source))
            continue
        score = float(source.get("relevance_score") or 0.0)
        if entities and not any(all(tok in text_terms for tok in entity) for entity in entities):
            score *= 0.5
            source = {**source, "entity_match": "partial"}
        kept_scored.append((score, index, source))
    kept_scored.sort(key=lambda row: (-row[0], row[1]))
    kept = [row[2] for row in kept_scored]
    if len(kept) >= min_strong:
        dropped.extend({**source, "drop_reason": "off_topic"} for _, source in weak)
    else:
        kept.extend({**source, "relevance": "weak"} for _, source in weak)
    return kept, dropped


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------

def _similar(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedupe_items(
    items: Iterable[Any],
    *,
    text_of=lambda item: item if isinstance(item, str) else str((item or {}).get("content") or (item or {}).get("claim") or (item or {}).get("heading") or ""),
    threshold: float = 0.8,
) -> List[Any]:
    kept: List[Any] = []
    signatures: List[set] = []
    for item in items or []:
        sig = set(keywords(text_of(item)))
        if sig and any(_similar(sig, other) >= threshold for other in signatures):
            continue
        kept.append(item)
        if sig:
            signatures.append(sig)
    return kept


def dedupe_sections(sections: List[Dict[str, Any]], *, threshold: float = 0.75) -> Tuple[List[Dict[str, Any]], int]:
    """Remove paragraphs that repeat an earlier paragraph anywhere in the document.

    Returns ``(sections, removed_count)``. A section is never emptied entirely;
    its first paragraph is retained if every paragraph was a repeat.
    """
    seen: List[set] = []
    removed = 0
    output: List[Dict[str, Any]] = []
    for section in sections:
        paragraphs = [p for p in re.split(r"\n\s*\n", str(section.get("content") or "")) if p.strip()]
        kept: List[str] = []
        for paragraph in paragraphs:
            sig = set(keywords(paragraph))
            if len(sig) >= 8 and any(_similar(sig, other) >= threshold for other in seen):
                removed += 1
                continue
            kept.append(paragraph.strip())
            if sig:
                seen.append(sig)
        if not kept and paragraphs:
            kept = [paragraphs[0].strip()]
            removed -= 1
        output.append({**section, "content": "\n\n".join(kept)})
    return output, max(0, removed)


def fallback_section_headings(topic: str, count: int = 6) -> List[str]:
    """Topic-neutral, topic-specific headings used only when the outline fails."""
    short = re.sub(r"\s+", " ", str(topic or "the topic")).strip().rstrip("?.!")
    if len(short) > 60:
        short = short[:60].rsplit(" ", 1)[0]
    angles = [
        f"The Current Landscape of {short}",
        f"How {short} Works in Practice",
        f"Evidence and Data on {short}",
        f"Implications for Decision-Makers",
        f"Risks, Limits, and Open Questions",
        f"Outlook: Where {short} Is Heading",
    ]
    return angles[:count] + [f"Further Analysis {i + 1}" for i in range(max(0, count - len(angles)))]


__all__ = [
    "clean_string_fields",
    "dedupe_items",
    "dedupe_sections",
    "entity_terms",
    "fallback_section_headings",
    "filter_relevant_sources",
    "is_disambiguation",
    "is_truncated",
    "keywords",
    "stem",
    "stems",
    "strip_echoed_heading",
    "strip_reasoning",
    "trim_to_last_sentence",
]
