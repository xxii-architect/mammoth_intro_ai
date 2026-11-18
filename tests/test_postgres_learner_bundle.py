from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from mammoth_os.postgres import database
from mammoth_os.agent_loop.runner import AgentRun
from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle, migration_lock
from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions
from mammoth_os.postgres_learning_controls import PostgresLearningControls
from mammoth_os.shared_state import StateConflict, StateUnavailable
from mammoth_os.learning_workspace import workspace_snapshot
from scripts.backup_learner_source import verify_backup, restore_fresh, collect_source, write_backup
from scripts.migrate_learner_bundle import (
    export_backup, export_full_namespace_rehearsal, export_full_rehearsal, export_with_controls_rehearsal,
    import_backup, import_combined_rehearsal, import_full_batch_rehearsal, import_full_namespace_rehearsal,
    import_full_rehearsal,
    import_reviewed_batch_rehearsal, import_with_controls_rehearsal,
)
from scripts.migrate_runtime_storage import CONTRACT as RUNTIME_BACKUP_CONTRACT, export_snapshot
from test_postgres_run_store import postgres as postgres_fixture, stores as run_stores_fixture

postgres = postgres_fixture
stores = run_stores_fixture


@pytest.fixture
def bundle_store(stores):
    store, _ = stores
    return PostgresLearnerBundle(store.dsn, store.namespace, "Owner+Exact")


def sample_bundle():
    return {
        "state": {"active_account_id": "default", "learning_erasure_epoch": "old"},
        "drafts": {"default": {"revision": 3, "text": "Private draft"}},
        "models": {"default": {"user_id": "workspace:default", "mastery": {"x": 0.5}}},
    }


def test_snapshot_is_atomic_exact_owner_scoped_and_revision_checked(bundle_store):
    bundle = sample_bundle()
    assert bundle_store.read() == ({"state": {}, "drafts": {}, "models": {}}, 0)
    assert bundle_store.write(bundle, revision=0) == 1
    for owner in ("owner+exact", "owner-exact", "Other"):
        assert PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, owner).read()[1] == 0
    assert PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-other",
                                 bundle_store.user_id).read()[1] == 0
    stale, revision = bundle_store.read()
    erased = deepcopy(stale)
    erased["state"]["learning_erasure_epoch"] = "new"
    erased["drafts"] = {}
    erased["models"] = {}
    assert bundle_store.write(erased, revision=revision) == 2
    with pytest.raises(StateConflict):
        bundle_store.write(stale, revision=revision)
    assert bundle_store.read() == (erased, 2)


def test_competing_creates_and_updates_have_one_winner(bundle_store):
    def attempt(revision, index):
        bundle = sample_bundle()
        bundle["state"]["index"] = index
        try:
            return bundle_store.write(bundle, revision=revision)
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lambda index: attempt(0, index), range(12))).count(1) == 1
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lambda index: attempt(1, index), range(12))).count(2) == 1
    assert bundle_store.read()[1] == 2


@pytest.mark.parametrize("invalid", [
    {}, {"state": [], "drafts": {}, "models": {}},
    {"state": {}, "drafts": {}, "models": {}, "extra": {}},
    {"state": {"nan": float("nan")}, "drafts": {}, "models": {}},
    {"state": {1: "not a JSON key"}, "drafts": {}, "models": {}},
    {"state": {"tuple": (1, 2)}, "drafts": {}, "models": {}},
])
def test_invalid_bundles_never_replace_existing_snapshot(bundle_store, invalid):
    original = sample_bundle()
    bundle_store.write(original, revision=0)
    with pytest.raises(ValueError):
        bundle_store.write(invalid, revision=1)
    assert bundle_store.read() == (original, 1)


@pytest.mark.parametrize("owner", ["", "anonymous", "local", "bad\x00owner", "a" * 257, None])
def test_owner_is_explicit_and_never_implicit(bundle_store, owner):
    with pytest.raises(ValueError):
        PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, owner)


@pytest.mark.parametrize("revision", [True, -1, 1.5, "0"])
def test_invalid_revision_is_rejected(bundle_store, revision):
    with pytest.raises(ValueError):
        bundle_store.write(sample_bundle(), revision=revision)


def test_private_permissions_and_idempotent_schema(postgres, bundle_store):
    bundle_store.write(sample_bundle(), revision=0)
    migration = (Path(__file__).resolve().parents[1] / ".mammoth" / "supabase_learner_bundles.sql").read_text()
    postgres(migration)
    assert bundle_store.read()[1] == 1
    for role in ("anon", "authenticated"):
        result = postgres(f"SET ROLE {role}; SELECT * FROM public.mammoth_learner_bundles", check=False)
        assert result.returncode != 0 and "permission denied" in result.stderr
    result = postgres("SET ROLE service_role; DELETE FROM public.mammoth_learner_bundles", check=False)
    assert result.returncode != 0 and "permission denied" in result.stderr


def test_database_failure_never_falls_back_to_local(bundle_store):
    broken = PostgresLearnerBundle("host=127.0.0.1 port=1 dbname=missing connect_timeout=1",
                                   bundle_store.namespace, bundle_store.user_id)
    with pytest.raises(StateUnavailable):
        broken.read()
    with pytest.raises(StateUnavailable):
        broken.write(sample_bundle(), revision=0)


def test_failed_database_write_preserves_previous_snapshot(bundle_store):
    original = sample_bundle()
    bundle_store.write(original, revision=0)
    invalid = deepcopy(original)
    invalid["state"]["value"] = "PostgreSQL does not accept a null \x00 character"
    with pytest.raises(StateUnavailable):
        bundle_store.write(invalid, revision=1)
    assert bundle_store.read() == (original, 1)


def test_exclusive_namespace_migration_lock_blocks_writes(bundle_store):
    with database(bundle_store.dsn) as connection:
        connection.execute("BEGIN")
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(bundle_store.namespace),))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(bundle_store.write, sample_bundle(), revision=0)
            try:
                deadline = time.monotonic() + 4
                waiting = False
                while time.monotonic() < deadline:
                    connection.execute("SELECT pg_stat_clear_snapshot()")
                    waiting = connection.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event='advisory' AND query LIKE 'SELECT pg_advisory_xact_lock_shared%')"
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.05)
                assert waiting and not future.done()
            finally:
                connection.execute("COMMIT")
            assert future.result(timeout=10) == 1


