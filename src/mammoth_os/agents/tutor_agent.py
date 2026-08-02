import os
import json
import asyncio
import time
from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent
from mammoth_os.agents.coding_agent import CodingAgent


class TutorAgent(BaseAgent):
    """TutorAgent MVP

    Responsibilities:
    - accept_submission(user_id, curriculum_id, lesson_id, files)
    - run tests via CodingAgent.run_tests
    - persist progress to .mammoth/progress.json (local fallback)
    - emit a result dict with pass/fail and test outputs
    """

    name = "TutorAgent"

    def __init__(self, router=None, storage_path: str = None):
        super().__init__(router)
        self.storage_path = storage_path or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.mammoth'))
        os.makedirs(self.storage_path, exist_ok=True)
        self.progress_file = os.path.join(self.storage_path, 'progress.json')

        # Optional Supabase persistence (disabled by default)
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.supabase_key = os.environ.get('SUPABASE_KEY')
        self.supabase = None
        if self.supabase_url and self.supabase_key:
            try:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception:
                # fail quietly — Supabase is optional
                self.supabase = None

    async def accept_submission(self, user_id: str, curriculum_id: str, lesson_id: str, files: Dict[str, str]) -> Dict[str, Any]:
        """Accept a student's submission and grade it by running tests.

        files is a dict mapping relative filenames to their contents.
        """
        # Ensure CodingAgent is available
        coding = CodingAgent()
        # Write files to a temp directory and call run_tests on that path
        import tempfile
        tmpdir = tempfile.mkdtemp()
        started = time.perf_counter()
        try:
            for rel, content in files.items():
                dest = os.path.join(tmpdir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w', encoding='utf-8') as fh:
                    fh.write(content)

            # Run tests (CodingAgent.run_tests is async)
            result = await coding.run_tests(tmpdir)
            duration_ms = int((time.perf_counter() - started) * 1000)
            error_fingerprint = self._fingerprint_error(result)

            # Persist progress locally and to Supabase (if configured)
            progress = self._record_progress(
                user_id,
                curriculum_id,
                lesson_id,
                result,
                duration_ms=duration_ms,
                error_fingerprint=error_fingerprint,
            )

            return {
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "lesson_id": lesson_id,
                "result": result,
                "recommendation": progress["recommendation"],
                "adaptive_signals": {
                    "attempt_index": progress["attempt_index"],
                    "time_to_pass_attempts": progress["time_to_pass_attempts"],
                    "duration_ms": duration_ms,
                    "error_fingerprint": error_fingerprint,
                },
            }
        finally:
            # best-effort cleanup
            try:
                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    def _record_progress(
        self,
        user_id: str,
        curriculum_id: str,
        lesson_id: str,
        result: Dict[str, Any],
        duration_ms: int,
        error_fingerprint: str,
    ) -> Dict[str, Any]:
        """Record progress locally and optionally to Supabase.

        Returns adaptive output containing recommendation and progress signals.
        """
        entry = {
            "user_id": user_id,
            "curriculum_id": curriculum_id,
            "lesson_id": lesson_id,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "result": result,
            "duration_ms": duration_ms,
            "error_fingerprint": error_fingerprint,
        }
        data: List[Dict[str, Any]] = []
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
            except Exception:
                data = []

        # compute prior attempts for this user+lesson
        prior_attempts = [
            d for d in data
            if d.get('user_id') == user_id and d.get('lesson_id') == lesson_id
        ]
        current_attempt = len(prior_attempts) + 1
        entry["attempt_index"] = current_attempt
        data.append(entry)

        # Write back
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

        # Persist to Supabase if configured
        if self.supabase:
            try:
                record = {
                    'user_id': user_id,
                    'curriculum_id': curriculum_id,
                    'lesson_id': lesson_id,
                    'timestamp': entry['timestamp'],
                    'passed': bool(result.get('passed')),
                    'stdout': result.get('stdout', ''),
                    'stderr': result.get('stderr', ''),
                    'returncode': int(result.get('returncode', -1)),
                    'duration_ms': duration_ms,
                    'error_fingerprint': error_fingerprint,
                    'attempt_index': current_attempt,
                }
                # Attempt to insert into table 'progress'
                self.supabase.table('progress').insert(record).execute()
            except Exception:
                # Do not fail if Supabase write fails
                pass

        passed = bool(result.get('passed'))
        recommendation = self._recommend_difficulty(
            passed=passed,
            current_attempt=current_attempt,
            duration_ms=duration_ms,
            error_fingerprint=error_fingerprint,
            prior_attempts=prior_attempts,
        )

        time_to_pass_attempts: Optional[int] = None
        if passed:
            time_to_pass_attempts = self._attempts_since_last_success(prior_attempts) + 1

        return {
            "recommendation": recommendation,
            "attempt_index": current_attempt,
            "time_to_pass_attempts": time_to_pass_attempts,
        }

    def _fingerprint_error(self, result: Dict[str, Any]) -> str:
        """Map test output to coarse error categories for adaptive tutoring."""
        if bool(result.get('passed')):
            return 'passed'
        text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".lower()
        if 'syntaxerror' in text:
            return 'syntax_error'
        if 'indentationerror' in text:
            return 'indentation_error'
        if 'modulenotfounderror' in text or 'importerror' in text:
            return 'import_error'
        if 'assertionerror' in text or 'assert ' in text:
            return 'assertion_error'
        if 'typeerror' in text:
            return 'type_error'
        if 'nameerror' in text:
            return 'name_error'
        if 'timeout' in text:
            return 'timeout'
        if 'notimplementederror' in text:
            return 'not_implemented'
        return 'unknown_failure'

    def _attempts_since_last_success(self, prior_attempts: List[Dict[str, Any]]) -> int:
        """Count attempts after the most recent pass (or all attempts if never passed)."""
        count = 0
        for attempt in reversed(prior_attempts):
            if bool((attempt.get('result') or {}).get('passed')):
                break
            count += 1
        return count

    def _recommend_difficulty(
        self,
        passed: bool,
        current_attempt: int,
        duration_ms: int,
        error_fingerprint: str,
        prior_attempts: List[Dict[str, Any]],
    ) -> str:
        """Heuristic recommendation using attempts, timing, and repeated error patterns."""
        if passed:
            attempts_since_last_success = self._attempts_since_last_success(prior_attempts) + 1
            # Fast pass with few retries indicates readiness for harder material.
            if attempts_since_last_success == 1 and duration_ms <= 60_000:
                return 'increase'
            if attempts_since_last_success <= 2 and duration_ms <= 120_000:
                return 'increase'
            return 'same'

        # Repeated failures with same fingerprint suggests cognitive overload.
        recent = prior_attempts[-2:]
        repeated_same_error = (
            len(recent) >= 1
            and all((r.get('error_fingerprint') == error_fingerprint) for r in recent)
        )
        if repeated_same_error and current_attempt >= 2:
            return 'decrease'

        # Multiple failures in a row, especially structural errors, should reduce difficulty.
        if current_attempt >= 3 and error_fingerprint in {'syntax_error', 'indentation_error', 'type_error', 'timeout'}:
            return 'decrease'

        return 'same'
