"""Shared public-analysis guidance and validation, never a private thought trace."""
from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import Any, Coroutine

from mammoth_os.research_quality import dedupe_items, strip_reasoning, trim_to_last_sentence


_PROVIDER_ERROR = re.compile(
    r"\binsufficient_quota\b|\binvalid_api_key\b|\bquota_exceeded\b"
    r"|^\s*(?:rate limit|billing|authentication|provider)\s+(?:error|failed|exceeded)\b",
    re.I,
)

REASONING_GUIDANCE = """Analyze the actual question as a critical, constructive collaborator.
Do not treat every question as a lesson, debugging error, or personal-growth exercise.
Anchor the answer in details supplied by the user or observed evidence.
Distinguish observations, interpretations, assumptions, and unknowns. Consider a
plausible alternative explanation and what evidence would change the recommendation.
Keep divergent exploration separate from evidence evaluation. When useful, explore
abstract models, analogies, counterfactuals, unconventional options, and speculative
hypotheses. Label them as hypotheses or thought experiments, state the assumptions,
and suggest what could test or disconfirm them. Brainstorming does not require
citations; do not discard an idea merely because it has no published source.
Evidence rules apply when asserting factual claims or recommending real-world action.
Explain a proposed mechanism and tradeoffs without presenting speculation as fact;
do not manufacture novelty, certainty, emotions, or a diagnosis of the user.
Give a concrete next step or discriminating test where useful, not motivational slogans.
No canned praise, operator persona, or 'consistency beats intensity' filler.
For factual questions, use relevant primary sources first (official agencies for
the correct jurisdiction/date, institutional research, original studies, official
technical documentation). A domain or a citation is not proof: inspect the
supporting passage and distinguish source-linked claims from unverified claims.
Analysis of user-provided circumstances is interpretation, not externally verified fact.
If evidence is missing, name the gap instead of inventing support.
Share concise public rationale, not private chain-of-thought."""


def run_analysis_sync(coro: Coroutine[Any, Any, Any]) -> Any:
    """Support synchronous SDK calls both inside and outside an active event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(copy_context().run, asyncio.run, coro).result()


def validate_analysis(
    raw: Any, *, text_fields: tuple[str, ...], list_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Accept complete structured analysis only; reject echo and template fallbacks."""
    traces = []
    if isinstance(raw, str):
        if raw.startswith("[LOCAL_ADAPTER]"):
            raise ValueError("Analysis provider is offline")
        raw, trace = strip_reasoning(raw)
        if trace:
            traces.append(trace)
        if raw.startswith("```json\n") and raw.endswith("```"):
            raw = raw[8:-3].strip()
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError("Analysis must be a JSON object")

    def clean(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Analysis fields must be nonempty strings")
        text, trace = strip_reasoning(value)
        if trace:
            traces.append(trace)
        text, _ = trim_to_last_sentence(text)
        if not text.strip() or _PROVIDER_ERROR.search(text) or any(marker in text.casefold() for marker in (
            "[local_adapter]", "<2 sentence diagnosis>", "<action>",
            "consistency beats intensity", "struggle is a signal, not a setback",
            "small victories compound", "the learner likely needs one prerequisite",
        )) or text.strip().casefold() in {"check 1", "check 2", "check 3"}:
            raise ValueError("Analysis contains placeholder content")
        return text.strip()

    result: dict[str, Any] = {key: clean(raw.get(key)) for key in text_fields}
    for key in list_fields:
        values = raw.get(key)
        if not isinstance(values, list) or not values:
            raise ValueError(f"Analysis requires a nonempty {key} list")
        result[key] = dedupe_items([clean(value) for value in values])[:8]
    result["trace"] = "\n\n".join(traces)
    return result