@pytest.mark.parametrize("action", [
    "snapshot", "set_limit", "begin", "cancel", "cancel_account", "is_cancelled", "finish",
])
def test_exclusive_namespace_migration_lock_blocks_generic_controls(bundle_store, action):
    controls = PostgresLearningControls(bundle_store.dsn, bundle_store.namespace, bundle_store.user_id)
    operation = controls.begin("/fixture", "default")
    calls = {
        "snapshot": lambda: controls.snapshot(),
        "set_limit": lambda: controls.set_limit(7),
        "begin": lambda: controls.begin("/second", "default"),
        "cancel": lambda: controls.cancel(operation),
        "cancel_account": lambda: controls.cancel_account("default"),
        "is_cancelled": lambda: controls.is_cancelled(operation),
        "finish": lambda: controls.finish(operation, "finished"),
    }
    with database(bundle_store.dsn) as connection:
        connection.execute("BEGIN")
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(bundle_store.namespace),))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(calls[action])
            try:
                deadline = time.monotonic() + 5
                waiting = False
                while time.monotonic() < deadline:
                    connection.execute("SELECT pg_stat_clear_snapshot()")
                    waiting = connection.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event='advisory' AND query LIKE 'SELECT pg_advisory_xact_lock_shared%')"
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.05)
                assert waiting and not future.done()
            finally:
                connection.execute("COMMIT")
            future.result(timeout=10)


def test_experimental_backup_import_export_restore_preserves_fences(bundle_store, tmp_path):
    snapshot = workspace_snapshot({"active_account_id": "default"})
    bundle = {
        "state": {"active_account_id": "default", "accounts": {"default": {}, "second": {}},
                  "learner_erasure": {"second": {"status": "pending", "epoch": "a" * 32}}},
        "drafts": {"default": {"exercise_key": snapshot["exercise_key"], "revision": 3,
                               "values": snapshot["values"], "extension": "preserve"}},
        "models": {"second": {"user_id": "workspace:second", "extension": {"preserve": True}}},
    }
    original, exported, restored = (tmp_path / name for name in ("source", "exported", "restored"))
    write_backup(original, bundle_store.user_id, bundle, ["default", "second"])
    with pytest.raises(ValueError, match="quiescence"):
        import_backup(bundle_store, original)
    assert bundle_store.read()[1] == 0
    assert import_backup(bundle_store, original, confirm_quiesced=True) == 1
    assert bundle_store.read() == (bundle, 1)
    with pytest.raises(StateConflict):
        import_backup(bundle_store, original, confirm_quiesced=True)
    assert bundle_store.read() == (bundle, 1)
    with pytest.raises(ValueError, match="quiescence"):
        export_backup(bundle_store, exported)
    assert not exported.exists()
    export_backup(bundle_store, exported, ["removed"], confirm_quiesced=True)
    assert verify_backup(exported, bundle_store.user_id)["accounts"] == ["default", "removed", "second"]
    restore_fresh(exported, restored, bundle_store.user_id)
    state_path = restored / "atlas_state_owner-exact.json"
    restored_bundle, _ = collect_source(state_path, bundle_store.user_id, ["removed"])
    assert restored_bundle == bundle
    assert (restored / "restore-complete.json").exists()


@pytest.fixture
def controls_rehearsal(bundle_store, tmp_path):
    bundle = {"state": {"active_account_id": "default",
                        "learner_erasure": {"default": {"epoch": "a" * 32, "status": "complete"}}},
              "drafts": {}, "models": {}}
    path = tmp_path / "source"
    write_backup(path, bundle_store.user_id, bundle, ["default"])
    snapshot = {
        "contract": RUNTIME_BACKUP_CONTRACT, "user_id": bundle_store.user_id,
        "daily_tokens": None, "runs": [], "attempts": [],
        "learning_controls": {
            "daily_limit": 8, "usage": [{"day": "2026-01-01", "admitted": 3}],
            "operations": [{"id": "finished", "route": "/fixture", "account_id": "default",
                            "status": "finished", "started_at": "2026-01-01T10:00:00+00:00",
                            "finished_at": "2026-01-01T10:01:00+00:00"}],
        },
    }
    return path, bundle, snapshot


def test_learner_and_controls_import_commit_together(bundle_store, controls_rehearsal):
    path, bundle, snapshot = controls_rehearsal
    with pytest.raises(ValueError, match="quiescence"):
        import_with_controls_rehearsal(bundle_store, path, snapshot)
    assert import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True) == 1
    assert bundle_store.read() == (bundle, 1)
    with database(bundle_store.dsn) as connection:
        owner = (bundle_store.namespace, bundle_store.user_id)
        assert connection.execute(
            "SELECT daily_limit FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s", owner
        ).fetchone() == (8,)
        assert connection.execute(
            "SELECT day::text,admitted FROM public.mammoth_learning_usage WHERE namespace=%s AND user_id=%s", owner
        ).fetchall() == [("2026-01-01", 3)]
        assert connection.execute(
            "SELECT id,status FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s", owner
        ).fetchall() == [("finished", "finished")]
    with pytest.raises(StateConflict):
        import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    assert bundle_store.read() == (bundle, 1)


@pytest.mark.parametrize("reason", [
    "wrong_owner", "missing_controls", "invalid_controls", "unknown_controls", "unknown_usage",
    "unfinished", "existing_controls", "tampered",
])
def test_atomic_import_refuses_unsafe_input_without_creating_bundle(bundle_store, controls_rehearsal, reason):
    path, _, snapshot = controls_rehearsal
    if reason == "wrong_owner":
        snapshot["user_id"] = "different-owner"
    elif reason == "missing_controls":
        del snapshot["learning_controls"]
    elif reason == "invalid_controls":
        snapshot["learning_controls"] = {"daily_limit": 8}
    elif reason == "unknown_controls":
        snapshot["learning_controls"]["extension"] = "preserve"
    elif reason == "unknown_usage":
        snapshot["learning_controls"]["usage"][0]["extension"] = "preserve"
    elif reason == "unfinished":
        snapshot["learning_controls"]["operations"][0].update(status="running", finished_at=None)
    elif reason == "existing_controls":
        with database(bundle_store.dsn) as connection:
            connection.execute("INSERT INTO public.mammoth_learning_policy VALUES(%s,%s,%s)",
                               (bundle_store.namespace, bundle_store.user_id, 4))
    else:
        payload = path / "learner.json"
        payload.write_bytes(payload.read_bytes() + b" ")
    with pytest.raises((ValueError, StateConflict)):
        import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    assert bundle_store.read()[1] == 0
    with database(bundle_store.dsn) as connection:
        row = connection.execute(
            "SELECT daily_limit FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s",
            (bundle_store.namespace, bundle_store.user_id),
        ).fetchone()
    assert row == ((4,) if reason == "existing_controls" else None)


