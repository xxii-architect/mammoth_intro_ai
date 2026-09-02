"""Wave 3 agent upgrade regression tests."""
import asyncio
import pytest

from mammoth_os.agents.planner_agent import PlannerAgent
from mammoth_os.agents.auth_agent import AuthAgent
from mammoth_os.agents.build_agent import BuildAgent
from mammoth_os.agents.executor_agent import ExecutorAgent
from mammoth_os.agents.filesystem_agent import FileSystemAgent
from mammoth_os.agents.deploy_agent import DeployAgent
from mammoth_os.agents.database_agent import DatabaseAgent
from mammoth_os.agents.vector_store_agent import VectorStoreAgent
from mammoth_os.agents.scheduler_agent import SchedulerAgent
from mammoth_os.agents.snapshot_agent import SnapshotAgent
from mammoth_os.agents.config_manager_agent import ConfigManagerAgent
from mammoth_os.rag_context_store import get_rag_context_store, RAGContextStore
from mammoth_os.audit_engine import get_audit_engine, AuditEngine
import api_server


def test_planner_agent_run():
    result = asyncio.run(PlannerAgent().run({"goal": "Learn Python basics"}))
    assert result["status"] == "ok"
    assert "plan" in result
    assert "valid" in result
    assert "quality_flags" in result


def test_auth_agent_status():
    result = asyncio.run(AuthAgent().run({"action": "status"}))
    assert result["status"] == "ok"
    assert "algorithm" in result


def test_auth_agent_token_roundtrip():
    agent = AuthAgent()
    token_result = asyncio.run(agent.run({"action": "issue", "user_id": "u123", "scopes": ["read", "write"]}))
    assert token_result["status"] == "ok"


def test_build_agent_invalid_path():
    result = asyncio.run(BuildAgent().run({"project_path": "/nonexistent/path/xyz"}))
    assert result["status"] == "error"


def test_executor_agent_run_python():
    result = asyncio.run(ExecutorAgent().run({"code": "print('hello')", "language": "python", "timeout_sec": 5}))
    assert result["status"] == "ok"
    assert "hello" in result["stdout"]


def test_executor_agent_unsupported_lang():
    result = asyncio.run(ExecutorAgent().run({"code": "x", "language": "cobol"}))
    assert result["status"] == "error"
    assert "Unsupported" in result["stderr"]


def test_filesystem_agent_status():
    import os
    import tempfile
    tmp = tempfile.mkdtemp()
    result = asyncio.run(FileSystemAgent(base_path=tmp).run({}))
    assert result["status"] == "ok"
    assert "base_path" in result


def test_filesystem_agent_path_traversal_blocked():
    import tempfile
    tmp = tempfile.mkdtemp()
    agent = FileSystemAgent(base_path=tmp)
    result = asyncio.run(agent.run({"op": "read", "path": "../../etc/passwd"}))
    assert result["status"] == "error"


def test_deploy_agent_status():
    result = asyncio.run(DeployAgent().run({}))
    assert result["status"] == "ok"
    assert "quality_flags" in result


def test_database_agent_status():
    result = asyncio.run(DatabaseAgent().run({}))
    assert result["status"] == "ok"
    assert result["backend"] == "memory"


def test_vector_store_agent_upsert_and_search():
    agent = VectorStoreAgent()
    vec = [0.1, 0.2, 0.3, 0.4, 0.5]
    upsert_result = asyncio.run(agent.run({"action": "upsert", "collection": "test", "doc_id": "d1", "vector": vec, "metadata": {"label": "a"}}))
    assert upsert_result["status"] == "ok"
    search_result = asyncio.run(agent.run({"action": "search", "collection": "test", "query_vector": vec, "top_k": 3}))
    assert search_result["status"] == "ok"
    assert len(search_result["results"]) >= 1


def test_vector_store_agent_privacy_scoping():
    agent = VectorStoreAgent()
    vec = [0.5, 0.5]
    asyncio.run(agent.run({"action": "upsert", "collection": "notes", "doc_id": "n1", "vector": vec, "user_id": "user_a"}))
    asyncio.run(agent.run({"action": "upsert", "collection": "notes", "doc_id": "n2", "vector": vec, "user_id": "user_b"}))
    results_a = asyncio.run(agent.run({"action": "search", "collection": "notes", "query_vector": vec, "user_id": "user_a"}))
    assert all(r.get("user_id") == "user_a" for r in results_a["results"])


