"""Tests for the ATLAS CLI commands (cli/atlas.py + cli/main.py).

Uses argparse + a temporary session state file to isolate each test.
No subprocess needed — we call the command functions directly with
parsed args and capture stdout with capsys.
"""
import asyncio
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

# Ensure src/ is on the path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cli.atlas as atlas_cli
from mammoth_os.atlas_session import ATLASSession


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_session(tmp_path, monkeypatch):
    """Redirect the CLI session state file to a temp directory for every test."""
    state_file = str(tmp_path / "atlas_cli_session.json")
    monkeypatch.setattr(atlas_cli, "_SESSION_STATE_FILE", state_file)
    monkeypatch.setattr(atlas_cli, "_DEFAULT_USER", "test_user")
    yield state_file


def _args(**kwargs):
    """Build a SimpleNamespace mimicking parsed argparse args."""
    return SimpleNamespace(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# 1. atlas lesson
# ─────────────────────────────────────────────────────────────────────────────

def test_atlas_lesson_output(capsys, isolated_session):
    args = _args(topic=["Adding", "numbers", "in", "Python"], module=0, lesson=0)
    atlas_cli.cmd_atlas_lesson(args)

    out = capsys.readouterr().out
    assert "ATLAS" in out
    assert "lesson" in out.lower() or "exercise" in out.lower()
    assert "solution.py" in out
    assert "NotImplementedError" in out


def test_atlas_lesson_saves_state(isolated_session):
    args = _args(topic=["Python", "loops"], module=0, lesson=0)
    atlas_cli.cmd_atlas_lesson(args)
    assert os.path.exists(isolated_session)
    with open(isolated_session) as f:
        state = json.load(f)
    assert state["curriculum"] is not None
    assert state["_lesson_id"] is not None


def test_atlas_lesson_empty_topic_exits():
    args = _args(topic=[], module=0, lesson=0)
    with pytest.raises(SystemExit):
        atlas_cli.cmd_atlas_lesson(args)


# ─────────────────────────────────────────────────────────────────────────────
# 2. atlas status
# ─────────────────────────────────────────────────────────────────────────────

def test_atlas_status_idle(capsys, isolated_session):
    atlas_cli.cmd_atlas_status(_args())
    out = capsys.readouterr().out
    assert "No active lesson" in out or "idle" in out.lower()


def test_atlas_status_active(capsys, isolated_session):
    # Start a lesson first
    atlas_cli.cmd_atlas_lesson(_args(topic=["Python", "functions"], module=0, lesson=0))
    capsys.readouterr()  # discard lesson output

    atlas_cli.cmd_atlas_status(_args())
    out = capsys.readouterr().out
    assert "Python" in out
    assert "Exercise" in out
    assert "solution.py" in out


# ─────────────────────────────────────────────────────────────────────────────
# 3. atlas submit
# ─────────────────────────────────────────────────────────────────────────────

def _start_add_lesson(isolated_session):
    """Helper: start an 'Adding numbers' lesson (generates an add test)."""
    atlas_cli.cmd_atlas_lesson(
        _args(topic=["Adding", "numbers", "in", "Python"], module=0, lesson=0)
    )


def test_atlas_submit_no_lesson_exits(isolated_session):
    with pytest.raises(SystemExit):
        atlas_cli.cmd_atlas_submit(_args(inline=None, file=None))


def test_atlas_submit_no_args_exits(isolated_session, capsys):
    _start_add_lesson(isolated_session)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        atlas_cli.cmd_atlas_submit(_args(inline=None, file=None))


def test_atlas_submit_inline_passing(capsys, isolated_session, monkeypatch):
    _start_add_lesson(isolated_session)
    capsys.readouterr()

    # Mock TutorAgent so sandbox doesn't run
    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor:
        mock_instance = MockTutor.return_value
        mock_instance.accept_submission = AsyncMock(return_value={
            "result": {"passed": True, "stdout": "1 passed", "stderr": "", "returncode": 0},
            "recommendation": "increase",
        })
        atlas_cli.cmd_atlas_submit(_args(inline="def solution(a, b): return a + b", file=None))

    out = capsys.readouterr().out
    assert "PASSED" in out
    assert "All tests passed" in out
    assert "harder challenges" in out.lower() or "advance" in out.lower()


def test_atlas_submit_inline_failing(capsys, isolated_session):
    _start_add_lesson(isolated_session)
    capsys.readouterr()

    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor:
        mock_instance = MockTutor.return_value
        mock_instance.accept_submission = AsyncMock(return_value={
            "result": {"passed": False, "stdout": "", "stderr": "AssertionError: assert 0 == 5", "returncode": 1},
            "recommendation": "same",
        })
        atlas_cli.cmd_atlas_submit(_args(inline="def solution(a, b): return 0", file=None))

    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "assertion" in out.lower() or "assert" in out.lower()


def test_atlas_submit_file_not_found_exits(isolated_session, capsys):
    _start_add_lesson(isolated_session)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        atlas_cli.cmd_atlas_submit(_args(inline=None, file="/nonexistent/path/solution.py"))


def test_atlas_submit_from_file(tmp_path, capsys, isolated_session):
    _start_add_lesson(isolated_session)
    capsys.readouterr()

    sol = tmp_path / "solution.py"
    sol.write_text("def solution(a, b):\n    return a + b\n")

    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor:
        mock_instance = MockTutor.return_value
        mock_instance.accept_submission = AsyncMock(return_value={
            "result": {"passed": True, "stdout": "1 passed", "stderr": "", "returncode": 0},
            "recommendation": "increase",
        })
        atlas_cli.cmd_atlas_submit(_args(inline=None, file=str(sol)))

    out = capsys.readouterr().out
    assert "PASSED" in out


# ─────────────────────────────────────────────────────────────────────────────
# 4. atlas next
# ─────────────────────────────────────────────────────────────────────────────

def test_atlas_next_without_curriculum_exits(capsys, isolated_session):
    with pytest.raises(SystemExit):
        atlas_cli.cmd_atlas_next(_args())


def test_atlas_next_advances_lesson(capsys, isolated_session):
    _start_add_lesson(isolated_session)
    capsys.readouterr()

    # Record first lesson_id
    with open(isolated_session) as f:
        state_before = json.load(f)
    lesson_id_before = state_before["_lesson_id"]

    atlas_cli.cmd_atlas_next(_args())
    out = capsys.readouterr().out
    assert "Lesson" in out

    with open(isolated_session) as f:
        state_after = json.load(f)
    assert state_after["_lesson_id"] != lesson_id_before


# ─────────────────────────────────────────────────────────────────────────────
# 5. atlas reset
# ─────────────────────────────────────────────────────────────────────────────

def test_atlas_reset_clears_state(capsys, isolated_session):
    _start_add_lesson(isolated_session)
    assert os.path.exists(isolated_session)

    atlas_cli.cmd_atlas_reset(_args())
    assert not os.path.exists(isolated_session)

    out = capsys.readouterr().out
    assert "cleared" in out.lower() or "clear" in out.lower()


def test_atlas_reset_no_session(capsys, isolated_session):
    atlas_cli.cmd_atlas_reset(_args())
    out = capsys.readouterr().out
    assert "No active session" in out or "nothing" in out.lower() or "clear" in out.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 6. ATLASSession save/load round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_session_save_load_round_trip(tmp_path):
    state_file = str(tmp_path / "test_state.json")

    session = ATLASSession(user_id="round_trip_user")
    session.start_lesson("Python variables")

    session.save_state(state_file)
    assert os.path.exists(state_file)

    restored = ATLASSession.load_state(state_file)
    assert restored.user_id == "round_trip_user"
    assert restored.curriculum is not None
    assert restored._curriculum_id == session._curriculum_id
    assert restored._lesson_id == session._lesson_id
    assert restored.current_exercise is not None
    assert restored.current_exercise["exercise_id"] == session.current_exercise["exercise_id"]


def test_session_load_missing_file_returns_idle(tmp_path):
    session = ATLASSession.load_state(str(tmp_path / "nonexistent.json"))
    assert session.curriculum is None
    assert session.status()["state"] == "idle"


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLI parser integration
# ─────────────────────────────────────────────────────────────────────────────

def test_build_parser_has_atlas():
    """The cli/main.py parser should expose the atlas subcommand."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from cli.main import build_parser
    parser = build_parser()
    # Verify atlas is a registered subcommand by parsing a basic invocation
    args = parser.parse_args(["atlas", "reset"])
    assert hasattr(args, "func")
    assert args.func == atlas_cli.cmd_atlas_reset


class _FakeUrlResp:
    def __init__(self, payload: str):
        self._payload = payload.encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_resolve_user_id_from_supabase(monkeypatch):
    monkeypatch.delenv("ATLAS_USER_ID", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    payload = '[{"id":"11111111-1111-1111-1111-111111111111","email":"a@b.com"}]'
    monkeypatch.setattr(
        atlas_cli.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeUrlResp(payload),
    )

    resolved = atlas_cli._resolve_user_id_from_supabase()
    assert resolved == "11111111-1111-1111-1111-111111111111"
    assert os.environ.get("ATLAS_USER_ID") == resolved


def test_load_session_auto_sets_resolved_user_id(monkeypatch, isolated_session):
    monkeypatch.delenv("ATLAS_USER_ID", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    payload = '[{"id":"22222222-2222-2222-2222-222222222222","email":"a@b.com"}]'
    monkeypatch.setattr(
        atlas_cli.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeUrlResp(payload),
    )

    session = atlas_cli._load_session()
    assert session.user_id == "22222222-2222-2222-2222-222222222222"


def test_atlas_code_generate_redirects_ui_component_prompts(capsys, isolated_session):
    args = _args(prompt=["upgrade", "my", "notes", "panel"], no_save=True)
    with pytest.raises(SystemExit) as exc:
        atlas_cli.cmd_atlas_code_generate(args)

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "UI-focused prompt detected" in out
    assert "atlas ui component" in out


def test_atlas_code_generate_redirects_ui_style_prompts(capsys, isolated_session):
    args = _args(prompt=["restyle", "the", "dashboard", "theme"], no_save=True)
    with pytest.raises(SystemExit) as exc:
        atlas_cli.cmd_atlas_code_generate(args)

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "atlas ui palette" in out