def test_competing_atomic_imports_have_one_winner(bundle_store, controls_rehearsal):
    path, bundle, snapshot = controls_rehearsal

    def run(_):
        try:
            return import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2)), key=lambda value: value or 0) == [None, 1]
    assert bundle_store.read() == (bundle, 1)
    with database(bundle_store.dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s",
            (bundle_store.namespace, bundle_store.user_id),
        ).fetchone() == (1,)


@pytest.fixture
def reviewed_batch(bundle_store, controls_rehearsal, tmp_path):
    source, bundle, runtime = controls_rehearsal
    second_owner = "z-second-owner"
    second_source = tmp_path / "second-source"
    second_bundle = deepcopy(bundle)
    second_bundle["state"]["topic"] = "Second owner's work"
    write_backup(second_source, second_owner, second_bundle, ["default"])
    second_runtime = deepcopy(runtime)
    second_runtime["user_id"] = second_owner
    return [(bundle_store.user_id, source, runtime), (second_owner, second_source, second_runtime)]


def test_reviewed_batch_import_is_atomic_and_owner_scoped(bundle_store, reviewed_batch):
    with pytest.raises(ValueError, match="quiescence"):
        import_reviewed_batch_rehearsal(bundle_store, reviewed_batch)
    assert import_reviewed_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True) == 2
    for owner, source, runtime in reviewed_batch:
        target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, owner)
        assert target.read()[0] == json.loads((source / "learner.json").read_bytes())
        with database(target.dsn) as connection:
            assert connection.execute(
                "SELECT daily_limit FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s",
                (target.namespace, owner),
            ).fetchone() == (runtime["learning_controls"]["daily_limit"],)
    with pytest.raises(StateConflict):
        import_reviewed_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)


@pytest.mark.parametrize("damage", ["duplicate", "wrong_owner", "tampered", "unfinished", "existing"])
def test_reviewed_batch_import_rejects_any_unsafe_owner_without_partial_writes(bundle_store, reviewed_batch, damage):
    second_owner, source, runtime = reviewed_batch[1]
    if damage == "duplicate":
        reviewed_batch.append(reviewed_batch[0])
    elif damage == "wrong_owner":
        runtime["user_id"] = "different-owner"
    elif damage == "tampered":
        payload = source / "learner.json"
        payload.write_bytes(payload.read_bytes() + b" ")
    elif damage == "unfinished":
        runtime["learning_controls"]["operations"][0].update(status="running", finished_at=None)
    else:
        with database(bundle_store.dsn) as connection:
            connection.execute(
                "INSERT INTO public.mammoth_learning_policy(namespace,user_id,daily_limit) VALUES(%s,%s,3)",
                (bundle_store.namespace, second_owner),
            )
    with pytest.raises((ValueError, StateConflict)):
        import_reviewed_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    assert bundle_store.read()[1] == 0
    second = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, second_owner)
    assert second.read()[1] == 0
    with database(bundle_store.dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s",
            (bundle_store.namespace, bundle_store.user_id),
        ).fetchone() == (0,)


def test_reviewed_batch_import_rolls_back_first_owner_on_second_owner_database_failure(bundle_store, reviewed_batch):
    reviewed_batch[1][2]["learning_controls"]["operations"][0]["route"] = "\x00"
    with pytest.raises(StateUnavailable):
        import_reviewed_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    with database(bundle_store.dsn) as connection:
        for table in ("mammoth_learner_bundles", "mammoth_learning_policy",
                      "mammoth_learning_usage", "mammoth_learning_operations"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s", (bundle_store.namespace,),
            ).fetchone() == (0,)


def test_reviewed_batch_rejects_normalized_owner_collision(bundle_store, reviewed_batch, tmp_path):
    collision = "owner-exact"
    source = tmp_path / "collision"
    bundle = json.loads((reviewed_batch[1][1] / "learner.json").read_bytes())
    write_backup(source, collision, bundle, ["default"])
    runtime = deepcopy(reviewed_batch[1][2])
    runtime["user_id"] = collision
    reviewed_batch[1] = (collision, source, runtime)
    with pytest.raises(ValueError, match="collide"):
        import_reviewed_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    assert bundle_store.read()[1] == 0
    assert PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, collision).read()[1] == 0


def test_competing_reviewed_batch_imports_commit_only_one_batch(bundle_store, reviewed_batch):
    def attempt():
        try:
            return import_reviewed_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted((result is not None for result in pool.map(lambda _: attempt(), range(2)))) == [False, True]
    with database(bundle_store.dsn) as connection:
        for table in ("mammoth_learner_bundles", "mammoth_learning_policy",
                      "mammoth_learning_usage", "mammoth_learning_operations"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s", (bundle_store.namespace,),
            ).fetchone() == (2,)


def test_full_batch_rehearsal_preserves_runtime_and_learner_records(bundle_store, reviewed_batch):
    for index, (owner, _, runtime) in enumerate(reviewed_batch):
        run = AgentRun(id=f"run-{index:016x}", user_id=owner, message="Saved run", storage_revision=1)
        runtime["runs"] = [{"payload": run.to_dict(), "cancellation_requested": True}]
        runtime["daily_tokens"] = 100
        runtime["attempts"] = [{
            "id": f"attempt-{index}", "day": "2026-01-01", "provider": "example", "model": "model",
            "started_at": "2026-01-01T10:00:00+00:00", "finished_at": None,
            "reserved": 10, "reported": None, "status": "pending",
        }]
    assert import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True) == 2
    for owner, source, runtime in reviewed_batch:
        assert export_snapshot(bundle_store.dsn, bundle_store.namespace, owner) == runtime
        assert PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, owner).read()[0] == json.loads(
            (source / "learner.json").read_bytes()
        )


