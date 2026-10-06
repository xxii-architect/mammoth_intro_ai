"""Per-reply thumbs up/down ratings for Mammoth Mind chat (contract ``mammoth.feedback.v1``).

Pure functions over a list of rating records; the API owns persistence and access.
A rating is a signal for humans and evals. Nothing here changes model, prompt, or
routing behavior on its own.

Record shape::

    {
      "contract_version": "mammoth.feedback.v1",
      "id": str, "message_key": "run:<id>" | "ts:<created_at>",
      "user_id": str, "account_id": str, "thread_id": str,
      "direction": "up" | "down", "reason": str, "comment": str,
      "agent_id": str, "provider": str, "model": str, "mode": str, "run_id": str,
      "message_created_at": str, "prompt_excerpt": str, "reply_excerpt": str,
      "created_at": str, "updated_at": str,
    }
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

CONTRACT_VERSION = "mammoth.feedback.v1"
REGRESSION_CONTRACT_VERSION = "mammoth.feedback.regression.v1"
MAX_RECORDS = 5000
PROMPT_EXCERPT_CHARS = 2000
REPLY_EXCERPT_CHARS = 4000
COMMENT_CHARS = 500
DIRECTIONS = ("up", "down")
REASONS = ("incorrect", "incomplete", "off_topic", "unsafe", "formatting", "too_long", "other")


class FeedbackError(ValueError):
    """Raised for client-correctable rating input."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def message_key(*, run_id: str = "", created_at: str = "") -> str:
    run_id = str(run_id or "").strip()
    if run_id:
        return f"run:{run_id}"
    created_at = str(created_at or "").strip()
    if created_at:
        return f"ts:{created_at}"
    raise FeedbackError("run_id or created_at is required to identify the message.")


def normalize_direction(value: Any) -> str:
    direction = str(value or "").strip().lower()
    if direction in DIRECTIONS or direction == "none":
        return direction
    raise FeedbackError("direction must be 'up', 'down', or 'none'.")


def normalize_reason(value: Any) -> str:
    reason = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not reason:
        return ""
    if reason not in REASONS:
        raise FeedbackError(f"reason must be one of: {', '.join(REASONS)}.")
    return reason


