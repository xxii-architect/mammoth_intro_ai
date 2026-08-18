import asyncio

import api_server


def test_terminal_allows_atlas_code_generate_command():
    assert api_server._is_allowed('python -m cli.main atlas code generate "build a neon notes panel"')


def test_terminal_allows_atlas_ui_scaffold_command():
    assert api_server._is_allowed('python -m cli.main atlas ui scaffold "atlas operator dashboard"')


def test_terminal_blocks_cli_command_chaining():
    assert not api_server._is_allowed('python -m cli.main atlas code generate "hello"; Remove-Item test.txt')


def test_terminal_uses_extended_timeout_for_atlas_code():
    assert api_server._terminal_timeout_for("python -m cli.main atlas code generate hello") == 180


def test_terminal_exec_returns_timeout_metadata(monkeypatch):
    async def fake_execute(cmd: str, timeout=None):
        return {
            "stdout": "ok",
            "stderr": "",
            "exit_code": 0,
            "cwd": "C:\\repo",
            "resolved": cmd,
            "timeout_seconds": 180,
        }

    monkeypatch.setattr(api_server, "_execute_terminal_command", fake_execute)
    result = asyncio.run(api_server.terminal_exec({"cmd": 'python -m cli.main atlas code generate "hello"'}))

    assert result["exit_code"] == 0
    assert result["timeout_seconds"] == 180

