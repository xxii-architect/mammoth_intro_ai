import asyncio
from datetime import datetime, timedelta, timezone
import subprocess
import sys

import pytest

import api_server
from mammoth_os.agent_loop import AgentRun, AgentRunner, RunStore, ToolContext, ToolRegistry
from mammoth_os.agent_registry import AgentManifest, AgentStatus, observed_agent_health
from mammoth_os.llm_client import FallbackAdapter
from mammoth_os.llm_completion import Completion, complete
from mammoth_os.runtime_ledger import RuntimeLedger, RuntimeLimitReached, ledger_context


def test_stale_writes_rejected_and_saved_evidence_survives_restart(tmp_path):
    store = RunStore(tmp_path, keep_per_user=1)
    run = AgentRun(AgentRun.new_id(), "alice", "hello")
    store.save(run)
    stale = RunStore(tmp_path).get(run.id, "alice")
    run.reply = "new evidence"
    store.save(run)
    stale.reply = "lost update"
    with pytest.raises(ValueError, match="changed"):
        RunStore(tmp_path).save(stale)
    assert RunStore(tmp_path).get(run.id, "alice").reply == "new evidence"
    assert RunStore(tmp_path).get(run.id, "bob") is None
    store.save(AgentRun(AgentRun.new_id(), "alice", "new run"))
    assert store.get(run.id, "alice") is not None  # Active work is never evicted.
    path = store._user_dir("alice") / f"{run.id}.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        store.get(run.id, "alice")


def test_retention_never_deletes_a_still_leased_terminal_run(tmp_path):
    store = RunStore(tmp_path, keep_per_user=1)
    run = AgentRun(AgentRun.new_id(), "alice", "finished", status="completed")
    store.save(run)
    lease = store.reserve(run)
    try:
        store.save(AgentRun(AgentRun.new_id(), "alice", "newer"))
        assert store.get(run.id, "alice") is not None
    finally:
        lease.close()
    store.save(AgentRun(AgentRun.new_id(), "alice", "newest"))
    assert store.get(run.id, "alice") is None


def test_discovery_does_not_forge_heartbeats(monkeypatch):
    import mammoth_os.agent_registry as registry

    fresh = registry.AgentRegistry()
    monkeypatch.setattr(registry, "agent_registry", fresh)
    registry._auto_register_agents()
    assert fresh._agents
    assert all(manifest.last_heartbeat is None for manifest in fresh._agents.values())
    assert all(observed_agent_health(manifest)["status"] == "not_verified" for manifest in fresh._agents.values())


def test_process_exit_releases_run_lease_and_cancellation_is_durable(tmp_path):
    store = RunStore(tmp_path)
    run = AgentRun(AgentRun.new_id(), "alice", "hello")
    store.save(run)
    code = """
import sys
from pathlib import Path
from mammoth_os.agent_loop import RunStore
store = RunStore(Path(sys.argv[1]))
run = store.get(sys.argv[2], 'alice')
lease = store.reserve(run)
print('leased', flush=True)
input()
"""
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path), run.id],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "leased"
        with pytest.raises(ValueError, match="active"):
            RunStore(tmp_path).reserve(run)
    finally:
        child.terminate()
        child.wait(timeout=10)
        child.stdin.close()
        child.stdout.close()
    lease = RunStore(tmp_path).reserve(run)
    lease.close()
    runner = AgentRunner(ToolRegistry(), lambda: None, store)
    runner.cancel(run)
    loaded = RunStore(tmp_path).get(run.id, "alice")
    assert not loaded.cancel_requested
    assert runner._cancel_requested(loaded)


