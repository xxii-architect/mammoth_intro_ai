from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import re
import threading

import pytest
from fastapi.testclient import TestClient

import api_server
from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions
from mammoth_os.postgres_learning_controls import PostgresLearningControls
from test_postgres_run_store import postgres as postgres_fixture, stores as run_stores_fixture

postgres = postgres_fixture
stores = run_stores_fixture


def _workspace_worker(action, queue):
    api_server._AUTH_REQUIRED = True
    api_server._resolve_supabase_user = lambda token: (
        {"id": token, "email": "", "is_admin": False} if token in {"alice", "bob"} else None
    )
    api_server._completion_ledger = lambda: None
    api_server._load_workspace_collections = api_server._load_shared_workspace_collections
    api_server._save_workspace_collection = api_server._save_shared_workspace_collection
    client = TestClient(api_server.app)
    if action == "write":
        response = client.post("/api/workspace/artifacts", headers={"Authorization": "Bearer alice"},
                               json={"id": "cross-worker", "body": "Durable private artifact"})
    else:
        response = client.get("/api/workspace/artifacts", headers={"Authorization": f"Bearer {action}"})
    queue.put((response.status_code, response.json()))


def _run_worker(action):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_workspace_worker, args=(action, queue))
    process.start()
    try:
        result = queue.get(timeout=60)
        process.join(timeout=15)
        assert process.exitcode == 0
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=15)
        queue.close()
        queue.join_thread()


def _draft_worker(action, body, owner, queue):
    import os

    api_server._AUTH_REQUIRED = True
    api_server._resolve_supabase_user = lambda token: (
        {"id": token, "email": "", "is_admin": False} if token in {"alice", "bob"} else None
    )
    api_server._save_learning_workspace = api_server._save_shared_learning_workspace

    def reject_local(*args, **kwargs):
        raise AssertionError("Shared recovery rehearsal must not use local learner state.")

    api_server._load_atlas_state = reject_local
    if action == "read":
        store = PostgresLearnerTransactions(
            os.environ["MAMMOTH_POSTGRES_DSN"], os.environ["MAMMOTH_STATE_NAMESPACE"], owner,
        )
        snapshot, revision = store.read_workspace(account="default")
        queue.put((revision, snapshot))
    else:
        response = TestClient(api_server.app).post(
            "/api/atlas/workspace", headers={"Authorization": f"Bearer {owner}"}, json=body,
        )
        queue.put((response.status_code, response.json()))


def _run_draft_worker(action, *, body=None, owner="alice"):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_draft_worker, args=(action, body, owner, queue))
    process.start()
    try:
        result = queue.get(timeout=60)
        process.join(timeout=15)
        assert process.exitcode == 0
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=15)
        queue.close()
        queue.join_thread()


def _account_worker(method, body, owner, queue):
    api_server._AUTH_REQUIRED = True
    api_server._resolve_supabase_user = lambda token: (
        {"id": token, "email": "", "is_admin": False} if token in {"alice", "bob"} else None
    )
    api_server._account_workspace_adapter = api_server._SharedAccountWorkspaceAdapter
    api_server._atlas_status_adapter = api_server._read_shared_atlas_status
    api_server._append_audit_event = lambda **event: None
    api_server._load_atlas_state = lambda: (_ for _ in ()).throw(
        AssertionError("Shared account rehearsal must not use local learner state.")
    )
    client = TestClient(api_server.app)
    if method == "get":
        response = client.get("/api/account/workspace", headers={"Authorization": f"Bearer {owner}"})
    else:
        response = client.post("/api/account/workspace", headers={"Authorization": f"Bearer {owner}"}, json=body)
    queue.put((response.status_code, response.json()))


def _run_account_worker(method, *, body=None, owner="alice"):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_account_worker, args=(method, body, owner, queue))
    process.start()
    try:
        result = queue.get(timeout=60)
        process.join(timeout=15)
        assert process.exitcode == 0
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=15)
        queue.close()
        queue.join_thread()


@pytest.fixture
def shared_workspace(monkeypatch, stores):
    base, _ = stores
    state = {
        "active_account_id": "default",
        "accounts": {
            "default": {"profile": {"display_name": "Default"}, "tier": "explorer", "developer_access": False},
            "other": {"profile": {"display_name": "Other"}, "tier": "explorer", "developer_access": False},
        },
        "account_sessions": {"default": {}, "other": {}},
    }
    for owner in ("alice", "bob"):
        PostgresLearnerBundle(base.dsn, base.namespace, owner).write(
            {"state": deepcopy(state), "drafts": {}, "models": {}}, revision=0,
        )
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", base.dsn)
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", base.namespace)
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: (
        {"id": token, "email": "", "is_admin": False} if token in {"alice", "bob"} else None
    ))
    monkeypatch.setattr(api_server, "_completion_ledger", lambda: None)
    monkeypatch.setattr(api_server, "_load_workspace_collections", api_server._load_shared_workspace_collections)
    monkeypatch.setattr(api_server, "_save_workspace_collection", api_server._save_shared_workspace_collection)
    monkeypatch.setattr(api_server, "_save_learning_workspace", api_server._save_shared_learning_workspace)
    monkeypatch.setattr(api_server, "_atlas_status_adapter", api_server._read_shared_atlas_status)

    def reject_local(*args, **kwargs):
        raise AssertionError("Shared workspace rehearsal must not use local learner state.")
    monkeypatch.setattr(api_server, "_load_atlas_state", reject_local)
    monkeypatch.setattr(api_server, "_save_atlas_state", reject_local)
    return base


def test_shared_workspace_routes_roundtrip_without_cross_owner_or_account_reads(shared_workspace):
    client_a, client_b = TestClient(api_server.app), TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    result = client_a.post("/api/workspace/artifacts", headers=alice, json={"body": "Alice's private artifact"})
    assert result.status_code == 200
    artifact = result.json()["artifact"]
    assert client_b.get("/api/workspace/artifacts", headers=bob).json()["artifacts"] == []
    assert client_b.get("/api/workspace/artifacts", headers=alice).json()["artifacts"][0]["id"] == artifact["id"]
    result = client_b.post("/api/workspace/run-history", headers=alice, json={"prompt": "Alice's private run"})
    assert result.status_code == 200


    assert client_a.get("/api/workspace/run-history", headers=bob).json()["entries"] == []
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    _, revision = tx.read_active_account()
    revision = tx.switch_account(revision=revision, account="default", target="other")
    assert client_b.get("/api/workspace/artifacts", headers=alice).json()["artifacts"] == []
    assert client_b.get("/api/workspace/run-history", headers=alice).json()["entries"] == []
    tx.switch_account(revision=revision, account="other", target="default")
    assert client_a.get("/api/workspace/artifacts", headers=alice).json()["artifacts"][0]["id"] == artifact["id"]
    assert len(client_a.get("/api/workspace/run-history", headers=alice).json()["entries"]) == 1
    assert client_a.get("/api/workspace/artifacts").status_code == 401
    assert client_b.delete(f"/api/workspace/artifacts/{artifact['id']}", headers=bob).json()["removed"] is False
    assert client_a.get("/api/workspace/artifacts", headers=alice).json()["artifacts"][0]["id"] == artifact["id"]
    assert client_b.delete(f"/api/workspace/artifacts/{artifact['id']}", headers=alice).json()["removed"] is True
    assert client_a.get("/api/workspace/artifacts", headers=alice).json()["artifacts"] == []
    assert client_b.delete("/api/workspace/run-history", headers=alice).json()["cleared"] == 1
    assert client_a.get("/api/workspace/run-history", headers=alice).json()["entries"] == []


def test_shared_curriculum_library_is_owner_scoped_and_persisted(shared_workspace):
    client = TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    course = {
        "curriculum_id": "shared-course",
        "subject": "Python",
        "modules": [{
            "title": "Foundations",
            "lessons": [{
                "lesson_id": "lesson-1",
                "title": "Variables",
                "content": "A variable names a value.",
                "summary": "Name and use values.",
                "objectives": ["Assign values"],
                "examples": ["count = 1"],
                "teaching_points": ["Names refer to values."],
            }],
        }],
    }
    saved = client.post("/api/atlas/curricula", headers=alice, json={"curriculum": course})
    assert saved.status_code == 200, saved.text
    assert client.get("/api/atlas/curricula", headers=bob).json()["curricula"] == []
    listed = client.get("/api/atlas/curricula", headers=alice)
    assert listed.status_code == 200
    assert listed.json()["curricula"][0]["curriculum"]["curriculum_id"] == "shared-course"


