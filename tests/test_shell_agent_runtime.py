import asyncio
from pathlib import Path

from mammoth_os.agents.shell_agent import ShellAgent


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_shell_agent_allows_read_only_commands():
    agent = ShellAgent()
    result = asyncio.run(
        agent.run(
            'python -c "print(123)"',
            cwd=str(REPO_ROOT),
            allow_mutating=False,
            timeout=30,
        )
    )

    assert result["status"] == "ok"
    assert result["returncode"] == 0
    assert "123" in result["stdout"]
    assert result["policy"]["allowed"] is True


def test_shell_agent_blocks_mutating_commands_without_explicit_approval():
    agent = ShellAgent()
    blocked = asyncio.run(
        agent.run(
            "git add README.md",
            cwd=str(REPO_ROOT),
            allow_mutating=False,
            timeout=30,
        )
    )

    assert blocked["status"] == "blocked"
    assert "allow_mutating" in blocked["policy"]["reason"]

    allowed = asyncio.run(
        agent.run(
            "git status --short",
            cwd=str(REPO_ROOT),
            allow_mutating=False,
            timeout=30,
        )
    )

    assert allowed["status"] == "ok"
    assert allowed["returncode"] == 0
