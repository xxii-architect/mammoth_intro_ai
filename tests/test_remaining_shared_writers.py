from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import asyncio
import json

import pytest

import api_server
from mammoth_os.shared_state import StateConflict, StateUnavailable, state_session


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path)
    monkeypatch.setenv("MAMMOTH_STATE_BACKEND", "local")
    for name in ("ONBOARDING_FILE", "NOTIFICATIONS_FILE", "EXECUTION_LOG_FILE", "ACCOUNT_DELETIONS_FILE",
                 "TRUST_METRICS_FILE"):
        monkeypatch.setattr(api_server, name, tmp_path / f"{name.lower()}.json")
    return tmp_path


@pytest.mark.parametrize("loader,name,default", [
    ("_load_onboarding", "ONBOARDING_FILE", {}),
    ("_load_notifications", "NOTIFICATIONS_FILE", []),
    ("_load_execution_log", "EXECUTION_LOG_FILE", []),
    ("_load_deletion_requests", "ACCOUNT_DELETIONS_FILE", []),
])
def test_missing_records_are_empty_but_corrupt_or_wrong_shape_are_not_reset(paths, loader, name, default):
    path = getattr(api_server, name)
    assert getattr(api_server, loader)() == default
    for content in ("{", "[]" if default == {} else "{}"):
        path.write_text(content, encoding="utf-8")
        with pytest.raises(StateUnavailable):
            getattr(api_server, loader)()
        assert path.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("loader,saver,initial,first,second", [
    ("_load_onboarding", "_save_onboarding", {}, {"alice": {"completed_steps": ["profile"]}},
     {"bob": {"completed_steps": ["first_lesson"]}}),
    ("_load_notifications", "_save_notifications", [{"id": "a", "read": False}, {"id": "b", "read": False}],
     [{"id": "a", "read": True}, {"id": "b", "read": False}],
     [{"id": "a", "read": False}, {"id": "b", "read": True}]),
    ("_load_deletion_requests", "_save_deletion_requests", [{"id": "a", "status": "pending"}, {"id": "b", "status": "pending"}],
     [{"id": "a", "status": "cancelled"}, {"id": "b", "status": "pending"}],
     [{"id": "a", "status": "pending"}, {"id": "b", "status": "confirmed"}]),
])
def test_disjoint_updates_merge_and_competing_edits_conflict(paths, loader, saver, initial, first, second):
    with state_session():
        getattr(api_server, loader)()
        getattr(api_server, saver)(initial)
        first_context, second_context = copy_context(), copy_context()
        first_context.run(getattr(api_server, loader))
        second_context.run(getattr(api_server, loader))
        first_context.run(getattr(api_server, saver), first)
        second_context.run(getattr(api_server, saver), second)
        merged = getattr(api_server, loader)()
        if isinstance(initial, dict):
            assert set(merged) == {"alice", "bob"}
        else:
            assert merged[0] == first[0] and merged[1] == second[1]
        stale = copy_context()
        stale.run(getattr(api_server, loader))
        winner = json.loads(json.dumps(merged))
        loser = json.loads(json.dumps(merged))
        if isinstance(merged, dict):
            winner["alice"]["completed_steps"] = ["winner"]
            loser["alice"]["completed_steps"] = ["loser"]
        else:
            winner[0]["status" if loader == "_load_deletion_requests" else "read"] = "winner"
            loser[0]["status" if loader == "_load_deletion_requests" else "read"] = "loser"
        getattr(api_server, saver)(winner)
        with pytest.raises(StateConflict):
            stale.run(getattr(api_server, saver), loser)


def test_notification_and_execution_appends_are_atomic_and_retained(paths, monkeypatch):
    with ThreadPoolExecutor(max_workers=8) as pool:
        notes = list(pool.map(lambda index: api_server._create_notification(
            str(index), "body", user_id="alice",
        ), range(30)))
        list(pool.map(lambda index: api_server._append_execution_event(
            "fixture", str(index), user_id="alice",
        ), range(30)))
    assert {row["id"] for row in api_server._load_notifications()} == {row["id"] for row in notes}
    assert len(api_server._load_execution_log()) == 30
    monkeypatch.setattr(api_server, "_EXECUTION_LOG_MAX", 5)
    api_server._append_execution_event("fixture", "newest")
    assert len(api_server._load_execution_log()) == 5
    with state_session():
        api_server._read_json(api_server.NOTIFICATIONS_FILE)
        api_server._write_json(api_server.NOTIFICATIONS_FILE, [{"id": str(index)} for index in range(1000)])
    newest = api_server._create_notification("newest", "body")
    rows = api_server._load_notifications()
    assert len(rows) == 1000 and rows[-1] == newest and rows[0]["id"] == "1"


