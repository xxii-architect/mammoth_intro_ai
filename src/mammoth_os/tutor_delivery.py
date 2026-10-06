"""Tutor delivery primitives: lesson manifests, stall telemetry, comprehension gate.

These helpers are pure functions over plain dicts so the same logic powers the
HTTP API (per-user persisted state), ``ATLASSession`` (in-process SDK usage),
and tests. Nothing here calls a model; every field is derived from lesson and
exercise data that already exists, and missing data stays empty instead of
being invented.
"""
from __future__ import annotations

import ast
import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from mammoth_os.research_quality import dedupe_items, strip_reasoning

MANIFEST_CONTRACT = "mammoth.lesson_manifest.v1"
TELEMETRY_CONTRACT = "mammoth.lesson_telemetry.v1"

STALL_FAILURE_STREAK = 3
STALL_REPEAT_ERROR_STREAK = 2
STALL_IDLE_MINUTES = 20

_MAX_ITEMS = 5


def build_lesson_flashcards(lesson: Any, exercise: Any = None) -> List[Dict[str, str]]:
    """Build recall cards from teaching content, never from learning objectives."""
    lesson = lesson if isinstance(lesson, dict) else {}
    exercise = exercise if isinstance(exercise, dict) else {}
    title = str(lesson.get("title") or lesson.get("lesson_title") or "this lesson")
    instruction = re.compile(
        r"^(?:identify|apply|explain|describe|practice|demonstrate|learn|understand)\b|"
        r"\bin your own words\b", re.IGNORECASE,
    )
    points = lesson.get("teaching_points") or []
    if not isinstance(points, list):
        points = []
    points = [
        strip_reasoning(item)[0].strip() for item in points
        if isinstance(item, str) and item not in (lesson.get("objectives") or [])
    ]
    points = [point for point in points if point and not instruction.search(point)]
    if not points:
        content = strip_reasoning(str(lesson.get("content") or ""))[0]
        points = [part.strip() for part in re.split(r"\n\s*\n", content) if len(part.split()) >= 8]
    cards: List[Dict[str, str]] = []
    for point in dedupe_items(points):
        if not point or instruction.search(point) or point in (lesson.get("objectives") or []):
            continue
        definition = re.match(r"^(.{2,70}?) (?:is|are|refers to|means) (.+)", point)
        front = (
            f"What is meant by {definition.group(1)}?"
            if definition else f"What does {title} teach in key idea {len(cards) + 1}?"
        )
        cards.append({"id": f"content-{len(cards) + 1}", "front": front, "back": point})
        if len(cards) >= 4:
            break
    for example in _assert_examples(str(exercise.get("expected_test") or "")):
        cards.append({
            "id": f"example-{len(cards) + 1}",
            "front": f"What should `{example['input']}` return?",
            "back": example["expected"],
        })
        if len(cards) >= 6:
            break
    return cards


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _text_list(value: Any, limit: int = _MAX_ITEMS) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Lesson manifest
# ---------------------------------------------------------------------------

def _assert_examples(expected_test: str) -> List[Dict[str, str]]:
    """Extract ``call == expected`` pairs from assert statements in a test file."""
    if not expected_test or "assert" not in expected_test:
        return []
    try:
        tree = ast.parse(expected_test)
    except SyntaxError:
        return []
    examples: List[Dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], (ast.Eq, ast.Is))
            and isinstance(test.left, ast.Call)
        ):
            examples.append({
                "input": ast.unparse(test.left),
                "expected": ast.unparse(test.comparators[0]),
            })
        if len(examples) >= _MAX_ITEMS:
            break
    return examples


def _prior_lesson_titles(curriculum: Any, lesson_id: str, limit: int = 3) -> List[str]:
    if not isinstance(curriculum, dict) or not lesson_id:
        return []
    titles: List[str] = []
    for module in curriculum.get("modules") or []:
        lessons = module.get("lessons") if isinstance(module, dict) else None
        for lesson in lessons or []:
            if not isinstance(lesson, dict):
                continue
            if str(lesson.get("lesson_id") or "") == lesson_id:
                return titles[-limit:]
            title = str(lesson.get("title") or "").strip()
            if title:
                titles.append(title)
    return []