def test_shared_saved_curriculum_activation_commits_under_learning_operation(shared_workspace, monkeypatch):
    from mammoth_os.atlas_session import ATLASSession
    import mammoth_os.curriculum_library as curriculum_library
    from mammoth_os.postgres_learning_controls import PostgresLearningControls

    monkeypatch.setattr(curriculum_library, "curriculum_readiness", lambda _: {"ready": True})
    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )
    course = {
        "curriculum_id": "activation-course",
        "subject": "Python",
        "modules": [{
            "module_id": "foundations",
            "title": "Foundations",
            "lessons": [
                {
                    "lesson_id": f"lesson-{index}",
                    "title": title,
                    "content": content,
                    "summary": summary,
                    "objectives": [objective],
                    "examples": [example],
                    "teaching_points": [point],
                }
                for index, (title, content, summary, objective, example, point) in enumerate((
                    (
                        "Variables", "A Python variable is a name that refers to a value. "
                        "Assign a number to a name, print it, and trace the result. "
                        "Reassignment changes the value associated with that name.",
                        "Assign and inspect a named value.", "Assign a value to a variable.",
                        "count = 3", "Assignment binds a name to its value.",
                    ),
                    (
                        "Expressions", "A Python expression combines values and operators. "
                        "Evaluate an addition, compare the result, and explain how precedence "
                        "changes the order of operations.",
                        "Combine values with operators.", "Evaluate a numeric expression.",
                        "total = 2 + 4", "Expressions produce values that can be inspected.",
                    ),
                ), start=1)
            ],
        }],
    }

    def start_fixture(self, value, *, difficulty, learner_context):
        self.curriculum = value
        self.current_lesson = value["modules"][0]["lessons"][0]
        self._curriculum_id = value["curriculum_id"]
        self._lesson_id = self.current_lesson["lesson_id"]
        return {
            "exercise_id": "saved-course-exercise",
            "prompt": "Explain the first lesson.",
            "starter_files": {},
        }

    monkeypatch.setattr(ATLASSession, "start_curriculum", start_fixture)
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    saved = client.post("/api/atlas/curricula", headers=headers, json={"curriculum": course})
    assert saved.status_code == 200, saved.text

    response = client.post(
        "/api/atlas/curricula/start", headers=headers,
        json={"curriculum_id": "activation-course"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["lesson_id"] == "lesson-1"
    store = PostgresLearnerTransactions(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    )
    session, _ = store.read_learning_session(account="default")
    assert session["curriculum_id"] == "activation-course"
    assert session["curriculum_origin"] == "saved"
    assert session["current_exercise"]["exercise_id"] == "saved-course-exercise"
    assert session["lesson_history"][-1]["lesson_id"] == "lesson-1"
    assert "lesson-1" in session["lesson_telemetry"]
    other, _ = PostgresLearnerTransactions(
        shared_workspace.dsn, shared_workspace.namespace, "bob",
    ).read_learning_session(account="default")
    assert "curriculum_id" not in other


def test_shared_workspace_route_rejects_stale_request_after_account_switch(shared_workspace, monkeypatch):
    save = api_server._save_shared_workspace_collection

    def switch_before_save(state, context, field):
        store, account, _, revision = context
        revision = store.switch_account(revision=revision, account=account, target="other")
        store.switch_account(revision=revision, account="other", target=account)
        return save(state, context, field)

    monkeypatch.setattr(api_server, "_save_workspace_collection", switch_before_save)
    client = TestClient(api_server.app)
    response = client.post("/api/workspace/artifacts", headers={"Authorization": "Bearer alice"},
                           json={"body": "Do not save stale work"})
    assert response.status_code == 409
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    assert tx.read_workspace_collections(account="default")[0]["workspace_artifacts"] == []


def test_shared_recovery_draft_route_preserves_owner_account_and_revision(shared_workspace):
    client = TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    snapshot, _ = tx.read_workspace(account="default")
    body = {"exercise_key": snapshot["exercise_key"], "revision": snapshot["revision"],
            "values": {**snapshot["values"], "lesson_response": "Private saved work"}}
    response = client.post("/api/atlas/workspace", headers=alice, json=body)
    assert response.status_code == 200 and response.json()["status"] == "saved"
    assert response.json()["values"]["lesson_response"] == "Private saved work"
    assert client.post("/api/atlas/workspace", headers=alice, json=body).status_code == 409
    bob_tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "bob")
    assert bob_tx.read_workspace(account="default")[0]["values"]["lesson_response"] != "Private saved work"
    assert client.post("/api/atlas/workspace", json=body).status_code == 401
    _, revision = tx.read_active_account()
    revision = tx.switch_account(revision=revision, account="default", target="other")
    assert tx.read_workspace(account="other")[0]["values"]["lesson_response"] != "Private saved work"
    tx.switch_account(revision=revision, account="other", target="default")
    assert client.post("/api/atlas/workspace", headers=alice, json={
        **body, "revision": response.json()["revision"],
    }).status_code == 409
    assert tx.read_workspace(account="default")[0]["values"]["lesson_response"] == "Private saved work"
    assert client.get("/api/workspace/artifacts", headers=bob).json()["artifacts"] == []


def test_shared_atlas_status_reads_consistent_owner_scoped_state_and_recovery(shared_workspace, monkeypatch):
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    session = bundle["state"]["account_sessions"]["default"]
    session.update({
        "status": "active", "topic": "Shared tutor topic", "lesson_id": "lesson-1",
        "current_lesson": {"lesson_id": "lesson-1", "title": "Shared lesson"},
        "current_exercise": {"starter_response": "starter"},
    })
    bundle_store.write(bundle, revision=revision)

    def reject_local(*args, **kwargs):
        raise AssertionError("Shared tutor status must not read local learner or draft files.")

    monkeypatch.setattr(api_server, "_atlas_state_file_for_request", reject_local)
    monkeypatch.setattr(api_server, "_learner_storage_action", reject_local)
    monkeypatch.setattr(api_server, "_load_eval_history", reject_local)
    monkeypatch.setattr(api_server, "_read_jsonl_records", reject_local)
    monkeypatch.setattr(api_server, "_load_activity_events", reject_local)
    client = TestClient(api_server.app)
    alice = client.get("/api/atlas/status", headers={"Authorization": "Bearer alice"})
    bob = client.get("/api/atlas/status", headers={"Authorization": "Bearer bob"})
    assert alice.status_code == 200 and bob.status_code == 200
    assert alice.json()["topic"] == "Shared tutor topic"
    assert alice.json()["workspace_recovery"]["values"]["lesson_response"] == "starter"
    assert alice.json()["learner_model"]["user_id"] == "workspace:default"
    assert bob.json().get("topic") != "Shared tutor topic"
    assert bob.json()["workspace_recovery"]["values"]["lesson_response"] != "starter"
    draft = alice.json()["workspace_recovery"]
    saved = client.post("/api/atlas/workspace", headers={"Authorization": "Bearer alice"}, json={
        "exercise_key": draft["exercise_key"], "revision": draft["revision"],
        "values": {**draft["values"], "lesson_response": "Saved in shared tutor state"},
    })
    assert saved.status_code == 200
    refreshed = client.get("/api/atlas/status", headers={"Authorization": "Bearer alice"})
    assert refreshed.json()["workspace_recovery"]["values"]["lesson_response"] == "Saved in shared tutor state"
    assert client.get("/api/atlas/status").status_code == 401


def test_shared_atlas_status_reports_pending_erasure_and_storage_failure(shared_workspace, monkeypatch):
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    bundle["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    bundle_store.write(bundle, revision=revision)
    client = TestClient(api_server.app)
    response = client.get("/api/atlas/status", headers={"Authorization": "Bearer alice"})
    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", "host=127.0.0.1 port=1 dbname=missing connect_timeout=1")
    response = client.get("/api/atlas/status", headers={"Authorization": "Bearer alice"})
    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"


def test_shared_tutor_read_routes_use_owner_scoped_status_snapshot(shared_workspace, monkeypatch):
    async def library(state):
        return {"topic": state.get("topic"), "owner": state["user_id"]}

    monkeypatch.setattr(api_server, "_build_atlas_library_snapshot", library)
    monkeypatch.setattr(api_server, "_load_eval_history", lambda: [])
    client = TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    for headers in (alice, bob):
        assert client.get("/api/atlas/learner", headers=headers).status_code == 200
        assert client.get("/api/atlas/lecture", headers=headers).status_code == 200
        assert client.get("/api/atlas/modules", headers=headers).status_code == 200
        assert client.get("/api/atlas/library", headers=headers).status_code == 200
    learner = client.get("/api/atlas/learner", headers=alice).json()
    assert learner["learner_model"]["user_id"] == "workspace:default"
    assert client.get("/api/atlas/library", headers=alice).json()["owner"] == "workspace:default"
    assert client.get("/api/atlas/modules").status_code == 401
    assert client.get("/api/atlas/library").status_code == 401


def test_shared_adaptation_preview_and_erasure_are_revision_bound(shared_workspace):
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    bundle["state"]["learner_context"] = {"private": "cache"}
    bundle["state"]["account_sessions"]["default"]["learner_profile"] = {"attempts": 4}
    bundle_store.write(bundle, revision=revision)
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    preview = client.get("/api/atlas/learner/deletion-preview", headers=headers)
    assert preview.status_code == 200 and preview.json()["deletion_available"] is True
    stale = preview.json()["preview_token"]
    bundle, revision = bundle_store.read()
    bundle["state"]["topic"] = "Changed after preview"
    bundle_store.write(bundle, revision=revision)
    rejected = client.request("DELETE", "/api/atlas/learner/adaptation", headers=headers, json={
        "confirmation": "DELETE PRIVATE ADAPTATION", "preview_token": stale,
    })
    assert rejected.status_code == 409
    preview = client.get("/api/atlas/learner/deletion-preview", headers=headers).json()
    deleted = client.request("DELETE", "/api/atlas/learner/adaptation", headers=headers, json={
        "confirmation": "DELETE PRIVATE ADAPTATION", "preview_token": preview["preview_token"],
    })
    assert deleted.status_code == 200 and deleted.json()["status"] == "deleted_from_active_storage"
    saved, revision = bundle_store.read()
    assert saved["state"]["learner_erasure"]["default"]["status"] == "complete"
    assert "learner_context" not in saved["state"]
    assert "learner_profile" not in saved["state"]["account_sessions"]["default"]
    assert revision == preview["revision"] + 1


def test_shared_adaptation_privacy_review_returns_supported_fields_only(shared_workspace):
    from mammoth_os.learner_model import _ensure_model_shape

    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    bundle["models"]["default"] = _ensure_model_shape(None, "workspace:default")
    bundle["models"]["default"]["mastery"] = {"loops": 2}
    bundle_store.write(bundle, revision=revision)
    review = TestClient(api_server.app).get(
        "/api/atlas/learner/privacy-review", headers={"Authorization": "Bearer alice"},
    )
    assert review.status_code == 200
    assert review.json()["model_status"] == "saved"
    assert review.json()["saved_record_counts"]["mastery_concepts"] == 1
    assert review.json()["not_a_transactional_snapshot"] is True
    assert "private_extension" not in review.text


def test_shared_learning_preview_and_erasure_remove_session_and_recovery(shared_workspace):
    store = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    snapshot, _ = store.read_workspace(account="default")
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    saved = client.post("/api/atlas/workspace", headers=headers, json={
        "exercise_key": snapshot["exercise_key"], "revision": snapshot["revision"],
        "values": {**snapshot["values"], "lesson_response": "Remove this recovery draft"},
    })
    assert saved.status_code == 200
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    bundle["state"]["account_sessions"]["default"].update({
        "topic": "Saved learning", "current_lesson": {"title": "Saved lesson"},
    })
    bundle_store.write(bundle, revision=revision)
    preview = client.get("/api/atlas/history/preview", headers=headers)
    assert preview.status_code == 200 and preview.json()["scope"] == "active_account_saved_lesson_session_and_recovery"
    deleted = client.request("DELETE", "/api/atlas/history", headers=headers, json={
        "confirmation": "DELETE SAVED LEARNING", "preview_token": preview.json()["preview_token"],
    })
    assert deleted.status_code == 200 and deleted.json()["status"] == "deleted_from_active_storage"
    after, _ = store.read_learning_session(account="default")
    assert "topic" not in after and after["status"] == "no_session"
    recovery, _ = store.read_workspace(account="default")
    assert recovery["revision"] == 0
    assert recovery["values"]["lesson_response"] != "Remove this recovery draft"


@pytest.mark.parametrize("damage", ["invalid_values", "missing_revision", "boolean_revision", "wrong_key"])
def test_shared_recovery_draft_route_validates_without_writes(shared_workspace, damage):
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    snapshot, _ = tx.read_workspace(account="default")
    body = {"exercise_key": snapshot["exercise_key"], "revision": snapshot["revision"],
            "values": snapshot["values"]}
    if damage == "invalid_values":
        body["values"] = {}
    elif damage == "missing_revision":
        del body["revision"]
    elif damage == "boolean_revision":
        body["revision"] = False
    else:
        body["exercise_key"] = "stale"
    response = TestClient(api_server.app).post(
        "/api/atlas/workspace", headers={"Authorization": "Bearer alice"}, json=body,
    )
    assert response.status_code == (400 if damage == "invalid_values" else 409)
    assert tx._store.read()[1] == 1


def test_shared_recovery_draft_route_fails_closed_when_database_unavailable(shared_workspace, monkeypatch):
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    snapshot, _ = tx.read_workspace(account="default")
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", "host=127.0.0.1 port=1 dbname=missing connect_timeout=1")
    response = TestClient(api_server.app).post(
        "/api/atlas/workspace", headers={"Authorization": "Bearer alice"},
        json={"exercise_key": snapshot["exercise_key"], "revision": snapshot["revision"], "values": snapshot["values"]},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"
    assert tx._store.read()[1] == 1


@pytest.mark.parametrize("change", ["switch", "erasure", "reset"])
def test_shared_recovery_draft_rejects_change_between_admission_and_save(shared_workspace, monkeypatch, change):
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    snapshot, _ = tx.read_workspace(account="default")
    original = PostgresLearnerTransactions.save_draft

    def change_then_save(store, **kwargs):
        revision = kwargs["revision"]
        if change == "switch":
            revision = store.switch_account(revision=revision, account="default", target="other")
            store.switch_account(revision=revision, account="other", target="default")
        elif change == "erasure":
            preview = store.preview_learning_erasure(account="default")
            store.confirm_learning_erasure(
                revision=revision, account="default", confirmation="DELETE SAVED LEARNING",
                preview_token=preview["preview_token"],
            )
        else:
            guard, _ = store.read_approval_guard(account="default")
            store.reset_learner(
                revision=revision, account="default", approval_guard=guard,
                session_reset=True, saved_at="2026-01-01",
            )
        return original(store, **kwargs)

    monkeypatch.setattr(PostgresLearnerTransactions, "save_draft", change_then_save)
    response = TestClient(api_server.app).post(
        "/api/atlas/workspace", headers={"Authorization": "Bearer alice"},
        json={"exercise_key": snapshot["exercise_key"], "revision": snapshot["revision"],
              "values": {**snapshot["values"], "lesson_response": "Old draft must not return"}},
    )
    assert response.status_code == 409
    result, _ = tx.read_workspace(account="default")
    assert result["values"]["lesson_response"] != "Old draft must not return"


def test_shared_recovery_draft_competing_tabs_do_not_overwrite(shared_workspace, monkeypatch):
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    snapshot, _ = tx.read_workspace(account="default")
    barrier = threading.Barrier(2)
    original = PostgresLearnerTransactions.save_draft

    def concurrent_save(store, **kwargs):
        barrier.wait(timeout=20)
        return original(store, **kwargs)

    monkeypatch.setattr(PostgresLearnerTransactions, "save_draft", concurrent_save)
    def submit(text):
        return TestClient(api_server.app).post(
            "/api/atlas/workspace", headers={"Authorization": "Bearer alice"},
            json={"exercise_key": snapshot["exercise_key"], "revision": snapshot["revision"],
                  "values": {**snapshot["values"], "lesson_response": text}},
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, ("first draft", "second draft")))
    assert sorted(response.status_code for response in responses) == [200, 409]
    saved, revision = tx.read_workspace(account="default")
    assert revision == 2 and saved["values"]["lesson_response"] in {"first draft", "second draft"}


def test_shared_recovery_draft_across_independent_workers(shared_workspace):
    initial_revision, initial = _run_draft_worker("read")
    body = {"exercise_key": initial["exercise_key"], "revision": initial["revision"],
            "values": {**initial["values"], "lesson_response": "Private cross-worker draft"}}
    status, saved = _run_draft_worker("write", body=body)
    assert status == 200 and saved["status"] == "saved"

    revision, observed = _run_draft_worker("read")
    assert revision == initial_revision + 1
    assert observed["values"]["lesson_response"] == "Private cross-worker draft"
    assert _run_draft_worker("write", body=body)[0] == 409
    assert _run_draft_worker("read", owner="bob")[1]["values"]["lesson_response"] != "Private cross-worker draft"

    updated = {"exercise_key": observed["exercise_key"], "revision": observed["revision"],
               "values": {**observed["values"], "lesson_response": "Updated by another worker"}}
    assert _run_draft_worker("write", body=updated)[0] == 200
    assert _run_draft_worker("read")[1]["values"]["lesson_response"] == "Updated by another worker"


@pytest.fixture
def shared_accounts(shared_workspace, monkeypatch):
    monkeypatch.setattr(api_server, "_account_workspace_adapter", api_server._SharedAccountWorkspaceAdapter)
    audit = []
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **event: audit.append(event))
    return shared_workspace, audit


def test_shared_account_routes_preserve_owner_scope_and_lifecycle(shared_accounts):
    base, audit = shared_accounts
    client = TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    response = client.post("/api/account/workspace", headers=alice, json={
        "action": "create", "display_name": "Alice New", "email": "alice@example.test",
        "activate": False,
    })
    assert response.status_code == 200
    assert response.json()["active_account_id"] == "default"
    assert {item["account_id"] for item in response.json()["accounts"]} == {"default", "other", "alice-new"}
    assert {item["account_id"] for item in client.get("/api/account/workspace", headers=bob).json()["accounts"]} == {"default", "other"}
    response = client.post("/api/account/workspace", headers=alice, json={"action": "switch", "account_id": "alice-new"})
    assert response.status_code == 200 and response.json()["active_account_id"] == "alice-new"
    assert client.get("/api/account/workspace", headers=alice).json()["active_account_id"] == "alice-new"
    response = client.post("/api/account/workspace", headers=alice, json={"action": "delete", "account_id": "alice-new"})
    assert response.status_code == 200 and response.json()["active_account_id"] == "default"
    assert [event["kind"] for event in audit] == ["account_created", "account_switch", "account_deleted"]
    assert client.get("/api/account/workspace").status_code == 401
    tx = PostgresLearnerTransactions(base.dsn, base.namespace, "alice")
    assert tx.read_active_account()[0] == "default"


def test_shared_account_route_rejects_stale_create_and_does_not_audit(shared_accounts, monkeypatch):
    base, audit = shared_accounts
    original = PostgresLearnerTransactions.create_account

    def switch_then_create(store, **kwargs):
        store.switch_account(revision=kwargs["revision"], account="default", target="other")
        return original(store, **kwargs)

    monkeypatch.setattr(PostgresLearnerTransactions, "create_account", switch_then_create)
    response = TestClient(api_server.app).post(
        "/api/account/workspace", headers={"Authorization": "Bearer alice"},
        json={"action": "create", "display_name": "Stale account"},
    )
    assert response.status_code == 409
    view, _ = PostgresLearnerTransactions(base.dsn, base.namespace, "alice").read_account_view()
    assert view["active_account_id"] == "other" and "stale-account" not in view["accounts"]
    assert audit == []


def test_shared_account_response_describes_committed_transition_not_later_state(shared_accounts, monkeypatch):
    base, _ = shared_accounts
    original = PostgresLearnerTransactions.create_account

    def create_then_switch(store, **kwargs):
        revision, result = original(store, **kwargs)
        store.switch_account(revision=revision, account="new-account", target="default")
        return revision, result

    monkeypatch.setattr(PostgresLearnerTransactions, "create_account", create_then_switch)
    response = TestClient(api_server.app).post(
        "/api/account/workspace", headers={"Authorization": "Bearer alice"},
        json={"action": "create", "display_name": "New Account"},
    )
    assert response.status_code == 200 and response.json()["active_account_id"] == "new-account"
    assert PostgresLearnerTransactions(base.dsn, base.namespace, "alice").read_active_account()[0] == "default"


@pytest.mark.parametrize("damage", ["orphan_session", "invalid_profile", "invalid_metadata"])
def test_shared_account_route_does_not_overwrite_unreviewed_or_invalid_data(shared_accounts, damage):
    base, audit = shared_accounts
    raw = PostgresLearnerBundle(base.dsn, base.namespace, "alice")
    bundle, revision = raw.read()
    if damage == "orphan_session":
        bundle["state"]["account_sessions"]["new-account"] = {"private_extension": "preserve"}
    elif damage == "invalid_profile":
        bundle["state"]["accounts"]["other"]["tier"] = []
    else:
        bundle["state"]["accounts"]["other"]["created_at"] = {"private_extension": "do not return"}
    raw.write(bundle, revision=revision)
    response = TestClient(api_server.app).post(
        "/api/account/workspace", headers={"Authorization": "Bearer alice"},
        json={"action": "create", "display_name": "New Account"},
    )
    assert response.status_code == (409 if damage == "orphan_session" else 503)
    observed, current_revision = raw.read()
    assert current_revision == revision + 1 and observed == bundle
    assert audit == []


def test_shared_account_concurrent_creations_reject_stale_transition(shared_accounts, monkeypatch):
    base, audit = shared_accounts
    barrier = threading.Barrier(2)
    original = PostgresLearnerTransactions.create_account

    def competing_create(store, **kwargs):
        barrier.wait(timeout=20)
        return original(store, **kwargs)

    monkeypatch.setattr(PostgresLearnerTransactions, "create_account", competing_create)

    def create(name):
        return TestClient(api_server.app).post(
            "/api/account/workspace", headers={"Authorization": "Bearer alice"},
            json={"action": "create", "display_name": name, "activate": False},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, ("First Account", "Second Account")))
    assert sorted(response.status_code for response in responses) == [200, 409]
    view, _ = PostgresLearnerTransactions(base.dsn, base.namespace, "alice").read_account_view()
    assert len(set(view["accounts"]) & {"first-account", "second-account"}) == 1
    assert [event["kind"] for event in audit] == ["account_created"]