@pytest.mark.parametrize("damage", ["runtime_conflict", "runtime_write", "unknown_runtime", "unknown_run"])
def test_full_batch_rehearsal_rolls_back_every_owner_on_failure(bundle_store, reviewed_batch, damage):
    owner, _, runtime = reviewed_batch[1]
    if damage == "runtime_conflict":
        with database(bundle_store.dsn) as connection:
            connection.execute(
                "INSERT INTO public.mammoth_private_runtime_policy(namespace,user_id,daily_tokens) VALUES(%s,%s,3)",
                (bundle_store.namespace, owner),
            )
    elif damage == "runtime_write":
        runtime["attempts"] = [{
            "id": "bad", "day": "2026-01-01", "provider": "invalid\x00value", "model": "model",
            "started_at": "2026-01-01T10:00:00+00:00", "finished_at": None,
            "reserved": 10, "reported": None, "status": "pending",
        }]
    elif damage == "unknown_runtime":
        runtime["future"] = {"must_not_be_discarded": True}
    else:
        run = AgentRun(id="run-0000000000000001", user_id=owner, message="Saved run", storage_revision=1)
        runtime["runs"] = [{"payload": run.to_dict(), "cancellation_requested": False, "future": True}]
    with pytest.raises((ValueError, StateUnavailable)):
        import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    with database(bundle_store.dsn) as connection:
        for table in ("mammoth_learner_bundles", "mammoth_learning_policy", "mammoth_learning_usage",
                      "mammoth_learning_operations", "mammoth_private_runtime_policy",
                      "mammoth_private_runtime_attempts", "mammoth_agent_runs"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s AND user_id=%s",
                (bundle_store.namespace, bundle_store.user_id),
            ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_learner_bundles WHERE namespace=%s AND user_id=%s",
            (bundle_store.namespace, owner),
        ).fetchone() == (0,)


def test_full_rehearsal_backup_restores_fences_runs_and_usage_to_fresh_namespace(bundle_store, reviewed_batch, tmp_path):
    owner, _, runtime = reviewed_batch[0]
    run = AgentRun(id="run-0000000000000042", user_id=owner, message="Saved run", storage_revision=1)
    runtime["runs"] = [{"payload": run.to_dict(), "cancellation_requested": True}]
    runtime["attempts"] = [{
        "id": "reservation", "day": "2026-01-01", "provider": "example", "model": "model",
        "started_at": "2026-01-01T10:00:00+00:00", "finished_at": None,
        "reserved": 10, "reported": None, "status": "pending",
    }]
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    tx = PostgresLearnerTransactions(bundle_store.dsn, bundle_store.namespace, owner)
    operation = tx.begin_operation(revision=1, account="default", route="/fixture")
    PostgresLearningControls(bundle_store.dsn, bundle_store.namespace, owner).finish(operation, "finished")
    backup = tmp_path / "full-backup"
    with pytest.raises(ValueError, match="quiescence"):
        export_full_rehearsal(bundle_store, backup)
    marker = export_full_rehearsal(bundle_store, backup, confirm_quiesced=True)
    assert marker["runtime_activation_supported"] is False
    with pytest.raises(ValueError, match="fences"):
        export_snapshot(bundle_store.dsn, bundle_store.namespace, owner)
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", owner)
    with pytest.raises(ValueError, match="quiescence"):
        import_full_rehearsal(target, backup)
    assert import_full_rehearsal(target, backup, confirm_quiesced=True) == 1
    assert target.read()[0] == bundle_store.read()[0]
    with database(target.dsn) as connection:
        for table in ("mammoth_learner_operation_fences", "mammoth_learning_operations",
                      "mammoth_learning_usage", "mammoth_learning_policy", "mammoth_agent_runs",
                      "mammoth_private_runtime_policy", "mammoth_private_runtime_attempts"):
            source = connection.execute(
                f"SELECT * FROM public.{table} WHERE namespace=%s AND user_id=%s ORDER BY 1,2,3",
                (bundle_store.namespace, owner),
            ).fetchall()
            restored = connection.execute(
                f"SELECT * FROM public.{table} WHERE namespace=%s AND user_id=%s ORDER BY 1,2,3",
                (target.namespace, owner),
            ).fetchall()
            assert [row[1:] for row in source] == [row[1:] for row in restored]
    with pytest.raises(StateConflict):
        import_full_rehearsal(target, backup, confirm_quiesced=True)


@pytest.mark.parametrize("damage", ["learner", "manifest", "controls", "runtime", "marker", "wrong_owner"])
def test_full_rehearsal_restore_rejects_corruption_without_writes(bundle_store, reviewed_batch, tmp_path, damage):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    backup = tmp_path / "full-backup"
    export_full_rehearsal(bundle_store, backup, confirm_quiesced=True)
    target_owner = "other" if damage == "wrong_owner" else bundle_store.user_id
    if damage in {"learner", "controls", "runtime"}:
        path = backup / "learner" / "learner.json" if damage == "learner" else backup / f"{damage}.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif damage == "manifest":
        path = backup / "learner" / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["accounts"].append("reviewed-but-empty")
        path.write_text(json.dumps(manifest), encoding="utf-8")
    elif damage == "marker":
        (backup / "complete.json").unlink()
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", target_owner)
    with pytest.raises(ValueError):
        import_full_rehearsal(target, backup, confirm_quiesced=True)
    assert target.read()[1] == 0
    with database(target.dsn) as connection:
        for table in ("mammoth_learning_policy", "mammoth_private_runtime_policy"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s", (target.namespace,),
            ).fetchone() == (0,)


def test_full_rehearsal_restore_rolls_back_learner_if_runtime_owner_exists(bundle_store, reviewed_batch, tmp_path):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    backup = tmp_path / "full-backup"
    export_full_rehearsal(bundle_store, backup, confirm_quiesced=True)
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", bundle_store.user_id)
    with database(target.dsn) as connection:
        connection.execute(
            "INSERT INTO public.mammoth_private_runtime_policy(namespace,user_id,daily_tokens) VALUES(%s,%s,3)",
            (target.namespace, target.user_id),
        )
    with pytest.raises(ValueError, match="already has state"):
        import_full_rehearsal(target, backup, confirm_quiesced=True)
    assert target.read()[1] == 0
    with database(target.dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_learning_policy WHERE namespace=%s", (target.namespace,),
        ).fetchone() == (0,)


