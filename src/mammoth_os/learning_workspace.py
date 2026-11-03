"""Bounded learner drafts; recovery never submits work or changes mastery."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from contextlib import contextmanager


CONTRACT = "mammoth.learning-workspace.v1"
VIEWS = {"lesson", "tutor", "agents", "curricula"}
_LOCK = threading.RLock()


class WorkspaceStorageError(RuntimeError):
    pass


@contextmanager
def _workspace_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.with_suffix(".lock").open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def workspace_snapshot(state, saved=None):
    exercise = state.get("current_exercise") or {}
    identity = json.dumps(
        [state.get("active_account_id"), state.get("workspace_epoch"), state.get("lesson_id"), exercise],
        sort_keys=True, ensure_ascii=True,
    )
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    saved = saved or {}
    starter = exercise.get("starter_response") or next(iter((exercise.get("starter_files") or {}).values()), "")
    values = {
        "view": saved.get("values", {}).get("view", "lesson"),
        "lesson_response": starter, "tutor_response": starter, "checklist": {},
        "tutor_message": "", "tutor_mode": "tutor",
    }
    if saved.get("exercise_key") == key:
        values.update(saved.get("values") or {})
    return {
        "contract": CONTRACT, "exercise_key": key, "revision": saved.get("revision", 0),
        "values": values, "saved_at": saved.get("saved_at") if saved.get("exercise_key") == key else None,
    }


def validate_workspace_values(values):
    if not isinstance(values, dict):
        raise ValueError("Workspace values must be an object.")
    expected = {"view", "lesson_response", "tutor_response", "checklist", "tutor_message", "tutor_mode"}
    if set(values) != expected:
        raise ValueError("Workspace fields are missing or unsupported.")
    for field in ("lesson_response", "tutor_response", "tutor_message"):
        if not isinstance(values[field], str) or len(values[field]) > 100_000:
            raise ValueError(f"{field} must be text of at most 100,000 characters.")
    if not isinstance(values["view"], str) or values["view"] not in VIEWS:
        raise ValueError("Unknown learning workspace view.")
    if values["tutor_mode"] not in ("tutor", "assistant", "build"):
        raise ValueError("Unknown tutor conversation mode.")
    checklist = values["checklist"]
    if not isinstance(checklist, dict) or len(checklist) > 12 or any(
        key not in {str(i) for i in range(12)} or type(value) is not bool
        for key, value in checklist.items()
    ):
        raise ValueError("Checklist must contain at most 12 numbered boolean values.")
    if len(json.dumps(values, ensure_ascii=True).encode("utf-8")) > 600_000:
        raise ValueError("Workspace draft exceeds the saved draft size limit.")
    return values


def read_workspace(path: Path):
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise WorkspaceStorageError("Saved learning workspace is invalid; it has not been overwritten.") from exc
    if (not isinstance(saved, dict) or not isinstance(saved.get("values"), dict)
            or type(saved.get("revision")) is not int or saved["revision"] < 1
            or not isinstance(saved.get("exercise_key"), str)):
        raise WorkspaceStorageError("Saved learning workspace is invalid; it has not been overwritten.")
    try:
        validate_workspace_values(saved["values"])
    except ValueError as exc:
        raise WorkspaceStorageError("Saved learning workspace is invalid; it has not been overwritten.") from exc
    return saved


def _write_workspace(path: Path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f"{path.stem}.", suffix=".tmp", delete=False) as stream:
            name = stream.name
            json.dump(record, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def save_workspace(path: Path, state, body, saved_at):
    values = validate_workspace_values(body.get("values"))
    with _workspace_lock(path):
        current = workspace_snapshot(state, read_workspace(path))
        if (type(body.get("revision")) is not int or body["revision"] != current["revision"]
                or body.get("exercise_key") != current["exercise_key"]):
            return None
        record = {
            "exercise_key": current["exercise_key"], "revision": current["revision"] + 1,
            "values": values, "saved_at": saved_at,
        }
        _write_workspace(path, record)
        return workspace_snapshot(state, record)


def clear_workspace(path: Path, state, saved_at):
    with _workspace_lock(path):
        previous = read_workspace(path)
        fresh = workspace_snapshot(state)
        _write_workspace(path, {
            "exercise_key": fresh["exercise_key"], "revision": previous.get("revision", 0) + 1,
            "values": fresh["values"], "saved_at": saved_at,
        })