def test_concurrent_process_token_admission_is_atomic(tmp_path):
    path = tmp_path / "usage.sqlite3"
    RuntimeLedger(path).set_limit(100)
    code = """
import sys
from pathlib import Path
from mammoth_os.runtime_ledger import RuntimeLedger, RuntimeLimitReached
try:
    RuntimeLedger(Path(sys.argv[1])).reserve('scripted', 'model', 100)
    print('admitted')
except RuntimeLimitReached:
    print('blocked')
"""
    children = [subprocess.Popen([sys.executable, "-c", code, str(path)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True) for _ in range(4)]
    results = [child.communicate(timeout=30) for child in children]
    assert all(child.returncode == 0 for child in children), results
    assert sorted(stdout.strip() for stdout, _ in results) == ["admitted", "blocked", "blocked", "blocked"]
    snapshot = RuntimeLedger(path).snapshot()
    assert snapshot["unresolved_reserved_tokens"] == snapshot["admission_tokens"] == 100
    assert snapshot["accounting_status"] == "incomplete"
    with pytest.raises(RuntimeLimitReached):
        RuntimeLedger(path).reserve("scripted", "model", 1)


def test_leaf_attempts_fallback_unknown_usage_and_zero_ceiling(tmp_path):
    ledger = RuntimeLedger(tmp_path / "usage.sqlite3")

    class Broken:
        async def generate(self, prompt, **kwargs):
            raise RuntimeError("429")

    class Good:
        async def generate_completion(self, prompt, **kwargs):
            assert kwargs["max_tokens"] == 100
            return Completion("answer", usage={"total_tokens": 15})

    async def work():
        with ledger_context(ledger):
            result = await complete(FallbackAdapter(Broken(), Good()), "hello", max_tokens=100)
            assert result.text == "answer"
            snapshot = ledger.snapshot()
            assert snapshot["attempts"] == 2  # Wrappers must not double count.
            assert snapshot["reported_tokens"] == 15
            assert snapshot["unknown_attempts"] == 1
            assert snapshot["unresolved_reserved_tokens"] > 100
            ledger.set_limit(0)
            with pytest.raises(RuntimeLimitReached):
                await complete(Good(), "blocked")
            assert ledger.snapshot()["attempts"] == 2
    asyncio.run(work())
    assert ledger.snapshot()["currency_spend"] is None
    assert RuntimeLedger(tmp_path / "other-user.sqlite3").snapshot()["attempts"] == 0


def test_reported_usage_finalization_and_stale_health(tmp_path):
    ledger = RuntimeLedger(tmp_path / "usage.sqlite3")
    identity = ledger.reserve("openai", "model", 100)
    ledger.finish(identity, usage={"total_tokens": 150})
    snapshot = ledger.snapshot()
    assert snapshot["admission_tokens"] == snapshot["reported_tokens"] == 150
    assert snapshot["providers"][0]["health"] == "available"
    with pytest.raises(ValueError, match="finalized"):
        ledger.finish(identity, usage={"total_tokens": 1})
    with ledger._db() as db:
        db.execute("UPDATE attempts SET finished_at=?", ((datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat(),))
    assert ledger.snapshot()["providers"][0]["health"] == "stale"
    for bad in (True, -1, 0.1, "100", 100_000_001):
        with pytest.raises(ValueError):
            ledger.set_limit(bad)


def test_direct_standard_adapter_generation_is_metered_once(monkeypatch, tmp_path):
    from mammoth_os.openai_adapter import OpenAIAdapter
    from mammoth_os.ollama_adapter import OllamaAdapter

    calls = []

    async def scripted(self, prompt, **kwargs):
        calls.append(kwargs)
        return Completion("answer", usage={"total_tokens": 10})

    monkeypatch.setattr(OpenAIAdapter, "generate_completion", scripted)
    monkeypatch.setattr(OllamaAdapter, "generate_completion", scripted)
    ledger = RuntimeLedger(tmp_path / "usage.sqlite3")

    async def work():
        with ledger_context(ledger):
            for adapter in (OpenAIAdapter({"model": "scripted"}), OllamaAdapter({"model": "scripted"})):
                assert await adapter.generate("direct") == "answer"
                assert (await complete(adapter, "structured")).text == "answer"
            ledger.set_limit(0)
            with pytest.raises(RuntimeLimitReached):
                await OpenAIAdapter({"model": "scripted"}).generate("blocked")
    asyncio.run(work())
    assert len(calls) == ledger.snapshot()["attempts"] == 4
    assert ledger.snapshot()["reported_tokens"] == 40


def test_killed_model_worker_retains_checkpoint_and_never_auto_replays(monkeypatch, tmp_path):
    store = RunStore(tmp_path)
    run = AgentRun(AgentRun.new_id(), "alice", "hello")
    store.save(run)
    code = """
import asyncio, sys
from pathlib import Path
from mammoth_os.agent_loop import AgentRunner, RunStore, ToolContext, ToolRegistry
class Blocked:
    async def generate(self, prompt, **kwargs):
        print('model-started', flush=True)
        await asyncio.sleep(120)
store = RunStore(Path(sys.argv[1]))
run = store.get(sys.argv[2], 'alice')
lease = store.reserve(run)
async def work():
    async for event in AgentRunner(ToolRegistry(), Blocked, store).start(run, ToolContext(user_id='alice')):
        pass
asyncio.run(work())
"""
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path), run.id],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "model-started"
    finally:
        child.terminate()
        child.wait(timeout=10)
        child.stdout.close()
        child.stderr.close()
    saved = RunStore(tmp_path).get(run.id, "alice")
    assert saved.inflight_activity == "model" and saved.status == "running"
    monkeypatch.setattr(api_server, "_AGENT_RUNS", RunStore(tmp_path))
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda: "alice")
    recovered = asyncio.run(api_server.mammoth_agent_run_get(run.id))["run"]
    assert recovered["status"] == "failed"
    assert recovered["failure_code"] == "run_interrupted"
    assert not recovered["can_continue"]
    assert [event["type"] for event in recovered["events"]] == ["run.started", "run.failed"]