def test_full_rehearsal_snapshot_starts_after_prior_learner_writer_commits(bundle_store, reviewed_batch, tmp_path):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    backup = tmp_path / "full-backup"
    with database(bundle_store.dsn) as connection:
        connection.execute("BEGIN")
        connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (migration_lock(bundle_store.namespace),))
        connection.execute(
            "UPDATE public.mammoth_learner_bundles SET state=jsonb_set(state,'{topic}',%s::jsonb) "
            "WHERE namespace=%s AND user_id=%s",
            ('"committed before snapshot"', bundle_store.namespace, bundle_store.user_id),
        )
        connection.execute(
            "UPDATE public.mammoth_private_runtime_policy SET daily_tokens=91 WHERE namespace=%s AND user_id=%s",
            (bundle_store.namespace, bundle_store.user_id),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(export_full_rehearsal, bundle_store, backup, confirm_quiesced=True)
            try:
                deadline = time.monotonic() + 4
                waiting = False
                while time.monotonic() < deadline:
                    connection.execute("SELECT pg_stat_clear_snapshot()")
                    waiting = connection.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event='advisory' AND query LIKE 'SELECT pg_advisory_lock%')"
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.05)
                assert waiting and not future.done()
            finally:
                connection.execute("COMMIT")
            future.result(timeout=10)
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", bundle_store.user_id)
    import_full_rehearsal(target, backup, confirm_quiesced=True)
    assert target.read()[0]["state"]["topic"] == "committed before snapshot"
    assert export_snapshot(target.dsn, target.namespace, target.user_id)["daily_tokens"] == 91


def test_namespace_rehearsal_restores_all_reviewed_owners_atomically(bundle_store, reviewed_batch, tmp_path):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    source_owner = reviewed_batch[0][0]
    operation = PostgresLearnerTransactions(bundle_store.dsn, bundle_store.namespace, source_owner).begin_operation(
        revision=1, account="default", route="/fixture",
    )
    PostgresLearningControls(bundle_store.dsn, bundle_store.namespace, source_owner).finish(operation, "finished")
    backup = tmp_path / "namespace-backup"
    owners = {owner: ["previously-removed"] for owner, _, _ in reviewed_batch}
    marker = export_full_namespace_rehearsal(bundle_store, backup, owners, confirm_quiesced=True)
    assert len(marker["owners"]) == 2 and marker["runtime_activation_supported"] is False
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", bundle_store.user_id)
    assert import_full_namespace_rehearsal(target, backup, confirm_quiesced=True) == 2
    for owner in owners:
        original = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, owner)
        restored = PostgresLearnerBundle(target.dsn, target.namespace, owner)
        assert original.read()[0] == restored.read()[0]
    with database(target.dsn) as connection:
        for table in ("mammoth_learner_bundles", "mammoth_learning_policy", "mammoth_learning_usage",
                      "mammoth_learning_operations", "mammoth_learner_operation_fences", "mammoth_agent_runs",
                      "mammoth_private_runtime_policy", "mammoth_private_runtime_attempts"):
            source = connection.execute(
                f"SELECT * FROM public.{table} WHERE namespace=%s ORDER BY 1,2,3", (bundle_store.namespace,),
            ).fetchall()
            restored = connection.execute(
                f"SELECT * FROM public.{table} WHERE namespace=%s ORDER BY 1,2,3", (target.namespace,),
            ).fetchall()
            assert [row[1:] for row in source] == [row[1:] for row in restored]
    with pytest.raises(StateConflict, match="namespace"):
        import_full_namespace_rehearsal(target, backup, confirm_quiesced=True)
    with pytest.raises(ValueError, match="fresh"):
        import_full_namespace_rehearsal(bundle_store, backup, confirm_quiesced=True)


@pytest.mark.parametrize("owners", [{}, {"owner": ["same", "same"]}, {"owner": [["invalid"]]}, {"owner": "default"}])
def test_namespace_rehearsal_rejects_invalid_review_inventory(bundle_store, tmp_path, owners):
    backup = tmp_path / "namespace-backup"
    with pytest.raises(ValueError):
        export_full_namespace_rehearsal(bundle_store, backup, owners, confirm_quiesced=True)
    assert not backup.exists()
    with pytest.raises(ValueError, match="quiescence"):
        export_full_namespace_rehearsal(bundle_store, backup, owners)


@pytest.mark.parametrize("table", [
    "mammoth_learner_bundles", "mammoth_learning_policy", "mammoth_learning_usage",
    "mammoth_learning_operations", "mammoth_agent_runs", "mammoth_private_runtime_policy",
    "mammoth_private_runtime_attempts",
])
def test_namespace_rehearsal_rejects_unreviewed_owner_records(bundle_store, reviewed_batch, tmp_path, table):
    reviewed_batch[1][2]["attempts"] = [{
        "id": "reservation", "day": "2026-01-01", "provider": "example", "model": "model",
        "started_at": "2026-01-01T10:00:00+00:00", "finished_at": None,
        "reserved": 10, "reported": None, "status": "pending",
    }]
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    with database(bundle_store.dsn) as connection:
        if table == "mammoth_agent_runs":
            run = AgentRun(id="run-0000000000000089", user_id="unreviewed", message="run", storage_revision=1)
            from psycopg.types.json import Jsonb
            connection.execute(
                "INSERT INTO public.mammoth_agent_runs(namespace,user_id,id,revision,payload,cancellation_requested,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (bundle_store.namespace, "unreviewed", run.id, 1, Jsonb(run.to_dict()), False, run.updated_at),
            )
        elif table.startswith("mammoth_learning_"):
            connection.execute(
                "INSERT INTO public.mammoth_learning_policy(namespace,user_id,daily_limit) VALUES(%s,%s,3)",
                (bundle_store.namespace, "unreviewed"),
            )
            if table == "mammoth_learning_usage":
                connection.execute(
                    "INSERT INTO public.mammoth_learning_usage(namespace,user_id,day,admitted) VALUES(%s,%s,%s,%s)",
                    (bundle_store.namespace, "unreviewed", "2026-01-01", 1),
                )
            elif table == "mammoth_learning_operations":
                connection.execute(
                    "INSERT INTO public.mammoth_learning_operations"
                    "(namespace,user_id,id,route,account_id,status,started_at,finished_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (bundle_store.namespace, "unreviewed", "op", "/fixture", "default", "finished",
                     "2026-01-01T10:00:00+00:00", "2026-01-01T10:01:00+00:00"),
                )
        elif table.startswith("mammoth_private_runtime_"):
            connection.execute(
                "INSERT INTO public.mammoth_private_runtime_policy(namespace,user_id,daily_tokens) VALUES(%s,%s,3)",
                (bundle_store.namespace, "unreviewed"),
            )
            if table == "mammoth_private_runtime_attempts":
                connection.execute(
                    "INSERT INTO public.mammoth_private_runtime_attempts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (bundle_store.namespace, "unreviewed", "attempt", "2026-01-01", "example", "model",
                     "2026-01-01T10:00:00+00:00", None, 1, None, "pending"),
                )
        else:
            connection.execute(
                "INSERT INTO public.mammoth_learner_bundles(namespace,user_id,state,drafts,models,revision) "
                "VALUES (%s,%s,'{}'::jsonb,'{}'::jsonb,'{}'::jsonb,1)",
                (bundle_store.namespace, "unreviewed"),
            )
    backup = tmp_path / "namespace-backup"
    with pytest.raises(ValueError, match="Unreviewed owner"):
        export_full_namespace_rehearsal(
            bundle_store, backup, {owner: [] for owner, _, _ in reviewed_batch}, confirm_quiesced=True,
        )
    assert not backup.exists()


