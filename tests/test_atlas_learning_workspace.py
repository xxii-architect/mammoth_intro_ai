from types import SimpleNamespace
import json
import hashlib

import pytest
from fastapi.testclient import TestClient

import api_server


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": "tenant-a", "email": "tenant@example.test", "is_admin": False,
    } if token == "tenant" else None)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)

    async def manifests():
        return [
            SimpleNamespace(agent_id=agent_id, name=agent_id, status="IDLE",
                            capabilities=["learning"], endpoint="private-host-path")
            for agent_id in ["tutor_agent", "curriculum_agent", "research_agent",
                             "reflection_agent", "coding_agent", "browser_agent",
                             "shell_agent", "custodial_agent", "community_engine_agent"]
        ]

    monkeypatch.setattr(api_server.agent_registry, "list_agents", manifests)
    with TestClient(api_server.app) as test_client:
        yield test_client


def test_learning_catalog_requires_sign_in(client):
    assert client.get("/api/atlas/agents").status_code == 401
    assert client.get("/api/atlas/lecture").status_code == 401


def test_lecture_reads_only_the_authenticated_request_users_lesson(client, monkeypatch):
    from mammoth_os.tutor_delivery import build_lesson_lecture

    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": token, "is_admin": False,
    } if token in {"tenant", "other-tenant"} else None)
    states = {
        uid: {"lesson_id": f"{uid}-lesson", "current_lesson": {
            "title": uid, "content": f"## Sources\n\nPrivate teaching for {uid}.",
        }} for uid in ("tenant", "other-tenant")
    }
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: states[api_server._current_request_user_id()])
    for uid in states:
        response = client.get("/api/atlas/lecture", headers={"Authorization": f"Bearer {uid}"})
        assert response.status_code == 200
        assert response.json() == build_lesson_lecture(states[uid]["current_lesson"], lesson_id=f"{uid}-lesson")
    assert states["tenant"]["current_lesson"]["content"] != states["other-tenant"]["current_lesson"]["content"]


def test_tenant_gets_curated_catalog_without_host_metadata(client):
    response = client.get("/api/atlas/agents", headers={"Authorization": "Bearer tenant"})
    assert response.status_code == 200
    agents = response.json()["agents"]
    assert {agent["id"] for agent in agents} == {
        "tutor_agent", "curriculum_agent", "research_agent",
        "reflection_agent", "coding_agent", "browser_agent",
    }
    assert all(set(agent) == {"id", "name", "status", "capabilities"} for agent in agents)
    assert "private-host-path" not in response.text
    assert client.get("/api/agents", headers={"Authorization": "Bearer tenant"}).status_code == 403