def test_shared_account_view_omits_session_and_unknown_account_extensions(shared_accounts):
    base, _ = shared_accounts
    raw = PostgresLearnerBundle(base.dsn, base.namespace, "alice")
    bundle, revision = raw.read()
    bundle["state"]["accounts"]["default"]["private_extension"] = "account-secret"
    bundle["state"]["account_sessions"]["default"]["private_extension"] = "session-secret"
    raw.write(bundle, revision=revision)
    response = TestClient(api_server.app).get(
        "/api/account/workspace", headers={"Authorization": "Bearer alice"},
    )
    assert response.status_code == 200
    assert "secret" not in response.text and "private_extension" not in response.text


def test_shared_account_routes_are_visible_across_independent_workers(shared_accounts):
    status, created = _run_account_worker("post", body={"action": "create", "display_name": "Worker Account"})
    assert status == 200 and created["active_account_id"] == "worker-account"
    status, observed = _run_account_worker("get")
    assert status == 200 and observed["active_account_id"] == "worker-account"
    assert "worker-account" not in {item["account_id"] for item in _run_account_worker("get", owner="bob")[1]["accounts"]}
    status, switched = _run_account_worker("post", body={"action": "switch", "account_id": "default"})
    assert status == 200 and switched["active_account_id"] == "default"
    assert _run_account_worker("get")[1]["active_account_id"] == "default"


