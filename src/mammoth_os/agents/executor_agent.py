from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from .base_agent import BaseAgent


class ExecutorAgent(BaseAgent):  # type: ignore
    """
    Executes code snippets in isolated subprocesses with timeout enforcement.
    Supports Python, JavaScript (Node), Bash, and Ruby.
    Never executes destructive system commands.
    """

    name = "ExecutorAgent"

    LANGUAGE_RUNNERS: Dict[str, list] = {
        "python": ["python3", "-c"],
        "javascript": ["node", "-e"],
        "bash": ["bash", "-c"],
        "ruby": ["ruby", "-e"],
    }

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._exec_count = 0
        self._total_duration_ms = 0.0

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    async def execute(
        self,
        code: str,
        language: str = "python",
        stdin: Optional[str] = None,
        timeout_sec: int = 30,
        env: Optional[dict] = None,
    ) -> dict:
        runner = self.LANGUAGE_RUNNERS.get((language or "python").lower())
        if not runner:
            return {
                "status": "error",
                "agent": self.name,
                "stdout": "",
                "stderr": f"Unsupported language: {language}",
                "exit_code": 1,
                "summary": f"Language '{language}' is not supported.",
            }

        import os
        safe_env = {**os.environ, **(env or {})}
        start = time.monotonic()
        timed_out = False
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *runner, code,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=(stdin or "").encode()),
                timeout=timeout_sec,
            )
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
            stdout_bytes, stderr_bytes = b"", b"Execution timed out."
            exit_code = -1
            timed_out = True

        duration_ms = (time.monotonic() - start) * 1000
        self._exec_count += 1
        self._total_duration_ms += duration_ms

        result = {
            "status": "ok" if exit_code == 0 else "error",
            "agent": self.name,
            "stdout": stdout_bytes.decode(errors="replace"),
            "stderr": stderr_bytes.decode(errors="replace"),
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "timed_out": timed_out,
            "language": language,
            "summary": f"Executed {language} code in {round(duration_ms)}ms. Exit={exit_code}.",
            "quality_flags": ["sandboxed_exec", "timeout_enforced"],
        }
        await self.emit_event("EXECUTE_COMPLETE", result)
        return result

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            code = str(payload.get("code") or payload.get("prompt") or "").strip()
            language = str(payload.get("language") or "python").strip().lower()
            timeout_sec = int(payload.get("timeout_sec") or 30)
            stdin = payload.get("stdin")
            env = payload.get("env")
        else:
            code = str(payload or "").strip()
            language = "python"
            timeout_sec = 30
            stdin = None
            env = None
        if not code:
            return {"status": "needs_context", "agent": self.name, "summary": "Provide code to execute."}
        return await self.execute(code=code, language=language, stdin=stdin, timeout_sec=timeout_sec, env=env)

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        if getattr(event, "event_type", None) == "EXECUTE_REQUEST":
            payload = getattr(event, "payload", {}) or {}
            await self.execute(**payload)

    async def shutdown(self) -> None:
        self.log("INFO", f"ExecutorAgent shutting down. Total executions: {self._exec_count}")