def test_configuration_is_not_observed_provider_or_agent_health(monkeypatch, tmp_path):
    ledger = RuntimeLedger(tmp_path / "usage.sqlite3")
    monkeypatch.setattr(api_server, "_runtime_ledger", lambda: ledger)
    monkeypatch.setattr(api_server, "_models_snapshot", lambda: {
        "active_adapter": "openai", "active_model": "model", "openai_key_present": True, "deepseek_key_present": True,
    })
    snapshot = api_server._runtime_status_snapshot()
    assert snapshot["state"] == "not_verified"
    assert all(not item["available"] for item in snapshot["providers"] if item["provider"] in {"openai", "deepseek"})
    api_server._remember_runtime_status({"state": "ready", "active_adapter": "openai", "used_provider": "openai"})
    merged = api_server._merge_latest_runtime_status(snapshot)
    assert merged["state"] == "not_verified"
    assert merged["active_provider"] is None
    assert not any(provider["active"] for provider in merged["providers"])
    identity = ledger.reserve("openai", "model", 100)
    ledger.finish(identity, usage={"total_tokens": 25})
    assert api_server._runtime_status_snapshot()["state"] == "ready"
    manifest = AgentManifest("agent", "Agent", "1", [], AgentStatus.IDLE, 1, [], "internal://agent")
    assert manifest.last_heartbeat is None
    assert observed_agent_health(manifest)["status"] == "not_verified"
    manifest.metadata["health_observation"] = {
        "status": "available", "source": "heartbeat",
        "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat(),
    }
    assert observed_agent_health(manifest)["status"] == "stale"
    monkeypatch.setattr(api_server, "_models_snapshot", lambda: {
        "active_adapter": "openai", "active_model": "different", "openai_key_present": True,
    })
    assert api_server._runtime_status_snapshot()["state"] == "not_verified"


def test_loaded_approval_route_claims_once_and_never_replays(monkeypatch, tmp_path):
    store = RunStore(tmp_path)
    run = AgentRun(AgentRun.new_id(), "alice", "hello", status="awaiting_approval",
                   pending_approval={"id": "approval-one", "tool": "missing", "args": {}})
    store.save(run)
    monkeypatch.setattr(api_server, "_AGENT_RUNS", store)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda: "alice")
    monkeypatch.setattr(api_server, "_agent_tool_context", lambda _: (ToolContext(user_id="alice"), None))
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(api_server, "_runtime_ledger", lambda *args: RuntimeLedger(tmp_path / "ledger.sqlite3"))
    runner = AgentRunner(ToolRegistry(), lambda: None, store)
    monkeypatch.setattr(api_server, "_AGENT_RUNNER", runner)

    async def work():
        body = {"decision": "reject", "approval_id": "approval-one"}
        first = await api_server.mammoth_agent_run_approval(run.id, body)
        second = await api_server.mammoth_agent_run_approval(run.id, body)
        assert second.status_code == 409
        # Consume only through the durable approval transition, then disconnect.
        iterator = first.body_iterator
        assert "approval.resolved" in await anext(iterator)
        await iterator.aclose()
        saved = RunStore(tmp_path).get(run.id, "alice")
        assert saved.pending_approval is None
        third = await api_server.mammoth_agent_run_approval(run.id, body)
        assert third.status_code == 409
        recovered = await api_server.mammoth_agent_run_get(run.id)
        assert recovered["run"]["failure_code"] == "run_interrupted"
        assert recovered["run"]["can_continue"] is False
    asyncio.run(work())


def test_cancel_after_pause_stream_closes_is_reconciled_without_execution(monkeypatch, tmp_path):
    store = RunStore(tmp_path)
    run = AgentRun(AgentRun.new_id(), "alice", "hello", status="awaiting_approval",
                   pending_approval={"id": "approval-one"})
    store.save(run)
    runner = AgentRunner(ToolRegistry(), lambda: None, store)
    monkeypatch.setattr(api_server, "_AGENT_RUNS", store)
    monkeypatch.setattr(api_server, "_AGENT_RUNNER", runner)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda: "alice")
    lease = store.reserve(run)
    try:
        cancelled = asyncio.run(api_server.mammoth_agent_run_cancel(run.id))
        assert cancelled["cancel_requested"]
    finally:
        lease.close()
    recovered = asyncio.run(api_server.mammoth_agent_run_get(run.id))["run"]
    assert recovered["status"] == "cancelled"
    assert recovered["pending_approval"] is None
    assert recovered["events"][-1]["type"] == "run.cancelled"


def test_usage_routes_scoped_and_invalid_policy_is_explicit(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path)
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {"id": token, "email": "", "is_admin": False})
    with TestClient(api_server.app) as client:
        alice = {"Authorization": "Bearer alice"}
        bob = {"Authorization": "Bearer bob"}
        assert client.get("/api/runtime/usage").status_code == 401
        assert client.put("/api/runtime/usage/policy", headers=alice, json={"daily_token_limit": 0}).json()["daily_token_limit"] == 0
        assert client.get("/api/runtime/usage", headers=bob).json()["daily_token_limit"] is None
        assert client.put("/api/runtime/usage/policy", headers=alice, json={}).status_code == 400
        assert client.put("/api/runtime/usage/policy", headers=alice, json={"daily_token_limit": True}).status_code == 400
