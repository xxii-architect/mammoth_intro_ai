import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from mammoth_os import learner_model
from mammoth_os.learner_model import (
    LearnerStorageError, load_learner_model, save_learner_model,
    set_onboarding_profile, update_learner_model,
)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user",
                        lambda token: {"id": token, "is_admin": False} if token in {"tenant-a", "tenant-b"} else None)
    monkeypatch.setattr(api_server, "_atlas_state_file_for_request",
                        lambda: tmp_path / f"{api_server._current_request_user_id()}.json")
    with TestClient(api_server.app) as test_client:
        yield test_client


def in_scope(tenant, action):
    token = api_server._REQUEST_USER_ID.set(tenant)
    try:
        return action()
    finally:
        api_server._REQUEST_USER_ID.reset(token)


def test_tenants_and_local_accounts_have_distinct_scoped_models(client):
    def update(account):
        state = {"active_account_id": account}
        return api_server._hydrate_learner_state(
            state, user_id="caller-cannot-select-another-owner",
            lesson={"title": "Evidence"}, result={"passed": True},
        )
    in_scope("tenant-a", lambda: update("default"))
    in_scope("tenant-a", lambda: update("second"))
    in_scope("tenant-a", lambda: update("second"))
    for tenant, account, attempts in [("tenant-a", "default", 1), ("tenant-a", "second", 2), ("tenant-b", "default", 0)]:
        state = {"active_account_id": account}
        model = in_scope(tenant, lambda: api_server._hydrate_learner_state(state))
        assert model["user_id"] == f"workspace:{account}"
        assert model["attempts"] == attempts
        assert state["learner_storage"]["legacy_imported"] is False
    a = in_scope("tenant-a", lambda: api_server._learner_storage_path("workspace:default"))
    b = in_scope("tenant-b", lambda: api_server._learner_storage_path("workspace:default"))
    assert a != b


def test_learner_endpoint_requires_auth_and_ignores_client_owner(client):
    assert client.get("/api/atlas/learner").status_code == 401
    in_scope("tenant-a", lambda: api_server._hydrate_learner_state(
        {"active_account_id": "default"}, result={"passed": True}, lesson={"title": "Private concept"},
    ))
    a = client.get("/api/atlas/learner", headers={"Authorization": "Bearer tenant-a"}).json()
    b = client.get("/api/atlas/learner?user_id=tenant-a&account_id=default",
                   headers={"Authorization": "Bearer tenant-b"}).json()
    assert a["learner_model"]["attempts"] == 1
    assert b["learner_model"]["attempts"] == 0
    assert b["learner_model"]["mastery"] == {}
    assert "private-concept" not in json.dumps(b)
    assert a["learner_storage"]["scope_key"] != b["learner_storage"]["scope_key"]


def test_legacy_file_and_unverified_cached_adaptation_are_not_imported(client, monkeypatch, tmp_path):
    legacy = tmp_path / "atlas_learner_model.json"
    raw = {"user_id": "workspace:default", "attempts": 900, "mastery": {"legacy-private": 1}}
    legacy.write_text(json.dumps(raw), encoding="utf-8")
    before = legacy.read_bytes()
    original_path = learner_model._model_path
    monkeypatch.setattr(learner_model, "_model_path",
                        lambda storage_path=None: original_path(storage_path) if storage_path else str(legacy))
    state = {"active_account_id": "default", "current_lesson": {"title": "Keep this lesson"},
             "learner_model": raw, "learner_context": {"secret": "old global cache"},
             "learner_profile": {"attempts": 900}}
    def normalize():
        api_server._ensure_account_collections(state)
        assert "learner_context" not in state
        assert "learner_model" not in state
        assert "learner_profile" not in state
        api_server._hydrate_learner_state(state)
    in_scope("tenant-a", normalize)
    assert state["current_lesson"]["title"] == "Keep this lesson"
    assert state["learner_model"]["attempts"] == 0
    assert legacy.read_bytes() == before
    assert state["learner_storage"]["legacy_ownership"] == "unverified_not_imported"


def test_verified_cached_context_survives_only_its_actual_scope(client):
    state = {"active_account_id": "default"}
    in_scope("tenant-a", lambda: api_server._hydrate_learner_state(state, result={"passed": True}))
    in_scope("tenant-a", lambda: api_server._persist_active_account_collections(state))
    in_scope("tenant-a", lambda: api_server._ensure_account_collections(state))
    assert state["learner_model"]["attempts"] == 1
    in_scope("tenant-b", lambda: api_server._ensure_account_collections(state))
    assert "learner_model" not in state
    assert "learner_context" not in state


