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
    assert client.post("/api/atlas/agents/run", json={"agent_id": "research_agent"}).status_code == 401
    assert client.get("/api/atlas/lecture").status_code == 401
    for method, path in [("get", "/api/atlas/controls"), ("put", "/api/atlas/controls"),
                         ("get", "/api/atlas/history/preview"), ("delete", "/api/atlas/history"),
                         ("post", "/api/atlas/operations/unknown/cancel")]:
        kwargs = {"json": {}} if method in {"put", "delete"} else {}
        assert client.request(method, path, **kwargs).status_code == 401


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


@pytest.mark.parametrize("route", ["lesson", "submit", "next", "curricula/start", "plan", "regenerate", "chat"])
def test_zero_learning_cap_blocks_each_generation_route_before_work(client, learning_export, route):
    headers = {"Authorization": "Bearer tenant-a"}
    configured = client.put("/api/atlas/controls", headers=headers, json={"daily_request_limit": 0})
    assert configured.status_code == 200
    assert configured.headers["cache-control"] == "no-store"
    response = client.post(f"/api/atlas/{route}", headers=headers, json={})
    assert response.status_code == 429
    assert "limit" in response.json()["detail"]
    result = client.get("/api/atlas/controls", headers=headers).json()
    assert result["admitted_requests"] == 0
    assert result["operations"] == []


def test_learning_controls_and_cancel_are_private_to_request_user(client, learning_export):
    a = {"Authorization": "Bearer tenant-a"}
    b = {"Authorization": "Bearer tenant-b"}
    client.put("/api/atlas/controls", headers=a, json={"daily_request_limit": 0})
    assert client.post("/agent/atlas/run", headers=a, params={"payload": "test"}).status_code == 429
    assert client.get("/api/atlas/controls", headers=b).json()["daily_request_limit"] is None
    assert client.post("/api/atlas/operations/missing/cancel", headers=b).status_code == 404
    for bad in [{"daily_request_limit": True}, {"daily_request_limit": 1, "user_id": "tenant-b"}]:
        assert client.put("/api/atlas/controls", headers=a, json=bad).status_code == 400


@pytest.mark.parametrize("agent_id", sorted(api_server._LEARNING_AGENT_IDS))
def test_zero_cap_blocks_learning_agent_before_dispatch(client, learning_export, monkeypatch, agent_id):
    calls = []
    async def dispatch(body):
        calls.append(body)
        return {"status": "ok"}
    monkeypatch.setattr(api_server, "run_agent", dispatch)
    headers = {"Authorization": "Bearer tenant-a"}
    client.put("/api/atlas/controls", headers=headers, json={"daily_request_limit": 0})
    response = client.post("/api/atlas/agents/run", headers=headers, json={"agent_id": agent_id})
    assert response.status_code == 429
    assert calls == []
    assert client.get("/api/atlas/controls", headers=headers).json()["admitted_requests"] == 0


@pytest.mark.parametrize("agent_id", ["shell_agent", "custodial_agent", "", None, []])
def test_learning_agent_route_rejects_non_catalog_agents(client, learning_export, monkeypatch, agent_id):
    async def dispatch(body):
        pytest.fail("Invalid learning agent must not dispatch")
    monkeypatch.setattr(api_server, "run_agent", dispatch)
    response = client.post("/api/atlas/agents/run", headers={"Authorization": "Bearer tenant-a"},
                           json={"agent_id": agent_id, "intent": "research"})
    assert response.status_code == 400


def test_learning_agent_admission_is_private_and_failures_count(client, learning_export, monkeypatch):
    calls = []
    async def dispatch(body):
        calls.append(api_server._current_request_user_id())
        return {"status": "ok", "result": {"status": "error"}}
    monkeypatch.setattr(api_server, "run_agent", dispatch)
    a = {"Authorization": "Bearer tenant-a"}
    b = {"Authorization": "Bearer tenant-b"}
    client.put("/api/atlas/controls", headers=a, json={"daily_request_limit": 1})
    body = {"agent_id": "research_agent", "user_id": "tenant-b"}
    assert client.post("/api/atlas/agents/run", headers=a, json=body).status_code == 200
    assert client.post("/api/atlas/agents/run", headers=a, json=body).status_code == 429
    snapshot = client.get("/api/atlas/controls", headers=a).json()
    assert snapshot["admitted_requests"] == 1
    assert snapshot["operations"][0]["status"] == "failed"
    assert snapshot["operations"][0]["route"] == "/api/atlas/agents/run"
    assert client.get("/api/atlas/controls", headers=b).json()["admitted_requests"] == 0
    assert client.post("/api/atlas/agents/run", headers=b, json=body).status_code == 200
    assert calls == ["tenant-a", "tenant-b"]


def test_uncapped_learning_agent_preserves_request_and_records_success(client, learning_export, monkeypatch):
    calls = []
    async def dispatch(body):
        calls.append(body)
        return {"status": "ok", "result": {"status": "ok", "output": {"answer": "Grounded explanation"}}}
    monkeypatch.setattr(api_server, "run_agent", dispatch)
    headers = {"Authorization": "Bearer tenant-a"}
    body = {"agent_id": "tutor_agent", "intent": "tutor",
            "payload": {"prompt": "Explain evidence", "lesson_id": "tenant-a-lesson"}}
    result = client.post("/api/atlas/agents/run", headers=headers, json=body)
    assert result.status_code == 200
    assert result.json()["result"]["output"]["answer"] == "Grounded explanation"
    assert calls == [body]
    snapshot = client.get("/api/atlas/controls", headers=headers).json()
    assert snapshot["daily_request_limit"] is None
    assert snapshot["admitted_requests"] == 1
    assert snapshot["operations"][0]["status"] == "finished"


