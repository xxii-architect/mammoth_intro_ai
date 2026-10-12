"""Additive metadata for saved outputs; categories confer no access or readiness."""
from typing import Any

ARTIFACT_CATEGORIES = [
    {"id": "curricula", "label": "Curricula"},
    {"id": "lessons", "label": "Lessons"},
    {"id": "research", "label": "Research & reports"},
    {"id": "notes", "label": "Notes"},
    {"id": "flashcards", "label": "Flashcards"},
    {"id": "code", "label": "Code & patch proposals"},
    {"id": "plans", "label": "Plans"},
    {"id": "uncategorized", "label": "Uncategorized"},
]
_TYPES = {
    "curriculum": "curricula", "curricula": "curricula",
    "lesson": "lessons", "lesson_summary": "lessons",
    "research": "research", "research_brief": "research", "long_form_research": "research",
    "report": "research", "research_report": "research",
    "market_intel": "research", "field_ops": "research", "seed_validation": "research",
    "note": "notes", "notes": "notes",
    "flashcard": "flashcards", "flashcards": "flashcards", "flashcard_deck": "flashcards",
    "code": "code", "coding": "code", "patch": "code", "patch_proposal": "code", "coding_report": "code",
    "plan": "plans", "planner": "plans", "task_plan": "plans",
}
_PAGES = {"atlas", "agent", "chat", "notes", "flashcards", "lessonnotes", "taskinbox", "artifacts"}


def artifact_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    artifact_type = str(raw.get("artifact_type") or meta.get("artifact_type") or "").strip().lower()
    category = _TYPES.get(artifact_type, "uncategorized")
    declared_category = str(raw.get("category") or meta.get("category") or "").strip()
    if category == "uncategorized" and declared_category in {item["id"] for item in ARTIFACT_CATEGORIES}:
        category = declared_category
    quality = raw.get("quality") if isinstance(raw.get("quality"), dict) else meta.get("quality")
    quality = quality if isinstance(quality, dict) else {}
    states = {str(value or "").strip().lower() for value in (
        raw.get("artifact_status"), raw.get("status"), meta.get("artifact_status"), quality.get("status"),
    )}
    if states & {"failed", "error", "blocked"}:
        status = "failed"
    elif quality.get("ready") is False or states & {"draft", "pending", "pending_approval", "needs_review", "partial", "insufficient_evidence", "needs_context"}:
        status = "draft"
    elif quality.get("ready") is True or "ready" in states:
        status = "ready"
    else:
        status = "unknown"
    origin = raw.get("origin") if isinstance(raw.get("origin"), dict) else meta.get("origin")
    origin = origin if isinstance(origin, dict) else {}
    page = str(origin.get("page") or "")
    page = {"agents": "agent", "tasks": "taskinbox", "lessons": "atlas"}.get(page, page)
    safe_origin = {"page": page} if page in _PAGES else {}
    for key in ("trace_id", "task_id", "lesson_id", "curriculum_id"):
        if isinstance(origin.get(key), str) and origin[key].strip():
            safe_origin[key] = origin[key].strip()[:200]
    filename = str(raw.get("docx_filename") or meta.get("docx_filename") or "").strip()
    if "/" in filename or "\\" in filename or not filename.lower().endswith(".docx"):
        filename = ""
    return {
        "artifact_type": artifact_type, "category": category, "artifact_status": status,
        "agent_id": str(raw.get("agent_id") or meta.get("agent_id") or "").strip(),
        "origin": safe_origin, "docx_filename": filename,
        **artifact_lineage(raw),
    }


def artifact_lineage(raw: dict[str, Any]) -> dict[str, Any]:
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    lineage = raw.get("lineage") if isinstance(raw.get("lineage"), dict) else meta.get("lineage")
    lineage = lineage if isinstance(lineage, dict) else {}
    recorded = {}
    for key in ("repo", "branch", "base_sha", "source_id"):
        value = lineage.get(key)
        if isinstance(value, str) and value.strip():
            recorded[key] = value.strip()[:200]
    quality = raw.get("quality") if isinstance(raw.get("quality"), dict) else meta.get("quality")
    verification = raw.get("verification") if isinstance(raw.get("verification"), dict) else meta.get("verification")
    revision = raw.get("revision")
    revisions = raw.get("revisions")
    return {
        "lineage": recorded,
        "quality": quality if isinstance(quality, dict) else {},
        "verification": verification if isinstance(verification, dict) else {},
        "revision": revision if type(revision) is int and revision > 0 else 1,
        "revisions": [
            {key: item[key] for key in (
                "revision", "title", "body", "format", "created_at", "updated_at",
                "artifact_status", "origin", "lineage", "quality", "verification",
            ) if key in item}
            for item in revisions[-10:] if isinstance(item, dict) and isinstance(item.get("body"), str)
        ] if isinstance(revisions, list) else [],
        "updated_at": str(raw.get("updated_at") or raw.get("created_at") or ""),
    }


def record_artifact_revision(artifact: dict[str, Any], previous: dict[str, Any] | None, *, now: str) -> dict[str, Any]:
    """Keep ten previous snapshots; revisions are assigned by the save operation."""
    record = dict(artifact)
    record["revision"] = previous["revision"] if previous else 1
    record["revisions"] = list(previous.get("revisions") or []) if previous else []
    record["updated_at"] = now
    if previous:
        record["created_at"] = previous["created_at"]
        fields = (
            "title", "summary", "body", "format", "artifact_status", "origin",
            "lineage", "quality", "verification", "agent_id", "artifact_type", "docx_filename",
        )
        if any(record.get(key) != previous.get(key) for key in fields):
            snapshot = {key: value for key, value in previous.items() if key not in {"revisions", "meta"}}
            record["revisions"] = [*record["revisions"], snapshot][-10:]
            record["revision"] += 1
    return record