def test_shared_account_routes_fail_closed_without_local_fallback(shared_accounts, monkeypatch):
    _, audit = shared_accounts
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", "host=127.0.0.1 port=1 dbname=missing connect_timeout=1")
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    assert client.get("/api/account/workspace", headers=headers).status_code == 503
    assert client.post("/api/account/workspace", headers=headers, json={"action": "create"}).status_code == 503
    assert client.get("/api/account/profile", headers=headers).status_code == 503
    assert audit == []


@pytest.fixture
def shared_admission(shared_workspace, monkeypatch):
    base = shared_workspace
    monkeypatch.setattr(api_server, "_begin_controlled_learning", api_server._begin_shared_controlled_learning)
    monkeypatch.setattr(api_server, "_learning_controls", lambda: PostgresLearningControls(
        base.dsn, base.namespace, api_server._current_request_user_id(),
    ))

    def reject_local(*args, **kwargs):
        raise AssertionError("Shared admission rehearsal must not use local learner state.")
    monkeypatch.setattr(api_server, "_load_learning_export_state", reject_local)
    return base


def test_shared_admission_uses_fenced_operation_and_finishes(shared_admission, monkeypatch):
    from mammoth_os.learning_controls import operation_context

    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="": "alice")
    controls = PostgresLearningControls(shared_admission.dsn, shared_admission.namespace, "alice")
    operation_id = api_server._begin_shared_controlled_learning(controls, "/fixture")
    tx = PostgresLearnerTransactions(shared_admission.dsn, shared_admission.namespace, "alice")
    with operation_context(controls, operation_id):
        account, revision = tx.read_active_account()
        tx.update_learning_session(
            revision=revision, account=account, operation_id=operation_id,
            changes={"topic": "Fenced admission"},
        )
    controls.finish(operation_id, "finished")
    snapshot = controls.snapshot()
    assert snapshot["admitted_requests"] == 1
    assert snapshot["operations"][0]["status"] == "finished"
    assert tx.read_learning_session(account="default")[0]["topic"] == "Fenced admission"


