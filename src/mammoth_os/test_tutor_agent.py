import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch
import json

from mammoth_os.agents.tutor_agent import TutorAgent


async def _run():
    import tempfile as _tempfile
    with _tempfile.TemporaryDirectory() as storage_dir:
        agent = TutorAgent(storage_path=storage_dir)
        user_id = 'user1'
        curriculum_id = 'cur1'
        lesson_id = 'lesson1'
        files = {'solution.py': 'def solution():\n    return 42\n'}

        # Mock CodingAgent.run_tests to avoid sandbox execution in unit test
        with patch('mammoth_os.agents.tutor_agent.CodingAgent') as MockCoding:
            mock_instance = MockCoding.return_value
            mock_instance.run_tests = AsyncMock(return_value={"passed": True, "stdout": "ok", "stderr": ""})
            res = await agent.accept_submission(user_id, curriculum_id, lesson_id, files)
            assert res['result']['passed'] is True
            # Recommendation should suggest increasing difficulty on first-pass success
            assert res.get('recommendation') == 'increase'
            assert res.get('adaptive_signals', {}).get('attempt_index') == 1
            assert res.get('adaptive_signals', {}).get('time_to_pass_attempts') == 1
            assert res.get('adaptive_signals', {}).get('error_fingerprint') == 'passed'
            # Check progress file exists
            assert os.path.exists(agent.progress_file)

    # Now simulate two failing attempts to see 'decrease' recommendation
    with _tempfile.TemporaryDirectory() as storage_dir2:
        agent2 = TutorAgent(storage_path=storage_dir2)
        with patch('mammoth_os.agents.tutor_agent.CodingAgent') as MockCoding2:
            mock_instance2 = MockCoding2.return_value
            # First call: fail
            # Second call: fail again
            mock_instance2.run_tests = AsyncMock(side_effect=[{"passed": False, "stdout": "", "stderr": "fail"}, {"passed": False, "stdout": "", "stderr": "fail"}])
            # Use asyncio.run for these synchronous test calls within sync context
            res1 = await agent2.accept_submission(user_id, curriculum_id, lesson_id, files)
            res2 = await agent2.accept_submission(user_id, curriculum_id, lesson_id, files)
            assert res2.get('recommendation') == 'decrease'
            assert res1.get('adaptive_signals', {}).get('error_fingerprint') == 'unknown_failure'
            assert res2.get('adaptive_signals', {}).get('attempt_index') == 2

    # Fail twice then pass: time-to-pass should report three attempts
    with _tempfile.TemporaryDirectory() as storage_dir3:
        agent3 = TutorAgent(storage_path=storage_dir3)
        with patch('mammoth_os.agents.tutor_agent.CodingAgent') as MockCoding3:
            mock_instance3 = MockCoding3.return_value
            mock_instance3.run_tests = AsyncMock(
                side_effect=[
                    {"passed": False, "stdout": "", "stderr": "SyntaxError: invalid syntax"},
                    {"passed": False, "stdout": "", "stderr": "SyntaxError: invalid syntax"},
                    {"passed": True, "stdout": "ok", "stderr": ""},
                ]
            )
            await agent3.accept_submission(user_id, curriculum_id, lesson_id, files)
            await agent3.accept_submission(user_id, curriculum_id, lesson_id, files)
            res3 = await agent3.accept_submission(user_id, curriculum_id, lesson_id, files)
            assert res3.get('recommendation') == 'same'
            assert res3.get('adaptive_signals', {}).get('time_to_pass_attempts') == 3

            with open(agent3.progress_file, 'r', encoding='utf-8') as fh:
                progress = json.load(fh)
            assert progress[-3]['error_fingerprint'] == 'syntax_error'
            assert progress[-2]['error_fingerprint'] == 'syntax_error'
            assert progress[-1]['error_fingerprint'] == 'passed'


def test_tutor_agent_accept_submission():
    asyncio.run(_run())
