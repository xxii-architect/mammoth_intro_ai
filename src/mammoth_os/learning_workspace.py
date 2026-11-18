"""Bounded learner drafts; recovery never submits work or changes mastery."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from contextlib import contextmanager


CONTRACT = "mammoth.learning-workspace.v1"
VIEWS = {"lesson", "tutor", "agents", "curricula"}
_LOCK = threading.RLock()

ERASABLE_LEARNING_FIELDS = (
    "topic", "curriculum_topic", "module_id", "active_module",
    "curriculum_id", "curriculum", "curriculum_origin", "lesson_id",
    "current_lesson", "current_exercise", "lesson_plan", "last_submission",
    "chat_history", "assistant_chat_history", "lesson_history", "study_aids",
    "learner_profile", "resume_packet", "regenerated_exercise",
)
LEARNING_ERASURE_EXCLUDES = (
    "linked_notes", "uploaded_files", "curriculum_library", "other_accounts",
    "learner_model_and_cached_context", "lesson_telemetry", "onboarding",
    "mammoth_mind_threads", "artifacts", "plans", "audit_logs",
    "usage_records", "provider_records", "backups", "other_tabs_and_downloads",
    "unknown_state_and_session_extensions",
)
LEARNER_CACHE_FIELDS = ("learner_model", "learner_context", "learner_profile", "learner_storage")
ACCOUNT_SESSION_FIELDS = (
    "status", "topic", "curriculum_topic", "current_exercise", "curriculum", "current_lesson",
    "curriculum_id", "curriculum_origin", "lesson_id", "lesson_plan", "module_id", "active_module",
    "lesson_telemetry",
    "last_submission", "assistant_chat_history", "chat_history", "mammoth_chat_history", "resume_packet",
    "lesson_history", "study_aids", "learner_profile", "learner_model", "learner_context", "learner_storage",
    "fab_usage_events", "workspace_artifacts", "agent_run_history", "curriculum_library",
    "plan_history", "active_plan",
    "eval_history", "regenerated_exercise", "workspace_epoch", "updated_at",
)
LEARNER_ERASURE_EXCLUDES = (
    "lesson_session_and_recovery", "linked_notes", "uploaded_files", "curriculum_library",
    "other_accounts", "unverified_legacy_models", "lesson_telemetry",
    "mammoth_mind_threads", "artifacts", "plans", "audit_logs", "usage_records",
    "provider_records", "backups", "other_tabs_and_downloads",
    "unknown_state_and_session_extensions",
)


class WorkspaceStorageError(RuntimeError):
    pass


def validate_learner_erasure_records(state):
    records = state.get("learner_erasure", {})
    if not isinstance(records, dict) or any(
        not isinstance(key, str) or not isinstance(value, dict)
        or set(value) != {"epoch", "status"}
        or not isinstance(value["epoch"], str) or not re.fullmatch(r"[a-f0-9]{32}", value["epoch"])
        or value["status"] not in ("pending", "complete")
        for key, value in records.items()
    ):
        raise WorkspaceStorageError("Private adaptation deletion state is invalid.")
    return records


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


def workspace_content_key(state):
    exercise = state.get("current_exercise") or {}
    identity = json.dumps(
        [state.get("active_account_id"), state.get("workspace_epoch"), state.get("lesson_id"), exercise],
        sort_keys=True, ensure_ascii=True,
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def workspace_snapshot(state, saved=None):
    exercise = state.get("current_exercise") or {}
    content_key = workspace_content_key(state)
    epoch = state.get("learning_account_epoch")
    key = content_key if epoch is None else hashlib.sha256(
        json.dumps([content_key, epoch], sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    saved = saved or {}
    same_exercise = saved.get("exercise_key") == content_key
    starter = exercise.get("starter_response") or next(iter((exercise.get("starter_files") or {}).values()), "")
    values = {
        "view": saved.get("values", {}).get("view", "lesson"),
        "lesson_response": starter, "tutor_response": starter, "checklist": {},
        "tutor_message": "", "tutor_mode": "tutor",
    }
    if same_exercise:
        values.update(saved.get("values") or {})
    return {
        "contract": CONTRACT, "exercise_key": key, "revision": saved.get("revision", 0),
        "values": values, "saved_at": saved.get("saved_at") if same_exercise else None,
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


def validate_workspace_record(saved):
    if (not isinstance(saved, dict) or not isinstance(saved.get("values"), dict)
            or type(saved.get("revision")) is not int or saved["revision"] < 1
            or not isinstance(saved.get("exercise_key"), str)):
        raise WorkspaceStorageError("Saved learning workspace is invalid; it has not been overwritten.")
    try:
        validate_workspace_values(saved["values"])
    except ValueError as exc:
        raise WorkspaceStorageError("Saved learning workspace is invalid; it has not been overwritten.") from exc
    return saved


def read_workspace(path: Path):
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise WorkspaceStorageError("Saved learning workspace is invalid; it has not been overwritten.") from exc
    return validate_workspace_record(saved)


def _write_workspace(path: Path, record, *, default=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f"{path.stem}.", suffix=".tmp", delete=False) as stream:
            name = stream.name
            json.dump(record, stream, ensure_ascii=True, default=default)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def save_workspace(path: Path, state, body, saved_at):
    values = validate_workspace_values(body.get("values"))
    with _workspace_lock(path):
        previous = read_workspace(path)
        current = workspace_snapshot(state, previous)
        if (type(body.get("revision")) is not int or body["revision"] != current["revision"]
                or body.get("exercise_key") != current["exercise_key"]):
            return None
        record = {
            **previous,
            "exercise_key": workspace_content_key(state), "revision": current["revision"] + 1,
            "values": values, "saved_at": saved_at,
        }
        _write_workspace(path, record)
        return workspace_snapshot(state, record)


def clear_workspace(path: Path, state, saved_at):
    with _workspace_lock(path):
        previous = read_workspace(path)
        fresh = workspace_snapshot(state)
        _write_workspace(path, {
            "exercise_key": workspace_content_key(state), "revision": previous.get("revision", 0) + 1,
            "values": fresh["values"], "saved_at": saved_at,
        })