def test_shared_admission_rejects_stale_account_before_provider_work(shared_admission, monkeypatch):
    from mammoth_os.shared_state import StateConflict

    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="": "alice")
    original = PostgresLearnerTransactions.begin_operation

    def switch_before_admission(store, **kwargs):
        store.switch_account(revision=kwargs["revision"], account="default", target="other")
        return original(store, **kwargs)

    monkeypatch.setattr(PostgresLearnerTransactions, "begin_operation", switch_before_admission)
    controls = PostgresLearningControls(shared_admission.dsn, shared_admission.namespace, "alice")
    with pytest.raises(StateConflict):
        api_server._begin_shared_controlled_learning(controls, "/fixture")
    assert PostgresLearningControls(shared_admission.dsn, shared_admission.namespace, "alice").snapshot()["admitted_requests"] == 0


def test_shared_admission_preserves_limit_and_cancellation(shared_admission, monkeypatch):
    from mammoth_os.learning_controls import LearningCancelled, LearningLimitReached, check_cancelled, operation_context

    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="": "alice")
    controls = PostgresLearningControls(shared_admission.dsn, shared_admission.namespace, "alice")
    controls.set_limit(0)
    with pytest.raises(LearningLimitReached):
        api_server._begin_shared_controlled_learning(controls, "/fixture")
    assert controls.snapshot()["admitted_requests"] == 0
    controls.set_limit(1)
    operation_id = api_server._begin_shared_controlled_learning(controls, "/fixture")
    tx = PostgresLearnerTransactions(shared_admission.dsn, shared_admission.namespace, "alice")
    with pytest.raises(LearningCancelled):
        with operation_context(controls, operation_id):
            _, revision = tx.read_active_account()
            tx.switch_account(revision=revision, account="default", target="other")
            check_cancelled()
    controls.finish(operation_id, "cancelled_at_boundary")
    snapshot = controls.snapshot()
    assert snapshot["admitted_requests"] == 1
    assert snapshot["operations"][0]["status"] == "cancelled_at_boundary"


def test_shared_account_profile_and_entitlement_updates_are_atomic_and_audited(shared_accounts, monkeypatch):
    base, _ = shared_accounts
    monkeypatch.setattr(api_server, "_request_is_admin", lambda: True)
    client = TestClient(api_server.app)
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}

    profile = client.get("/api/account/profile", headers=alice)
    assert profile.status_code == 200
    assert {item["account_id"] for item in profile.json()["available_accounts"]} == {"default", "other"}
    updated = client.post("/api/account/profile", headers=alice, json={
        "display_name": "Alice Updated", "organization": "Example Org",
    })
    assert updated.status_code == 200
    assert updated.json()["profile"]["display_name"] == "Alice Updated"
    assert client.get("/api/account/profile", headers=bob).json()["profile"]["display_name"] == "Default"

    tier = client.post("/api/entitlements/tier", headers=alice, json={"tier": "pro"})
    assert tier.status_code == 200 and tier.json()["tier"] == "pro"
    entitlements = client.get("/api/entitlements", headers=alice)
    assert entitlements.status_code == 200 and entitlements.json()["tier"] == "pro"
    developer = client.post("/api/account/developer-access", headers=alice, json={"enabled": True})
    assert developer.status_code == 200 and developer.json()["effective_tier"] == "developer"

    bundle, _ = PostgresLearnerBundle(base.dsn, base.namespace, "alice").read()
    audit = bundle["state"]["account_metadata_audit"]
    assert [item["action"] for item in audit] == ["profile_update", "tier_change", "developer_access"]
    bob_bundle, _ = PostgresLearnerBundle(base.dsn, base.namespace, "bob").read()
    assert "account_metadata_audit" not in bob_bundle["state"]


@pytest.mark.parametrize("failure", ["wrong_owner", "local_controls", "database"])
def test_shared_admission_never_falls_back_or_executes_on_storage_failure(shared_admission, monkeypatch, failure):
    from mammoth_os.learning_controls import LearningControls
    from mammoth_os.shared_state import StateUnavailable

    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="": "alice")
    def controls():
        if failure == "local_controls":
            return LearningControls(None)
        dsn = ("host=127.0.0.1 port=1 dbname=missing connect_timeout=1"
               if failure == "database" else shared_admission.dsn)
        owner = "bob" if failure == "wrong_owner" else "alice"
        return PostgresLearningControls(dsn, shared_admission.namespace, owner)

    with pytest.raises(StateUnavailable):
        api_server._begin_shared_controlled_learning(controls(), "/fixture")
    assert PostgresLearningControls(shared_admission.dsn, shared_admission.namespace, "alice").snapshot()["admitted_requests"] == 0


def test_unintegrated_tutor_routes_fail_closed_in_shared_reader_mode(shared_workspace):
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    for path, body in (
        ("/api/atlas/export", None),
        ("/api/atlas/lesson", {"topic": "must not run"}),
        ("/agent/atlas/run", {"payload": "must not run"}),
        ("/api/account/profile", None),
        ("/api/account/workspace", None),
        ("/api/entitlements", None),
        ("/api/billing/usage/current", None),
    ):
        if path.startswith("/api/account/") or path in {"/api/entitlements", "/api/billing/usage/current"}:
            response = client.get(path, headers=headers)
        else:
            response = client.post(path, headers=headers, json=body) if body is not None else client.post(path, headers=headers)
        assert response.status_code == 503
        assert response.json()["code"] == "storage_unavailable"
    tier = client.post("/api/entitlements/tier", headers=headers, json={"tier": "pro"})
    assert tier.status_code == 503 and tier.json()["code"] == "storage_unavailable"


def test_shared_approval_routes_use_only_owner_scoped_storage(shared_workspace):
    from fastapi import HTTPException

    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    listed = client.get("/api/approvals", headers=headers)
    assert listed.status_code == 200 and listed.json() == []
    approved = client.post("/api/approvals/not-found/approve", headers=headers)
    assert approved.status_code == 200 and approved.json()["message"] == "approval not found"
    deleted = client.delete("/api/approvals/not-found", headers=headers)
    assert deleted.status_code == 200 and deleted.json()["message"] == "approval not found"
    with pytest.raises(HTTPException, match="not integrated"):
        api_server._create_approval_record(
            "task", agent_id="agent", operation="unsupported", target="target", preview={},
        )
    with pytest.raises(HTTPException, match="owner-scoped"):
        api_server._approve_record("not-found")
    with pytest.raises(HTTPException, match="owner-scoped"):
        api_server._delete_approval_record("not-found")


