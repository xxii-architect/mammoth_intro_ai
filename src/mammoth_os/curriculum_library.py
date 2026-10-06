"""Bounded per-learner course snapshots; callers supply a tenant-resolved path."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mammoth_os.tutor_delivery import curriculum_readiness

_LOCK = threading.RLock()
MAX_COURSES = 20
MAX_BYTES = 2_000_000


def prepare_curriculum(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Curriculum must be an object.")
    course = deepcopy(value)
    if not isinstance(course.get("curriculum_id"), str) or not course["curriculum_id"].strip():
        raise ValueError("Curriculum needs an id.")
    if not isinstance(course.get("subject"), str) or not course["subject"].strip():
        raise ValueError("Curriculum needs a subject.")
    modules = course.get("modules")
    if not isinstance(modules, list) or not 1 <= len(modules) <= 20:
        raise ValueError("Curriculum needs 1-20 modules.")
    for module in modules:
        if not isinstance(module, dict) or not isinstance(module.get("lessons"), list) or not 1 <= len(module["lessons"]) <= 40:
            raise ValueError("Each module needs 1-40 lessons.")
        for lesson in module["lessons"]:
            if not isinstance(lesson, dict):
                raise ValueError("Each lesson must be an object.")
            for field in ("objectives", "examples", "teaching_points"):
                items = lesson.get(field, [])
                if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                    raise ValueError(f"Lesson {field} must be a list of text.")
            for field in ("title", "content", "summary", "lesson_id", "source"):
                if field in lesson and not isinstance(lesson[field], str):
                    raise ValueError(f"Lesson {field} must be text.")
    if len(json.dumps(course).encode("utf-8")) > MAX_BYTES:
        raise ValueError("Curriculum exceeds the 2 MB limit.")
    course["quality"] = curriculum_readiness(course)
    return course


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) and isinstance(item.get("curriculum"), dict) for item in data):
        raise ValueError("Saved curriculum library is invalid.")
    return data


def list_curricula(path: Path) -> list[dict]:
    with _LOCK:
        return _read(path)


def save_curriculum(path: Path, value: Any) -> dict:
    course = prepare_curriculum(value)
    record = {"curriculum": course, "saved_at": datetime.now(timezone.utc).isoformat()}
    with _LOCK:
        records = _read(path)
        records = [item for item in records if item["curriculum"].get("curriculum_id") != course["curriculum_id"]]
        if len(records) >= MAX_COURSES:
            raise ValueError("Curriculum library is full (20 courses).")
        records.append(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=True, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    return record
