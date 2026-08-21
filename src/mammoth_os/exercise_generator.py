import asyncio
import concurrent.futures
import json
import os
import re
import uuid
from typing import Dict, Any, List

from mammoth_os.llm_client import get_llm_client


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _looks_like_coding_lesson(text: str) -> bool:
    return bool(
        re.search(
            r"\b(python|javascript|coding|programming|function|loop|algorithm|string|math|addition|conditionals|shell|cli|linux)\b",
            text,
            re.IGNORECASE,
        )
    )


def _lesson_type(lesson: Dict[str, Any]) -> str:
    explicit = str(lesson.get("lesson_type") or "").strip().lower()
    if explicit:
        return explicit
    blob = " ".join([str(lesson.get("title") or ""), *[str(item) for item in (lesson.get("objectives") or [])]])
    return "code" if _looks_like_coding_lesson(blob) else "knowledge"


def _template_exercises(lesson: Dict[str, Any], count: int = 1) -> List[Dict[str, Any]]:
    """Deterministic fallback generator used when LLM mode is disabled/unavailable."""
    exercises: List[Dict[str, Any]] = []
    base_title = lesson.get("title") or "Exercise"
    objectives = lesson.get("objectives", [])
    lesson_text = " ".join([str(base_title), *[str(item) for item in objectives]])
    coding_lesson = _lesson_type(lesson) == "code" or _looks_like_coding_lesson(lesson_text)

    for i in range(1, count + 1):
        ex_id = f"{uuid.uuid4().hex}-e{i}"
        if coding_lesson:
            func_name = "solution"
            prompt = (
                f"Implement a Python function called '{func_name}' for the lesson '{base_title}'. "
                f"Use these objectives as guidance: {objectives}. Write a clear, well-tested implementation."
            )
            starter_files = {f"{func_name}.py": "def solution(*args, **kwargs):\n    raise NotImplementedError()\n"}
            test_lines = []
            obj_text = " ".join(objectives + [base_title]).lower()
            if "add" in obj_text or "sum" in obj_text:
                test_lines.append("from solution import solution\ndef test_solution_add():\n    assert solution(2,3) == 5")
            else:
                test_lines.append("from solution import solution\ndef test_solution_returns():\n    assert solution() is not None")
            expected_test = "\n\n".join(test_lines)
        else:
            objective_lines = "\n".join(f"- {item}" for item in objectives if str(item).strip()) or "- Explain the main ideas clearly.\n- Include one practical example."
            prompt = (
                f"Lesson focus: '{base_title}'.\n"
                "Teach this topic in plain language for a beginner.\n"
                "Respond as a practical lesson summary, not as a coding exercise.\n"
                "Use the ideas below to shape your answer:\n"
                f"{objective_lines}\n\n"
                "Write 3-5 short points or a brief paragraph covering: what the topic is, why it matters, the key principles, and one real-world example or first action step."
            )
            starter_files = {}
            expected_test = (
                "Lesson rubric:\n"
                "- Explain the topic in plain language\n"
                "- Cover at least two concrete ideas from the lesson objectives\n"
                "- Include one practical example or action step\n"
                "- Keep the response beginner-friendly and specific to the lesson theme"
            )

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
    lesson_type = _lesson_type(lesson)
    for i, ex in enumerate(raw_exercises[:count], start=1):
        if not isinstance(ex, dict):
            raise ValueError("LLM exercise entry must be a JSON object")
        prompt = ex.get("prompt")
        starter_files = ex.get("starter_files")
        starter_response = ex.get("starter_response")
        expected_test = ex.get("expected_test")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("LLM exercise missing 'prompt' string")
        if starter_files is None:
            starter_files = {}
        if not isinstance(starter_files, dict):
            raise ValueError("LLM exercise missing 'starter_files' mapping")
        if not isinstance(expected_test, str):
            raise ValueError("LLM exercise missing valid 'expected_test' string")
        if not starter_files and lesson_type == "code":
            raise ValueError("LLM coding exercise missing starter_files")
        if lesson_type == "code" and "assert" not in expected_test:
            raise ValueError("LLM exercise missing valid 'expected_test' with assertions or lesson rubric")
        if lesson_type != "code" and starter_response not in (None, "") and not isinstance(starter_response, str):
            raise ValueError("LLM non-code exercise starter_response must be a string when provided")
        normalized.append(
            {
                "exercise_id": f"{uuid.uuid4().hex}-e{i}",
                "title": ex.get("title") or f"{base_title} — Exercise {i}",
                "prompt": prompt.strip(),
                "starter_files": starter_files,
                "starter_response": starter_response.strip() if isinstance(starter_response, str) else "",
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
    lesson_type = _lesson_type(lesson)
    lesson_summary = str(lesson.get("summary") or lesson.get("content") or "").strip()
    teaching_points = [str(item).strip() for item in (lesson.get("teaching_points") or []) if str(item).strip()]
    examples = [str(item).strip() for item in (lesson.get("examples") or []) if str(item).strip()]

    if lesson_type == "code":
        prompt = (
            "You are ATLAS, an AI tutor. Generate personalized coding exercises.\n"
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
            f"Lesson summary: {lesson_summary}\n"
            f"Teaching points: {teaching_points}\n"
            f"Examples: {examples}\n"
            f"Estimated lesson minutes: {estimated_minutes}\n"
            f"Difficulty level: {difficulty}\n"
            f"Learner context: {json.dumps(context)}\n"
            "Requirements:\n"
            "- Keep exercises deterministic and testable.\n"
            "- Ensure starter code and tests align exactly.\n"
            "- Use realistic but concise prompts suitable for tutoring."
        )
    else:
        prompt = (
            "You are ATLAS, an AI tutor. Generate personalized non-coding lesson exercises.\n"
            "Return STRICT JSON only in this schema:\n"
            "{\n"
            '  "exercises": [\n'
            "    {\n"
            '      "title": "string",\n'
            '      "prompt": "string",\n'
            '      "starter_files": {},\n'
            '      "starter_response": "string",\n'
            '      "expected_test": "plain-language evaluation rubric"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Generate exactly {count} exercise(s).\n"
            f"Lesson title: {lesson_title}\n"
            f"Objectives: {objectives}\n"
            f"Lesson summary: {lesson_summary}\n"
            f"Teaching points: {teaching_points}\n"
            f"Examples: {examples}\n"
            f"Estimated lesson minutes: {estimated_minutes}\n"
            f"Difficulty level: {difficulty}\n"
            f"Learner context: {json.dumps(context)}\n"
            "Requirements:\n"
            "- Keep the exercise truly about the subject, not about writing code.\n"
            "- Make the prompt beginner-friendly, practical, and specific.\n"
            "- Provide a useful starter_response scaffold.\n"
            "- expected_test must be a clear rubric or checklist for grading a written response."
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
    lesson_prefers_llm = str(lesson.get("exercise_generation_mode") or lesson.get("generation_mode") or "").strip().lower() in {"llm", "llm_preferred"}
    llm_enabled = use_llm if use_llm is not None else (mode == "llm" or lesson_prefers_llm)
    if not llm_enabled:
        return _template_exercises(lesson, count=count)

    try:
        return _run_async(
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
