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
    elif quality.get("ready") is False or states & {"draft", "pending", "pending_approval", "needs_review", "partial"}:
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
    }