@pytest.mark.parametrize("damage", ["marker", "child_marker", "child_payload", "missing_owner", "occupied"])
def test_namespace_rehearsal_rejects_corruption_or_occupied_destination_without_partial_restore(
        bundle_store, reviewed_batch, tmp_path, damage):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    backup = tmp_path / "namespace-backup"
    marker = export_full_namespace_rehearsal(
        bundle_store, backup, {owner: [] for owner, _, _ in reviewed_batch}, confirm_quiesced=True,
    )
    child = backup / marker["owners"][1]["directory"]
    if damage == "marker":
        (backup / "complete.json").unlink()
    elif damage == "child_marker":
        path = child / "complete.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif damage == "child_payload":
        path = child / "runtime.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif damage == "missing_owner":
        (child / "complete.json").unlink()
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", bundle_store.user_id)
    if damage == "occupied":
        with database(target.dsn) as connection:
            connection.execute(
                "INSERT INTO public.mammoth_private_runtime_policy(namespace,user_id,daily_tokens) VALUES(%s,%s,3)",
                (target.namespace, "unrelated-owner"),
            )
    with pytest.raises((ValueError, StateConflict)):
        import_full_namespace_rehearsal(target, backup, confirm_quiesced=True)
    with database(target.dsn) as connection:
        for table in ("mammoth_learner_bundles", "mammoth_learning_policy", "mammoth_learning_usage",
                      "mammoth_learning_operations", "mammoth_learner_operation_fences", "mammoth_agent_runs",
                      "mammoth_private_runtime_attempts"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s", (target.namespace,),
            ).fetchone() == (0,)


def test_namespace_restore_rolls_back_first_owner_on_second_database_failure(
        bundle_store, reviewed_batch, tmp_path, postgres):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    backup = tmp_path / "namespace-backup"
    export_full_namespace_rehearsal(
        bundle_store, backup, {owner: [] for owner, _, _ in reviewed_batch}, confirm_quiesced=True,
    )
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", bundle_store.user_id)
    postgres("""
CREATE FUNCTION public.test_reject_second_restore_owner() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.user_id = 'z-second-owner' THEN RAISE EXCEPTION 'injected restore failure'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER test_reject_second_restore_owner BEFORE INSERT ON public.mammoth_private_runtime_policy
FOR EACH ROW EXECUTE FUNCTION public.test_reject_second_restore_owner();
""")
    try:
        with pytest.raises(StateUnavailable):
            import_full_namespace_rehearsal(target, backup, confirm_quiesced=True)
    finally:
        postgres("DROP TRIGGER test_reject_second_restore_owner ON public.mammoth_private_runtime_policy; "
                 "DROP FUNCTION public.test_reject_second_restore_owner();")
    with database(target.dsn) as connection:
        for table in ("mammoth_learner_bundles", "mammoth_learning_policy", "mammoth_learning_usage",
                      "mammoth_learning_operations", "mammoth_learner_operation_fences", "mammoth_agent_runs",
                      "mammoth_private_runtime_policy", "mammoth_private_runtime_attempts"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s", (target.namespace,),
            ).fetchone() == (0,)


def test_namespace_snapshot_starts_after_prior_learner_writer_commits(bundle_store, reviewed_batch, tmp_path):
    import_full_batch_rehearsal(bundle_store, reviewed_batch, confirm_quiesced=True)
    backup = tmp_path / "namespace-backup"
    owners = {owner: [] for owner, _, _ in reviewed_batch}
    with database(bundle_store.dsn) as connection:
        connection.execute("BEGIN")
        connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (migration_lock(bundle_store.namespace),))
        connection.execute(
            "UPDATE public.mammoth_learner_bundles SET state=jsonb_set(state,'{topic}',%s::jsonb) "
            "WHERE namespace=%s AND user_id=%s",
            ('"namespace writer committed"', bundle_store.namespace, reviewed_batch[1][0]),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(export_full_namespace_rehearsal, bundle_store, backup, owners,
                                 confirm_quiesced=True)
            try:
                deadline = time.monotonic() + 4
                waiting = False
                while time.monotonic() < deadline:
                    connection.execute("SELECT pg_stat_clear_snapshot()")
                    waiting = connection.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event='advisory' AND query LIKE 'SELECT pg_advisory_lock%')"
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.05)
                assert waiting and not future.done()
            finally:
                connection.execute("COMMIT")
            future.result(timeout=10)
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-fresh", bundle_store.user_id)
    import_full_namespace_rehearsal(target, backup, confirm_quiesced=True)
    second = PostgresLearnerBundle(target.dsn, target.namespace, reviewed_batch[1][0])
    assert second.read()[0]["state"]["topic"] == "namespace writer committed"