@pytest.mark.parametrize("thread_checks", [False, True])
def test_learning_agent_cancel_crosses_worker_and_discards_reply(client, learning_export, monkeypatch, thread_checks):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from mammoth_os.learning_controls import check_cancelled, has_operation

    started, release = threading.Event(), threading.Event()
    calls, updates, activities = [], [], []
    async def manifest(agent_id):
        return None
    monkeypatch.setattr(api_server.agent_registry, "get_agent", manifest)
    monkeypatch.setattr(api_server, "AGENTS", {"research": object()})
    monkeypatch.setattr(api_server, "_runtime_status_snapshot", lambda: {"state": "ready"})
    monkeypatch.setattr(api_server, "_upsert_task",
                        lambda task_id, title, **kwargs: updates.append(kwargs) or {"title": title})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: activities.append(kwargs))
    def run(agent, payload):
        calls.append((agent, has_operation(), api_server._current_request_user_id()))
        started.set()
        assert release.wait(10)
        if thread_checks:
            check_cancelled()
        return {"status": "ok", "output": {"answer": "Do not deliver this cancelled result."}}
    monkeypatch.setattr(api_server, "registry_run_agent", run)
    headers = {"Authorization": "Bearer tenant-a"}
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(client.post, "/api/atlas/agents/run", headers=headers,
                              json={"agent_id": "research_agent", "intent": "research",
                                    "payload": {"prompt": "Compare evidence."}})
        try:
            assert started.wait(10)
            operation = client.get("/api/atlas/controls", headers=headers).json()["operations"][0]
            assert client.post(f"/api/atlas/operations/{operation['id']}/cancel",
                               headers={"Authorization": "Bearer tenant-b"}).status_code == 404
            assert client.post(f"/api/atlas/operations/{operation['id']}/cancel",
                               headers=headers).json()["status"] == "cancellation_requested"
            assert not request.done()
        finally:
            release.set()
        response = request.result(timeout=15)
    assert response.status_code == 409
    assert response.json()["status"] == "cancelled"
    assert "Do not deliver" not in response.text
    assert calls == [("research", True, "tenant-a")]
    assert updates[-1]["status"] == "cancelled"
    assert not any(update["status"] == "completed" for update in updates)
    assert activities[-1]["kind"] == "task_cancelled"
    snapshot = client.get("/api/atlas/controls", headers=headers).json()
    assert snapshot["admitted_requests"] == 1
    assert snapshot["operations"][0]["status"] == "cancelled_at_boundary"


def test_corrupt_learning_controls_fail_closed_without_reset_or_generation(client, learning_export):
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        path = api_server._learning_controls().path
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    path.write_bytes(b"not-a-sqlite-database")
    headers = {"Authorization": "Bearer tenant-a"}
    assert client.get("/api/atlas/controls", headers=headers).status_code == 503
    assert client.post("/api/atlas/chat", headers=headers, json={"message": "Do not generate."}).status_code == 503
    assert client.post("/api/atlas/agents/run", headers=headers,
                       json={"agent_id": "research_agent"}).status_code == 503
    assert path.read_bytes() == b"not-a-sqlite-database"


@pytest.mark.parametrize("field,value", [("accounts", []), ("account_sessions", {"default": "invalid"}),
                                        ("accounts", {"default": {"profile": "invalid"}})])
def test_invalid_saved_account_shapes_block_learning_changes(client, learning_export, field, value):
    states, _ = learning_export
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state[field] = value
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    before = states["tenant-a"].read_bytes()
    headers = {"Authorization": "Bearer tenant-a"}
    for method, path, body in [("POST", "/api/atlas/export", {}),
                                ("POST", "/api/atlas/chat", {"message": "Do not generate."}),
                                ("DELETE", "/api/atlas/history", {"confirmation": "DELETE SAVED LEARNING", "preview_token": "old"})]:
        assert client.request(method, path, headers=headers, json=body).status_code == 503
    assert states["tenant-a"].read_bytes() == before


def test_chat_cancellation_waits_for_provider_boundary_and_does_not_save_reply(client, learning_export, monkeypatch):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from mammoth_os import llm_client

    states, _ = learning_export
    before = states["tenant-a"].read_bytes()
    started = threading.Event()
    release = threading.Event()
    headers = {"Authorization": "Bearer tenant-a"}

    class Client:
        async def generate(self, prompt, **kwargs):
            started.set()
            await asyncio.to_thread(release.wait, 10)
            return "A complete answer that must not be saved after cancellation."

    monkeypatch.setattr(llm_client, "get_llm_client", lambda config=None: Client())
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: {})
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(client.post, "/api/atlas/chat", headers=headers,
                              json={"message": "Explain evidence comparisons.", "mode": "assistant"})
        try:
            assert started.wait(10)
            operation = client.get("/api/atlas/controls", headers=headers).json()["operations"][0]
            assert client.post(f"/api/atlas/operations/{operation['id']}/cancel",
                               headers={"Authorization": "Bearer tenant-b"}).status_code == 404
            cancel = client.post(f"/api/atlas/operations/{operation['id']}/cancel", headers=headers)
            assert cancel.json()["status"] == "cancellation_requested"
            assert not request.done()
        finally:
            release.set()
        response = request.result(timeout=15)
    assert response.status_code == 409
    assert response.json()["status"] == "cancelled"
    assert states["tenant-a"].read_bytes() == before
    result = client.get("/api/atlas/controls", headers=headers).json()
    assert result["admitted_requests"] == 1
    assert result["operations"][0]["status"] == "cancelled_at_boundary"
    assert result["operations"][0]["finished_at"]


