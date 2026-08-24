import asyncio

import pytest

from mammoth_os.agents.auth_agent import AuthAgent
from mammoth_os.agents.build_agent import BuildAgent
from mammoth_os.memory_engine import MemoryEngine


def test_auth_agent_issues_tokens_and_checks_scope():
    agent = AuthAgent(router=None)
    token = asyncio.run(agent.issue_token("user-42", ["read", "write"], role="admin"))

    claims = asyncio.run(agent.validate_token(token))
    assert claims["sub"] == "user-42"
    assert "write" in claims["scopes"]
    assert asyncio.run(agent.check_permission(token, "write")) is True
    assert asyncio.run(agent.check_permission(token, "delete")) is False


def test_build_agent_validates_paths_and_tracks_success(monkeypatch, tmp_path):
    agent = BuildAgent(router=None)

    with pytest.raises(FileNotFoundError):
        asyncio.run(agent.build(str(tmp_path / "missing-project"), "python"))

    async def fake_run_step(step_name, command, project_path):
        return {"step": step_name, "status": "passed", "exit_code": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(agent, "_run_step", fake_run_step)
    result = asyncio.run(agent.build(str(tmp_path), "python"))

    assert result["success"] is True
    assert result["results"]["lint"]["status"] == "passed"
    assert result["results"]["build"]["status"] == "passed"


def test_memory_engine_persists_and_retrieves_recent_context(tmp_path):
    engine = MemoryEngine({"storage_path": str(tmp_path / "memory_store.json"), "max_entries": 25})
    memory_id = engine.store(
        "Keep session memory for continuity across every tutoring cycle.",
        memory_type="semantic",
        metadata={"namespace": "workspace"},
    )

    assert memory_id
    results = engine.retrieve("session memory continuity", top_k=5)
    assert len(results) >= 1
    assert results[0]["content"].startswith("Keep session memory")
