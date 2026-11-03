import asyncio
import json

import pytest
from fastapi import HTTPException

import api_server
from mammoth_os.learning_workspace import validate_workspace_values
from mammoth_os import learning_workspace


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas.json")
    monkeypatch.setattr(api_server, "_require_signed_in_api", lambda: None)
    state = api_server._load_atlas_state()
    state.update(lesson_id="one", current_exercise={"prompt": "Explain a loop.", "starter_response": "Start here"})
    api_server._save_atlas_state(state)
    return api_server._learning_workspace_snapshot(state)


def save(snapshot, **changes):
    return asyncio.run(api_server.atlas_save_workspace({
        "revision": snapshot["revision"], "exercise_key": snapshot["exercise_key"],
        "values": {**snapshot["values"], **changes},
    }))


def test_full_workspace_roundtrip_preserves_empty_drafts_without_submission(workspace):
    saved = save(workspace, lesson_response="", tutor_response="Tutor draft", tutor_message="Unsent question",
                 checklist={"0": True}, view="tutor")
    state = api_server._load_atlas_state()
    assert api_server._learning_workspace_snapshot(state) == {key: value for key, value in saved.items() if key != "status"}
    assert saved["values"]["lesson_response"] == ""
    assert state.get("last_submission") is None
    assert state["current_exercise"]["starter_response"] == "Start here"


def test_conflicting_tabs_and_changed_exercise_cannot_overwrite_saved_work(workspace):
    saved = save(workspace, lesson_response="First tab")
    with pytest.raises(HTTPException) as conflict:
        save(workspace, lesson_response="Stale tab")
    assert conflict.value.status_code == 409
    state = api_server._load_atlas_state()
    state["current_exercise"] = {"prompt": "A new variant"}
    api_server._save_atlas_state(state)
    with pytest.raises(HTTPException) as changed:
        save(saved, lesson_response="Old exercise")
    assert changed.value.status_code == 409
    fresh = api_server._learning_workspace_snapshot(api_server._load_atlas_state())
    assert fresh["values"]["lesson_response"] == ""
    assert fresh["values"]["checklist"] == {}


def test_workspace_isolated_between_local_accounts(workspace):
    save(workspace, lesson_response="Account one private draft")
    first_state = api_server._load_atlas_state()
    # Use the same switch surface as the application, not a payload user ID.
    asyncio.run(api_server.mutate_account_workspace({
        "action": "create", "account_id": "second", "display_name": "Second", "activate": True,
    }))
    second_state = api_server._load_atlas_state()
    second_state.update(lesson_id=first_state["lesson_id"], current_exercise=first_state["current_exercise"])
    api_server._save_atlas_state(second_state)
    second = api_server._learning_workspace_snapshot(second_state)
    assert second["exercise_key"] != workspace["exercise_key"]
    with pytest.raises(HTTPException) as stale:
        save(workspace, lesson_response="Late write for another local account")
    assert stale.value.status_code == 409
    assert second["values"]["lesson_response"] != "Account one private draft"
    asyncio.run(api_server.mutate_account_workspace({"action": "switch", "account_id": "default"}))
    assert api_server._learning_workspace_snapshot(api_server._load_atlas_state())["values"]["lesson_response"] == "Account one private draft"


@pytest.mark.parametrize("changes", [
    {"view": "host"}, {"tutor_mode": {}}, {"checklist": {"13": True}},
    {"checklist": {"0": 1}}, {"lesson_response": "a" * 100_001},
    {"tutor_message": None}, {"unexpected": True},
])
def test_invalid_or_oversized_drafts_fail_explicitly(workspace, changes):
    with pytest.raises(HTTPException) as error:
        save(workspace, **changes)
    assert error.value.status_code == 400
    assert api_server._learning_workspace_snapshot(api_server._load_atlas_state())["revision"] == 0


def test_reset_epoch_invalidates_inflight_drafts(workspace):
    state = api_server._load_atlas_state()
    state["workspace_epoch"] = "reset"
    api_server._save_atlas_state(state)
    with pytest.raises(HTTPException) as error:
        save(workspace, lesson_response="Before reset")
    assert error.value.status_code == 409


def test_recovery_reuses_server_chat_history_instead_of_copying_it(workspace):
    state = api_server._load_atlas_state()
    state["chat_history"] = [{"role": "assistant", "message": "Existing tutor answer"}]
    api_server._save_atlas_state(state)
    save(workspace, tutor_message="My next question")
    assert api_server._load_atlas_state()["chat_history"] == state["chat_history"]