def test_shared_backend_wiring_never_updates_local_copies(paths, monkeypatch):
    state = {}

    def rpc(name, params):
        key = params["p_key"]
        current = state.get(key, {"revision": 0, "payload": None})
        if name == "mammoth_state_read":
            return json.loads(json.dumps(current))
        if params["p_revision"] != current["revision"]:
            return {"saved": False}
        state[key] = {"revision": current["revision"] + 1, "payload": params["p_payload"]}
        return {"saved": True, "revision": state[key]["revision"]}

    monkeypatch.setenv("MAMMOTH_STATE_BACKEND", "supabase")
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", "fixture")
    monkeypatch.setattr("mammoth_os.shared_state.service_rpc", rpc)
    api_server._load_onboarding()
    api_server._save_onboarding({"alice": {"completed_steps": ["profile"]}})
    api_server._load_deletion_requests()
    api_server._save_deletion_requests([{"id": "request", "status": "pending"}])
    api_server._create_notification("title", "body")
    api_server._append_execution_event("fixture", "event")
    assert len(state) == 4
    assert api_server._load_onboarding()["alice"]["completed_steps"] == ["profile"]
    assert api_server._load_deletion_requests()[0]["id"] == "request"
    assert api_server._load_json_file(api_server.NOTIFICATIONS_FILE)[0]["title"] == "title"
    assert not list(paths.iterdir())


def test_execution_log_and_export_reads_surface_corruption(paths):
    api_server.EXECUTION_LOG_FILE.write_text("{", encoding="utf-8")
    with pytest.raises(StateUnavailable):
        api_server._append_execution_event("fixture", "must not silently disappear")
    with pytest.raises(StateUnavailable):
        api_server._load_json_file(api_server.EXECUTION_LOG_FILE)


def test_legacy_unkeyed_trust_metrics_keep_shape_and_report_conflicts(paths, monkeypatch, caplog):
    legacy = {"endpoint": "old"}
    api_server.TRUST_METRICS_FILE.write_text(json.dumps([legacy]), encoding="utf-8")
    api_server._record_trust_metric("fixture", "general", "offline", 1.0, [], True)
    rows = api_server._read_json(api_server.TRUST_METRICS_FILE)
    assert rows[0] == legacy and rows[1]["endpoint"] == "fixture"
    assert "id" not in rows[1]

    def competing_write(*args):
        raise StateConflict("fixture conflict")

    monkeypatch.setattr(api_server, "_write_json", competing_write)
    api_server._record_trust_metric("fixture", "general", "offline", 1.0, [], True)
    assert "Trust telemetry could not be saved" in caplog.text
    assert api_server._read_json(api_server.TRUST_METRICS_FILE) == rows
    caplog.clear()
    api_server.TRUST_METRICS_FILE.write_text("{", encoding="utf-8")
    api_server._record_trust_metric("fixture", "general", "offline", 1.0, [], True)
    assert "Trust telemetry could not be saved" in caplog.text
    assert api_server.TRUST_METRICS_FILE.read_text(encoding="utf-8") == "{"


def test_loaded_onboarding_notification_and_deletion_routes_keep_existing_contracts(paths, monkeypatch):
    class Request:
        def __init__(self, user_id, body=None):
            self.user_id, self.body = user_id, body or {}

        async def json(self):
            return self.body

    async def user(request):
        return {"id": request.user_id}

    monkeypatch.setattr(api_server, "_require_auth_user", user)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    with state_session():
        response = asyncio.run(api_server.complete_onboarding_step(Request("alice", {"step_id": "profile"})))
        assert response["completed_steps"] == ["profile"]
        assert asyncio.run(api_server.get_onboarding_state(Request("bob")))["completed"] == 0
        note = api_server._create_notification("private", "body", user_id="alice")
        denied = asyncio.run(api_server.mark_notification_read(note["id"], Request("bob")))
        assert denied.status_code == 404
        assert asyncio.run(api_server.mark_notification_read(note["id"], Request("alice")))["status"] == "ok"
        assert api_server._load_notifications()[0]["read"] is True
        result = asyncio.run(api_server.request_account_deletion(Request("alice")))
        assert result["grace_days"] == 30
        assert asyncio.run(api_server.get_deletion_status(Request("alice")))["deletion_pending"] is True
        assert asyncio.run(api_server.get_deletion_status(Request("bob")))["deletion_pending"] is False
        assert asyncio.run(api_server.cancel_account_deletion(Request("alice")))["status"] == "ok"
        assert api_server._load_deletion_requests()[0]["status"] == "cancelled"
