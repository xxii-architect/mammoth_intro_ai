import asyncio
import os
import re
import shlex
from typing import Any, Dict, List, Optional

from mammoth_os.agents.base_agent import BaseAgent  # type: ignore


class ShellAgent(BaseAgent):  # type: ignore
    """
    Executes shell commands in a controlled, policy-checked environment.
    The default policy allows read-only and focused validation commands while
    blocking destructive or externalized actions unless explicitly opted in.
    """

    ALLOWED_COMMANDS = {
        "git",
        "python",
        "python3",
        "pytest",
        "node",
        "npm",
        "ls",
        "dir",
        "pwd",
        "echo",
        "which",
        "find",
        "grep",
        "sed",
        "head",
        "tail",
        "cat",
        "type",
        "uvicorn",
    }

    BLOCKED_COMMANDS = {
        "rm",
        "sudo",
        "shutdown",
        "reboot",
        "poweroff",
        "mkfs",
        "dd",
        "chmod",
        "chown",
        "mount",
        "umount",
        "kill",
        "pkill",
        "killall",
        "curl",
        "wget",
        "ssh",
        "scp",
        "rsync",
        "ftp",
        "nc",
        "ncat",
        "bash",
        "sh",
        "pwsh",
        "powershell",
        "cmd",
        "del",
        "copy",
        "move",
        "ren",
        "rmdir",
        "rd",
        "format",
        "attrib",
    }

    MUTATING_GIT_SUBCOMMANDS = {"add", "commit", "push", "pull", "checkout", "merge", "reset", "rebase", "clean"}

    def __init__(self, router: Optional[Any] = None):
        super().__init__(router)
        self.name = "ShellAgent"

    def _coerce_command(self, command: str) -> List[str]:
        if not isinstance(command, str):
            raise ValueError("command must be a string")
        cleaned = command.strip()
        if not cleaned:
            raise ValueError("command is required")
        if len(cleaned) > 2000:
            raise ValueError("command exceeds the safe execution limit")
        if re.search(r"[`$;|&]", cleaned):
            raise ValueError("command chaining and shell metacharacters are not allowed")
        try:
            parsed = shlex.split(cleaned, posix=True)
        except ValueError as exc:
            raise ValueError(f"unparseable command: {exc}") from exc
        if not parsed:
            raise ValueError("command is empty after parsing")
        return parsed

    def _policy(self, command: str, *, allow_mutating: bool = False) -> Dict[str, Any]:
        try:
            argv = self._coerce_command(command)
        except ValueError as exc:
            return {
                "allowed": False,
                "reason": str(exc),
                "command": command,
                "argv": [],
                "allow_mutating": allow_mutating,
            }

        executable = os.path.basename(argv[0]).lower()
        if executable in self.BLOCKED_COMMANDS:
            return {
                "allowed": False,
                "reason": f"command '{executable}' is blocked for safety",
                "command": command,
                "argv": argv,
                "allow_mutating": allow_mutating,
            }

        if executable not in self.ALLOWED_COMMANDS:
            return {
                "allowed": False,
                "reason": f"command '{executable}' is not in the allowlist",
                "command": command,
                "argv": argv,
                "allow_mutating": allow_mutating,
            }

        if executable == "git":
            subcommand = (argv[1].lower() if len(argv) > 1 else "")
            if subcommand in self.MUTATING_GIT_SUBCOMMANDS and not allow_mutating:
                return {
                    "allowed": False,
                    "reason": f"git {subcommand} requires allow_mutating=True",
                    "command": command,
                    "argv": argv,
                    "allow_mutating": allow_mutating,
                }

        return {
            "allowed": True,
            "reason": "safe command policy passed",
            "command": command,
            "argv": argv,
            "allow_mutating": allow_mutating,
        }

    async def run(self, command: str, cwd: Optional[str] = None, env: Optional[dict] = None, stream: bool = False, allow_mutating: bool = False, timeout: int = 120) -> dict:  # type: ignore
        safe_env = {**os.environ, **(env or {})}
        policy = self._policy(command, allow_mutating=allow_mutating)
        if not policy["allowed"]:
            return {
                "status": "blocked",
                "agent": self.name,
                "command": command,
                "cwd": cwd,
                "policy": policy,
            }

        target_cwd = cwd or os.getcwd()
        proc = await asyncio.create_subprocess_exec(
            *policy["argv"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=target_cwd,
            env=safe_env,
            limit=1024 * 64,
        )

        if stream:
            try:
                if proc.stdout:
                    async for line in proc.stdout:
                        print(f"[ShellAgent] {line.decode(errors='replace').rstrip()}")
            except Exception:
                pass

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {
                "status": "timeout",
                "agent": self.name,
                "command": command,
                "cwd": target_cwd,
                "stdout": "",
                "stderr": "Command timed out.",
                "returncode": None,
                "policy": policy,
            }

        payload = {
            "status": "ok" if proc.returncode == 0 else "error",
            "agent": self.name,
            "command": command,
            "cwd": target_cwd,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "returncode": proc.returncode,
            "policy": policy,
        }
        return payload

    async def kill(self, pid: int) -> None:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    async def shutdown(self) -> None:
        print("[ShellAgent] shutting down.")
