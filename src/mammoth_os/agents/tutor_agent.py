import os
import json
import asyncio
from typing import Dict, Any

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

            # Persist progress locally
            self._record_progress(user_id, curriculum_id, lesson_id, result)

            return {
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "lesson_id": lesson_id,
                "result": result,
            }
        finally:
            # best-effort cleanup
            try:
                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    def _record_progress(self, user_id: str, curriculum_id: str, lesson_id: str, result: Dict[str, Any]):
        entry = {
            "user_id": user_id,
            "curriculum_id": curriculum_id,
            "lesson_id": lesson_id,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "result": result,
        }
        data = []
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
            except Exception:
                data = []
        data.append(entry)
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass
