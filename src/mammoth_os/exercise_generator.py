import asyncio
import json
import os
import re
import uuid
from typing import Dict, Any, List

from mammoth_os.llm_client import get_llm_client


def _template_exercises(lesson: Dict[str, Any], count: int = 1) -> List[Dict[str, Any]]:
    """Deterministic fallback generator used when LLM mode is disabled/unavailable."""
    exercises: List[Dict[str, Any]] = []
    base_title = lesson.get("title") or "Exercise"
    objectives = lesson.get("objectives", [])

    for i in range(1, count + 1):
        ex_id = f"{uuid.uuid4().hex}-e{i}"
        func_name = "solution"
        prompt = (
            f"Implement a Python function called '{func_name}' that satisfies the objective(s): {objectives}. "
            "Write a clear, well-tested implementation."
        )
        starter_files = {f"{func_name}.py": "def solution(*args, **kwargs):\n    raise NotImplementedError()\n"}

        test_lines = []
        obj_text = " ".join(objectives + [base_title]).lower()
        if "add" in obj_text or "sum" in obj_text:
            test_lines.append("from solution import solution\ndef test_solution_add():\n    assert solution(2,3) == 5")
        else:
            test_lines.append("from solution import solution\ndef test_solution_returns():\n    assert solution() is not None")

        expected_test = "\n\n".join(test_lines)
        exercises.append(
            {
                "exercise_id": ex_id,
                "title": f"{base_title} — Exercise {i}",
                "prompt": prompt,
                "starter_files": starter_files,
                "expected_test": expected_test,
                "generation_method": "template",
            }
        )

    return exercises


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Extract and parse the first JSON object from raw LLM text."""
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidates = fenced + [text]
    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[\s\S]*\}", candidate)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    raise ValueError("No valid JSON object found in LLM response")


def _normalize_llm_exercises(payload: Dict[str, Any], lesson: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
    """Normalize LLM payload into ATLAS exercise objects."""
    raw_exercises = payload.get("exercises")
    if not isinstance(raw_exercises, list) or not raw_exercises:
        raise ValueError("LLM payload missing non-empty 'exercises' list")

    normalized: List[Dict[str, Any]] = []
    base_title = lesson.get("title") or "Exercise"
    for i, ex in enumerate(raw_exercises[:count], start=1):
        if not isinstance(ex, dict):
            raise ValueError("LLM exercise entry must be a JSON object")
        prompt = ex.get("prompt")
        starter_files = ex.get("starter_files")
        expected_test = ex.get("expected_test")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("LLM exercise missing 'prompt' string")
        if not isinstance(starter_files, dict) or not starter_files:
            raise ValueError("LLM exercise missing 'starter_files' mapping")
        if not isinstance(expected_test, str) or "assert" not in expected_test:
            raise ValueError("LLM exercise missing valid 'expected_test' with assertions")
        normalized.append(
            {
                "exercise_id": f"{uuid.uuid4().hex}-e{i}",
                "title": ex.get("title") or f"{base_title} — Exercise {i}",
                "prompt": prompt.strip(),
                "starter_files": starter_files,
                "expected_test": expected_test.strip(),
                "generation_method": "llm",
            }
        )
    return normalized


async def generate_exercises_for_lesson_llm(
    lesson: Dict[str, Any],
    count: int = 1,
    difficulty: str = "beginner",
    learner_context: Dict[str, Any] | None = None,
    llm_config: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """LLM-backed personalized exercise generation."""
    client = get_llm_client(config=llm_config or {})
    lesson_title = lesson.get("title") or "Exercise"
    objectives = lesson.get("objectives", [])
    estimated_minutes = lesson.get("estimated_minutes")
    context = learner_context or {}

    prompt = (
        "You are ATLAS, an AI tutor. Generate personalized Python coding exercises.\n"
        "Return STRICT JSON only in this schema:\n"
        "{\n"
        '  "exercises": [\n'
        "    {\n"
        '      "title": "string",\n'
        '      "prompt": "string",\n'
        '      "starter_files": {"solution.py": "python code"},\n'
        '      "expected_test": "pytest code with at least one assert"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Generate exactly {count} exercise(s).\n"
        f"Lesson title: {lesson_title}\n"
        f"Objectives: {objectives}\n"
        f"Estimated lesson minutes: {estimated_minutes}\n"
        f"Difficulty level: {difficulty}\n"
        f"Learner context: {json.dumps(context)}\n"
        "Requirements:\n"
        "- Keep exercises deterministic and testable.\n"
        "- Ensure starter code and tests align exactly.\n"
        "- Use realistic but concise prompts suitable for tutoring."
    )

    raw = await client.generate(prompt, temperature=0.2, max_tokens=1600)
    payload = _extract_json_object(raw)
    return _normalize_llm_exercises(payload, lesson, count)


def generate_exercises_for_lesson(
    lesson: Dict[str, Any],
    count: int = 1,
    use_llm: bool | None = None,
    difficulty: str = "beginner",
    learner_context: Dict[str, Any] | None = None,
    llm_config: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Generate exercises for a lesson, optionally using an LLM.

    Modes:
    - template (default): deterministic local templates
    - llm: personalized LLM generation with automatic fallback to template on parse/call errors

    Control via args or environment:
    - use_llm=True/False
    - ATLAS_EXERCISE_GEN_MODE=llm|template
    """
    mode = os.getenv("ATLAS_EXERCISE_GEN_MODE", "template").strip().lower()
    llm_enabled = use_llm if use_llm is not None else (mode == "llm")
    if not llm_enabled:
        return _template_exercises(lesson, count=count)

    try:
        return asyncio.run(
            generate_exercises_for_lesson_llm(
                lesson=lesson,
                count=count,
                difficulty=difficulty,
                learner_context=learner_context,
                llm_config=llm_config,
            )
        )
    except Exception:
        # Deterministic fallback keeps ATLAS functional if LLM output is malformed/unavailable.
        return _template_exercises(lesson, count=count)
