"""End-to-end tests for ATLASSession — the full ATLAS loop.

Tests cover:
  1. start_lesson() returns a well-formed exercise
  2. submit() with a correct solution → passed=True, recommendation='increase'
  3. submit() with wrong solution → passed=False, meaningful hint
  4. submit() with NotImplementedError placeholder → appropriate hint
  5. next_lesson() advances to the next lesson
  6. status() reflects session state
  7. Missing start_lesson() guard on submit()
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from mammoth_os.atlas_session import ATLASSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run a coroutine in a fresh event loop (compatible with pytest-asyncio absent)."""
    return asyncio.run(coro)


def _make_session(user_id="test_user"):
    return ATLASSession(user_id=user_id)


def _passing_result():
    return {"passed": True, "stdout": "1 passed", "stderr": "", "returncode": 0}


def _failing_result(stderr="AssertionError: assert solution(2,3) == 5"):
    return {"passed": False, "stdout": "", "stderr": stderr, "returncode": 1}


# ---------------------------------------------------------------------------
# 1. start_lesson returns a well-formed exercise
# ---------------------------------------------------------------------------

def test_start_lesson_returns_exercise():
    session = _make_session()
    exercise = session.start_lesson("Python basics: addition")

    assert "exercise_id" in exercise
    assert "title" in exercise
    assert "prompt" in exercise
    assert "starter_files" in exercise
    assert isinstance(exercise["starter_files"], dict)
    assert "expected_test" in exercise
    assert "lesson" in exercise
    assert "curriculum_id" in exercise
    assert "lesson_id" in exercise
    # curriculum_id and lesson_id are consistent
    assert session._curriculum_id == exercise["curriculum_id"]
    assert session._lesson_id == exercise["lesson_id"]


def test_start_lesson_populates_session_state():
    session = _make_session()
    session.start_lesson("Python loops")
    assert session.curriculum is not None
    assert session.current_lesson is not None
    assert session.current_exercise is not None


def test_start_lesson_module_lesson_clamping():
    """Requesting an out-of-range module/lesson should clamp to last available."""
    session = _make_session()
    # 99 is way beyond the 3 modules generated
    exercise = session.start_lesson("Python strings", module_idx=99, lesson_idx=99)
    assert exercise["exercise_id"]  # should still work


# ---------------------------------------------------------------------------
# 2. submit() with correct solution → passed, increase
# ---------------------------------------------------------------------------

async def _submit_passing():
    session = _make_session()
    session.start_lesson("Python math: add two numbers")

    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor:
        mock_instance = MockTutor.return_value
        mock_instance.accept_submission = AsyncMock(return_value={
            "result": _passing_result(),
            "recommendation": "increase",
        })
        result = await session.submit({"solution.py": "def solution(a, b): return a + b"})

    return result

def test_submit_passing():
    result = run(_submit_passing())
    assert result["passed"] is True
    assert result["recommendation"] == "increase"
    assert "✅" in result["hint"]
    assert result["exercise_id"] is not None
    assert result["lesson_id"] is not None


# ---------------------------------------------------------------------------
# 3. submit() with wrong solution → failed, meaningful hint
# ---------------------------------------------------------------------------

async def _submit_failing_assertion():
    session = _make_session()
    session.start_lesson("Python math: add two numbers")

    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor:
        mock_instance = MockTutor.return_value
        mock_instance.accept_submission = AsyncMock(return_value={
            "result": _failing_result("AssertionError: assert solution(2,3) == 5"),
            "recommendation": "same",
        })
        return await session.submit({"solution.py": "def solution(a, b): return 0"})


def test_submit_failing_assertion_hint():
    result = run(_submit_failing_assertion())
    assert result["passed"] is False
    assert "assertion" in result["hint"].lower() or "assert" in result["hint"].lower()


# ---------------------------------------------------------------------------
# 4. NotImplementedError placeholder hint
# ---------------------------------------------------------------------------