def test_combined_backup_round_trip_to_fresh_namespace(bundle_store, controls_rehearsal, tmp_path):
    path, bundle, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    fence = {"account_epoch": "before", "learning_erasure_epoch": None,
             "adaptation_erasure": {"epoch": "a" * 32, "status": "complete"},
             "future_extension": {"preserve": True}}
    with database(bundle_store.dsn) as connection:
        connection.execute(
            "INSERT INTO public.mammoth_learner_operation_fences(namespace,user_id,operation_id,fence) "
            "VALUES(%s,%s,%s,%s::jsonb)",
            (bundle_store.namespace, bundle_store.user_id, "finished", json.dumps(fence)),
        )
    backup = tmp_path / "combined"
    with pytest.raises(ValueError, match="quiescence"):
        export_with_controls_rehearsal(bundle_store, backup)
    assert not backup.exists()
    marker = export_with_controls_rehearsal(bundle_store, backup, ["removed"], confirm_quiesced=True)
    assert marker["runtime_activation_supported"] is False
    assert verify_backup(backup / "learner", bundle_store.user_id)["accounts"] == ["default", "removed"]
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-restored", bundle_store.user_id)
    with pytest.raises(ValueError, match="quiescence"):
        import_combined_rehearsal(target, backup)
    assert import_combined_rehearsal(target, backup, confirm_quiesced=True) == 1
    assert target.read() == (bundle, 1)
    with database(target.dsn) as connection:
        owner = (target.namespace, target.user_id)
        assert connection.execute(
            "SELECT daily_limit FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s", owner
        ).fetchone() == (8,)
        assert connection.execute(
            "SELECT day::text,admitted FROM public.mammoth_learning_usage WHERE namespace=%s AND user_id=%s", owner
        ).fetchall() == [("2026-01-01", 3)]
        assert connection.execute(
            "SELECT id,status FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s", owner
        ).fetchall() == [("finished", "finished")]
        assert connection.execute(
            "SELECT operation_id,fence FROM public.mammoth_learner_operation_fences "
            "WHERE namespace=%s AND user_id=%s", owner
        ).fetchall() == [("finished", fence)]


@pytest.mark.parametrize("damage", ["missing", "unknown_operation", "duplicate", "not_object"])
def test_combined_restore_refuses_incomplete_or_invalid_fences(bundle_store, controls_rehearsal, tmp_path, damage):
    import hashlib
    path, _, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    backup = tmp_path / "combined"
    export_with_controls_rehearsal(bundle_store, backup, confirm_quiesced=True)
    controls_path = backup / "controls.json"
    controls = json.loads(controls_path.read_bytes())
    valid = {"operation_id": "finished", "fence": {"epoch": "preserve"}}
    if damage == "missing":
        del controls["fences"]
    elif damage == "unknown_operation":
        controls["fences"] = [{"operation_id": "unknown", "fence": {}}]
    elif damage == "duplicate":
        controls["fences"] = [valid, valid]
    else:
        controls["fences"] = [{"operation_id": "finished", "fence": []}]
    payload = json.dumps(controls).encode()
    controls_path.write_bytes(payload)
    marker_path = backup / "complete.json"
    marker = json.loads(marker_path.read_bytes())
    marker["controls_sha256"] = hashlib.sha256(payload).hexdigest()
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-restored", bundle_store.user_id)
    with pytest.raises(ValueError):
        import_combined_rehearsal(target, backup, confirm_quiesced=True)
    assert target.read()[1] == 0
    with database(target.dsn) as connection:
        for table in ("mammoth_learning_policy", "mammoth_learning_operations",
                      "mammoth_learner_operation_fences"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s AND user_id=%s",
                (target.namespace, target.user_id),
            ).fetchone() == (0,)


def test_combined_backup_round_trips_a_real_completed_operation_fence(bundle_store, controls_rehearsal, tmp_path):
    path, _, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    transactions = PostgresLearnerTransactions(bundle_store.dsn, bundle_store.namespace, bundle_store.user_id)
    controls = PostgresLearningControls(bundle_store.dsn, bundle_store.namespace, bundle_store.user_id)
    operation = transactions.begin_operation(revision=1, account="default", route="/fixture")
    controls.finish(operation, "finished")
    with database(bundle_store.dsn) as connection:
        before = connection.execute(
            "SELECT fence FROM public.mammoth_learner_operation_fences "
            "WHERE namespace=%s AND user_id=%s AND operation_id=%s",
            (bundle_store.namespace, bundle_store.user_id, operation),
        ).fetchone()[0]
    backup = tmp_path / "combined"
    export_with_controls_rehearsal(bundle_store, backup, confirm_quiesced=True)
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-restored", bundle_store.user_id)
    import_combined_rehearsal(target, backup, confirm_quiesced=True)
    with database(target.dsn) as connection:
        after = connection.execute(
            "SELECT fence FROM public.mammoth_learner_operation_fences "
            "WHERE namespace=%s AND user_id=%s AND operation_id=%s",
            (target.namespace, target.user_id, operation),
        ).fetchone()[0]
    assert after == before


def test_combined_restore_rolls_back_if_database_rejects_fence(bundle_store, controls_rehearsal, tmp_path):
    import hashlib

    path, _, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    backup = tmp_path / "combined"
    export_with_controls_rehearsal(bundle_store, backup, confirm_quiesced=True)
    controls_path = backup / "controls.json"
    controls = json.loads(controls_path.read_bytes())
    controls["fences"] = [{"operation_id": "finished", "fence": {"invalid_for_postgres": "\x00"}}]
    payload = json.dumps(controls).encode()
    controls_path.write_bytes(payload)
    marker_path = backup / "complete.json"
    marker = json.loads(marker_path.read_bytes())
    marker["controls_sha256"] = hashlib.sha256(payload).hexdigest()
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-restored", bundle_store.user_id)
    with pytest.raises(StateUnavailable):
        import_combined_rehearsal(target, backup, confirm_quiesced=True)
    assert target.read()[1] == 0
    with database(target.dsn) as connection:
        for table in ("mammoth_learning_policy", "mammoth_learning_usage",
                      "mammoth_learning_operations", "mammoth_learner_operation_fences"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s AND user_id=%s",
                (target.namespace, target.user_id),
            ).fetchone() == (0,)


