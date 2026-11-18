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


def test_saved_draft_validation_is_reusable_without_losing_unknown_fields(workspace):
    record = {"exercise_key": workspace["exercise_key"], "revision": 1,
              "values": workspace["values"], "saved_at": "fixture",
              "unknown_extension": {"preserve": True}}
    assert learning_workspace.validate_workspace_record(record) is record
    with pytest.raises(learning_workspace.WorkspaceStorageError):
        learning_workspace.validate_workspace_record({**record, "revision": True})
    with pytest.raises(learning_workspace.WorkspaceStorageError):
        learning_workspace.validate_workspace_record({**record, "values": {}})


def test_saving_draft_preserves_unknown_record_extensions(workspace):
    state = api_server._load_atlas_state()
    path = api_server._learning_workspace_path(state)
    record = {"exercise_key": workspace["exercise_key"], "revision": 1,
              "values": workspace["values"], "saved_at": "fixture",
              "extension": {"retain": "future format"}}
    learning_workspace._write_workspace(path, record)
    current = api_server._learning_workspace_snapshot(state)
    saved = save(current, lesson_response="Updated")
    assert saved["revision"] == 2 and saved["values"]["lesson_response"] == "Updated"
    assert learning_workspace.read_workspace(path)["extension"] == record["extension"]


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
    saved = save(workspace, lesson_response="Account one private draft")
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
    restored = api_server._learning_workspace_snapshot(api_server._load_atlas_state())
    assert restored["values"]["lesson_response"] == "Account one private draft"
    assert restored["exercise_key"] != saved["exercise_key"]
    with pytest.raises(HTTPException) as stale:
        save(saved, lesson_response="A delayed tab must not overwrite recovery")
    assert stale.value.status_code == 409
    assert save(restored, lesson_response="Explicitly resumed")["values"]["lesson_response"] == "Explicitly resumed"


def test_legacy_draft_remains_readable_after_account_switch_and_rollback(workspace):
    state = api_server._load_atlas_state()
    path = api_server._learning_workspace_path(state)
    legacy = {"exercise_key": workspace["exercise_key"], "revision": 1,
              "values": {**workspace["values"], "lesson_response": "Legacy saved text"}, "saved_at": "before"}
    learning_workspace._write_workspace(path, legacy)
    asyncio.run(api_server.mutate_account_workspace({
        "action": "create", "account_id": "second", "display_name": "Second", "activate": True,
    }))
    asyncio.run(api_server.mutate_account_workspace({"action": "switch", "account_id": "default"}))
    current = api_server._load_atlas_state()
    restored = api_server._learning_workspace_snapshot(current)
    assert restored["values"]["lesson_response"] == "Legacy saved text"
    save(restored, lesson_response="Saved after switch")
    disk_record = learning_workspace.read_workspace(path)
    assert disk_record["exercise_key"] == learning_workspace.workspace_content_key(current)
    assert disk_record["values"]["lesson_response"] == "Saved after switch"


def test_account_session_extensions_survive_save_and_switch(workspace, monkeypatch):
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    path = api_server._atlas_state_file_for_request()
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["account_sessions"]["default"]["future_extension"] = {"private": ["retained"]}
    learning_workspace._write_workspace(path, raw)
    state = api_server._load_atlas_state()
    state.pop("current_exercise")
    api_server._save_atlas_state(state)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["account_sessions"]["default"]["future_extension"] == {"private": ["retained"]}
    assert "current_exercise" not in saved["account_sessions"]["default"]
    asyncio.run(api_server.mutate_account_workspace({
        "action": "create", "account_id": "second", "activate": True,
    }))
    asyncio.run(api_server.mutate_account_workspace({"action": "switch", "account_id": "default"}))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["account_sessions"]["default"]["future_extension"] == {"private": ["retained"]}
    assert "future_extension" not in saved["account_sessions"]["second"]
    assert "future_extension" not in api_server._load_atlas_state()


