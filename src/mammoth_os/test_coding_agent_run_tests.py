import asyncio
import tempfile
import os

from mammoth_os.agents.coding_agent import CodingAgent


async def _run():
    # create temp project
    with tempfile.TemporaryDirectory() as tmp:
        # simple module
        os.makedirs(os.path.join(tmp, "pkg"), exist_ok=True)
        with open(os.path.join(tmp, "pkg", "mathlib.py"), "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\n")
        # test file
        with open(os.path.join(tmp, "test_math.py"), "w", encoding="utf-8") as f:
            f.write("from pkg.mathlib import add\ndef test_add():\n    assert add(2,3)==5\n")

        agent = CodingAgent()
        res = await agent.run_tests(tmp)
        assert res["passed"] is True, f"Tests failed: {res.get('stdout')} {res.get('stderr')}"


def test_coding_agent_run_tests():
    asyncio.run(_run())
