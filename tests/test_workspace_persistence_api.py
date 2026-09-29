from fastapi.testclient import TestClient

import api_server


def _auth_setup(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(
        api_server,
        "_resolve_supabase_user",
        lambda token: {"id": "user-alpha", "email": "alpha@example.com", "is_admin": False} if token == "token-alpha" else None,
    )


def test_workspace_artifacts_crud(monkeypatch):
    state = {"workspace_artifacts": []}
    _auth_setup(monkeypatch)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)

    client = TestClient(api_server.app)
    create = client.post(
        "/api/workspace/artifacts",
        headers={"Authorization": "Bearer token-alpha"},
        json={"title": "Run report", "body": "Plan completed", "format": "md"},
    )
    assert create.status_code == 200
    created = create.json()["artifact"]
    assert created["title"] == "Run report"
    assert created["body"] == "Plan completed"
    assert created["format"] == "md"
    assert len(state["workspace_artifacts"]) == 1

    listed = client.get("/api/workspace/artifacts", headers={"Authorization": "Bearer token-alpha"})
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["status"] == "ok"
    assert len(payload["artifacts"]) == 1
    assert payload["artifacts"][0]["id"] == created["id"]

    deleted = client.delete(f"/api/workspace/artifacts/{created['id']}", headers={"Authorization": "Bearer token-alpha"})
    assert deleted.status_code == 200
    assert deleted.json()["removed"] is True
    assert state["workspace_artifacts"] == []


def test_workspace_artifact_rejects_empty_body(monkeypatch):
    state = {"workspace_artifacts": []}
    _auth_setup(monkeypatch)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/workspace/artifacts",
        headers={"Authorization": "Bearer token-alpha"},
        json={"title": "No body"},
    )
    assert response.status_code == 400


def test_workspace_run_history_crud(monkeypatch):
    state = {"agent_run_history": []}
    _auth_setup(monkeypatch)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)

    client = TestClient(api_server.app)
    create = client.post(
        "/api/workspace/run-history",
        headers={"Authorization": "Bearer token-alpha"},
        json={"agent_id": "coding_agent", "intent": "generate_code", "prompt": "Generate tests", "status": "ok"},
    )
    assert create.status_code == 200
    entry = create.json()["entry"]
    assert entry["agent_id"] == "coding_agent"
    assert entry["prompt"] == "Generate tests"
    assert len(state["agent_run_history"]) == 1

    listed = client.get("/api/workspace/run-history", headers={"Authorization": "Bearer token-alpha"})
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["status"] == "ok"
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["id"] == entry["id"]

    cleared = client.delete("/api/workspace/run-history", headers={"Authorization": "Bearer token-alpha"})
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] == 1
    assert state["agent_run_history"] == []


def test_workspace_run_history_requires_prompt(monkeypatch):
    state = {"agent_run_history": []}
    _auth_setup(monkeypatch)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/workspace/run-history",
        headers={"Authorization": "Bearer token-alpha"},
        json={"agent_id": "coding_agent", "intent": "generate_code"},
    )
    assert response.status_code == 400