def build_record(
    *,
    user_id: str,
    account_id: str,
    key: str,
    direction: str,
    assistant_entry: Dict[str, Any],
    prompt: str,
    thread_id: str = "",
    reason: str = "",
    comment: str = "",
    existing: Optional[Dict[str, Any]] = None,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a rating from server-side message data. Excerpts never come from the client."""
    if direction not in DIRECTIONS:
        raise FeedbackError("direction must be 'up' or 'down'.")
    stamp = now or _now()
    entry = assistant_entry if isinstance(assistant_entry, dict) else {}
    # Reasons explain what went wrong, so they are only kept on thumbs-down.
    keep_reason = direction == "down"
    return {
        "contract_version": CONTRACT_VERSION,
        "id": str((existing or {}).get("id") or uuid.uuid4()),
        "message_key": key,
        "user_id": str(user_id),
        "account_id": str(account_id or "default"),
        "thread_id": str(thread_id or ""),
        "direction": direction,
        "reason": normalize_reason(reason) if keep_reason else "",
        "comment": _clip(comment, COMMENT_CHARS) if keep_reason else "",
        "agent_id": str(entry.get("agent_id") or "assistant"),
        "provider": str(entry.get("adapter") or (entry.get("trust_metadata") or {}).get("provider") or "unknown"),
        "model": str(entry.get("model") or "unknown"),
        "mode": str(entry.get("mode") or ""),
        "run_id": str(entry.get("run_id") or ""),
        "message_created_at": str(entry.get("created_at") or ""),
        "prompt_excerpt": _clip(prompt, PROMPT_EXCERPT_CHARS),
        "reply_excerpt": _clip(entry.get("message"), REPLY_EXCERPT_CHARS),
        "created_at": str((existing or {}).get("created_at") or stamp),
        "updated_at": stamp,
    }


def _same_rating(record: Dict[str, Any], *, user_id: str, account_id: str, key: str) -> bool:
    return (
        str(record.get("user_id") or "") == user_id
        and str(record.get("account_id") or "default") == account_id
        and str(record.get("message_key") or "") == key
    )


def find_rating(records: Iterable[Dict[str, Any]], *, user_id: str, account_id: str, key: str) -> Optional[Dict[str, Any]]:
    for record in records:
        if isinstance(record, dict) and _same_rating(record, user_id=user_id, account_id=account_id, key=key):
            return record
    return None


def upsert(records: List[Dict[str, Any]], record: Dict[str, Any], *, max_records: int = MAX_RECORDS) -> List[Dict[str, Any]]:
    """One rating per user, account, and message. The newest ratings are kept when bounded."""
    kept = [
        item for item in records
        if isinstance(item, dict)
        and not _same_rating(item, user_id=record["user_id"], account_id=record["account_id"], key=record["message_key"])
    ]
    kept.append(record)
    return kept[-max_records:]


def remove(records: List[Dict[str, Any]], *, user_id: str, account_id: str, key: str) -> Tuple[List[Dict[str, Any]], bool]:
    kept = [item for item in records if isinstance(item, dict) and not _same_rating(item, user_id=user_id, account_id=account_id, key=key)]
    return kept, len(kept) != len(records)


def for_user(records: Iterable[Dict[str, Any]], *, user_id: str, account_id: str) -> List[Dict[str, Any]]:
    return [
        item for item in records
        if isinstance(item, dict)
        and str(item.get("user_id") or "") == user_id
        and str(item.get("account_id") or "default") == account_id
    ]


def public_view(record: Dict[str, Any]) -> Dict[str, Any]:
    """What the rater needs to render state. Excerpts stay server-side."""
    return {key: record.get(key, "") for key in ("message_key", "direction", "reason", "comment", "thread_id", "updated_at")}


def _ratio(up: int, down: int) -> Optional[float]:
    total = up + down
    return round(up / total, 3) if total else None


def filter_records(
    records: Iterable[Dict[str, Any]], *,
    agent_id: str = "", date_from: str = "", date_to: str = "",
) -> List[Dict[str, Any]]:
    """Filter before aggregation/deduplication, by latest rating date (inclusive UTC)."""
    def parse_date(value: str, name: str) -> Optional[date]:
        if not value:
            return None
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError
            return date.fromisoformat(value)
        except ValueError as exc:
            raise FeedbackError(f"{name} must be a valid YYYY-MM-DD date.") from exc

    start = parse_date(date_from, "date_from")
    end = parse_date(date_to, "date_to")
    if start and end and start > end:
        raise FeedbackError("date_from must not be after date_to.")
    selected_agent = str(agent_id or "").strip()
    filtered = []
    for record in records:
        if not isinstance(record, dict) or record.get("direction") not in DIRECTIONS:
            continue
        if selected_agent and str(record.get("agent_id") or "assistant") != selected_agent:
            continue
        if start or end:
            stamp = str(record.get("updated_at") or record.get("created_at") or "")
            try:
                rated_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if rated_at.tzinfo is None:
                rated_at = rated_at.replace(tzinfo=timezone.utc)
            rated_date = rated_at.astimezone(timezone.utc).date()
            if (start and rated_date < start) or (end and rated_date > end):
                continue
        filtered.append(record)
    return filtered


def summarize(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate counts by provider/model, agent, and down-vote reason."""
    totals = {"up": 0, "down": 0}
    by_model: Dict[Tuple[str, str], Dict[str, int]] = {}
    by_agent: Dict[str, Dict[str, int]] = {}
    reasons: Dict[str, int] = {}
    raters = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        direction = record.get("direction")
        if direction not in DIRECTIONS:
            continue
        totals[direction] += 1
        raters.add(str(record.get("user_id") or ""))
        model_key = (str(record.get("provider") or "unknown"), str(record.get("model") or "unknown"))
        by_model.setdefault(model_key, {"up": 0, "down": 0})[direction] += 1
        by_agent.setdefault(str(record.get("agent_id") or "assistant"), {"up": 0, "down": 0})[direction] += 1
        if direction == "down":
            reason = str(record.get("reason") or "unspecified")
            reasons[reason] = reasons.get(reason, 0) + 1

    def _rows(groups: Dict[Any, Dict[str, int]], label) -> List[Dict[str, Any]]:
        rows = [{**label(key), **counts, "total": counts["up"] + counts["down"], "approval": _ratio(counts["up"], counts["down"])} for key, counts in groups.items()]
        return sorted(rows, key=lambda row: (-row["total"], str(row)))

    return {
        "contract_version": CONTRACT_VERSION,
        "totals": {**totals, "total": totals["up"] + totals["down"], "approval": _ratio(totals["up"], totals["down"]), "raters": len(raters - {""})},
        "by_model": _rows(by_model, lambda key: {"provider": key[0], "model": key[1]}),
        "by_agent": _rows(by_agent, lambda key: {"agent_id": key}),
        "down_reasons": dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
    }


def _prompt_fingerprint(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", str(prompt or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def build_regression_cases(records: Iterable[Dict[str, Any]], *, limit: int = 200) -> List[Dict[str, Any]]:
    """Thumbs-down replies become replayable cases, one per distinct prompt (newest wins).

    Cases carry the rejected reply as a baseline for human side-by-side review. They are
    not graded automatically; a rating says a reply was bad, not what the right one is.
    """
    cases: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or record.get("direction") != "down":
            continue
        prompt = str(record.get("prompt_excerpt") or "").strip()
        if not prompt:
            continue
        case_id = _prompt_fingerprint(prompt)
        existing = cases.get(case_id)
        stamp = str(record.get("updated_at") or "")
        reports = (existing or {}).get("reports", 0) + 1
        if existing is None or stamp >= str(existing.get("rated_at") or ""):
            cases[case_id] = {
                "contract_version": REGRESSION_CONTRACT_VERSION,
                "id": case_id,
                "prompt": prompt,
                "rejected_reply": str(record.get("reply_excerpt") or ""),
                "reason": str(record.get("reason") or ""),
                "comment": str(record.get("comment") or ""),
                "agent_id": str(record.get("agent_id") or "assistant"),
                "provider": str(record.get("provider") or "unknown"),
                "model": str(record.get("model") or "unknown"),
                "rated_at": stamp,
                "reports": reports,
            }
        else:
            existing["reports"] = reports
    newest_first = sorted(cases.values(), key=lambda case: case["rated_at"], reverse=True)
    ordered = sorted(newest_first, key=lambda case: -case["reports"])
    return ordered[: max(0, int(limit))]
