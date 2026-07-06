class BuildAgent(BaseAgent):# type: ignore
    """
    Manages the full build pipeline: lint → compile → test → package.
    Integrates with ShellAgent for command execution and emits
    BUILD_COMPLETE or BUILD_FAILED events upon completion.
    """

    async def build(self, project_path: str, language: str, config: dict = None) -> dict:# type: ignore
        config = config or {}
        results = {}

        # Step 1: Lint
        lint_cmd = config.get("lint_command", f"cd {project_path} && flake8 .")
        results["lint"] = await self._run_step("LINT", lint_cmd)

        # Step 2: Test
        test_cmd = config.get("test_command", f"cd {project_path} && pytest --tb=short")
        results["tests"] = await self._run_step("TEST", test_cmd)

        # Step 3: Build artifact
        build_cmd = config.get("build_command", f"cd {project_path} && python setup.py build")
        results["build"] = await self._run_step("BUILD", build_cmd)

        success = all(r.get("exit_code") == 0 for r in results.values())
        event_type = "BUILD_COMPLETE" if success else "BUILD_FAILED"
        await self.emit_event(event_type, {"project_path": project_path, "results": results})
        return {"success": success, **results}

    async def _run_step(self, step_name: str, command: str) -> dict:# type: ignore
        self.log("INFO", "Build step: %s → %s", step_name, command)
        # Delegates to ShellAgent via event
        ...

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "BUILD_REQUEST":
            await self.build(**event.payload)

    async def shutdown(self) -> None:
        self.log("INFO", "BuildAgent shutting down.")