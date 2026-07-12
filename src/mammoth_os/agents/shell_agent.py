class ShellAgent(BaseAgent):# type: ignore
    """
    Executes arbitrary shell commands in a controlled environment.
    Streams stdout/stderr via WebSocket. Tracks running processes
    and supports graceful termination.
    """

    async def run(self, command: str, cwd: str = None, env: dict = None, stream: bool = False) -> dict:# type: ignore
        import os
        safe_env = {**os.environ, **(env or {})}
        proc = await asyncio.create_subprocess_shell(# type: ignore
            command,
            stdout=asyncio.subprocess.PIPE,# type: ignore
            stderr=asyncio.subprocess.PIPE,# type: ignore
            cwd=cwd,
            env=safe_env,
        )
        if stream:
            # Emit lines as they arrive
            async for line in proc.stdout:
                await self.emit_event("SHELL_OUTPUT", {"line": line.decode(), "pid": proc.pid})
        stdout, stderr = await proc.communicate()
        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": proc.returncode,
        }

    async def kill(self, pid: int) -> None:
        import os, signal
        os.kill(pid, signal.SIGTERM)

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "SHELL_RUN":
            await self.run(**event.payload)

    async def shutdown(self) -> None:
        self.log("INFO", "ShellAgent shutting down.")
