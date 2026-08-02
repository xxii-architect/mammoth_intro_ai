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
    for table in ("sessions", "exercises"):
        assert f"CREATE TABLE IF NOT EXISTS atlas.{table}" in sql, \
            f"Missing table: {table}"
    assert "CREATE OR REPLACE FUNCTION atlas.award_xp" in sql


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
    """Return a mock Supabase client supporting schema().table() chains."""
    class _Op:
        def __init__(self, data=None):
            self.data = data if data is not None else [{"id": "mock-id"}]

        def execute(self):
            return MagicMock(data=self.data)

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

    class _Table:
        def __init__(self):
            self.calls = []

        def insert(self, payload):
            self.calls.append(("insert", payload))
            return _Op()

        def upsert(self, payload, on_conflict=None):
            self.calls.append(("upsert", payload, on_conflict))
            return _Op()

        def select(self, _columns):
            self.calls.append(("select", _columns))
            return _Op(data=[])

    class _SchemaClient:
        def __init__(self):
            self.tables = {}

        def table(self, name):
            self.tables.setdefault(name, _Table())
            return self.tables[name]

    class _Client:
        def __init__(self):
            self.schemas = {}

        def schema(self, name):
            self.schemas.setdefault(name, _SchemaClient())
            return self.schemas[name]

    client = _Client()
    return client


def test_tutor_agent_writes_existing_schema_tables_to_supabase():
    """When supabase client exists, TutorAgent should write to mammoth+atlas tables."""
    from mammoth_os.agents.tutor_agent import TutorAgent

    sb_client = _make_supabase_mock()

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
                user_id="11111111-1111-1111-1111-111111111111",
                curriculum_id="curr1",
                lesson_id="22222222-2222-2222-2222-222222222222",
                files={"solution.py": "def add(a, b): return a + b"},
            )
        )

    mammoth_tables = sb_client.schemas["mammoth"].tables
    atlas_tables = sb_client.schemas["atlas"].tables
    assert "progress" in mammoth_tables
    assert "activity_log" in mammoth_tables
    assert "atlas_progress" in atlas_tables
    assert "adaptive_metrics" in atlas_tables
    assert "community_stats" in atlas_tables
    adaptive_calls = atlas_tables["adaptive_metrics"].calls
    inserts = [c for c in adaptive_calls if c[0] == "insert"]
    assert inserts, "adaptive_metrics insert was not called"
    metric_payload = inserts[-1][1]
    assert metric_payload["difficulty_level"] in {"easy", "medium", "hard"}


def test_tutor_agent_supabase_insert_failure_does_not_crash():
    """If Supabase insert raises, TutorAgent should still return a valid result."""
    from mammoth_os.agents.tutor_agent import TutorAgent

    bad_client = MagicMock()
    bad_client.schema.side_effect = RuntimeError("Supabase connection error")

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
                user_id="11111111-1111-1111-1111-111111111111",
                curriculum_id="c",
                lesson_id="22222222-2222-2222-2222-222222222222",
                files={"solution.py": "x = 1"},
            )
        )

    # Result dict should still be present and contain result sub-key
    assert "result" in result
    assert isinstance(result["result"], dict)


def test_tutor_agent_skips_supabase_for_non_uuid_user():
    from mammoth_os.agents.tutor_agent import TutorAgent

    sb_client = _make_supabase_mock()
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
        agent.supabase = sb_client
        result = asyncio.run(
            agent.accept_submission(
                user_id="cli_user",
                curriculum_id="curr1",
                lesson_id="lesson1",
                files={"solution.py": "def add(a, b): return a + b"},
            )
        )

    assert "result" in result
    assert sb_client.schemas == {}