@pytest.mark.parametrize("activate", [True, False])
def test_account_creation_refuses_to_overwrite_unassigned_session(workspace, monkeypatch, activate):
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    path = api_server._atlas_state_file_for_request()
    state = json.loads(path.read_text(encoding="utf-8"))
    state["account_sessions"]["orphan"] = {"topic": "Unassigned saved work", "extension": {"retain": True}}
    learning_workspace._write_workspace(path, state)
    before = path.read_bytes()
    with pytest.raises(HTTPException) as conflict:
        asyncio.run(api_server.mutate_account_workspace({
            "action": "create", "account_id": "orphan", "activate": activate,
        }))
    assert conflict.value.status_code == 409
    assert path.read_bytes() == before


@pytest.mark.parametrize("switch_back", [False, True])
def test_stale_state_save_cannot_reverse_account_switch_or_restore_old_session(workspace, switch_back):
    stale = api_server._load_atlas_state()
    stale["topic"] = "Outdated request"
    asyncio.run(api_server.mutate_account_workspace({
        "action": "create", "account_id": "second", "display_name": "Second", "activate": True,
    }))
    if switch_back:
        asyncio.run(api_server.mutate_account_workspace({"action": "switch", "account_id": "default"}))
    before = api_server._atlas_state_file_for_request().read_bytes()
    with pytest.raises(HTTPException) as conflict:
        api_server._save_atlas_state(stale)
    assert conflict.value.status_code == 409
    assert api_server._atlas_state_file_for_request().read_bytes() == before
    current = api_server._load_atlas_state()
    assert current["active_account_id"] == ("default" if switch_back else "second")
    assert current.get("topic") != "Outdated request"
    current["topic"] = "Fresh request"
    api_server._save_atlas_state(current)
    assert api_server._load_atlas_state()["topic"] == "Fresh request"


def test_concurrent_inactive_account_creation_rejects_lost_update(workspace, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    original_load = api_server._load_account_transition_state
    barrier = threading.Barrier(2)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)

    def synchronized_load():
        result = original_load()
        barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(api_server, "_load_account_transition_state", synchronized_load)

    def create(account):
        try:
            return asyncio.run(api_server.mutate_account_workspace({
                "action": "create", "account_id": account, "activate": False,
            }))
        except HTTPException as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ("first", "second")))
    successes = [result for result in results if isinstance(result, dict)]
    conflicts = [result for result in results if isinstance(result, HTTPException)]
    assert len(successes) == len(conflicts) == 1
    assert successes[0]["status"] == "ok" and conflicts[0].status_code == 409
    state = api_server._load_atlas_state()
    assert len(set(state["accounts"]) & {"first", "second"}) == 1
    assert state["active_account_id"] == "default"


def test_inactive_account_change_fences_stale_state_and_preserves_draft(workspace, monkeypatch):
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    saved = save(workspace, lesson_response="Keep this draft")
    stale = api_server._load_atlas_state()
    result = asyncio.run(api_server.mutate_account_workspace({
        "action": "create", "account_id": "other", "activate": False,
    }))
    assert result["status"] == "ok"
    stale["topic"] = "Outdated write"
    with pytest.raises(HTTPException) as adaptation_conflict:
        api_server._hydrate_learner_state(stale, result={"passed": True})
    assert adaptation_conflict.value.status_code == 409
    with pytest.raises(HTTPException) as conflict:
        api_server._save_atlas_state(stale)
    assert conflict.value.status_code == 409
    current = api_server._load_atlas_state()
    assert "other" in current["accounts"] and current.get("topic") != "Outdated write"
    restored = api_server._learning_workspace_snapshot(current)
    assert restored["exercise_key"] == saved["exercise_key"]
    assert restored["values"]["lesson_response"] == "Keep this draft"


def test_account_transition_rejects_concurrent_learning_state_change(workspace):
    state, snapshot = api_server._load_account_transition_state()
    newer = api_server._load_atlas_state()
    newer["topic"] = "Newer learning work"
    api_server._save_atlas_state(newer)
    state["topic"] = "Old account request"
    with pytest.raises(HTTPException) as conflict:
        api_server._save_atlas_state(state, expected_account_state=snapshot)
    assert conflict.value.status_code == 409
    assert api_server._load_atlas_state()["topic"] == "Newer learning work"


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