def test_learning_deletion_erases_selected_storage_and_rejects_stale_saves(client, learning_export):
    from mammoth_os.learning_workspace import save_workspace, workspace_snapshot
    from fastapi import HTTPException

    states, notes = learning_export
    other_before = states["tenant-b"].read_bytes()
    notes_before = notes.read_bytes()
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["account_sessions"] = {
        "default": {key: state[key] for key in ["lesson_id", "current_lesson", "current_exercise", "chat_history"]},
        "other": {"chat_history": [{"message": "Other account retained."}]},
    }
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        stale = api_server._load_learning_export_state()
        draft_path = api_server._learning_workspace_path(stale)
        snapshot = workspace_snapshot(stale)
        save_workspace(draft_path, stale, {**snapshot, "values": {**snapshot["values"], "lesson_response": "Private saved draft"}}, "now")
        headers = {"Authorization": "Bearer tenant-a"}
        preview = client.get("/api/atlas/history/preview", headers=headers)
        assert preview.status_code == 200
        assert preview.headers["cache-control"] == "no-store"
        body = {"confirmation": "DELETE SAVED LEARNING", "preview_token": preview.json()["preview_token"]}
        assert client.request("DELETE", "/api/atlas/history", headers=headers,
                              json={**body, "confirmation": "yes"}).status_code == 400
        response = client.request("DELETE", "/api/atlas/history", headers=headers, json=body)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted_from_active_storage"
        assert response.json()["provider_erasure_confirmed"] is False
        after = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
        assert all(field not in after for field in api_server._ERASABLE_LEARNING_FIELDS)
        assert all(field not in after["account_sessions"]["default"] for field in api_server._ERASABLE_LEARNING_FIELDS)
        assert after["account_sessions"]["other"] == state["account_sessions"]["other"]
        assert after["provider_key"] == "do-not-export-config"
        assert not draft_path.exists()
        assert states["tenant-b"].read_bytes() == other_before
        assert notes.read_bytes() == notes_before
        with pytest.raises(HTTPException) as error:
            api_server._save_atlas_state(stale)
        assert error.value.status_code == 409
        assert client.request("DELETE", "/api/atlas/history", headers=headers, json=body).status_code == 409
        exported = client.post("/api/atlas/export", headers=headers).json()
        assert exported["saved_learning"] == {}
        assert exported["workspace_recovery"]["saved_at"] is None
    finally:
        api_server._REQUEST_USER_ID.reset(token)


def test_deletion_preview_is_invalidated_by_saved_changes(client, learning_export):
    states, _ = learning_export
    headers = {"Authorization": "Bearer tenant-a"}
    preview = client.get("/api/atlas/history/preview", headers=headers).json()
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["chat_history"].append({"message": "A newer message."})
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    before = states["tenant-a"].read_bytes()
    response = client.request("DELETE", "/api/atlas/history", headers=headers,
                              json={"confirmation": "DELETE SAVED LEARNING", "preview_token": preview["preview_token"]})
    assert response.status_code == 409
    assert states["tenant-a"].read_bytes() == before


