"""ATLASSession — End-to-End ATLAS Loop

Chains together:
  CurriculumAgent → ExerciseGenerator → TutorAgent → CodingAgent.run_tests

Usage:
    import asyncio
    from mammoth_os.atlas_session import ATLASSession

    session = ATLASSession(user_id="student_1")

    # Step 1: Start a lesson on a topic
    exercise = session.start_lesson("Python basics: variables and functions")
    print(exercise["prompt"])
    print(exercise["starter_files"])

    # Step 2: Student writes their solution and submits
    files = {"solution.py": "def solution(a, b): return a + b"}
    result = asyncio.run(session.submit(files))
    print(result["passed"], result["recommendation"], result["hint"])
"""
import asyncio
import re
from typing import Dict, Any, List, Optional

# Top-level imports allow unittest.mock.patch to intercept these at the module level
from mammoth_os.agents.tutor_agent import TutorAgent  # noqa: F401  (re-exported for patching)
from mammoth_os.agents.curriculum_agent import CurriculumAgent  # noqa: F401
from mammoth_os.exercise_generator import generate_exercises_for_lesson  # noqa: F401


class ATLASSession:
    """Manages a single learner's ATLAS session end-to-end.

    One session = one topic → one lesson → one or more submission attempts.

    State kept on the object so the user can call start_lesson() once,
    then submit() as many times as they want (with re-attempts handled by TutorAgent).
    """

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id

        # populated by start_lesson()
        self.curriculum: Optional[Dict[str, Any]] = None
        self.current_lesson: Optional[Dict[str, Any]] = None
        self.current_exercise: Optional[Dict[str, Any]] = None
        self._curriculum_id: Optional[str] = None
        self._lesson_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Step 1 — Start a lesson on a topic
    # ------------------------------------------------------------------

    def start_lesson(
        self,
        topic: str,
        module_idx: int = 0,
        lesson_idx: int = 0,
        exercise_count: int = 1,
        use_llm: bool | None = None,
        difficulty: str = "beginner",
        learner_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Generate a curriculum from *topic* and return the first exercise.

        Args:
            topic:          Natural-language topic string, e.g. "Python for loops".
            module_idx:     Which module to pick (default: first = 0).
            lesson_idx:     Which lesson within that module (default: first = 0).
            exercise_count: How many exercises to generate (default: 1).
            use_llm:        Enable personalized LLM generation for exercises.
            difficulty:     Difficulty hint for LLM generation (beginner/intermediate/advanced).
            learner_context: Optional learner profile, strengths, weaknesses, and goals.

        Returns a dict with keys:
            exercise_id, title, prompt, starter_files, expected_test,
            lesson, curriculum_id, lesson_id
        """
        # 1. Generate curriculum
        agent = CurriculumAgent(router=None)
        result = agent.run(topic)
        if result.get("status") != "ok":
            raise RuntimeError(f"CurriculumAgent failed: {result}")

        self.curriculum = result["curriculum"]
        self._curriculum_id = self.curriculum["curriculum_id"]

        # 2. Pick lesson (clamp indices to avoid IndexError)
        modules: List[Dict] = self.curriculum.get("modules", [])
        if not modules:
            raise RuntimeError("CurriculumAgent returned no modules.")
        module = modules[min(module_idx, len(modules) - 1)]
        lessons: List[Dict] = module.get("lessons", [])
        if not lessons:
            raise RuntimeError(f"Module {module_idx} has no lessons.")
        lesson = lessons[min(lesson_idx, len(lessons) - 1)]
        self.current_lesson = lesson
        self._lesson_id = lesson["lesson_id"]

        # 3. Generate exercises
        exercises = generate_exercises_for_lesson(
            lesson,
            count=exercise_count,
            use_llm=use_llm,
            difficulty=difficulty,
            learner_context=learner_context,
        )
        self.current_exercise = exercises[0]

        return {
            **self.current_exercise,
            "lesson": lesson,
            "curriculum_id": self._curriculum_id,
            "lesson_id": self._lesson_id,
        }

    # ------------------------------------------------------------------
    # Step 2 — Submit a solution
    # ------------------------------------------------------------------

    async def submit(self, files: Dict[str, str]) -> Dict[str, Any]:
        """Accept a student's file submission and run tests.

        Args:
            files: dict mapping filename → file content.
                   e.g. {"solution.py": "def solution(a, b): return a + b"}

        Returns a dict with:
            passed        (bool)
            recommendation ('increase' | 'same' | 'decrease')
            hint          (str)  — human-readable feedback based on test output
            result        (dict) — raw sandbox result (returncode, stdout, stderr)
            exercise_id   (str)
            lesson_id     (str)
        """
        if self.current_exercise is None:
            raise RuntimeError("No active exercise. Call start_lesson() first.")

        # Merge the expected test into the submission files so the sandbox can run it
        merged_files = dict(files)
        expected_test = self.current_exercise.get("expected_test", "")
        if expected_test and "test_solution.py" not in merged_files:
            merged_files["test_solution.py"] = expected_test

        tutor = TutorAgent()
        submission_result = await tutor.accept_submission(
            user_id=self.user_id,
            curriculum_id=self._curriculum_id or "unknown",
            lesson_id=self._lesson_id or "unknown",
            files=merged_files,
        )

        raw_result = submission_result.get("result", {})
        passed = bool(raw_result.get("passed"))
        recommendation = submission_result.get("recommendation", "same")

        hint = self._generate_hint(passed, raw_result, self.current_exercise)

        return {
            "passed": passed,
            "recommendation": recommendation,
            "hint": hint,
            "result": raw_result,
            "exercise_id": self.current_exercise.get("exercise_id"),
            "lesson_id": self._lesson_id,
        }

    # ------------------------------------------------------------------
    # Hint generation — no LLM, fully local
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_hint(
        passed: bool,
        result: Dict[str, Any],
        exercise: Dict[str, Any],
    ) -> str:
        """Produce a helpful hint string from test output without calling an LLM."""
        if passed:
            return "✅ All tests passed! Great work."

        stderr: str = result.get("stderr", "") or ""
        stdout: str = result.get("stdout", "") or ""
        combined = (stdout + "\n" + stderr).strip()

        # Pattern-match common failure types
        if "NotImplementedError" in combined:
            return (
                "💡 Your function raises NotImplementedError — "
                "replace the placeholder body with a real implementation."
            )

        if "AssertionError" in combined:
            # Try to extract the failing assertion line
            match = re.search(r"assert (.+)", combined)
            assertion = match.group(1).strip() if match else ""
            if assertion:
                return f"💡 Test assertion failed: `{assertion}`. Check your return value matches what the test expects."
            return "💡 An assertion in the test failed. Double-check your return value and data types."

        if "ImportError" in combined or "ModuleNotFoundError" in combined:
            return (
                "💡 Import error — make sure your file is named exactly as the test expects "
                "(usually solution.py) and the function name matches."
            )

        if "SyntaxError" in combined:
            # Find line number hint if available
            match = re.search(r"line (\d+)", combined)
            line = f" on line {match.group(1)}" if match else ""
            return f"💡 SyntaxError{line} — check your code for missing colons, parentheses, or indentation errors."

        if "TypeError" in combined:
            return (
                "💡 TypeError — your function may be returning the wrong type or "
                "accepting the wrong number of arguments."
            )

        if "IndentationError" in combined:
            return "💡 IndentationError — check that your code uses consistent spaces (4 spaces per indent level)."

        if combined:
            # Return the first meaningful line from stderr as a clue
            first_line = next(
                (ln.strip() for ln in combined.splitlines() if ln.strip() and not ln.startswith("===")),
                "",
            )
            if first_line:
                return f"💡 Tests did not pass. Error clue: {first_line}"

        return "💡 Tests did not pass. Review the exercise prompt and try again."

    # ------------------------------------------------------------------
    # Convenience — advance to the next lesson
    # ------------------------------------------------------------------

    def next_lesson(self, lesson_idx_delta: int = 1) -> Dict[str, Any]:
        """Advance to the next lesson in the current module.

        Returns the new exercise, same as start_lesson().
        """
        if self.curriculum is None:
            raise RuntimeError("No curriculum loaded. Call start_lesson() first.")

        # Find current module and lesson indices
        modules: List[Dict] = self.curriculum.get("modules", [])
        cur_lesson_id = self._lesson_id

        for m_idx, module in enumerate(modules):
            for l_idx, lesson in enumerate(module.get("lessons", [])):
                if lesson["lesson_id"] == cur_lesson_id:
                    new_l_idx = l_idx + lesson_idx_delta
                    if new_l_idx < len(module["lessons"]):
                        return self._load_lesson(module["lessons"][new_l_idx])
                    # Move to next module
                    if m_idx + 1 < len(modules):
                        next_module = modules[m_idx + 1]
                        if next_module.get("lessons"):
                            return self._load_lesson(next_module["lessons"][0])
                    raise RuntimeError("No more lessons in this curriculum.")

        raise RuntimeError("Current lesson not found in curriculum.")

    def _load_lesson(self, lesson: Dict[str, Any]) -> Dict[str, Any]:
        """Internal: switch to a lesson and generate its first exercise."""
        self.current_lesson = lesson
        self._lesson_id = lesson["lesson_id"]
        exercises = generate_exercises_for_lesson(lesson, count=1)
        self.current_exercise = exercises[0]
        return {
            **self.current_exercise,
            "lesson": lesson,
            "curriculum_id": self._curriculum_id,
            "lesson_id": self._lesson_id,
        }

    # ------------------------------------------------------------------
    # State summary (useful for CLI display)
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Return a human-readable summary of the current session state."""
        if self.curriculum is None:
            return {"state": "idle", "message": "No lesson started. Call start_lesson(topic)."}
        return {
            "state": "active",
            "user_id": self.user_id,
            "curriculum_title": self.curriculum.get("title"),
            "lesson_title": (self.current_lesson or {}).get("title"),
            "exercise_title": (self.current_exercise or {}).get("title"),
            "exercise_prompt": (self.current_exercise or {}).get("prompt"),
            "starter_files": (self.current_exercise or {}).get("starter_files", {}),
            "curriculum_id": self._curriculum_id,
            "lesson_id": self._lesson_id,
        }

    # ------------------------------------------------------------------
    # State persistence — save/load to JSON so CLI calls share state
    # ------------------------------------------------------------------

    def save_state(self, path: str) -> None:
        """Persist session state to a JSON file."""
        import json, os
        state = {
            "user_id": self.user_id,
            "curriculum": self.curriculum,
            "current_lesson": self.current_lesson,
            "current_exercise": self.current_exercise,
            "_curriculum_id": self._curriculum_id,
            "_lesson_id": self._lesson_id,
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)

    @classmethod
    def load_state(cls, path: str) -> "ATLASSession":
        """Restore a session from a previously saved JSON file.

        Returns an idle ATLASSession if the file does not exist.
        """
        import json, os
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            session = cls(user_id=state.get("user_id", "default_user"))
            session.curriculum = state.get("curriculum")
            session.current_lesson = state.get("current_lesson")
            session.current_exercise = state.get("current_exercise")
            session._curriculum_id = state.get("_curriculum_id")
            session._lesson_id = state.get("_lesson_id")
            return session
        except Exception:
            return cls()