def test_unavailable_registry_is_explicit(client, monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", False)
    response = client.get("/api/atlas/agents", headers={"Authorization": "Bearer tenant"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["error"]


def test_failed_registry_is_not_empty_success(client, monkeypatch):
    async def broken():
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr(api_server.agent_registry, "list_agents", broken)
    response = client.get("/api/atlas/agents", headers={"Authorization": "Bearer tenant"})
    assert response.status_code == 503
    assert "private diagnostic" not in response.text


@pytest.fixture
def learning_export(monkeypatch, tmp_path):
    states = {}
    for uid in ("tenant-a", "tenant-b"):
        state = {
            "active_account_id": "default",
            "lesson_id": f"{uid}-lesson", "current_lesson": {"title": uid, "content": "Real teaching."},
            "current_exercise": {"prompt": "Explain the evidence."},
            "chat_history": [{"role": "assistant", "message": f"{uid} private answer"}],
            "assistant_chat_history": [], "study_aids": [],
            "accounts": {"another-account": {"private": "do not export"}},
            "provider_key": "do-not-export-config", "lesson_telemetry": {"other": "excluded"},
        }
        path = tmp_path / f"{uid}.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        states[uid] = path
    monkeypatch.setattr(api_server, "_atlas_state_file_for_request",
                        lambda: states[api_server._current_request_user_id()])
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps([
        {"id": uid, "body": f"{uid} private note", "user_id": uid, "account_id": account,
         "metadata": {"learning_context": {"contract": "mammoth.learning-selection.v1"}}}
        for uid, account in [("tenant-a", "default"), ("tenant-b", "default"), ("tenant-a", "other")]
    ]), encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": token, "is_admin": False,
    } if token in states else None)
    return states, notes


def test_learning_export_is_authenticated_private_and_saved_only(client, learning_export):
    states, _ = learning_export
    assert client.post("/api/atlas/export").status_code == 401
    before = {uid: path.read_bytes() for uid, path in states.items()}
    for uid in states:
        response = client.post("/api/atlas/export", headers={"Authorization": f"Bearer {uid}"},
                               json={"user_id": "other", "account_id": "other"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        result = response.json()
        assert result["contract"] == "mammoth.learning-export.v1"
        assert result["user_id"] == uid and result["account_id"] == "default"
        assert result["saved_learning"]["chat_history"][0]["message"] == f"{uid} private answer"
        assert len(result["linked_notes"]) == 1
        assert result["linked_notes"][0]["body"] == f"{uid} private note"
        assert result["cost"]["model_calls"] == 0
        assert result["cost"]["generation_price_estimate"] is None
        assert "accounts" not in result["saved_learning"]
        assert "lesson_telemetry" not in result["saved_learning"]
        assert "do-not-export-config" not in response.text
        assert "another-account" not in response.text
    assert {uid: path.read_bytes() for uid, path in states.items()} == before


@pytest.mark.parametrize("storage", ["state", "notes", "draft"])
def test_learning_export_fails_explicitly_for_corrupt_saved_data(client, learning_export, storage):
    states, notes = learning_export
    if storage == "state":
        path = states["tenant-a"]
    elif storage == "notes":
        path = notes
    else:
        key = hashlib.sha256(b"default").hexdigest()
        path = states["tenant-a"].with_name(f"tenant-a_workspace_{key}.json")
    path.write_text("{invalid", encoding="utf-8")
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 503
    assert path.read_text(encoding="utf-8") == "{invalid"


def test_learning_export_rejects_oversize_instead_of_trimming(client, learning_export):
    states, _ = learning_export
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["chat_history"][0]["message"] = "x" * (8 * 1024 * 1024)
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 413
    assert "no shortened export" in response.json()["detail"]


def test_learning_export_accepts_exact_eight_mib_boundary(client, learning_export):
    states, _ = learning_export
    headers = {"Authorization": "Bearer tenant-a"}
    original = client.post("/api/atlas/export", headers=headers).json()
    size = len(json.dumps(original, ensure_ascii=True).encode("utf-8"))
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["chat_history"][0]["message"] += "x" * (8 * 1024 * 1024 - size)
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    response = client.post("/api/atlas/export", headers=headers)
    assert response.status_code == 200
    assert len(json.dumps(response.json(), ensure_ascii=True).encode("utf-8")) == 8 * 1024 * 1024
    state["chat_history"][0]["message"] += "x"
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    assert client.post("/api/atlas/export", headers=headers).status_code == 413


def test_learning_export_includes_confirmed_draft_and_only_active_local_account(client, learning_export):
    states, _ = learning_export
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["active_account_id"] = "other"
    state["account_sessions"] = {
        "default": {"chat_history": [{"message": "Do not include default account conversation"}]},
        "other": {"lesson_id": "other-lesson", "current_lesson": {"title": "Other lesson"},
                  "current_exercise": {"prompt": "Explain a different claim."},
                  "chat_history": [{"message": "Selected account conversation"}]},
    }
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    headers = {"Authorization": "Bearer tenant-a"}
    original = client.post("/api/atlas/export", headers=headers).json()
    recovery = original["workspace_recovery"]
    values = {**recovery["values"], "lesson_response": "Confirmed full response."}
    saved = client.post("/api/atlas/workspace", headers=headers, json={
        "exercise_key": recovery["exercise_key"], "revision": recovery["revision"], "values": values,
    })
    assert saved.status_code == 200
    result = client.post("/api/atlas/export", headers=headers)
    assert result.status_code == 200
    payload = result.json()
    assert payload["account_id"] == "other"
    assert payload["saved_learning"]["chat_history"][0]["message"] == "Selected account conversation"
    assert "Do not include default account" not in result.text
    assert payload["workspace_recovery"]["values"]["lesson_response"] == "Confirmed full response."
    assert payload["workspace_recovery"]["saved_at"]
    assert len(payload["linked_notes"]) == 1
    assert payload["linked_notes"][0]["account_id"] == "other"


def test_account_export_reuses_learning_export_instead_of_omitting_tutor_history(client, learning_export, monkeypatch):
    monkeypatch.setattr(api_server, "_load_json_file", lambda path: [])
    monkeypatch.setattr(api_server, "_load_notifications", lambda: [])
    monkeypatch.setattr(api_server, "_load_message_feedback", lambda: [])
    monkeypatch.setattr(api_server, "_load_deletion_requests", lambda: [])
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    headers = {"Authorization": "Bearer tenant-a"}
    response = client.post("/api/account/export-data", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    learning = response.json()["learning_workspace"]
    assert learning["contract"] == "mammoth.learning-export.v1"
    assert learning["saved_learning"]["chat_history"][0]["message"] == "tenant-a private answer"
    assert learning["workspace_recovery"]["exercise_key"]


def test_learning_export_does_not_adopt_unowned_legacy_notes(client, learning_export):
    _, notes = learning_export
    data = json.loads(notes.read_text(encoding="utf-8"))
    data.append({"body": "Unowned legacy content must not be assigned to this user",
                 "metadata": {"learning_context": {"contract": "mammoth.learning-selection.v1"}}})
    notes.write_text(json.dumps(data), encoding="utf-8")
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 200
    assert "Unowned legacy" not in response.text
    assert response.json()["linked_notes"] == [data[0]]


def test_learning_export_preserves_stored_history_instead_of_applying_new_trimming(client, learning_export):
    states, _ = learning_export
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["chat_history"] = [{"role": "user", "message": f"Stored message {index}"} for index in range(75)]
    state["lesson_history"] = [{"lesson_id": f"stored-{index}", "lesson": {"content": "Real saved lesson."}}
                               for index in range(85)]
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 200
    assert response.json()["saved_learning"]["chat_history"] == state["chat_history"]
    assert response.json()["saved_learning"]["lesson_history"] == state["lesson_history"]
