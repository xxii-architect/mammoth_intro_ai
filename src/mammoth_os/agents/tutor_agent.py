import os
import json
import asyncio
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
        try:
            for rel, content in files.items():
                dest = os.path.join(tmpdir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w', encoding='utf-8') as fh:
                    fh.write(content)

            # Run tests (CodingAgent.run_tests is async)
            result = await coding.run_tests(tmpdir)

            # Persist progress locally and to Supabase (if configured)
            recommendation = self._record_progress(user_id, curriculum_id, lesson_id, result)

            return {
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "lesson_id": lesson_id,
                "result": result,
                "recommendation": recommendation,
            }
        finally:
            # best-effort cleanup
            try:
                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    def _record_progress(self, user_id: str, curriculum_id: str, lesson_id: str, result: Dict[str, Any]) -> str:
        """Record progress locally and optionally to Supabase.

        Returns a simple difficulty recommendation: 'increase', 'decrease', or 'same'.
        """
        entry = {
            "user_id": user_id,
            "curriculum_id": curriculum_id,
            "lesson_id": lesson_id,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "result": result,
        }
        data: List[Dict[str, Any]] = []
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
            except Exception:
                data = []

        # compute attempts for this user+lesson
        attempts = sum(1 for d in data if d.get('user_id') == user_id and d.get('lesson_id') == lesson_id)
        # attempts is previous attempts count; current attempt is attempts+1
        current_attempt = attempts + 1
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
                }
                # Attempt to insert into table 'progress'
                self.supabase.table('progress').insert(record).execute()
            except Exception:
                # Do not fail if Supabase write fails
                pass

        # Simple adaptive heuristics:
        # - If passed on first attempt -> increase difficulty
        # - If failed for two or more attempts -> decrease difficulty
        # - Otherwise -> same
        recommendation = 'same'
        passed = bool(result.get('passed'))
        if passed and current_attempt == 1:
            recommendation = 'increase'
        elif (not passed) and current_attempt >= 2:
            recommendation = 'decrease'

        return recommendation