def test_learning_deletion_does_not_claim_success_when_write_fails(client, learning_export, monkeypatch):
    from mammoth_os import learning_workspace

    headers = {"Authorization": "Bearer tenant-a"}
    preview = client.get("/api/atlas/history/preview", headers=headers).json()
    states, _ = learning_export
    before = states["tenant-a"].read_bytes()

    def failed(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(learning_workspace, "_write_workspace", failed)
    response = client.request("DELETE", "/api/atlas/history", headers=headers,
                              json={"confirmation": "DELETE SAVED LEARNING", "preview_token": preview["preview_token"]})
    assert response.status_code == 503
    assert states["tenant-a"].read_bytes() == before


@pytest.fixture
def learning_export(monkeypatch, tmp_path, isolate_learning_request_controls):
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
    monkeypatch.setattr(api_server, "_learning_controls", isolate_learning_request_controls)
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
        assert result["learner_adaptation"]["status"] == "not_saved"
        assert result["learner_adaptation"]["model"] is None
        assert "accounts" not in result["saved_learning"]
        assert "lesson_telemetry" not in result["saved_learning"]
        assert "do-not-export-config" not in response.text
        assert "another-account" not in response.text
    assert {uid: path.read_bytes() for uid, path in states.items()} == before


def _saved_adaptation(uid, account="default"):
    from pathlib import Path
    token = api_server._REQUEST_USER_ID.set(uid)
    try:
        root = Path(api_server._learner_storage_path(f"workspace:{account}"))
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "atlas_learner_model.json"
    model = {
        "version": 1, "user_id": f"workspace:{account}", "attempts": 24,
        "mastery": {f"{uid}-{account}": 0.8}, "confidence": {"evidence": 0.7},
        "recent_outcomes": [{"concept": f"evidence-{i}", "timestamp": str(i)} for i in range(24)],
        "onboarding": {"goals": [f"{uid}-{account} goal"]},
        "memory_graph": {"nodes": [{"id": "real", "label": "Actual saved concept"}], "edges": []},
        "private_provider_config": "never-export-this-extension",
    }
    path.write_text(json.dumps(model), encoding="utf-8")
    return path, model


def _erasable_adaptation(uid="tenant-a", account="default"):
    path, model = _saved_adaptation(uid, account)
    model.pop("private_provider_config")
    path.write_text(json.dumps(model), encoding="utf-8")
    return path, model


def _delete_adaptation(client, *, tenant="tenant-a", preview=None, confirmation="DELETE PRIVATE ADAPTATION"):
    headers = {"Authorization": f"Bearer {tenant}"}
    if preview is None:
        response = client.get("/api/atlas/learner/deletion-preview", headers=headers)
        assert response.status_code == 200
        preview = response.json()
    return client.request("DELETE", "/api/atlas/learner/adaptation", headers=headers, json={
        "confirmation": confirmation, "preview_token": preview["preview_token"],
    })


def test_adaptation_erasure_is_authenticated_reviewed_scoped_and_verified(client, learning_export):
    states, notes = learning_export
    assert client.get("/api/atlas/learner/deletion-preview").status_code == 401
    assert client.request("DELETE", "/api/atlas/learner/adaptation", json={}).status_code == 401
    path, model = _erasable_adaptation()
    other, _ = _erasable_adaptation("tenant-b")
    second, _ = _erasable_adaptation("tenant-a", "second")
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    caches = {"learner_model": model, "learner_context": {"goals": ["private"]},
              "learner_profile": {"attempts": 24}, "learner_storage": {"old": True}}
    state.update(caches)
    state["account_sessions"] = {"default": {**caches, "chat_history": state["chat_history"],
                                            "unknown_session_field": "preserve"},
                                  "second": {"learner_model": {"private": "second cache"}}}
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    preserved = {p: p.read_bytes() for p in (other, second, notes, states["tenant-b"])}
    response = client.get("/api/atlas/learner/deletion-preview?user_id=tenant-b&account_id=second",
                          headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    preview = response.json()
    assert preview["account_id"] == "default"
    assert preview["cached_fields"] == sorted(caches)
    assert preview["deletion_available"] is True
    assert "private" not in json.dumps(preview["cached_fields"])
    assert "tenant-a-default goal" not in response.text
    result = _delete_adaptation(client, preview=preview)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    receipt = result.json()
    assert receipt["status"] == "deleted_from_active_storage" and len(receipt["receipt_id"]) == 32
    assert receipt["provider_erasure_confirmed"] is receipt["backup_erasure_confirmed"] is False
    assert not path.exists()
    saved = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    assert saved["learner_erasure"]["default"] == {"epoch": receipt["receipt_id"], "status": "complete"}
    for key in caches:
        assert key not in saved and key not in saved["account_sessions"]["default"]
    for key, value in state.items():
        if key not in caches and key != "account_sessions":
            assert saved[key] == value
    assert saved["account_sessions"]["default"]["unknown_session_field"] == "preserve"
    assert saved["account_sessions"]["second"] == state["account_sessions"]["second"]
    assert {p: p.read_bytes() for p in preserved} == preserved
    export = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert export.json()["learner_adaptation"]["status"] == "not_saved"
    assert not path.exists()


@pytest.mark.parametrize("confirmation", ["delete private adaptation", "DELETE SAVED LEARNING", ""])
def test_adaptation_erasure_requires_exact_confirmation(client, learning_export, confirmation):
    path, _ = _erasable_adaptation()
    before = path.read_bytes()
    assert _delete_adaptation(client, confirmation=confirmation).status_code == 400
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["model", "cache", "account", "tenant"])
def test_changed_adaptation_preview_cannot_delete(client, learning_export, change):
    states, _ = learning_export
    path, model = _erasable_adaptation()
    preview = client.get("/api/atlas/learner/deletion-preview", headers={"Authorization": "Bearer tenant-a"}).json()
    tenant = "tenant-a"
    if change == "model":
        model["attempts"] += 1
        path.write_text(json.dumps(model), encoding="utf-8")
    elif change == "tenant":
        tenant = "tenant-b"
    else:
        state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
        if change == "account":
            state["active_account_id"] = "second"
        else:
            state["learner_context"] = {"changed": True}
        states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    assert _delete_adaptation(client, preview=preview, tenant=tenant).status_code == 409
    assert path.exists()


def test_unknown_extensions_block_erasure_and_corrupt_models_do_not_get_receipts(client, learning_export):
    path, _ = _saved_adaptation("tenant-a")
    before = path.read_bytes()
    preview = client.get("/api/atlas/learner/deletion-preview", headers={"Authorization": "Bearer tenant-a"}).json()
    assert preview["deletion_available"] is False
    assert _delete_adaptation(client, preview=preview).status_code == 409
    assert path.read_bytes() == before
    path.write_text("{bad", encoding="utf-8")
    assert client.get("/api/atlas/learner/deletion-preview", headers={"Authorization": "Bearer tenant-a"}).status_code == 503
    assert _delete_adaptation(client, preview=preview).status_code == 503
    assert path.read_text(encoding="utf-8") == "{bad"


def test_stale_hosted_writers_and_old_approvals_cannot_resurrect_adaptation(client, learning_export, monkeypatch):
    from fastapi import HTTPException
    _erasable_adaptation()
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        stale = api_server._load_atlas_state()
        guard = api_server._learner_approval_guard(stale)
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    assert _delete_adaptation(client).status_code == 200
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        with pytest.raises(HTTPException) as error:
            api_server._hydrate_learner_state(stale, result={"passed": True})
        assert error.value.status_code == 409
        with pytest.raises(HTTPException) as error:
            api_server._save_atlas_state(stale)
        assert error.value.status_code == 409
        with pytest.raises(HTTPException) as error:
            api_server._reset_learner_model_state("workspace:default", state=stale)
        assert error.value.status_code == 409
        for operation, payload in [
            ("atlas_onboard_update", {"onboarding": {"goals": ["old goal"]}}),
            ("atlas_learner_reset", {}), ("atlas_session_reset", {}),
        ]:
            for binding in (guard, {}, None):
                with pytest.raises(HTTPException) as error:
                    api_server._execute_approval_record({"operation": operation, "payload": {
                        **payload, "learner_write_guard": binding,
                    }})
                assert error.value.status_code == 409
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    fresh = client.post("/api/atlas/onboard", headers={"Authorization": "Bearer tenant-a"},
                        json={"experience_level": "advanced", "goals": ["New explicit goal"]})
    assert fresh.status_code == 200
    assert fresh.json()["learner_model"]["attempts"] == 0
    assert fresh.json()["learner_model"]["onboarding"]["goals"] == ["New explicit goal"]
    assert "old goal" not in fresh.text


def test_erasure_cancels_delayed_assessment_before_it_can_recreate_model(client, learning_export, monkeypatch):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from mammoth_os import lesson_assessment
    states, _ = learning_export
    path, _ = _erasable_adaptation()
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["current_exercise"]["submission_mode"] = "text"
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    started, release = threading.Event(), threading.Event()
    async def delayed(*args):
        started.set()
        assert await asyncio.to_thread(release.wait, 20)
        return {"passed": True, "feedback": "Do not retain this obsolete assessment."}
    monkeypatch.setattr(lesson_assessment, "assess_text_response", delayed)
    headers = {"Authorization": "Bearer tenant-a"}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, "/api/atlas/submit", headers=headers, json={"response": "Evidence"})
        try:
            assert started.wait(10)
            assert _delete_adaptation(client).status_code == 200
            assert not path.exists()
        finally:
            release.set()
        response = future.result(timeout=20)
    assert response.status_code == 409 and response.json()["status"] == "cancelled"
    assert not path.exists()
    saved = states["tenant-a"].read_text(encoding="utf-8")
    assert "obsolete assessment" not in saved and '"last_submission"' not in saved
    operations = client.get("/api/atlas/controls", headers=headers).json()["operations"]
    assert operations[0]["status"] == "cancelled_at_boundary"


