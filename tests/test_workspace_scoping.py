import asyncio
import json

import pytest

import api_server


@pytest.fixture()
def workspace(monkeypatch, tmp_path):
    state = {}
    notes_file = tmp_path / "notes.json"
    buildlog_file = tmp_path / "buildlog.json"
    notes_file.write_text("[]", encoding="utf-8")
    buildlog_file.write_text(json.dumps([{"id": "legacy", "title": "Owner entry"}]), encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes_file)
    monkeypatch.setattr(api_server, "BUILDLOG_FILE", buildlog_file)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_active_account_id", lambda payload: "default")
    return state


@pytest.fixture()
def as_user(monkeypatch):
    tokens = []

    def _set(user_id, is_admin=False):
        monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
        tokens.append((api_server._REQUEST_USER_ID, api_server._REQUEST_USER_ID.set(user_id)))
        tokens.append((api_server._REQUEST_IS_ADMIN, api_server._REQUEST_IS_ADMIN.set(is_admin)))

    yield _set
    for var, token in reversed(tokens):
        var.reset(token)


def test_explorer_tier_is_blocked_server_side(workspace, as_user):
    as_user("user-a")
    response = asyncio.run(api_server.get_buildlog())
    assert response.status_code == 403
    assert json.loads(response.body)["code"] == "tier_required"
    assert asyncio.run(api_server.get_notes()).status_code == 403


def test_anonymous_is_rejected(workspace, as_user):
    as_user("anonymous")
    assert asyncio.run(api_server.get_buildlog()).status_code == 401


def test_pro_users_get_private_buildlog(workspace, as_user):
    workspace["tier"] = "pro"
    as_user("user-a")
    created = asyncio.run(api_server.append_buildlog({"title": "Shipped login"}))
    assert created["user_id"] == "user-a"
    assert [e["title"] for e in asyncio.run(api_server.get_buildlog())] == ["Shipped login"]


def test_buildlog_entries_are_not_shared_between_users(workspace, as_user):
    workspace["tier"] = "pro"
    as_user("user-a")
    asyncio.run(api_server.append_buildlog({"title": "A private"}))
    as_user("user-b")
    assert asyncio.run(api_server.get_buildlog()) == []


def test_admin_sees_legacy_operator_entries(workspace, as_user):
    as_user("owner", is_admin=True)
    titles = [e["title"] for e in asyncio.run(api_server.get_buildlog())]
    assert titles == ["Owner entry"]


def test_developer_access_unlocks_notes(workspace, as_user):
    workspace["developer_access"] = True
    as_user("dev-1")
    created = asyncio.run(api_server.upsert_note({"content": "hello"}))
    assert created["user_id"] == "dev-1"
    assert len(asyncio.run(api_server.get_notes())) == 1
