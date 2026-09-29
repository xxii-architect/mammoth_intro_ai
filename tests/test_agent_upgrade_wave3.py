import asyncio
import pytest
from mammoth_os.agents.tutor_agent_v2_upgrade import (
    _extract_difficulty_hint,
    _build_adaptive_checkpoints,
    _build_coaching_summary,
)
from mammoth_os.agents.reasoning_agent_v2_upgrade import (
    _extract_error_pattern_enhanced,
    _socratic_questions_enhanced,
    _micro_lesson_enhanced,
    _estimate_confidence_enhanced,
)
from mammoth_os.agents.autonomous_task_engine_v2_upgrade import WorkflowExecutor


# ─────────────────────────────────────────────────────────────────────
# TutorAgent V2 Tests
# ─────────────────────────────────────────────────────────────────────

def test_difficulty_hint_extraction():
    """Test that difficulty hints are extracted from signal summaries."""
    hard_signal = "Signals:\n- Difficulty: hard\n- Struggle tags: syntax"
    easy_signal = "Signals:\n- Difficulty: easy\n- Fast pass detected"
    unknown_signal = "Signals:\n- Difficulty: unknown"
    
    assert _extract_difficulty_hint(hard_signal) == "easy"
    assert _extract_difficulty_hint(easy_signal) == "hard"
    assert _extract_difficulty_hint(unknown_signal) == "medium"
    assert _extract_difficulty_hint(None) == "medium"


def test_adaptive_checkpoints_for_easy():
    """Test that easy difficulty adds extension checkpoints."""
    checkpoints = _build_adaptive_checkpoints("Variables", "m1", "easy")
    assert any("push" in cp.lower() or "constraint" in cp.lower() for cp in checkpoints)


def test_adaptive_checkpoints_for_hard():
    """Test that hard difficulty adds structure-first guidance."""
    checkpoints = _build_adaptive_checkpoints("Loops", "m2", "hard")
    assert any("structure" in cp.lower() or "compile" in cp.lower() for cp in checkpoints)


def test_coaching_summary_reflects_context():
    """Test that coaching summary changes based on available context."""
    with_context = _build_coaching_summary("Lesson", "medium", has_context=True)
    without_context = _build_coaching_summary("Lesson", "medium", has_context=False)
    
    assert "Limited context" in without_context
    assert "Limited context" not in with_context


# ─────────────────────────────────────────────────────────────────────
# ReasoningAgent V2 Tests
# ─────────────────────────────────────────────────────────────────────

def test_error_pattern_extraction_with_fingerprint():
    """Test that explicit fingerprints override heuristic detection."""
    context = {
        "tutor_result": {
            "adaptive_signals": {
                "error_fingerprint": "syntax_error"
            }
        }
    }
    assert _extract_error_pattern_enhanced(context) == "syntax_error"


def test_error_pattern_extraction_from_output():
    """Test heuristic error pattern extraction from output text."""
    context = {
        "tutor_result": {
            "stdout": "IndentationError: unexpected indent",
            "stderr": "",
        }
    }
    assert _extract_error_pattern_enhanced(context) == "indentation_error"
    
    context2 = {
        "tutor_result": {
            "stdout": "RecursionError: maximum recursion depth exceeded",
            "stderr": "",
        }
    }
    assert _extract_error_pattern_enhanced(context2) == "recursion_error"


def test_socratic_questions_for_syntax_error():
    """Test that syntax errors get structure-focused questions."""
    questions = _socratic_questions_enhanced("syntax_error", "my code")
    assert any("bracket" in q.lower() or "parser" in q.lower() for q in questions)


def test_socratic_questions_for_assertion_error():
    """Test that assertion errors get behavior-focused questions."""
    questions = _socratic_questions_enhanced("assertion_error", "my test")
    assert any("expect" in q.lower() or "actual" in q.lower() for q in questions)


def test_micro_lesson_for_timeout():
    """Test that timeout micro-lessons mention infinite loops."""
    lesson = _micro_lesson_enhanced("timeout")
    assert "loop" in lesson.lower() or "stuck" in lesson.lower()


def test_confidence_estimation():
    """Test that confidence varies by error clarity and context."""
    high = _estimate_confidence_enhanced("syntax_error", has_context=True)
    low = _estimate_confidence_enhanced("unknown", has_context=False)
    
    assert high > 0.90
    assert low < 0.70


# ─────────────────────────────────────────────────────────────────────
# AutonomousTaskEngine V2 Tests
# ─────────────────────────────────────────────────────────────────────

def test_workflow_executor_validates_dependencies():
    """Test that workflow validation catches missing dependencies."""
    executor = WorkflowExecutor()
    task_map = {
        "task1": {"depends_on": ["missing"]},
    }
    errors = executor._validate_dependencies(task_map)
    assert any("missing" in err.lower() for err in errors)


def test_workflow_executor_detects_cycles():
    """Test that workflow validation detects circular dependencies."""
    executor = WorkflowExecutor()
    task_map = {
        "task1": {"task_id": "task1", "depends_on": ["task2"]},
        "task2": {"task_id": "task2", "depends_on": ["task1"]},
    }
    errors = executor._validate_dependencies(task_map)
    assert any("cycle" in err.lower() for err in errors)


def test_workflow_executor_empty_workflow():
    """Test that empty workflows execute gracefully."""
    executor = WorkflowExecutor()
    result = asyncio.run(executor.execute_workflow({"workflow_id": "w1", "tasks": []}))
    
    assert result["status"] == "ok"
    assert result["tasks_completed"] == 0
    assert "Empty" in result["summary"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