def test_erasure_generation_survives_a_separate_worker_process(client, learning_export, tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    states, _ = learning_export
    path, _ = _erasable_adaptation()
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        stale = api_server._load_atlas_state()
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    snapshot = tmp_path / "old-worker-state.json"
    snapshot.write_text(json.dumps(stale), encoding="utf-8")
    assert _delete_adaptation(client).status_code == 200
    script = """
import json, sys
from pathlib import Path
import api_server
from fastapi import HTTPException
api_server._REQUEST_USER_ID.set("tenant-a")
api_server._atlas_state_file_for_request = lambda: Path(sys.argv[1])
state = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
for write in (lambda: api_server._hydrate_learner_state(state, result={"passed": True}),
              lambda: api_server._save_atlas_state(state)):
    try:
        write()
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError("A stale worker saved erased adaptation")
"""
    env = {**os.environ, "PYTHONPATH": str(Path(api_server.__file__).parent / "src")}
    worker = subprocess.run([sys.executable, "-c", script, str(states["tenant-a"]), str(snapshot)],
                            env=env, capture_output=True, text=True, timeout=45)
    assert worker.returncode == 0, worker.stderr
    assert not path.exists()


def test_erasure_serializes_with_an_active_hosted_writer_in_another_process(client, learning_export, monkeypatch):
    import os
    import subprocess
    import sys
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from pathlib import Path
    from mammoth_os import learning_workspace
    states, _ = learning_export
    path, _ = _erasable_adaptation()
    headers = {"Authorization": "Bearer tenant-a"}
    preview = client.get("/api/atlas/learner/deletion-preview", headers=headers).json()
    script = """
import sys
from pathlib import Path
import api_server
from mammoth_os.learner_model import set_onboarding_profile
api_server._REQUEST_USER_ID.set("tenant-a")
api_server._atlas_state_file_for_request = lambda: Path(sys.argv[1])
state = api_server._load_atlas_state()
def write(*, storage_path):
    print("READY", flush=True)
    assert sys.stdin.readline().strip() == "continue"
    return set_onboarding_profile(user_id="workspace:default", storage_path=storage_path,
                                  onboarding={"goals": ["Writer completed first"]})
api_server._learner_storage_action(write, "workspace:default", guard_state=state)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(api_server.__file__).parent / "src")}
    attempted = threading.Event()
    original = learning_workspace._workspace_lock
    @contextmanager
    def observed(target):
        if target == states["tenant-a"]:
            attempted.set()
        with original(target):
            yield
    monkeypatch.setattr(learning_workspace, "_workspace_lock", observed)
    with subprocess.Popen([sys.executable, "-c", script, str(states["tenant-a"])],
                          env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as worker:
        assert worker.stdout.readline().strip() == "READY"
        with ThreadPoolExecutor(max_workers=1) as pool:
            deletion = pool.submit(_delete_adaptation, client, preview=preview)
            try:
                assert attempted.wait(10)
                assert not deletion.done()
            finally:
                _, errors = worker.communicate(input="continue\n", timeout=45)
            response = deletion.result(timeout=20)
    assert worker.returncode == 0, errors
    assert response.status_code == 409
    assert json.loads(path.read_text(encoding="utf-8"))["onboarding"]["goals"] == ["Writer completed first"]
    assert _delete_adaptation(client).status_code == 200
    assert not path.exists()


def test_erasure_preserves_other_account_operations_and_all_usage(client, learning_export):
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        store = api_server._learning_controls()
        own = store.begin("/api/atlas/chat", "default")
        other = store.begin("/api/atlas/chat", "second")
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    assert _delete_adaptation(client).status_code == 200
    operations = {item["id"]: item for item in store.snapshot()["operations"]}
    assert operations[own]["status"] == "cancellation_requested"
    assert operations[other]["status"] == "running"
    assert store.snapshot()["admitted_requests"] == 2


def test_absent_model_erasure_preserves_legacy_files_and_removes_caches_only(client, learning_export, monkeypatch, tmp_path):
    from mammoth_os import learner_model
    states, _ = learning_export
    legacy = tmp_path / "ambiguous-legacy.json"
    legacy.write_text('{"user_id":"workspace:default","attempts":999}', encoding="utf-8")
    before = legacy.read_bytes()
    original = learner_model._model_path
    def scoped_only(storage_path=None):
        assert storage_path is not None, "Deletion must not touch the shared legacy model"
        return original(storage_path)
    monkeypatch.setattr(learner_model, "_model_path", scoped_only)
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["learner_context"] = {"unverified": "cached"}
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    response = _delete_adaptation(client)
    assert response.status_code == 200
    saved = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    assert "learner_context" not in saved
    assert saved["chat_history"] == state["chat_history"]
    assert legacy.read_bytes() == before
    preview = client.get("/api/atlas/learner/deletion-preview", headers={"Authorization": "Bearer tenant-a"}).json()
    assert preview["model_status"] == "not_saved" and preview["cached_fields"] == []


def test_second_account_erasure_leaves_first_account_model_and_caches(client, learning_export):
    states, _ = learning_export
    first, _ = _erasable_adaptation()
    second, _ = _erasable_adaptation("tenant-a", "second")
    before = first.read_bytes()
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["active_account_id"] = "second"
    first_session = {"learner_model": {"private": "first cache"}, "chat_history": [{"message": "first conversation"}]}
    state["account_sessions"] = {"default": first_session, "second": {"learner_context": {"private": "second cache"}}}
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    response = _delete_adaptation(client)
    assert response.status_code == 200 and response.json()["account_id"] == "second"
    assert not second.exists() and first.read_bytes() == before
    saved = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    assert saved["account_sessions"]["default"] == first_session
    assert "learner_context" not in saved["account_sessions"]["second"]
    assert set(saved["learner_erasure"]) == {"second"}


def test_learner_mutation_approvals_capture_server_scope_and_fresh_approval_still_works(client, learning_export, monkeypatch):
    captured = []
    def approval(*args, **kwargs):
        record = {"id": "test-learner-approval", **kwargs}
        captured.append(record)
        return record
    monkeypatch.setattr(api_server, "_create_approval_record", approval)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    for route in ("/api/atlas/onboard", "/api/atlas/learner/reset", "/api/atlas/reset"):
        response = client.post(route, headers={"Authorization": "Bearer tenant-a"}, json={
            "approval_mode": True, "experience_level": "advanced", "learner_write_guard": {"forged": True},
        })
        assert response.status_code == 200
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        expected = api_server._learner_approval_guard(api_server._load_learning_export_state())
        assert all(record["payload"]["learner_write_guard"] == expected for record in captured)
        result = api_server._execute_approval_record(captured[0])
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    assert result["learner_model"]["onboarding"]["experience_level"] == "advanced"


@pytest.mark.parametrize("records", [None, [], {"default": {}},
                                     {"default": {"epoch": "bad", "status": "complete"}}])
def test_invalid_erasure_fence_fails_closed(client, learning_export, records):
    states, _ = learning_export
    path, _ = _erasable_adaptation()
    before = path.read_bytes()
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["learner_erasure"] = records
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    for route in ("/api/atlas/learner", "/api/atlas/learner/deletion-preview"):
        assert client.get(route, headers={"Authorization": "Bearer tenant-a"}).status_code == 503
    assert path.read_bytes() == before


@pytest.mark.parametrize("failure", ["fence", "unlink", "completion", "verification"])
def test_partial_adaptation_erasure_never_issues_receipt_and_is_retryable(client, learning_export, monkeypatch, failure):
    from pathlib import Path
    from mammoth_os import learning_workspace
    states, _ = learning_export
    path, _ = _erasable_adaptation()
    original_write = learning_workspace._write_workspace
    original_unlink = Path.unlink
    calls = 0
    def fail_write(target, record, **kwargs):
        nonlocal calls
        if target == states["tenant-a"]:
            calls += 1
            if (failure == "fence" and calls == 1) or (failure == "completion" and calls == 2):
                raise OSError("test write failure")
        original_write(target, record, **kwargs)
        if failure == "verification" and target == states["tenant-a"] and calls == 1:
            invalid = json.loads(target.read_text(encoding="utf-8"))
            invalid["learner_context"] = {"still": "cached"}
            original_write(target, invalid, **kwargs)
    def fail_unlink(target, *args, **kwargs):
        if target == path and failure == "unlink":
            raise OSError("test unlink failure")
        return original_unlink(target, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(learning_workspace, "_write_workspace", fail_write)
        patch.setattr(Path, "unlink", fail_unlink)
        result = _delete_adaptation(client)
    assert result.status_code == 503 and "receipt_id" not in result.json()
    if failure != "fence":
        state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
        assert state["learner_erasure"]["default"]["status"] == "pending"
        assert client.get("/api/atlas/learner", headers={"Authorization": "Bearer tenant-a"}).status_code == 503
        export = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
        assert export.status_code == 200 and export.json()["learner_adaptation"]["pending_deletion"] is True
        review = client.get("/api/atlas/learner/privacy-review", headers={"Authorization": "Bearer tenant-a"})
        assert review.status_code == 200 and review.json()["pending_deletion"] is True
    else:
        assert path.exists()
    assert _delete_adaptation(client).status_code == 200
    assert not path.exists()


def test_adaptation_review_requires_auth_and_is_read_only_private(client, learning_export, monkeypatch):
    states, _ = learning_export
    assert client.get("/api/atlas/learner/privacy-review").status_code == 401
    path, _ = _saved_adaptation("tenant-a")
    other, _ = _saved_adaptation("tenant-b")
    second, _ = _saved_adaptation("tenant-a", "second")
    before = {p: p.read_bytes() for p in (path, other, second, *states.values())}
    def forbidden(*args, **kwargs):
        pytest.fail("Scope review must not hydrate, generate, save or cancel")
    monkeypatch.setattr(api_server, "_hydrate_learner_state", forbidden)
    monkeypatch.setattr(api_server, "_learning_control_action", forbidden)
    response = client.get("/api/atlas/learner/privacy-review?user_id=tenant-b&account_id=second",
                          headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["contract"] == "mammoth.learner-privacy-review.v1"
    assert result["account_id"] == "default"
    assert result["model_status"] == "saved"
    assert result["saved_record_counts"] == {
        "mastery_concepts": 1, "confidence_concepts": 1, "error_patterns": 0,
        "retained_outcomes": 24, "memory_nodes": 1, "memory_edges": 0,
    }
    assert result["review_only"] is True
    assert result["deletion_available"] is False
    assert result["model_calls"] == 0
    assert "receipt_id" not in result and "preview_token" not in result
    assert "unverified_legacy_models" in result["retained_outside_scope"]
    assert "tenant-b" not in response.text
    assert "tenant-a-default goal" not in response.text
    assert "never-export-this-extension" not in response.text
    assert {p: p.read_bytes() for p in before} == before


def test_absent_adaptation_review_creates_nothing(client, learning_export):
    from pathlib import Path
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        root = Path(api_server._learner_storage_path("workspace:default"))
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    response = client.get("/api/atlas/learner/privacy-review", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 200
    assert response.json()["model_status"] == "not_saved"
    assert response.json()["saved_record_counts"] is None
    assert response.json()["saved_fields"] == []
    assert not root.exists()


def test_adaptation_review_follows_server_account_and_authenticated_owner(client, learning_export):
    states, _ = learning_export
    _saved_adaptation("tenant-a")
    other, _ = _saved_adaptation("tenant-b", "second")
    record = json.loads(other.read_text(encoding="utf-8"))
    record["recent_outcomes"] = []
    other.write_text(json.dumps(record), encoding="utf-8")
    state = json.loads(states["tenant-b"].read_text(encoding="utf-8"))
    state["active_account_id"] = "second"
    state["accounts"]["second"] = {"profile": {}}
    states["tenant-b"].write_text(json.dumps(state), encoding="utf-8")
    response = client.get("/api/atlas/learner/privacy-review?user_id=tenant-a&account_id=default",
                          headers={"Authorization": "Bearer tenant-b"})
    assert response.status_code == 200
    result = response.json()
    assert result["account_id"] == "second"
    assert result["saved_record_counts"]["retained_outcomes"] == 0
    token = api_server._REQUEST_USER_ID.set("tenant-b")
    try:
        assert result["storage_scope"] == api_server._learner_storage_scope("workspace:second")
    finally:
        api_server._REQUEST_USER_ID.reset(token)


def test_adaptation_review_never_imports_legacy_or_masks_unreadable_storage(client, learning_export, monkeypatch, tmp_path):
    from mammoth_os import learner_model
    legacy = tmp_path / "ambiguous-legacy.json"
    legacy.write_text('{"user_id":"workspace:default","mastery":{"private-legacy":1}}', encoding="utf-8")
    before = legacy.read_bytes()
    original = learner_model._model_path
    def scoped_only(storage_path=None):
        assert storage_path is not None, "Review must never open the shared legacy model"
        return original(storage_path)
    monkeypatch.setattr(learner_model, "_model_path", scoped_only)
    response = client.get("/api/atlas/learner/privacy-review", headers={"Authorization": "Bearer tenant-a"})
    assert response.json()["model_status"] == "not_saved"
    assert "private-legacy" not in response.text
    assert legacy.read_bytes() == before
    path, _ = _saved_adaptation("tenant-a")
    path.unlink()
    path.mkdir()
    response = client.get("/api/atlas/learner/privacy-review", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 503
    assert "not_saved" not in response.text
    assert path.is_dir()
    assert legacy.read_bytes() == before


@pytest.mark.parametrize("record", ["bad-json", '{"user_id":"workspace:second"}',
                                     '{"user_id":"workspace:default","memory_graph":{"nodes":{}}}'])
def test_adaptation_review_storage_errors_are_not_empty_success(client, learning_export, record):
    path, _ = _saved_adaptation("tenant-a")
    path.write_text(record, encoding="utf-8")
    before = path.read_bytes()
    response = client.get("/api/atlas/learner/privacy-review", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 503
    assert path.read_bytes() == before
    assert "model_status" not in response.json()


def test_learning_export_contains_only_saved_active_private_adaptation(client, learning_export, monkeypatch):
    a_path, a_model = _saved_adaptation("tenant-a")
    b_path, _ = _saved_adaptation("tenant-b")
    second_path, _ = _saved_adaptation("tenant-a", "second")
    before = {path: path.read_bytes() for path in (a_path, b_path, second_path)}
    def no_model(*args, **kwargs):
        pytest.fail("Export must not hydrate, generate or save a model")
    monkeypatch.setattr(api_server, "_hydrate_learner_state", no_model)
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"},
                           json={"user_id": "tenant-b", "account_id": "second"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    adaptation = result["learner_adaptation"]
    assert adaptation["contract"] == "mammoth.learner-export.v1"
    assert adaptation["status"] == "saved"
    assert adaptation["model"] == {key: value for key, value in a_model.items() if key != "private_provider_config"}
    assert len(adaptation["model"]["recent_outcomes"]) == 24
    assert adaptation["storage_scope"]["legacy_imported"] is False
    assert "tenant-b" not in response.text
    assert "tenant-a-second" not in response.text
    assert "never-export-this-extension" not in response.text
    assert result["cost"]["model_calls"] == 0
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("record", ["bad-json", "[]", '{"user_id":"workspace:second"}',
                                     '{"user_id":"workspace:default","mastery":{"x":NaN}}'])
def test_learning_export_rejects_bad_private_model_without_partial_success(client, learning_export, record):
    path, _ = _saved_adaptation("tenant-a")
    path.write_text(record, encoding="utf-8")
    before = path.read_bytes()
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 503
    assert "learner_adaptation" not in response.json()
    assert path.read_bytes() == before


def test_adaptation_alone_cannot_bypass_export_size_limit(client, learning_export):
    path, model = _saved_adaptation("tenant-a")
    model["onboarding"]["goals"] = ["x" * (8 * 1024 * 1024)]
    path.write_text(json.dumps(model), encoding="utf-8")
    before = path.read_bytes()
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 413
    assert "no shortened export" in response.json()["detail"]
    assert path.read_bytes() == before


def test_missing_adaptation_export_does_not_create_or_import_model(client, learning_export, monkeypatch, tmp_path):
    from pathlib import Path
    from mammoth_os import learner_model
    legacy = tmp_path / "ambiguous-legacy.json"
    legacy.write_text('{"user_id":"workspace:default","attempts":999}', encoding="utf-8")
    before = legacy.read_bytes()
    original = learner_model._model_path
    def scoped_only(storage_path=None):
        assert storage_path is not None, "Export must never open the shared legacy model"
        return original(storage_path)
    monkeypatch.setattr(learner_model, "_model_path", scoped_only)
    token = api_server._REQUEST_USER_ID.set("tenant-a")
    try:
        root = Path(api_server._learner_storage_path("workspace:default"))
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    assert not root.exists()
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 200
    assert response.json()["learner_adaptation"]["model"] is None
    assert response.json()["learner_adaptation"]["status"] == "not_saved"
    assert not root.exists()
    assert legacy.read_bytes() == before


def test_export_follows_server_active_learning_account(client, learning_export):
    states, _ = learning_export
    _saved_adaptation("tenant-a")
    _, model = _saved_adaptation("tenant-a", "second")
    state = json.loads(states["tenant-a"].read_text(encoding="utf-8"))
    state["active_account_id"] = "second"
    state["accounts"]["second"] = {"profile": {"display_name": "Second learner"}}
    state["account_sessions"] = {"second": {"chat_history": []}}
    states["tenant-a"].write_text(json.dumps(state), encoding="utf-8")
    response = client.post("/api/atlas/export", headers={"Authorization": "Bearer tenant-a"},
                           json={"account_id": "default"})
    assert response.status_code == 200
    assert response.json()["account_id"] == "second"
    assert response.json()["learner_adaptation"]["model"]["mastery"] == model["mastery"]
    assert "tenant-a-default" not in response.text


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
    _, model = _saved_adaptation("tenant-a")
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
    assert learning["learner_adaptation"]["model"]["mastery"] == model["mastery"]


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
