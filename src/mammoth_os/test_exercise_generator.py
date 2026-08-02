from unittest.mock import patch

from mammoth_os.exercise_generator import generate_exercises_for_lesson, generate_exercises_for_lesson_llm


def test_generate_basic_exercise():
    lesson = {
        "title": "Addition Basics",
        "objectives": ["Practice problem: add two numbers"],
    }
    exercises = generate_exercises_for_lesson(lesson, count=1)
    assert isinstance(exercises, list) and len(exercises) == 1
    ex = exercises[0]
    assert 'exercise_id' in ex
    assert 'expected_test' in ex
    assert 'assert' in ex['expected_test']
    assert ex["generation_method"] == "template"


def test_generate_exercise_llm_mode_success():
    lesson = {
        "title": "Loops Practice",
        "objectives": ["Practice loops and accumulators"],
    }

    class FakeClient:
        async def generate(self, prompt: str, **kwargs) -> str:
            return """{
  "exercises": [
    {
      "title": "Loop Sum",
      "prompt": "Implement solution(nums) returning the sum of all nums using a loop.",
      "starter_files": {"solution.py": "def solution(nums):\\n    total = 0\\n    for n in nums:\\n        total += n\\n    return total\\n"},
      "expected_test": "from solution import solution\\ndef test_sum():\\n    assert solution([1,2,3]) == 6"
    }
  ]
}"""

    with patch("mammoth_os.exercise_generator.get_llm_client", return_value=FakeClient()):
        exercises = generate_exercises_for_lesson(lesson, count=1, use_llm=True, difficulty="intermediate")

    assert len(exercises) == 1
    ex = exercises[0]
    assert ex["generation_method"] == "llm"
    assert ex["title"] == "Loop Sum"
    assert "solution.py" in ex["starter_files"]
    assert "assert solution([1,2,3]) == 6" in ex["expected_test"]


def test_generate_exercise_llm_mode_fallback_on_bad_payload():
    lesson = {
        "title": "Functions",
        "objectives": ["Write simple functions"],
    }

    class FakeClient:
        async def generate(self, prompt: str, **kwargs) -> str:
            return "not json and not parseable"

    with patch("mammoth_os.exercise_generator.get_llm_client", return_value=FakeClient()):
        exercises = generate_exercises_for_lesson(lesson, count=1, use_llm=True)

    assert len(exercises) == 1
    assert exercises[0]["generation_method"] == "template"


def test_generate_exercise_llm_async_direct():
    lesson = {
        "title": "Conditionals",
        "objectives": ["Use if/else to choose outputs"],
        "estimated_minutes": 20,
    }

    class FakeClient:
        async def generate(self, prompt: str, **kwargs) -> str:
            assert "Difficulty level: advanced" in prompt
            return """```json
{
  "exercises": [
    {
      "title": "Conditional Branching",
      "prompt": "Implement solution(x) returning 'positive', 'zero', or 'negative'.",
      "starter_files": {"solution.py": "def solution(x):\\n    return 'zero'\\n"},
      "expected_test": "from solution import solution\\ndef test_conditional():\\n    assert solution(2) == 'positive'"
    }
  ]
}
```"""

    with patch("mammoth_os.exercise_generator.get_llm_client", return_value=FakeClient()):
        import asyncio

        exercises = asyncio.run(
            generate_exercises_for_lesson_llm(
                lesson=lesson,
                count=1,
                difficulty="advanced",
                learner_context={"struggles": ["branching"]},
            )
        )

    assert len(exercises) == 1
    assert exercises[0]["generation_method"] == "llm"
    assert "assert solution(2) == 'positive'" in exercises[0]["expected_test"]