def test_scheduler_agent_schedule_and_list():
    agent = SchedulerAgent()
    result = asyncio.run(agent.run({"action": "schedule", "job_id": "job1", "cron": "0 * * * *", "task": {"agent": "tutor", "prompt": "review"}}))
    assert result["status"] == "ok"
    list_result = asyncio.run(agent.run({"action": "list"}))
    assert list_result["status"] == "ok"
    assert any(j["job_id"] == "job1" for j in list_result["jobs"])


def test_snapshot_agent_create_and_list():
    agent = SnapshotAgent()
    result = asyncio.run(agent.run({"action": "create", "label": "test-snap"}))
    assert result["status"] == "ok"
    list_result = asyncio.run(agent.run({"action": "list"}))
    assert list_result["count"] >= 1


def test_config_manager_set_and_get():
    agent = ConfigManagerAgent()
    asyncio.run(agent.run({"action": "set", "scope": "test_scope", "key": "my_key", "value": "my_value"}))
    result = asyncio.run(agent.run({"action": "get", "scope": "test_scope", "key": "my_key"}))
    assert result["value"] == "my_value"


def test_rag_context_store_privacy_isolation():
    store = RAGContextStore()
    store.store("user_a", "Python", "lesson_summary", "Python is great", "tutor")
    store.store("user_b", "Python", "lesson_summary", "Python rocks", "tutor")
    results_a = store.retrieve("user_a", topic="Python")
    results_b = store.retrieve("user_b", topic="Python")
    assert all(r["user_id"] == "user_a" for r in results_a)
    assert all(r["user_id"] == "user_b" for r in results_b)
    assert results_a[0]["content"] != results_b[0]["content"]


def test_rag_context_store_expiry():
    store = RAGContextStore()
    store.store("user_x", "topic", "summary", "content", "agent", ttl_hours=0)
    # TTL=0 means expires immediately
    results = store.retrieve("user_x", topic="topic")
    assert len(results) == 0


def test_rag_context_store_gdpr_wipe():
    store = RAGContextStore()
    store.store("user_del", "topic", "summary", "data", "agent")
    count = store.delete_user_data("user_del")
    assert count >= 1
    assert store.retrieve("user_del") == []


def test_audit_engine_record_and_query():
    engine = AuditEngine()
    engine.record("TASK_RUN", "tutor", "success", severity="INFO", user_id="u1", tags=["lesson"])
    engine.record("TASK_RUN", "tutor", "failure", severity="ERROR", user_id="u1")
    entries = engine.query(agent="tutor", min_severity="ERROR")
    assert len(entries) >= 1
    assert all(e["severity"] in ("ERROR", "CRITICAL") for e in entries)


def test_audit_engine_diagnose():
    engine = AuditEngine()
    engine.record("BUILD_COMPLETE", "build_agent", "success", severity="INFO")
    engine.record("BUILD_FAILED", "build_agent", "failure", severity="ERROR")
    diag = engine.diagnose()
    assert diag["error_count"] >= 1
    assert "top_events" in diag


def test_audit_engine_privacy_wipe():
    engine = AuditEngine()
    engine.record("LOGIN", "auth_agent", "ok", user_id="user_wipe")
    removed = engine.clear_user_data("user_wipe")
    assert removed >= 1
    remaining = engine.query(user_id="user_wipe")
    assert len(remaining) == 0


def test_wave3_quality_scores():
    """All wave-3 agents must be at least strong (score >= 84)."""
    wave3_agents = [
        "planner_agent", "auth_agent", "build_agent", "executor_agent",
        "filesystem_agent", "deploy_agent", "database_agent",
        "vector_store_agent", "scheduler_agent", "snapshot_agent",
        "config_manager_agent",
    ]
    for agent_id in wave3_agents:
        snapshot = api_server._agent_quality_snapshot(agent_id)
        assert snapshot["quality_score"] >= 84, f"{agent_id} scored {snapshot['quality_score']}: {snapshot['quality_findings']}"
        assert snapshot["quality_tier"] in {"strong", "top-tier"}, f"{agent_id} tier={snapshot['quality_tier']}"