def test_onboarding_and_reset_touch_only_selected_private_model(client, monkeypatch):
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    for tenant in ("tenant-a", "tenant-b"):
        in_scope(tenant, lambda: api_server._hydrate_learner_state(
            {"active_account_id": "default"}, result={"passed": True}, lesson={"title": "Evidence"},
        ))
    in_scope("tenant-a", lambda: api_server._hydrate_learner_state(
        {"active_account_id": "second"}, result={"passed": True},
    ))
    result = in_scope("tenant-a", lambda: api_server._apply_atlas_onboarding_update(
        {"experience_level": "advanced", "goals": ["Compare evidence"]},
    ))
    assert result["learner_model"]["onboarding"]["experience_level"] == "advanced"
    in_scope("tenant-a", api_server._apply_atlas_learner_reset)
    for tenant, account, expected in [("tenant-a", "default", 0), ("tenant-a", "second", 1), ("tenant-b", "default", 1)]:
        model = in_scope(tenant, lambda: api_server._hydrate_learner_state({"active_account_id": account}))
        assert model["attempts"] == expected
    other = in_scope("tenant-b", lambda: api_server._hydrate_learner_state({"active_account_id": "default"}))
    assert other["onboarding"]["experience_level"] == "unknown"
    own = in_scope("tenant-a", lambda: api_server._hydrate_learner_state({"active_account_id": "default"}))
    assert own["onboarding"]["experience_level"] == "advanced"


@pytest.mark.parametrize("raw", ["not-json", "[]", '{"user_id":"another-learner"}',
                               '{"user_id":"workspace:default","mastery":[],"attempts":"invalid"}',
                               '{"user_id":"workspace:default","mastery":{"x":NaN}}'])
def test_bad_private_model_fails_explicitly_without_reset(client, raw):
    root = Path(in_scope("tenant-a", lambda: api_server._learner_storage_path("workspace:default")))
    root.mkdir(parents=True)
    path = root / "atlas_learner_model.json"
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()
    response = client.get("/api/atlas/learner", headers={"Authorization": "Bearer tenant-a"})
    assert response.status_code == 503
    assert "No reset or save was confirmed" in response.json()["detail"]
    assert path.read_bytes() == before


def test_atomic_model_save_failure_preserves_existing_record_and_onboarding_state(tmp_path, monkeypatch):
    root = str(tmp_path)
    save_learner_model(load_learner_model("one", storage_path=root), storage_path=root)
    before = (tmp_path / "atlas_learner_model.json").read_bytes()
    def fail(path, record):
        raise OSError("disk write failed")
    monkeypatch.setattr(learner_model, "_write_workspace", fail)
    state = {"topic": "Evidence"}
    with pytest.raises(LearnerStorageError, match="No save was confirmed"):
        set_onboarding_profile(state, user_id="one", storage_path=root, onboarding={"experience_level": "advanced"})
    assert state == {"topic": "Evidence"}
    assert (tmp_path / "atlas_learner_model.json").read_bytes() == before


def test_standalone_model_cannot_be_reassigned_to_another_user(tmp_path):
    root = str(tmp_path)
    update_learner_model("one", storage_path=root, result={"passed": True})
    before = (tmp_path / "atlas_learner_model.json").read_bytes()
    with pytest.raises(LearnerStorageError):
        load_learner_model("two", storage_path=root)
    with pytest.raises(LearnerStorageError):
        save_learner_model({"user_id": "two"}, storage_path=root)
    assert (tmp_path / "atlas_learner_model.json").read_bytes() == before


def test_concurrent_updates_do_not_lose_attempts(tmp_path):
    root = str(tmp_path)
    def update(_):
        return update_learner_model("one", storage_path=root, result={"passed": True})["attempts"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        attempts = list(pool.map(update, range(16)))
    assert sorted(attempts) == list(range(1, 17))
    assert load_learner_model("one", storage_path=root)["attempts"] == 16


def test_process_workers_serialize_actual_model_updates(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(Path(learner_model.__file__).parent.parent)}
    script = (
        "import sys; from mammoth_os.learner_model import update_learner_model; "
        "[update_learner_model('one', storage_path=sys.argv[1], result={'passed': True}) for _ in range(4)]"
    )
    def worker(_):
        return subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env,
                              capture_output=True, text=True, timeout=45)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(worker, range(4)):
            assert result.returncode == 0, result.stderr
    assert load_learner_model("one", storage_path=str(tmp_path))["attempts"] == 16


def test_cancelled_model_save_does_not_write(tmp_path):
    from mammoth_os.learning_controls import LearningCancelled, LearningControls, operation_context
    store = LearningControls(tmp_path / "controls.sqlite3")
    operation = store.begin("/api/atlas/submit", "default")
    with operation_context(store, operation):
        store.cancel(operation)
        with pytest.raises(LearningCancelled):
            update_learner_model("one", storage_path=str(tmp_path), result={"passed": True})
    assert not (tmp_path / "atlas_learner_model.json").exists()


def test_evaluation_uses_disposable_storage_not_private_or_legacy_model(client, monkeypatch):
    paths = []
    original = learner_model._model_path
    def record(storage_path=None):
        assert storage_path is not None
        path = original(storage_path)
        paths.append(Path(path))
        return path
    monkeypatch.setattr(learner_model, "_model_path", record)
    response = in_scope("tenant-a", lambda: api_server._run_atlas_evals({
        "active_account_id": "default", "topic": "Evidence",
        "current_lesson": {"title": "Evidence", "content": "Compare recorded observations."},
        "current_exercise": {"prompt": "Explain the observations."},
    }))
    assert response["status"] == "ok"
    assert paths
    assert all(not path.exists() for path in paths)
    assert all("mammoth-learner-eval-" in str(path.parent) for path in paths)
