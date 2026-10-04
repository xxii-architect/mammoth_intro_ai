"""Replay thumbs-down regression cases (``mammoth.feedback.regression.v1``) for human review.

Each case's prompt is re-sent to the current model and the new reply is placed next to the
rejected one. Nothing is graded automatically: a thumbs-down says a reply was bad, not what
the right reply is, so a person decides whether the new answer is an improvement.

Usage (operator machine, never exposed as an API route)::

    python -m mammoth_os.feedback_replay --input .mammoth/message_feedback.json --out replay.md
    python -m mammoth_os.feedback_replay --input cases.json --no-replay --out cases.md

``--input`` accepts either the raw rating store or an exported regression-case list
(``GET /api/message-feedback/regression-cases``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from mammoth_os import message_feedback
from mammoth_os.research_quality import strip_reasoning

REPORT_CONTRACT_VERSION = "mammoth.feedback.replay.v1"
Generate = Callable[[str], Awaitable[str]]


def load_cases(payload: Any, *, limit: int = 50) -> List[Dict[str, Any]]:
    """Accept a rating store, a regression-case list, or the regression-cases API response."""
    if isinstance(payload, dict):
        payload = payload.get("cases", [])
    if not isinstance(payload, list):
        raise ValueError("Expected a JSON list of ratings or regression cases.")
    items = [item for item in payload if isinstance(item, dict)]
    if items and all(item.get("contract_version") == message_feedback.REGRESSION_CONTRACT_VERSION for item in items):
        return items[: max(0, int(limit))]
    return message_feedback.build_regression_cases(items, limit=limit)


async def replay_cases(
    cases: List[Dict[str, Any]],
    generate: Optional[Generate],
    *,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Run each case sequentially. One failed case never stops the batch."""
    results: List[Dict[str, Any]] = []
    for case in cases:
        row: Dict[str, Any] = {
            "id": case.get("id", ""),
            "prompt": case.get("prompt", ""),
            "rejected_reply": case.get("rejected_reply", ""),
            "reason": case.get("reason", ""),
            "comment": case.get("comment", ""),
            "original_model": f"{case.get('provider', 'unknown')}/{case.get('model', 'unknown')}",
            "reports": case.get("reports", 1),
            "status": "skipped",
            "new_reply": "",
            "error": "",
            "seconds": None,
        }
        if generate is not None:
            started = time.monotonic()
            try:
                raw = await asyncio.wait_for(generate(str(row["prompt"])), timeout=timeout)
                clean, _trace = strip_reasoning(raw)
                row["new_reply"] = clean.strip()
                row["status"] = "replayed" if row["new_reply"] else "empty"
            except asyncio.TimeoutError:
                row["status"], row["error"] = "failed", f"timed out after {timeout:.0f}s"
            except Exception as exc:  # noqa: BLE001 - report every provider failure, keep going
                row["status"], row["error"] = "failed", f"{type(exc).__name__}: {exc}"[:300]
            row["seconds"] = round(time.monotonic() - started, 2)
        results.append(row)

    counts: Dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "contract_version": REPORT_CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "cases": results,
    }


def _quote(text: str) -> str:
    body = str(text or "").strip() or "(empty)"
    return "\n".join(f"> {line}" if line else ">" for line in body.splitlines())


def render_markdown(report: Dict[str, Any]) -> str:
    counts = ", ".join(f"{key}: {value}" for key, value in sorted(report.get("counts", {}).items())) or "no cases"
    lines = [
        "# Thumbs-down replay",
        "",
        f"Generated {report.get('generated_at', '')} · {counts}",
        "",
        "Not auto-graded. Compare each pair and decide whether the new reply fixes the complaint.",
    ]
    for index, row in enumerate(report.get("cases", []), start=1):
        reason = row.get("reason") or "unspecified"
        lines += [
            "",
            f"## {index}. `{row.get('id', '')}` · {reason} · reported {row.get('reports', 1)}x",
            "",
            f"Original model: `{row.get('original_model', '')}` · replay: **{row.get('status', '')}**"
            + (f" in {row['seconds']}s" if row.get("seconds") is not None else ""),
        ]
        if row.get("comment"):
            lines += ["", f"Rater comment: {row['comment']}"]
        lines += ["", "**Prompt**", "", _quote(row.get("prompt", "")), "", "**Rejected reply**", "", _quote(row.get("rejected_reply", ""))]
        if row.get("status") in {"replayed", "empty"}:
            lines += ["", "**New reply**", "", _quote(row.get("new_reply", ""))]
        if row.get("error"):
            lines += ["", f"Error: `{row['error']}`"]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replay thumbs-down chat replies for side-by-side review.")
    parser.add_argument("--input", required=True, help="Rating store or exported regression cases (JSON).")
    parser.add_argument("--out", default="", help="Write the report here (.md or .json). Defaults to stdout markdown.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum cases to replay (default 25).")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-case timeout in seconds.")
    parser.add_argument("--no-replay", action="store_true", help="Only list the cases; do not call a model.")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        cases = load_cases(payload, limit=args.limit)
    except (OSError, ValueError) as exc:
        print(f"Could not read cases: {exc}", file=sys.stderr)
        return 2

    generate: Optional[Generate] = None
    if not args.no_replay:
        from mammoth_os.llm_client import get_llm_client

        generate = get_llm_client().generate
    report = asyncio.run(replay_cases(cases, generate, timeout=args.timeout))

    if args.out.lower().endswith(".json"):
        output = json.dumps(report, indent=2, ensure_ascii=False)
    else:
        output = render_markdown(report)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Wrote {len(report['cases'])} case(s) to {args.out}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
