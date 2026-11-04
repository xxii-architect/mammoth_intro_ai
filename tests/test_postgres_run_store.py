import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys
import uuid

import pytest

from mammoth_os.agent_loop import AgentRun, AgentRunner, ToolContext, ToolRegistry
from mammoth_os.agent_loop.lease import RunBusyError
from mammoth_os.agent_loop.postgres_store import PostgresRunStore, configured_run_store
from mammoth_os.shared_state import StateUnavailable
from test_shared_state_admission import postgres as postgres_fixture

postgres = postgres_fixture


@pytest.fixture
def stores(postgres):
    port = subprocess.run(
        ["docker", "port", postgres.container, "5432/tcp"],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip()
    assert port.startswith("127.0.0.1:"), "The dedicated test database must bind only loopback."
    dsn = f"postgresql://postgres:fixture-only@{port}/{postgres.database}"
    namespace = "runs-" + uuid.uuid4().hex
    return PostgresRunStore(dsn, namespace, keep_per_user=1), PostgresRunStore(dsn, namespace, keep_per_user=1)


def test_postgres_runs_are_owner_scoped_revision_checked_and_cancelled_across_replicas(stores):
    first, second = stores
    run = AgentRun(AgentRun.new_id(), "alice", "fixture")
    first.save(run)
    stale = second.get(run.id, "alice")
    assert second.get(run.id, "bob") is None
    assert PostgresRunStore(first.dsn, "other-namespace").get(run.id, "alice") is None
    lease = first.reserve(run)
    try:
        with pytest.raises(RunBusyError):
            second.reserve(stale)
        with pytest.raises(RunBusyError):
            second.save(stale)
        second.request_cancel(stale)
        assert first.cancellation_requested(run)
        run.reply = "saved under the original lease"
        first.save(run)
        assert second.get(run.id, "alice").cancel_requested is True
    finally:
        lease.close()
    with pytest.raises(ValueError, match="changed"):
        second.save(stale)
    loaded = second.get(run.id, "alice")
    assert loaded.reply == run.reply and loaded.storage_revision == run.storage_revision
    assert second.list("bob") == []
    assert second.list("alice")[0]["id"] == run.id
    with pytest.raises(StateUnavailable, match="no local directory"):
        first._user_dir("alice")


def test_postgres_lost_lease_cannot_reconnect_or_publish_a_late_checkpoint(stores):
    first, second = stores
    run = AgentRun(AgentRun.new_id(), "alice", "fixture")
    lease = first.reserve(run)
    first.save(run)
    run.inflight_activity = "tool"
    first.save(run)
    # Simulate the session being severed during an unknown external action.
    lease.connection.close()
    recovered = second.get(run.id, "alice")
    recovery_lease = second.reserve(recovered)
    try:
        recovered.status, recovered.failure_code = "failed", "run_interrupted"
        second.save(recovered)
        run.reply = "must not overwrite recovery"
        with pytest.raises(StateUnavailable, match="lost"):
            first.save(run)
    finally:
        lease.close()
        recovery_lease.close()
    assert second.get(run.id, "alice").status == "failed"
    assert second.get(run.id, "alice").inflight_activity == "tool"


def test_postgres_killed_worker_releases_session_lease_without_replaying_work(stores):
    first, second = stores
    run = AgentRun(AgentRun.new_id(), "alice", "fixture")
    first.save(run)
    code = """
import os
from mammoth_os.agent_loop.postgres_store import PostgresRunStore
store=PostgresRunStore(os.environ['FIXTURE_DSN'],os.environ['FIXTURE_NAMESPACE'])
run=store.get(os.environ['FIXTURE_RUN'],'alice')
lease=store.reserve(run)
run.inflight_activity='model'
store.save(run)
print('leased',flush=True)
input()
"""
    environment = {**os.environ, "FIXTURE_DSN": first.dsn, "FIXTURE_NAMESPACE": first.namespace, "FIXTURE_RUN": run.id}
    child = subprocess.Popen([sys.executable, "-c", code], env=environment, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "leased"
        with pytest.raises(RunBusyError):
            second.reserve(second.get(run.id, "alice"))
    finally:
        child.terminate()
        child.wait(timeout=15)
        child.stdin.close()
        child.stdout.close()
        child.stderr.close()
    recovered = second.get(run.id, "alice")
    lease = second.reserve(recovered)
    try:
        assert recovered.inflight_activity == "model" and recovered.status == "running"
    finally:
        lease.close()


def test_postgres_parallel_run_claims_have_exactly_one_owner(stores):
    first, _ = stores
    run = AgentRun(AgentRun.new_id(), "alice", "fixture")
    first.save(run)
    leases = []

    def claim(_):
        store = PostgresRunStore(first.dsn, first.namespace)
        try:
            lease = store.reserve(store.get(run.id, "alice"))
            leases.append(lease)
            return True
        except RunBusyError:
            return False

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert sum(pool.map(claim, range(16))) == 1
    finally:
        for lease in leases:
            lease.close()


def test_postgres_retention_keeps_active_approval_and_leased_terminal_runs(stores):
    first, second = stores
    active = AgentRun(AgentRun.new_id(), "alice", "active")
    approval = AgentRun(AgentRun.new_id(), "alice", "approval", status="awaiting_approval")
    finished = AgentRun(AgentRun.new_id(), "alice", "finished", status="completed")
    for run in (active, approval, finished):
        first.save(run)
    lease = second.reserve(second.get(finished.id, "alice"))
    try:
        first.save(AgentRun(AgentRun.new_id(), "alice", "new"))
        assert first.get(finished.id, "alice") is not None
    finally:
        lease.close()
    first.save(AgentRun(AgentRun.new_id(), "alice", "newest"))
    assert first.get(finished.id, "alice") is None
    assert first.get(active.id, "alice") is not None
    assert first.get(approval.id, "alice") is not None
    with pytest.raises(ValueError, match="removed"):
        first.save(finished)


def test_loaded_ordinary_and_recursive_routes_recover_postgres_state_without_disk(stores, monkeypatch):
    import api_server
    from mammoth_os.recursive.runtime import RecursiveRuntime

    first, second = stores
    monkeypatch.setattr(api_server, "_AGENT_RUNS", second)
    runner = AgentRunner(ToolRegistry(), lambda: None, second)
    monkeypatch.setattr(api_server, "_AGENT_RUNNER", runner)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda: "alice")
    monkeypatch.setattr(api_server, "_agent_tool_context", lambda _: (ToolContext(user_id="alice"), None))

    ordinary = AgentRun(AgentRun.new_id(), "alice", "fixture", inflight_activity="tool")
    first.save(ordinary)
    result = asyncio.run(api_server.mammoth_agent_run_get(ordinary.id))["run"]
    assert result["failure_code"] == "run_interrupted" and not result["can_continue"]
    recursive = AgentRun(AgentRun.new_id(), "alice", "fixture", recursive={
        "reservation": 100, "usage": {}, "limits": {},
    })
    first.save(recursive)
    result = asyncio.run(api_server.mammoth_agent_run_get(recursive.id))["run"]
    assert result["failure_code"] == "recursive_outcome_unknown" and not result["can_continue"]
    cancellation = AgentRun(AgentRun.new_id(), "alice", "fixture", recursive={"reservation": 1})
    first.save(cancellation)
    runtime = RecursiveRuntime(AgentRunner(ToolRegistry(), lambda: None, first), cancellation, None)
    lease = runtime.reserve()
    try:
        asyncio.run(api_server.mammoth_agent_run_cancel(cancellation.id))
        assert runtime.is_cancelled()
    finally:
        lease.close()
    result = asyncio.run(api_server.mammoth_agent_run_get(cancellation.id))["run"]
    assert result["failure_code"] == "recursive_outcome_unknown"  # No replay even when cancellation is requested.


def test_postgres_run_configuration_is_opt_in_and_never_uses_transaction_pooling(monkeypatch, tmp_path):
    monkeypatch.setenv("MAMMOTH_RUN_BACKEND", "postgres")
    monkeypatch.delenv("MAMMOTH_POSTGRES_SESSION_MODE", raising=False)
    with pytest.raises(StateUnavailable, match="direct/session"):
        configured_run_store(tmp_path)
    monkeypatch.setenv("MAMMOTH_POSTGRES_SESSION_MODE", "transaction")
    with pytest.raises(StateUnavailable):
        configured_run_store(tmp_path)


def test_postgres_run_tables_deny_public_clients(postgres):
    for role in ("anon", "authenticated"):
        for table in ("mammoth_agent_runs", "mammoth_private_runtime_policy", "mammoth_private_runtime_attempts"):
            result = postgres(f"SET ROLE {role}; SELECT * FROM public.{table}", check=False)
            assert result.returncode != 0 and "permission denied" in result.stderr


def test_postgres_private_ledger_is_shared_atomic_and_preserves_wire_shape(stores):
    from mammoth_os.postgres_ledger import PostgresRuntimeLedger
    from mammoth_os.runtime_ledger import RuntimeLimitReached

    store, _ = stores
    first = PostgresRuntimeLedger(store.dsn, store.namespace, "alice")
    second = PostgresRuntimeLedger(store.dsn, store.namespace, "alice")
    other = PostgresRuntimeLedger(store.dsn, store.namespace, "bob")
    first.set_limit(30)

    def reserve(_):
        try:
            return second.reserve("fixture", "model", 10)
        except RuntimeLimitReached:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        identities = [item for item in pool.map(reserve, range(16)) if item]
    assert len(identities) == 3
    assert first.snapshot()["admission_tokens"] == 30
    assert first.snapshot()["unknown_attempts"] == 3
    assert other.snapshot()["attempts"] == 0
    second.finish(identities[0], usage={"total_tokens": 2})
    first.finish(identities[1], failed=True)
    assert second.snapshot()["reported_tokens"] == 2
    assert second.snapshot()["unresolved_reserved_tokens"] == 20
    second.abandon_unstarted(identities[2])
    assert first.snapshot()["admission_tokens"] == 12
    with pytest.raises(ValueError):
        first.finish(identities[0], usage={"total_tokens": 2})
    first.set_limit(0)
    with pytest.raises(RuntimeLimitReached):
        second.reserve("fixture", "model", 1)
    snapshot = second.snapshot()
    assert snapshot["daily_token_limit"] == 0 and snapshot["invoice_verified"] is False
    assert snapshot["providers"][0]["source"] == "completion_attempt"


def test_postgres_private_overrun_unknowns_and_definitively_rejected_tenant_admission(stores):
    from mammoth_os.postgres_ledger import PostgresRuntimeLedger
    from mammoth_os.runtime_ledger import RuntimeLimitReached
    from mammoth_os.tenant_admission import CombinedLedger

    store, _ = stores
    ledger = PostgresRuntimeLedger(store.dsn, store.namespace, "alice")
    ledger.set_limit(10)
    identity = ledger.reserve("fixture", "model", 10)
    ledger.finish(identity, usage={"total_tokens": 20})
    assert ledger.snapshot()["admission_tokens"] == 20
    with pytest.raises(RuntimeLimitReached):
        ledger.reserve("fixture", "model", 1)
    with pytest.raises(ValueError):
        ledger.abandon_unstarted(identity)
    unrelated = PostgresRuntimeLedger(store.dsn, store.namespace + "-other", "alice")
    assert unrelated.snapshot()["attempts"] == 0
    with pytest.raises(ValueError):
        unrelated.finish(identity, usage={"total_tokens": 0})

    class RejectingTenant:
        def reserve(self, *args, **kwargs):
            raise RuntimeLimitReached("Tenant admission definitively rejected.")

    ledger.set_limit(None)
    with pytest.raises(RuntimeLimitReached):
        CombinedLedger(ledger, RejectingTenant()).reserve("fixture", "model", 10)
    assert ledger.snapshot()["attempts"] == 1
    unknown = ledger.reserve("fixture", "model", 11)
    ledger.finish(unknown, usage={"invalid": 2})
    assert ledger.snapshot()["unresolved_reserved_tokens"] == 11


def test_missing_postgres_driver_is_explicit_and_never_uses_local_storage(monkeypatch, tmp_path):
    from mammoth_os.postgres_ledger import PostgresRuntimeLedger

    monkeypatch.setitem(sys.modules, "psycopg", None)
    store = PostgresRunStore("fixture-unavailable", "fixture")
    run = AgentRun(AgentRun.new_id(), "alice", "fixture")
    for action in (lambda: store.save(run), lambda: store.reserve(run),
                   lambda: PostgresRuntimeLedger("fixture-unavailable", "fixture", "alice").snapshot()):
        with pytest.raises(StateUnavailable, match="package extra"):
            action()
    assert list(tmp_path.iterdir()) == []


def test_runtime_storage_migration_preserves_runs_usage_cancellation_and_rollback(stores, tmp_path):
    import runpy
    from pathlib import Path

    from mammoth_os.agent_loop.runner import RunStore
    from mammoth_os.runtime_ledger import RuntimeLedger

    migration = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "migrate_runtime_storage.py"))
    store, _ = stores
    source = RunStore(tmp_path / "source-runs")
    run = AgentRun(id="run-0123456789abcdef", user_id="alice", message="preserve approved work")
    source.save(run)
    source.request_cancel(run)
    ledger_path = tmp_path / "source.sqlite3"
    ledger = RuntimeLedger(ledger_path)
    ledger.set_limit(100)
    pending = ledger.reserve("fixture", "model", 30)
    known = ledger.reserve("fixture", "model", 20)
    ledger.finish(known, usage={"total_tokens": 7})
    snapshot = migration["local_snapshot"]("alice", source._user_dir("alice"), ledger_path)
    migration["import_snapshot"](store.dsn, store.namespace, "alice", snapshot)
    assert store.get(run.id, "alice").message == run.message
    assert store.cancellation_requested(run)
    exported = migration["export_snapshot"](store.dsn, store.namespace, "alice")
    assert exported == snapshot
    with pytest.raises(ValueError, match="already has state"):
        migration["import_snapshot"](store.dsn, store.namespace, "alice", snapshot)
    with pytest.raises(ValueError, match="owner"):
        migration["import_snapshot"](store.dsn, store.namespace, "bob", snapshot)
    backup = tmp_path / "backup.json"
    migration["write_backup"](backup, exported)
    with pytest.raises(FileExistsError):
        migration["write_backup"](backup, exported)
    restored_runs, restored_ledger = tmp_path / "restored-runs", tmp_path / "restored.sqlite3"
    migration["restore_local"]("alice", restored_runs, restored_ledger, exported)
    assert migration["local_snapshot"]("alice", restored_runs, restored_ledger) == snapshot
    restored = RuntimeLedger(restored_ledger)
    assert restored.snapshot()["admission_tokens"] == 37
    restored.finish(pending, failed=True)
    assert restored.snapshot()["unresolved_reserved_tokens"] == 30
    with pytest.raises(ValueError, match="never overwritten"):
        migration["restore_local"]("alice", restored_runs, restored_ledger, exported)