def test_save_failure_is_not_reported_as_saved(workspace, monkeypatch):
    def fail(*_):
        raise OSError("Storage unavailable")
    monkeypatch.setattr(learning_workspace, "_write_workspace", fail)
    with pytest.raises(HTTPException) as error:
        save(workspace, lesson_response="Keep locally")
    assert error.value.status_code == 503


def test_missing_draft_object_rejected():
    with pytest.raises(ValueError):
        validate_workspace_values(None)


def test_text_and_combined_serialized_limits_are_enforced_at_the_boundary(workspace):
    values = {**workspace["values"], "lesson_response": "x" * 100_000}
    assert validate_workspace_values(values)["lesson_response"] == "x" * 100_000
    values.update(lesson_response="\u00a9" * 90_000, tutor_response="", tutor_message="")
    padding = 600_000 - len(json.dumps(values, ensure_ascii=True).encode("utf-8"))
    values["tutor_response"] = "x" * padding
    assert len(json.dumps(values, ensure_ascii=True).encode("utf-8")) == 600_000
    validate_workspace_values(values)
    values["tutor_response"] += "x"
    with pytest.raises(ValueError, match="size limit"):
        validate_workspace_values(values)


def test_anonymous_cannot_save_a_private_workspace(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    token = api_server._REQUEST_USER_ID.set("anonymous")
    try:
        assert asyncio.run(api_server.atlas_save_workspace({})).status_code == 401
    finally:
        api_server._REQUEST_USER_ID.reset(token)


def test_slow_lesson_state_write_cannot_erase_a_saved_draft(workspace):
    old_state = api_server._load_atlas_state()
    save(workspace, lesson_response="Saved while a provider call was running")
    api_server._save_atlas_state(old_state)
    assert api_server._learning_workspace_snapshot(api_server._load_atlas_state())["values"]["lesson_response"] == "Saved while a provider call was running"


def test_request_scoped_tenant_files_are_isolated(workspace, monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_STATE_DIR", tmp_path)
    token = api_server._REQUEST_USER_ID.set("tenant-one")
    try:
        state = api_server._load_atlas_state()
        state.update(lesson_id="one", current_exercise={"prompt": "Same lesson"})
        api_server._save_atlas_state(state)
        first = api_server._learning_workspace_snapshot(state)
        save(first, lesson_response="Private tenant one")
        api_server._REQUEST_USER_ID.set("tenant-two")
        other = api_server._load_atlas_state()
        other.update(lesson_id="one", current_exercise={"prompt": "Same lesson"})
        api_server._save_atlas_state(other)
        assert api_server._learning_workspace_snapshot(other)["values"]["lesson_response"] == ""
    finally:
        api_server._REQUEST_USER_ID.reset(token)


def test_parallel_writers_compare_revisions_under_one_lock(workspace):
    from concurrent.futures import ThreadPoolExecutor

    state = api_server._load_atlas_state()
    path = api_server._learning_workspace_path(state)
    payload = {"exercise_key": workspace["exercise_key"], "revision": 0, "values": workspace["values"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: learning_workspace.save_workspace(path, state, payload, "now"), range(2)))
    assert sum(result is not None for result in results) == 1


def test_reset_clears_the_draft_text_from_storage(workspace):
    save(workspace, lesson_response="Remove on reset", tutor_message="Private unsent message")
    state = api_server._load_atlas_state()
    path = api_server._learning_workspace_path(state)
    api_server._apply_atlas_session_reset()
    record = learning_workspace.read_workspace(path)
    assert "Remove on reset" not in path.read_text(encoding="utf-8")
    assert record["values"]["tutor_message"] == ""


def test_corrupt_storage_is_not_silently_discarded(workspace):
    path = api_server._learning_workspace_path(api_server._load_atlas_state())
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(HTTPException) as error:
        save(workspace, lesson_response="Must not overwrite corrupt storage")
    assert error.value.status_code == 503
    assert path.read_text(encoding="utf-8") == "{broken"
    with pytest.raises(HTTPException) as recovery:
        api_server._learning_workspace_snapshot(api_server._load_atlas_state())
    assert recovery.value.status_code == 503


def test_atomic_replace_failure_preserves_the_previous_confirmed_draft(workspace, monkeypatch):
    saved = save(workspace, lesson_response="Confirmed")
    state = api_server._load_atlas_state()
    path = api_server._learning_workspace_path(state)

    def fail(*_):
        raise OSError("Replace failed")

    monkeypatch.setattr(learning_workspace.os, "replace", fail)
    with pytest.raises(HTTPException) as error:
        save(saved, lesson_response="Unconfirmed")
    assert error.value.status_code == 503
    assert learning_workspace.read_workspace(path)["values"]["lesson_response"] == "Confirmed"
    assert list(path.parent.glob("*.tmp")) == []