def test_shared_onboarding_and_reset_http_routes_use_transaction_adapter(monkeypatch):
    class Store:
        def __init__(self):
            self.onboarding = {}
            self.mastery = {"before-reset": 0.8}
            self.update_error = None
            self.reset_error = None
            self.approvals = []

        def read_active_account(self):
            return "default", 7

        def read_approval_guard(self, *, account):
            assert account == "default"
            return {"fence": "current"}, 7

        def create_learner_approval(self, **kwargs):
            assert kwargs["revision"] == 7
            assert kwargs["account"] == "default"
            record = deepcopy(kwargs["record"])
            record["status"] = "pending"
            self.approvals.append(record)
            return record

        def update_onboarding(self, **kwargs):
            if self.update_error:
                raise self.update_error
            assert kwargs["revision"] == 7
            assert kwargs["approval_guard"] == {"fence": "current"}
            self.onboarding.update(kwargs["onboarding"])

        def reset_learner(self, **kwargs):
            if self.reset_error:
                raise self.reset_error
            assert kwargs["revision"] == 7
            assert kwargs["approval_guard"] == {"fence": "current"}
            assert kwargs["session_reset"] is False
            self.mastery = {}

    store = Store()
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_atlas_status_adapter", lambda: ({}, {}))
    monkeypatch.setattr(api_server, "_shared_learner_store", lambda: store)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: pytest.fail("Local learner state was read."))

    def status():
        return ({
            "learner_model": {
                "onboarding": dict(store.onboarding), "mastery": dict(store.mastery),
            },
            "learner_context": {}, "learner_profile": {},
        }, {})

    monkeypatch.setattr(api_server, "_read_shared_atlas_status", status)
    client = TestClient(api_server.app)

    onboarded = client.post("/api/atlas/onboard", json={"experience_level": "advanced"})
    assert onboarded.status_code == 200
    assert onboarded.json()["learner_model"]["onboarding"]["experience_level"] == "advanced"

    queued = client.post("/api/atlas/onboard", json={"approval_mode": True})
    assert queued.status_code == 200
    assert queued.json()["approval"]["status"] == "pending"
    assert store.onboarding == {"experience_level": "advanced"}

    reset = client.post("/api/atlas/learner/reset", json={})
    assert reset.status_code == 200
    assert reset.json()["learner_model"]["mastery"] == {}
    queued_reset = client.post("/api/atlas/learner/reset", json={"preview_only": True})
    assert queued_reset.status_code == 200
    assert queued_reset.json()["approval"]["status"] == "pending"
    assert store.mastery == {}

    from mammoth_os.shared_state import StateConflict, StateUnavailable
    store.update_error = StateConflict("stale onboarding")
    conflict = client.post("/api/atlas/onboard", json={"experience_level": "expert"})
    assert conflict.status_code == 409
    store.reset_error = StateUnavailable("shared database unavailable")
    unavailable = client.post("/api/atlas/learner/reset", json={})
    assert unavailable.status_code == 503


def test_shared_onboarding_and_reset_are_transactional_and_approval_paths_stay_blocked(shared_workspace):
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")

    onboarded = client.post(
        "/api/atlas/onboard", headers=headers,
        json={"experience_level": "intermediate", "preferred_pacing": "steady", "goals": ["Build apps"]},
    )
    assert onboarded.status_code == 200
    learner_model, _ = tx.read_adaptation(account="default")
    assert learner_model["onboarding"]["experience_level"] == "intermediate"
    assert learner_model["onboarding"]["goals"] == ["Build apps"]

    approval = client.post("/api/atlas/onboard", headers=headers, json={
        "approval_mode": True, "experience_level": "advanced",
    })
    assert approval.status_code == 200
    approval_record = approval.json()["approval"]
    assert approval_record["status"] == "pending"
    assert tx.read_adaptation(account="default")[0]["onboarding"]["experience_level"] == "intermediate"

    from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    bundle["models"]["default"]["mastery"] = {"shared-reset-test": 0.9}
    bundle["models"]["default"]["attempts"] = 4
    bundle["state"]["lesson_telemetry"] = {"shared-reset-test": {"attempts": 2}}
    bundle["state"]["account_sessions"]["default"]["lesson_telemetry"] = {
        "shared-reset-test": {"attempts": 2},
    }
    bundle_store.write(bundle, revision=revision)

    reset = client.post("/api/atlas/learner/reset", headers=headers, json={})
    assert reset.status_code == 200
    reset_model, _ = tx.read_adaptation(account="default")
    assert reset_model["mastery"] == {}
    assert reset_model["attempts"] == 0
    assert reset_model["onboarding"]["experience_level"] == "intermediate"
    assert "lesson_telemetry" not in tx.read_learning_session(account="default")[0]

    reset_approval = client.post("/api/atlas/learner/reset", headers=headers, json={"approval_mode": True})
    assert reset_approval.status_code == 200
    assert reset_approval.json()["approval"]["status"] == "pending"
    assert tx.read_adaptation(account="default")[0]["mastery"] == {}

    session_reset = client.post("/api/atlas/reset", headers=headers, json={})
    assert session_reset.status_code == 200 and session_reset.json()["message"] == "Session reset"
    session_state, _ = tx.read_learning_session(account="default")
    assert session_state["status"] == "reset"
    assert "lesson_telemetry" not in session_state
    session_reset_preview = client.post(
        "/api/atlas/reset", headers=headers, json={"preview_only": True},
    )
    assert session_reset_preview.status_code == 200
    assert session_reset_preview.json()["approval"]["status"] == "pending"