async def _submit_not_implemented():
    session = _make_session()
    session.start_lesson("Python basics")

    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor:
        mock_instance = MockTutor.return_value
        mock_instance.accept_submission = AsyncMock(return_value={
            "result": _failing_result(stderr="NotImplementedError"),
            "recommendation": "same",
        })
        return await session.submit({"solution.py": "def solution(*args, **kwargs):\n    raise NotImplementedError()\n"})


def test_submit_not_implemented_hint():
    result = run(_submit_not_implemented())
    assert result["passed"] is False
    assert "NotImplementedError" in result["hint"] or "placeholder" in result["hint"].lower()


# ---------------------------------------------------------------------------
# 5. Hint patterns for other error types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stderr,expected_keyword", [
    ("ImportError: No module named 'solution'", "import"),
    ("SyntaxError: invalid syntax on line 3", "syntax"),
    ("TypeError: solution() takes 0 positional arguments but 2 were given", "type"),
    ("IndentationError: unexpected indent", "indent"),
])
def test_hint_patterns(stderr, expected_keyword):
    hint = ATLASSession._generate_hint(
        passed=False,
        result={"passed": False, "stdout": "", "stderr": stderr, "returncode": 1},
        exercise={},
    )
    assert expected_keyword.lower() in hint.lower()


# ---------------------------------------------------------------------------
# 6. submit() without start_lesson() raises RuntimeError
# ---------------------------------------------------------------------------

def test_submit_without_start_lesson_raises():
    session = _make_session()
    with pytest.raises(RuntimeError, match="start_lesson"):
        run(session.submit({"solution.py": ""}))


# ---------------------------------------------------------------------------
# 7. next_lesson() advances to the next lesson
# ---------------------------------------------------------------------------

def test_next_lesson_advances():
    session = _make_session()
    first = session.start_lesson("Python variables")
    first_lesson_id = first["lesson_id"]

    second = session.next_lesson()
    second_lesson_id = second["lesson_id"]

    assert second_lesson_id != first_lesson_id
    assert session._lesson_id == second_lesson_id


def test_next_lesson_without_start_raises():
    session = _make_session()
    with pytest.raises(RuntimeError, match="start_lesson"):
        session.next_lesson()


# ---------------------------------------------------------------------------
# 8. status() reflects session state
# ---------------------------------------------------------------------------

def test_status_idle():
    session = _make_session()
    s = session.status()
    assert s["state"] == "idle"


def test_status_active():
    session = _make_session()
    session.start_lesson("Python for loops")
    s = session.status()
    assert s["state"] == "active"
    assert s["user_id"] == "test_user"
    assert s["curriculum_title"] is not None
    assert s["lesson_title"] is not None
    assert s["exercise_title"] is not None


# ---------------------------------------------------------------------------
# 9. Full end-to-end smoke test with real sandbox subprocess fallback
# ---------------------------------------------------------------------------

async def _full_e2e():
    """
    Full loop with FORCE_SUBPROCESS_FALLBACK=1:
    start_lesson → submit correct solution → check passed.
    No mocking — exercises the real sandbox path.
    """
    import os
    os.environ["FORCE_SUBPROCESS_FALLBACK"] = "1"
    try:
        session = ATLASSession(user_id="e2e_user")
        # "Adding numbers" goes into the lesson title → exercise_generator detects 'add' → generates add(2,3)==5 test
        exercise = session.start_lesson("Adding numbers in Python")

        # Build a correct solution matching the expected test
        correct_solution = "def solution(a, b):\n    return a + b\n"
        result = await session.submit({"solution.py": correct_solution})
        return result
    finally:
        os.environ.pop("FORCE_SUBPROCESS_FALLBACK", None)


def test_full_e2e_passing():
    result = run(_full_e2e())
    assert result["passed"] is True, (
        f"E2E test failed.\nHint: {result['hint']}\nRaw: {result['result']}"
    )
    assert result["recommendation"] == "increase"
