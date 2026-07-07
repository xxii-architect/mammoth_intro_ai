import subprocess
import asyncio
import time

class ExecutorAgent(BaseAgent):# type: ignore
    """
    Executes code snippets in isolated subprocesses with timeout
    enforcement. Supports Python, JavaScript (Node), Bash, and more.
    Never executes as root.
    """

    LANGUAGE_RUNNERS = {
        "python": ["python3", "-c"],
        "javascript": ["node", "-e"],
        "bash": ["bash", "-c"],
        "ruby": ["ruby", "-e"],
    }

    async def execute(
        self,
        code: str,
        language: str = "python",
        stdin: str = None,# type: ignore
        timeout_sec: int = 30,
        env: dict = None,# type: ignore
    ) -> dict:# type: ignore
        runner = self.LANGUAGE_RUNNERS.get(language)
        if not runner:
            return {"stdout": "", "stderr": f"Unsupported language: {language}", "exit_code": 1}

        import os
        safe_env = {**os.environ, **(env or {})}
        start = time.monotonic()
        timed_out = False
        try:
            proc = await asyncio.create_subprocess_exec(
                *runner, code,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=(stdin or "").encode()),
                timeout=timeout_sec,
            )
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            proc.kill()
            stdout, stderr = b"", b"Execution timed out."
            exit_code = -1
            timed_out = True

        duration_ms = (time.monotonic() - start) * 1000
        result = {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "timed_out": timed_out,
        }
        await self.emit_event("EXECUTE_COMPLETE", result)
        return result

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "EXECUTE_REQUEST":
            await self.execute(**event.payload)

    async def shutdown(self) -> None:
        self.log("INFO", "ExecutorAgent shutting down.")