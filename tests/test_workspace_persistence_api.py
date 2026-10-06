from copy import deepcopy

import pytest
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


@pytest.mark.parametrize(("artifact_type", "category"), [
    ("curriculum", "curricula"), ("lesson_summary", "lessons"), ("long_form_research", "research"),
    ("market_intel", "research"), ("notes", "notes"), ("flashcard_deck", "flashcards"),
    ("patch_proposal", "code"), ("task_plan", "plans"), ("document", "uncategorized"), ("", "uncategorized"),
])
def test_artifact_metadata_preserves_type_and_is_stable(artifact_type, category):
    raw = {"id": "saved", "body": "Original text.", "artifact_type": artifact_type,
           "agent_id": "research_agent", "quality": {"ready": True},
           "origin": {"page": "agents", "trace_id": "trace-one", "task_id": "task-one"},
           "docx_filename": "report.docx", "meta": {"existing": "preserved"}}
    record = api_server._normalize_workspace_artifact_record(raw)
    assert record["category"] == category
    assert record["artifact_type"] == artifact_type
    assert record["artifact_status"] == "ready"
    assert record["agent_id"] == "research_agent"
    assert record["origin"]["trace_id"] == "trace-one"
    assert record["origin"]["page"] == "agent"
    assert record["docx_filename"] == "report.docx"
    assert record["meta"] == {"existing": "preserved"}
    assert record == api_server._normalize_workspace_artifact_record(record)


@pytest.mark.parametrize(("metadata", "expected"), [
    ({}, "unknown"), ({"status": "ok"}, "unknown"),
    ({"category": "research"}, "unknown"),
    ({"status": "draft"}, "draft"), ({"status": "pending_approval"}, "draft"),
    ({"quality": {"ready": False}, "artifact_status": "ready"}, "draft"),
    ({"status": "error", "quality": {"ready": True}}, "failed"),
    ({"quality": {"status": "failed"}}, "failed"),
])
def test_category_and_run_success_do_not_imply_readiness(metadata, expected):
    item = api_server._normalize_workspace_artifact_record({"body": "Content", **metadata})
    assert item["artifact_status"] == expected
    assert api_server._normalize_workspace_artifact_record(item)["artifact_status"] == expected


def test_legacy_metadata_and_unsafe_origin():
    legacy = api_server._normalize_workspace_artifact_record({
        "body": "Preserved legacy report", "meta": {"artifact_type": "research", "agent_id": "research_agent"},
        "origin": {"page": "https://unsafe.example", "trace_id": "run"},
        "docx_filename": "..\\private.docx",
    })
    assert legacy["category"] == "research"
    assert legacy["agent_id"] == "research_agent"
    assert legacy["origin"] == {"trace_id": "run"}
    assert legacy["docx_filename"] == ""
    untyped = api_server._normalize_workspace_artifact_record({"title": "Research lesson plan", "body": "Unchanged"})
    assert untyped["category"] == "uncategorized"
    assert untyped["body"] == "Unchanged"


def test_artifact_categories_and_crud_are_user_scoped(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: (
        {"id": token, "email": f"{token}@example.test", "is_admin": False} if token in {"alice", "bob"} else None
    ))
    states = {}
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: deepcopy(states.get(api_server._current_request_user_id(), {})))
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda state: states.update({api_server._current_request_user_id(): deepcopy(state)}))
    client = TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    created = client.post("/api/workspace/artifacts", headers=alice, json={
        "id": "same-id", "body": "Alice private output", "artifact_type": "patch_proposal", "status": "pending_approval",
        "user_id": "bob",
    })
    assert created.status_code == 200
    assert created.json()["artifact"]["category"] == "code"
    assert created.json()["artifact"]["artifact_status"] == "draft"
    listing = client.get("/api/workspace/artifacts", headers=alice).json()
    assert {item["id"] for item in listing["categories"]} == {"curricula", "lessons", "research", "notes", "flashcards", "code", "plans", "uncategorized"}
    assert client.get("/api/workspace/artifacts", headers=bob).json()["artifacts"] == []
    assert client.delete("/api/workspace/artifacts/same-id", headers=bob).json()["removed"] is False
    assert len(client.get("/api/workspace/artifacts", headers=alice).json()["artifacts"]) == 1
    assert client.delete("/api/workspace/artifacts", headers=bob).json()["cleared"] == 0
    assert client.get("/api/workspace/artifacts").status_code == 401