def test_shared_learner_approval_claim_effect_and_audit_are_atomic(shared_workspace, monkeypatch):
    from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
    from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions

    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    queued = client.post(
        "/api/atlas/onboard", headers=headers,
        json={"approval_mode": True, "experience_level": "advanced", "goals": ["Build safely"]},
    )
    assert queued.status_code == 200, queued.text
    approval_id = queued.json()["approval"]["id"]
    bob_headers = {"Authorization": "Bearer bob"}
    assert client.get("/api/approvals", headers=bob_headers).json() == []
    assert client.post(
        f"/api/approvals/{approval_id}/approve", headers=bob_headers,
    ).json()["message"] == "approval not found"
    before, _ = PostgresLearnerTransactions(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    ).read_adaptation(account="default")
    assert before is None

    listed = client.get("/api/approvals", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [approval_id]
    applied = client.post(f"/api/approvals/{approval_id}/approve", headers=headers)
    assert applied.status_code == 200, applied.text
    assert applied.json()["approval"]["status"] == "approved"
    assert applied.json()["result"]["status"] == "ok"

    transactions = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    model, _ = transactions.read_adaptation(account="default")
    assert model["onboarding"]["experience_level"] == "advanced"
    assert model["onboarding"]["goals"] == ["Build safely"]
    bundle, _ = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice").read()
    assert [item["action"] for item in bundle["state"]["learner_approval_audit"]] == [
        "requested", "approved",
    ]

    bundle, revision = PostgresLearnerBundle(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    ).read()
    bundle["models"]["default"]["mastery"] = {"needs-reset": 0.9}
    PostgresLearnerBundle(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    ).write(bundle, revision=revision)
    reset_request = client.post(
        "/api/atlas/learner/reset", headers=headers, json={"approval_mode": True},
    )
    reset_id = reset_request.json()["approval"]["id"]
    reset_result = client.post(f"/api/approvals/{reset_id}/approve", headers=headers)
    assert reset_result.status_code == 200, reset_result.text
    assert reset_result.json()["approval"]["status"] == "approved"
    model, _ = transactions.read_adaptation(account="default")
    assert model["mastery"] == {}
    assert model["onboarding"]["experience_level"] == "advanced"
    bundle, _ = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice").read()
    assert [item["action"] for item in bundle["state"]["learner_approval_audit"]] == [
        "requested", "approved", "requested", "approved",
    ]

    replay = client.post(f"/api/approvals/{approval_id}/approve", headers=headers)
    assert replay.status_code == 200
    bundle, _ = PostgresLearnerBundle(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    ).read()
    assert [item["action"] for item in bundle["state"]["learner_approval_audit"]] == [
        "requested", "approved", "requested", "approved",
    ]
    queued_reset = client.post(
        "/api/atlas/learner/reset", headers=headers,
        json={"approval_mode": True},
    )
    assert queued_reset.status_code == 200
    deleted_id = queued_reset.json()["approval"]["id"]
    discarded = client.delete(f"/api/approvals/{deleted_id}", headers=headers)
    assert discarded.status_code == 200
    assert discarded.json()["approval"]["status"] == "deleted"
    bundle, _ = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice").read()
    assert [item["action"] for item in bundle["state"]["learner_approval_audit"]] == [
        "requested", "approved", "requested", "approved", "requested", "deleted",
    ]


def test_shared_learner_approval_becomes_stale_after_account_switch(shared_workspace):
    from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions

    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    queued = client.post(
        "/api/atlas/learner/reset", headers=headers,
        json={"approval_mode": True},
    )
    assert queued.status_code == 200, queued.text
    approval_id = queued.json()["approval"]["id"]
    transactions = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    _, revision = transactions.read_account_view()
    transactions.switch_account(
        revision=revision, account="default", target="other",
    )
    response = client.post(f"/api/approvals/{approval_id}/approve", headers=headers)
    assert response.status_code == 409
    assert "account changed" in response.json()["detail"].lower()


def test_shared_learning_controls_use_owner_scoped_postgres_and_cancel_without_local_state(shared_workspace, monkeypatch):
    from mammoth_os.postgres_learning_controls import PostgresLearningControls

    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )
    monkeypatch.setattr(
        api_server, "_atlas_state_file_for_request",
        lambda: pytest.fail("Shared learning controls must not resolve local learner state."),
    )
    initial = client.get("/api/atlas/controls", headers=headers)
    assert initial.status_code == 200
    configured = client.put("/api/atlas/controls", headers=headers, json={"daily_request_limit": 2})
    assert configured.status_code == 200
    assert configured.json()["daily_request_limit"] == 2

    controls = PostgresLearningControls(shared_workspace.dsn, shared_workspace.namespace, "alice")
    operation_id = controls.begin("/fixture", "default")
    assert any(item["id"] == operation_id for item in controls.snapshot()["operations"])
    visible = client.get("/api/atlas/controls", headers=headers)
    assert any(item["id"] == operation_id for item in visible.json()["operations"]), visible.text
    cancelled = client.post(f"/api/atlas/operations/{operation_id}/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancellation_requested"
    assert PostgresLearningControls(
        shared_workspace.dsn, shared_workspace.namespace, "bob",
    ).snapshot()["operations"] == []


def test_shared_learning_export_requires_shared_notes_and_uses_shared_learner_snapshot(shared_workspace, monkeypatch):
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    local_notes = client.post("/api/atlas/export", headers=headers)
    assert local_notes.status_code == 503

    monkeypatch.setenv("MAMMOTH_STATE_BACKEND", "supabase")
    state = {
        "status": "active", "active_account_id": "default", "user_id": "workspace:default",
        "learner_model": {"onboarding": {"experience_level": "beginner"}},
        "learner_storage": {"kind": "shared"},
        "topic": "Shared export topic",
    }
    recovery = {"contract": "mammoth.learning-workspace.v1", "values": {}}
    monkeypatch.setattr(api_server, "_atlas_status_adapter", lambda: (deepcopy(state), recovery))
    monkeypatch.setattr(
        api_server, "_load_learning_export_state",
        lambda: pytest.fail("Shared export must not load local learner state."),
    )
    monkeypatch.setattr(
        api_server, "_learner_storage_action",
        lambda *args, **kwargs: pytest.fail("Shared export must not read local adaptation."),
    )
    note = {
        "id": "linked", "user_id": "alice", "account_id": "default",
        "metadata": {"learning_context": {"contract": "mammoth.learning-selection.v1"}},
    }
    monkeypatch.setattr(api_server, "_read_json", lambda path, default=None: [note])
    response = client.post("/api/atlas/export", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert result["account_id"] == "default"
    assert result["learner_adaptation"]["model"] == state["learner_model"]
    assert result["workspace_recovery"] == recovery
    assert [item["id"] for item in result["linked_notes"]] == ["linked"]


def test_shared_lesson_generation_persists_to_owner_transaction(shared_workspace, monkeypatch):
    from mammoth_os.atlas_session import ATLASSession
    from mammoth_os.postgres_learning_controls import PostgresLearningControls

    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )

    def generate_fixture(self, topic, *, difficulty, learner_context):
        self.curriculum = {
            "curriculum_id": "shared-curriculum",
            "modules": [{"title": topic, "lessons": []}],
        }
        self.current_lesson = {
            "lesson_id": "shared-lesson", "title": topic,
            "objectives": ["Persist shared lesson state"],
        }
        self._curriculum_id = "shared-curriculum"
        self._lesson_id = "shared-lesson"
        return {
            "exercise_id": "shared-exercise", "title": "Shared exercise",
            "prompt": "A test fixture", "starter_files": {},
        }

    monkeypatch.setattr(ATLASSession, "start_lesson", generate_fixture)
    response = TestClient(api_server.app).post(
        "/api/atlas/lesson", headers={"Authorization": "Bearer alice"},
        json={"topic": "Shared transactions"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["exercise"]["exercise_id"] == "shared-exercise"
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    session, _ = tx.read_learning_session(account="default")
    assert session["lesson_id"] == "shared-lesson"
    assert session["current_exercise"]["exercise_id"] == "shared-exercise"
    assert session["lesson_history"][-1]["lesson_id"] == "shared-lesson"
    other_owner, _ = PostgresLearnerTransactions(
        shared_workspace.dsn, shared_workspace.namespace, "bob",
    ).read_learning_session(account="default")
    assert "lesson_id" not in other_owner


def test_shared_lesson_navigation_is_revision_and_operation_fenced(shared_workspace, monkeypatch):
    from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
    from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions
    from mammoth_os.postgres_learning_controls import PostgresLearningControls

    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    first = {"lesson_id": "lesson-1", "title": "First lesson", "objectives": ["First"]}
    second = {"lesson_id": "lesson-2", "title": "Second lesson", "objectives": ["Second"]}
    exercise = {"exercise_id": "exercise-1", "prompt": "", "lesson_type": "knowledge"}
    bundle["state"].update({
        "status": "active", "topic": "Shared navigation", "lesson_id": "lesson-1",
        "current_lesson": first, "current_exercise": exercise,
        "curriculum": {"modules": [{"module_id": "module-1", "title": "Module",
                                    "lessons": [first, second]}]},
        "lesson_history": [{"lesson_id": "lesson-1", "lesson": first, "exercise": exercise}],
    })
    bundle["state"]["account_sessions"]["default"].update({
        key: bundle["state"][key] for key in (
            "status", "topic", "lesson_id", "current_lesson", "current_exercise",
            "curriculum", "lesson_history",
        )
    })
    bundle_store.write(bundle, revision=revision)
    monkeypatch.setattr(
        "mammoth_os.exercise_generator.generate_exercises_for_lesson",
        lambda lesson, **kwargs: [{
            "exercise_id": "exercise-2", "title": lesson["title"],
            "prompt": "Continue", "lesson_type": "knowledge",
        }],
    )
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    advanced = client.post("/api/atlas/next", headers=headers, json={})
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["lesson_id"] == "lesson-2"
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    saved, _ = tx.read_learning_session(account="default")
    assert saved["lesson_id"] == "lesson-2"
    assert saved["lesson_history"][-1]["lesson_id"] == "lesson-2"

    returned = client.post("/api/atlas/back", headers=headers)
    assert returned.status_code == 200, returned.text
    assert returned.json()["lesson"]["lesson_id"] == "lesson-1"
    saved, _ = tx.read_learning_session(account="default")
    assert saved["lesson_id"] == "lesson-1"
    assert saved["lesson_history"][-1]["lesson_id"] == "lesson-1"


def test_shared_manual_exercise_regeneration_persists_transactionally(shared_workspace, monkeypatch):
    from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
    from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions
    from mammoth_os.postgres_learning_controls import PostgresLearningControls

    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    lesson = {"lesson_id": "regen-lesson", "title": "Regeneration"}
    original = {"exercise_id": "original", "title": "Original", "prompt": "Try"}
    bundle["state"].update({
        "status": "active", "topic": "Shared regeneration", "lesson_id": "regen-lesson",
        "current_lesson": lesson, "current_exercise": original,
        "lesson_history": [{"lesson_id": "regen-lesson", "lesson": lesson, "exercise": original}],
    })
    bundle["state"]["account_sessions"]["default"].update({
        key: bundle["state"][key] for key in (
            "status", "topic", "lesson_id", "current_lesson", "current_exercise", "lesson_history",
        )
    })
    bundle_store.write(bundle, revision=revision)
    monkeypatch.setattr(
        "mammoth_os.exercise_generator.generate_exercises_for_lesson",
        lambda lesson, **kwargs: [{
            "exercise_id": "regenerated", "title": "Fresh exercise", "prompt": "Try again",
        }],
    )
    response = TestClient(api_server.app).post(
        "/api/atlas/regenerate", headers={"Authorization": "Bearer alice"},
        json={"reason": "learner_requested"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["exercise"]["exercise_id"] == "regenerated"
    saved, _ = PostgresLearnerTransactions(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    ).read_learning_session(account="default")
    assert saved["current_exercise"]["exercise_id"] == "regenerated"
    assert saved["regenerated_exercise"]["reason"] == "learner_requested"
    assert saved["lesson_history"][-1]["exercise"]["exercise_id"] == "regenerated"


def test_shared_submission_commits_result_and_adaptation_atomically(shared_workspace, monkeypatch):
    from mammoth_os.atlas_session import ATLASSession
    from mammoth_os.postgres_learning_controls import PostgresLearningControls
    from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle

    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )
    store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = store.read()
    lesson = {"lesson_id": "submitted-lesson", "title": "Shared result"}
    exercise = {
        "exercise_id": "submitted-exercise", "title": "Answer",
        "lesson_type": "code", "submission_mode": "code",
    }
    bundle["state"].update({
        "status": "active", "topic": "Shared result", "lesson_id": "submitted-lesson",
        "current_lesson": lesson, "current_exercise": exercise,
        "lesson_history": [{
            "lesson_id": "submitted-lesson", "lesson": lesson, "exercise": exercise,
        }],
    })
    bundle["state"]["account_sessions"]["default"].update({
        key: bundle["state"][key] for key in (
            "status", "topic", "lesson_id", "current_lesson", "current_exercise", "lesson_history",
        )
    })
    store.write(bundle, revision=revision)

    async def submit(self, files):
        assert files == {"solution.py": "print('done')"}
        return {"passed": True, "mastery_evidence": True, "score": 1.0, "result": {"passed": True}}

    monkeypatch.setattr(ATLASSession, "submit", submit)
    response = TestClient(api_server.app).post(
        "/api/atlas/submit", headers={"Authorization": "Bearer alice"},
        json={"code": "print('done')"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["passed"] is True
    tx = PostgresLearnerTransactions(shared_workspace.dsn, shared_workspace.namespace, "alice")
    saved, _ = tx.read_learning_session(account="default")
    assert saved["last_submission"]["passed"] is True
    assert saved["lesson_history"][-1]["last_submission"]["passed"] is True
    assert saved["lesson_telemetry"]["submitted-lesson"]["attempts"] == 1
    model, _ = tx.read_adaptation(account="default")
    assert model["attempts"] == 1
    assert model["recent_outcomes"][-1]["passed"] is True


def test_shared_failed_submission_can_regenerate_remediation_without_replay(shared_workspace, monkeypatch):
    from mammoth_os.atlas_session import ATLASSession
    from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
    from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions
    from mammoth_os.postgres_learning_controls import PostgresLearningControls

    monkeypatch.setenv("MAMMOTH_LEARNING_CONTROLS_BACKEND", "postgres")
    monkeypatch.setattr(
        api_server, "_learning_controls",
        lambda: PostgresLearningControls(
            shared_workspace.dsn, shared_workspace.namespace, api_server._current_request_user_id(),
        ),
    )
    bundle_store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    bundle, revision = bundle_store.read()
    lesson = {"lesson_id": "remediation-lesson", "title": "Remediation"}
    exercise = {
        "exercise_id": "failed-exercise", "title": "Failing exercise",
        "lesson_type": "code", "submission_mode": "code", "prompt": "Solve it",
    }
    bundle["state"].update({
        "status": "active", "topic": "Shared remediation", "lesson_id": "remediation-lesson",
        "current_lesson": lesson, "current_exercise": exercise,
        "lesson_history": [{"lesson_id": "remediation-lesson", "lesson": lesson, "exercise": exercise}],
    })
    bundle["state"]["account_sessions"]["default"].update({
        key: bundle["state"][key] for key in (
            "status", "topic", "lesson_id", "current_lesson", "current_exercise", "lesson_history",
        )
    })
    bundle_store.write(bundle, revision=revision)

    async def submit(self, files):
        return {"passed": False, "score": 0.2, "result": {"passed": False}}

    monkeypatch.setattr(ATLASSession, "submit", submit)
    monkeypatch.setattr(api_server, "_build_submit_adaptation", lambda *_: {"remediation_needed": True})
    monkeypatch.setattr(
        "mammoth_os.exercise_generator.generate_exercises_for_lesson",
        lambda lesson, **kwargs: [{
            "exercise_id": "remediation-exercise", "title": "Targeted practice", "prompt": "Try again",
        }],
    )
    response = TestClient(api_server.app).post(
        "/api/atlas/submit", headers={"Authorization": "Bearer alice"},
        json={"code": "incorrect", "regenerate_on_fail": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["passed"] is False
    assert response.json()["regenerated_exercise"]["exercise_id"] == "remediation-exercise"
    saved, _ = PostgresLearnerTransactions(
        shared_workspace.dsn, shared_workspace.namespace, "alice",
    ).read_learning_session(account="default")
    assert saved["last_submission"]["passed"] is False
    assert saved["current_exercise"]["exercise_id"] == "remediation-exercise"
    assert saved["regenerated_exercise"]["reason"] == "remediation_after_failed_submission"


def test_every_unintegrated_atlas_route_is_guarded(shared_workspace):
    supported = {
        ("GET", "/api/atlas/status"), ("POST", "/api/atlas/workspace"),
        ("POST", "/api/atlas/onboard"), ("POST", "/api/atlas/learner/reset"),
        ("GET", "/api/atlas/lecture"), ("GET", "/api/atlas/history/preview"),
        ("GET", "/api/atlas/learner/privacy-review"), ("DELETE", "/api/atlas/history"),
        ("GET", "/api/atlas/learner/deletion-preview"),
        ("DELETE", "/api/atlas/learner/adaptation"), ("GET", "/api/atlas/modules"),
        ("GET", "/api/atlas/library"), ("GET", "/api/atlas/learner"),
        ("GET", "/api/atlas/curricula"), ("POST", "/api/atlas/curricula"),
        ("POST", "/api/atlas/reset"),
        ("POST", "/api/atlas/next"), ("POST", "/api/atlas/back"),
        ("POST", "/api/atlas/regenerate"),
    }
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer alice"}
    guarded = 0
    for route in api_server.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith(("/api/atlas/", "/agent/atlas/", "/api/account/")):
            continue
        path = re.sub(r"\{[^}]+\}", "fixture", path)
        for method in getattr(route, "methods", set()):
            method = method.upper()
            if (method, getattr(route, "path", "")) in supported:
                continue
            response = client.request(method, path, headers=headers)
            assert response.status_code == 503, f"{method} {path} was not guarded"
            assert response.json()["code"] == "storage_unavailable"
            guarded += 1
    assert guarded >= 30


def test_shared_workspace_database_outage_never_falls_back(shared_workspace, monkeypatch):
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", "host=127.0.0.1 port=1 dbname=missing connect_timeout=1")
    response = TestClient(api_server.app).get("/api/workspace/artifacts", headers={"Authorization": "Bearer alice"})
    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"


def test_shared_workspace_missing_owner_is_not_initialized_or_read_from_disk(shared_workspace, monkeypatch):
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: (
        {"id": "new-owner", "email": "", "is_admin": False} if token == "new" else None
    ))
    client = TestClient(api_server.app)
    for method in ("get", "post"):
        kwargs = {"headers": {"Authorization": "Bearer new"}}
        if method == "post":
            kwargs["json"] = {"body": "must not create data"}
        response = getattr(client, method)("/api/workspace/artifacts", **kwargs)
        assert response.status_code == 409
    assert PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "new-owner").read()[1] == 0


def test_independent_worker_processes_share_workspace_and_preserve_owner_isolation(shared_workspace):
    status, created = _run_worker("write")
    assert status == 200 and created["artifact"]["id"] == "cross-worker"
    status, listed = _run_worker("alice")
    assert status == 200 and listed["artifacts"][0]["body"] == "Durable private artifact"
    status, other = _run_worker("bob")
    assert status == 200 and other["artifacts"] == []


def test_runtime_archive_uses_shared_workspace_seam(shared_workspace):
    token = api_server._REQUEST_USER_ID.set("alice")
    try:
        result = api_server._archive_runtime_result(
            {"title": "Shared result", "summary": "Saved output", "status": "ok"},
            artifact_id="archive", agent_id="coding_agent", origin={},
        )
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    assert result["status"] == "saved"
    client = TestClient(api_server.app)
    assert client.get("/api/workspace/artifacts", headers={"Authorization": "Bearer alice"}).json()["artifacts"][0]["id"] == "archive"
    assert client.get("/api/workspace/artifacts", headers={"Authorization": "Bearer bob"}).json()["artifacts"] == []


def test_runtime_archive_reports_shared_storage_failure(shared_workspace, monkeypatch):
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", "host=127.0.0.1 port=1 dbname=missing connect_timeout=1")
    token = api_server._REQUEST_USER_ID.set("alice")
    try:
        result = api_server._archive_runtime_result(
            {"title": "Unsaved result", "summary": "Saved output", "status": "ok"},
            artifact_id="not-saved", agent_id="coding_agent", origin={},
        )
    finally:
        api_server._REQUEST_USER_ID.reset(token)
    assert result["status"] == "failed"
    assert "saved" in result["error"]
    store = PostgresLearnerBundle(shared_workspace.dsn, shared_workspace.namespace, "alice")
    assert store.read()[1] == 1