def test_combined_export_snapshot_starts_after_waiting_for_prior_learner_writer(
        bundle_store, controls_rehearsal, tmp_path):
    path, bundle, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    target = tmp_path / "combined"
    with database(bundle_store.dsn) as connection:
        connection.execute("BEGIN")
        connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (migration_lock(bundle_store.namespace),))
        connection.execute(
            "UPDATE public.mammoth_learner_bundles SET state=jsonb_set(state,'{topic}',%s::jsonb),"
            "revision=revision+1 WHERE namespace=%s AND user_id=%s",
            ('"writer committed before export"', bundle_store.namespace, bundle_store.user_id),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(export_with_controls_rehearsal, bundle_store, target, confirm_quiesced=True)
            try:
                deadline = time.monotonic() + 4
                waiting = False
                while time.monotonic() < deadline:
                    connection.execute("SELECT pg_stat_clear_snapshot()")
                    waiting = connection.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event='advisory' AND query LIKE 'SELECT pg_advisory_lock%')"
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.05)
                assert waiting and not future.done()
            finally:
                connection.execute("COMMIT")
            future.result(timeout=10)
    restored = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-restored", bundle_store.user_id)
    import_combined_rehearsal(restored, target, confirm_quiesced=True)
    restored_bundle, _ = restored.read()
    assert restored_bundle["state"]["topic"] == "writer committed before export"
    assert restored_bundle["models"] == bundle["models"]


@pytest.mark.parametrize("damage", ["controls", "learner", "missing_marker", "wrong_owner"])
def test_combined_backup_rejects_tamper_and_incomplete_output(bundle_store, controls_rehearsal, tmp_path, damage):
    path, _, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    backup = tmp_path / "combined"
    export_with_controls_rehearsal(bundle_store, backup, confirm_quiesced=True)
    if damage == "controls":
        payload = backup / "controls.json"
        payload.write_bytes(payload.read_bytes() + b" ")
    elif damage == "learner":
        payload = backup / "learner" / "learner.json"
        payload.write_bytes(payload.read_bytes() + b" ")
    elif damage == "missing_marker":
        (backup / "complete.json").unlink()
    owner = "Other" if damage == "wrong_owner" else bundle_store.user_id
    target = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace + "-restored", owner)
    with pytest.raises(ValueError):
        import_combined_rehearsal(target, backup, confirm_quiesced=True)
    assert target.read()[1] == 0
    with database(target.dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s",
            (target.namespace, target.user_id),
        ).fetchone() == (0,)


def test_combined_export_refuses_unfinished_operations_without_output(bundle_store, controls_rehearsal, tmp_path):
    path, _, snapshot = controls_rehearsal
    import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    with database(bundle_store.dsn) as connection:
        connection.execute(
            "UPDATE public.mammoth_learning_operations SET status='running',finished_at=NULL "
            "WHERE namespace=%s AND user_id=%s",
            (bundle_store.namespace, bundle_store.user_id),
        )
    target = tmp_path / "combined"
    with pytest.raises(ValueError, match="Unfinished"):
        export_with_controls_rehearsal(bundle_store, target, confirm_quiesced=True)
    assert not target.exists()


def test_atomic_import_rolls_back_both_bundle_and_controls_on_database_failure(bundle_store, controls_rehearsal):
    path, _, snapshot = controls_rehearsal
    snapshot["learning_controls"]["operations"][0]["route"] = "\x00"
    with pytest.raises(StateUnavailable):
        import_with_controls_rehearsal(bundle_store, path, snapshot, confirm_quiesced=True)
    assert bundle_store.read()[1] == 0
    with database(bundle_store.dsn) as connection:
        owner = (bundle_store.namespace, bundle_store.user_id)
        for table in ("mammoth_learning_policy", "mammoth_learning_usage", "mammoth_learning_operations"):
            assert connection.execute(
                f"SELECT count(*) FROM public.{table} WHERE namespace=%s AND user_id=%s", owner
            ).fetchone() == (0,)


def test_import_rejects_wrong_owner_tamper_and_failed_transaction(bundle_store, tmp_path):
    bundle = {"state": {"active_account_id": "default"}, "drafts": {},
              "models": {"default": {"user_id": "workspace:default", "mastery": {},
                                     "note": "database rejects \x00"}}}
    path = tmp_path / "source"
    write_backup(path, bundle_store.user_id, bundle, ["default"])
    other = PostgresLearnerBundle(bundle_store.dsn, bundle_store.namespace, "Other")
    with pytest.raises(ValueError, match="owner"):
        import_backup(other, path, confirm_quiesced=True)
    with pytest.raises(StateUnavailable):
        import_backup(bundle_store, path, confirm_quiesced=True)
    assert bundle_store.read()[1] == 0
    payload = path / "learner.json"
    payload.write_bytes(payload.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        import_backup(bundle_store, path, confirm_quiesced=True)
    assert bundle_store.read()[1] == 0


def test_export_missing_or_invalid_bundle_creates_no_backup(bundle_store, tmp_path):
    path = tmp_path / "backup"
    with pytest.raises(ValueError, match="No learner bundle"):
        export_backup(bundle_store, path, confirm_quiesced=True)
    assert not path.exists()
    bundle_store.write(sample_bundle(), revision=0)
    with pytest.raises(ValueError, match="invalid draft or model"):
        export_backup(bundle_store, path, confirm_quiesced=True)
    assert not path.exists()


def test_experimental_cli_requires_explicit_test_only_confirmation(bundle_store, tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "MAMMOTH_POSTGRES_DSN": bundle_store.dsn}
    path = tmp_path / "source"
    bundle = {"state": {"active_account_id": "default"}, "drafts": {}, "models": {}}
    write_backup(path, bundle_store.user_id, bundle, ["default"])
    args = [sys.executable, "-m", "scripts.migrate_learner_bundle", "import",
            "--user-id", bundle_store.user_id, "--namespace", bundle_store.namespace,
            "--backup", str(path), "--confirm-quiesced"]
    rejected = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert rejected.returncode != 0 and "--confirm-test-only" in rejected.stderr
    assert bundle_store.read()[1] == 0
    accepted = subprocess.run(args + ["--confirm-test-only"], cwd=root, env=env,
                              capture_output=True, text=True, timeout=30)
    assert accepted.returncode == 0, accepted.stderr
    assert bundle_store.read() == (bundle, 1)
