import uuid
from typing import Dict, Any, List


def generate_exercises_for_lesson(lesson: Dict[str, Any], count: int = 1) -> List[Dict[str, Any]]:
    """Generate simple template-based exercises for a lesson.

    This implementation is intentionally deterministic and template-driven to
    minimize LLM usage during initial ATLAS integration.

    Returns a list of exercises with fields:
    - exercise_id
    - title
    - prompt (instructions)
    - starter_files: dict of filename -> content (optional)
    - expected_test: a pytest-compatible test string that validates correct behavior
    """
    exercises = []
    base_title = lesson.get("title") or "Exercise"
    objectives = lesson.get("objectives", [])

    for i in range(1, count + 1):
        ex_id = f"{uuid.uuid4().hex}-e{i}"
        # Simple heuristic: create a function name from title
        func_name = "solution"
        # Basic prompt
        prompt = (
            f"Implement a Python function called '{func_name}' that satisfies the objective(s): {objectives}. "
            "Write a clear, well-tested implementation."
        )
        # Starter file: a module with placeholder implementation
        starter_files = {f"{func_name}.py": "def solution(*args, **kwargs):\n    raise NotImplementedError()\n"}

        # Expected test: a conservative template that the student must satisfy.
        # Use a simple numeric example when possible based on 'Practice problem' phrase
        test_lines = []
        # If lesson objectives contain the word 'add' or 'sum' produce an add test
        obj_text = " ".join(objectives).lower()
        if 'add' in obj_text or 'sum' in obj_text:
            test_lines.append("from solution import solution\ndef test_solution_add():\n    assert solution(2,3) == 5")
        else:
            # Generic smoke test that ensures function is callable and returns something non-None
            test_lines.append("from solution import solution\ndef test_solution_returns():\n    assert solution() is not None")

        expected_test = "\n\n".join(test_lines)

        exercises.append({
            "exercise_id": ex_id,
            "title": f"{base_title} — Exercise {i}",
            "prompt": prompt,
            "starter_files": starter_files,
            "expected_test": expected_test,
        })

    return exercises
