import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch

from mammoth_os.agents.tutor_agent import TutorAgent


async def _run():
    agent = TutorAgent()
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
        # Check progress file exists
        assert os.path.exists(agent.progress_file)


def test_tutor_agent_accept_submission():
    asyncio.run(_run())