def build_lesson_manifest(
    lesson: Optional[Dict[str, Any]],
    exercise: Optional[Dict[str, Any]] = None,
    curriculum: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a normalized, learner-facing manifest for the active lesson.

    The manifest answers "what do I need, what will I do, and how do I know I
    am done" using only data present on the lesson/exercise.
    """
    lesson = lesson if isinstance(lesson, dict) else {}
    exercise = exercise if isinstance(exercise, dict) else {}
    lesson_id = str(lesson.get("lesson_id") or exercise.get("lesson_id") or "").strip()

    submission_mode = str(exercise.get("submission_mode") or "").strip().lower()
    if not submission_mode:
        lesson_type = str(exercise.get("lesson_type") or lesson.get("lesson_type") or "code").strip().lower()
        submission_mode = "code" if lesson_type == "code" else "text"

    prerequisites = _text_list(lesson.get("prerequisites") or exercise.get("prerequisites"))
    if not prerequisites:
        prerequisites = _prior_lesson_titles(curriculum, lesson_id)

    expected_test = str(exercise.get("expected_test") or "")
    examples = _assert_examples(expected_test) if submission_mode == "code" else []

    sample_data = _text_list(exercise.get("sample_data") or exercise.get("sample_input"))
    if not sample_data:
        sample_data = [example["input"] for example in examples]
    expected_output = _text_list(exercise.get("expected_output"))
    if not expected_output:
        expected_output = [f"{example['input']} -> {example['expected']}" for example in examples]

    success_criteria = _text_list(exercise.get("success_criteria") or lesson.get("success_criteria"))
    if not success_criteria:
        if submission_mode == "code" and expected_test.strip():
            success_criteria = ["All provided tests pass."]
            success_criteria += [f"`{example['input']}` returns `{example['expected']}`." for example in examples[:3]]
        elif submission_mode == "text" and expected_test.strip():
            rubric = [line.strip(" -*\t") for line in expected_test.splitlines()]
            success_criteria = _text_list([line for line in rubric if len(line) > 3])
    has_exercise = bool(str(exercise.get("prompt") or exercise.get("description") or "").strip())

    estimated = lesson.get("estimated_minutes") or lesson.get("duration_minutes") or exercise.get("estimated_minutes")
    try:
        estimated_minutes: Optional[int] = int(estimated) if estimated not in (None, "") else None
    except (TypeError, ValueError):
        estimated_minutes = None

    return {
        "contract": MANIFEST_CONTRACT,
        "lesson_id": lesson_id,
        "title": str(lesson.get("title") or exercise.get("title") or "").strip(),
        "objectives": _text_list(lesson.get("objectives")),
        "prerequisites": prerequisites,
        "submission_mode": submission_mode,
        "has_exercise": has_exercise,
        "sample_data": sample_data,
        "expected_output": expected_output,
        "success_criteria": success_criteria,
        "estimated_minutes": estimated_minutes,
    }


# ---------------------------------------------------------------------------
# Stall telemetry
# ---------------------------------------------------------------------------

def error_fingerprint(result: Optional[Dict[str, Any]]) -> Optional[str]:
    """Stable short id for "the same mistake" across attempts, or None if passed/unknown."""
    if not isinstance(result, dict) or result.get("passed"):
        return None
    raw = result.get("result") if isinstance(result.get("result"), dict) else {}
    source = ""
    for candidate in (result.get("error"), raw.get("stderr"), raw.get("stdout"), result.get("hint")):
        text = str(candidate or "").strip()
        if text:
            source = text
            break
    if not source:
        return None
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    signal = next((line for line in reversed(lines) if re.search(r"(Error|assert|Exception|FAILED)", line)), lines[-1])
    normalized = re.sub(r"0x[0-9a-f]+|\d+", "#", signal.lower())
    normalized = re.sub(r"\s+", " ", normalized)[:160]
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _empty_entry(now: datetime) -> Dict[str, Any]:
    return {
        "attempts": 0,
        "failures": 0,
        "consecutive_failures": 0,
        "repeat_error_streak": 0,
        "last_error": None,
        "first_seen_at": _iso(now),
        "last_attempt_at": None,
        "last_progress_at": _iso(now),
        "passed_at": None,
    }


def touch_lesson(telemetry: Dict[str, Any], lesson_id: str, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Ensure a telemetry entry exists for a lesson (called when a lesson opens)."""
    if not lesson_id:
        return {}
    now = now or _now()
    entry = telemetry.get(lesson_id)
    if not isinstance(entry, dict):
        entry = _empty_entry(now)
        telemetry[lesson_id] = entry
    return entry


def record_attempt(
    telemetry: Dict[str, Any],
    lesson_id: str,
    result: Optional[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    max_lessons: int = 80,
) -> Dict[str, Any]:
    """Record one submission against a lesson and return the updated entry."""
    if not lesson_id:
        return {}
    now = now or _now()
    entry = touch_lesson(telemetry, lesson_id, now=now)
    passed = bool((result or {}).get("passed"))
    entry["attempts"] = int(entry.get("attempts") or 0) + 1
    entry["last_attempt_at"] = _iso(now)
    if passed:
        entry["consecutive_failures"] = 0
        entry["repeat_error_streak"] = 0
        entry["last_error"] = None
        entry["last_progress_at"] = _iso(now)
        entry["passed_at"] = entry.get("passed_at") or _iso(now)
    else:
        entry["failures"] = int(entry.get("failures") or 0) + 1
        entry["consecutive_failures"] = int(entry.get("consecutive_failures") or 0) + 1
        fingerprint = error_fingerprint(result)
        if fingerprint and fingerprint == entry.get("last_error"):
            entry["repeat_error_streak"] = int(entry.get("repeat_error_streak") or 1) + 1
        else:
            entry["repeat_error_streak"] = 1 if fingerprint else 0
            if fingerprint:
                entry["last_progress_at"] = _iso(now)
        entry["last_error"] = fingerprint
    if len(telemetry) > max_lessons:
        oldest = sorted(
            (key for key in telemetry if key != lesson_id),
            key=lambda key: str((telemetry.get(key) or {}).get("last_attempt_at") or (telemetry.get(key) or {}).get("first_seen_at") or ""),
        )
        for key in oldest[: len(telemetry) - max_lessons]:
            telemetry.pop(key, None)
    return entry


def stall_signal(entry: Optional[Dict[str, Any]], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Classify whether the learner is stuck on this step and suggest one intervention."""
    entry = entry if isinstance(entry, dict) else {}
    now = now or _now()
    reasons: List[str] = []
    if entry.get("passed_at"):
        return {"contract": TELEMETRY_CONTRACT, "stalled": False, "reasons": [], "suggestion": None, "attempts": int(entry.get("attempts") or 0)}

    consecutive = int(entry.get("consecutive_failures") or 0)
    repeats = int(entry.get("repeat_error_streak") or 0)
    if consecutive >= STALL_FAILURE_STREAK:
        reasons.append(f"{consecutive} failed attempts in a row")
    if repeats >= STALL_REPEAT_ERROR_STREAK:
        reasons.append(f"same error {repeats} times")
    last_progress = _parse_iso(entry.get("last_progress_at"))
    if last_progress and int(entry.get("attempts") or 0) > 0:
        idle_minutes = (now - last_progress).total_seconds() / 60.0
        if idle_minutes >= STALL_IDLE_MINUTES:
            reasons.append(f"no progress for {int(idle_minutes)} minutes")

    suggestion = None
    if repeats >= STALL_REPEAT_ERROR_STREAK:
        suggestion = "You are hitting the same error. Read the last line of the error, change only that line, and re-run."
    elif consecutive >= STALL_FAILURE_STREAK:
        suggestion = "Shrink the problem: get one test passing with the simplest code possible, then extend."
    elif reasons:
        suggestion = "Take a step back: re-read the success criteria and ask Mammoth Mind for a hint on the first one."

    return {
        "contract": TELEMETRY_CONTRACT,
        "stalled": bool(reasons),
        "reasons": reasons,
        "suggestion": suggestion,
        "attempts": int(entry.get("attempts") or 0),
    }


# ---------------------------------------------------------------------------
# Comprehension gate
# ---------------------------------------------------------------------------

def comprehension_gate(
    *,
    lesson_id: str,
    exercise: Optional[Dict[str, Any]],
    telemetry_entry: Optional[Dict[str, Any]] = None,
    history_submission: Optional[Dict[str, Any]] = None,
    override: bool = False,
) -> Dict[str, Any]:
    """Decide whether the learner may advance past ``lesson_id``.

    Lessons without a gradable exercise are never gated. ``override`` always
    allows advancing (the learner explicitly chose to move on).
    """
    exercise = exercise if isinstance(exercise, dict) else {}
    has_exercise = bool(str(exercise.get("prompt") or exercise.get("description") or "").strip())
    passed = bool((telemetry_entry or {}).get("passed_at")) or bool((history_submission or {}).get("passed"))
    attempts = int((telemetry_entry or {}).get("attempts") or 0)

    if not lesson_id or not has_exercise or passed:
        return {"allowed": True, "reason": "passed" if passed else "ungated", "overridden": False}
    if override:
        return {"allowed": True, "reason": "override", "overridden": True}
    if attempts == 0:
        message = "You haven't submitted this exercise yet. Try it once before moving on, or continue anyway."
    else:
        message = f"This exercise isn't passing yet ({attempts} attempt{'s' if attempts != 1 else ''}). Keep practicing, or continue anyway."
    return {
        "allowed": False,
        "reason": "not_attempted" if attempts == 0 else "not_passed",
        "overridden": False,
        "attempts": attempts,
        "message": message,
        "stall": stall_signal(telemetry_entry),
    }


# ---------------------------------------------------------------------------
# Retrieval hygiene
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall(text.lower()))


def clean_chunks(
    chunks: Iterable[Dict[str, Any]],
    *,
    text_key: str = "chunk_text",
    min_chars: int = 20,
    near_duplicate: float = 0.9,
    max_total_chars: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Drop empty/near-empty and duplicate chunks, preserving order, and add source labels.

    Order is preserved so callers can run this on ranked output. ``max_total_chars``
    caps the combined context handed to a model.
    """
    kept: List[Dict[str, Any]] = []
    kept_tokens: List[set] = []
    seen_exact: set = set()
    total = 0
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        text = str(chunk.get(text_key) or "").strip()
        if len(text) < min_chars:
            continue
        exact = re.sub(r"\s+", " ", text.lower())
        if exact in seen_exact:
            continue
        tokens = _tokens(text)
        if tokens and any(
            len(tokens & other) / max(1, len(tokens | other)) >= near_duplicate for other in kept_tokens
        ):
            continue
        if max_total_chars is not None and kept and total + len(text) > max_total_chars:
            break
        item = dict(chunk)
        if not item.get("source_label"):
            lesson_id = str(item.get("lesson_id") or "").strip()
            index = item.get("chunk_index")
            label = f"Lesson {lesson_id}" if lesson_id else "Lesson material"
            if isinstance(index, int):
                label += f" · part {index + 1}"
            item["source_label"] = label
        kept.append(item)
        kept_tokens.append(tokens)
        seen_exact.add(exact)
        total += len(text)
    return kept




def curriculum_readiness(curriculum: Dict[str, Any]) -> Dict[str, Any]:
    """Check saved/imported courses without trusting model-written quality flags."""
    from mammoth_os.agents.curriculum_validation_v2 import validate_curriculum

    valid, validation = validate_curriculum(curriculum)
    issues = list(validation.get("errors") or [])
    seen_ids = set()
    seen_content = set()
    results = []
    for module in curriculum.get("modules", []):
        if not isinstance(module, dict) or not isinstance(module.get("lessons"), list):
            continue
        for lesson in module["lessons"]:
            if not isinstance(lesson, dict):
                continue
            lesson_id = str(lesson.get("lesson_id") or "").strip()
            errors = []
            if not lesson_id or lesson_id in seen_ids:
                errors.append("Each lesson needs a unique, non-empty id.")
            seen_ids.add(lesson_id)
            content = str(lesson.get("content") or "").strip()
            if len(content.split()) < 180:
                errors.append("Lesson needs at least 180 words of teaching content, not just an outline.")
            if content.endswith(("...", "\u2026")):
                errors.append("Lesson content appears truncated.")
            normalized = " ".join(content.lower().split())
            if normalized and normalized in seen_content:
                errors.append("Lesson duplicates another lesson's content.")
            seen_content.add(normalized)
            if len(lesson.get("examples") or []) < 2:
                errors.append("Provide at least two worked examples.")
            if len(lesson.get("teaching_points") or []) < 3:
                errors.append("Provide at least three concrete teaching points.")
            validation_result = next((item for item in validation.get("lesson_results", []) if item["lesson_id"] == lesson_id), {})
            errors = list(validation_result.get("errors") or []) + errors
            results.append({"lesson_id": lesson_id, "ready": not errors, "errors": errors})
    ready = valid and bool(results) and all(item["ready"] for item in results)
    return {"status": "ready" if ready else "draft", "ready": ready, "errors": issues, "lessons": results,
            "note": "Automated checks are not factual verification or professional certification."}


__all__ = [
    "MANIFEST_CONTRACT",
    "TELEMETRY_CONTRACT",
    "build_lesson_manifest",
    "clean_chunks",
    "comprehension_gate",
    "curriculum_readiness",
    "error_fingerprint",
    "record_attempt",
    "stall_signal",
    "touch_lesson",
]
