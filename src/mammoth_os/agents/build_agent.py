import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from mammoth_os.agents.base_agent import BaseAgent


class BuildAgent(BaseAgent):  # type: ignore
    """
    Manages the full build pipeline: lint → compile → test → package.
    Integrates with ShellAgent for command execution and emits
    BUILD_COMPLETE or BUILD_FAILED events upon completion.
    """

    name = "BuildAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._logger = logging.getLogger("mammoth.agent.build")

    def _default_commands(self, project_path: str, language: str, config: Dict[str, Any]) -> Dict[str, str]:
        lang = (language or "python").lower()
        project = str(project_path)
        if lang == "node":
            return {
                "lint": config.get("lint_command") or f"cd \"{project}\" && npm run lint -- --max-warnings=0",
                "test": config.get("test_command") or f"cd \"{project}\" && npm test -- --runInBand",
                "build": config.get("build_command") or f"cd \"{project}\" && npm run build",
            }
        return {
            "lint": config.get("lint_command") or f"cd \"{project}\" && python -m compileall .",
            "test": config.get("test_command") or f"cd \"{project}\" && pytest --tb=short",
            "build": config.get("build_command") or f"cd \"{project}\" && python -m build",
        }

    def _validate_project_path(self, project_path: str) -> Path:
        if not project_path or not str(project_path).strip():
            raise ValueError("project_path is required")
        path = Path(project_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")
        return path

    async def _run_step(self, step_name: str, command: str, project_path: str) -> dict:  # type: ignore
        if not command or not str(command).strip():
            return {"step": step_name, "status": "skipped", "exit_code": 0, "stdout": "", "stderr": ""}
        self._logger.info("Build step: %s → %s", step_name, command)
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(project_path),
                text=True,
                capture_output=True,
                timeout=180,
            )
            return {
                "step": step_name,
                "status": "passed" if completed.returncode == 0 else "failed",
                "exit_code": int(completed.returncode),
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "command": command,
            }
        except FileNotFoundError:
            return {"step": step_name, "status": "failed", "exit_code": 127, "stdout": "", "stderr": f"Command not found while running {step_name}.", "command": command}
        except subprocess.TimeoutExpired as exc:
            return {"step": step_name, "status": "failed", "exit_code": 124, "stdout": (exc.stdout or "").strip(), "stderr": (exc.stderr or "Timed out while running the build step.").strip(), "command": command}

    async def build(self, project_path: str, language: str = "python", config: Optional[dict] = None) -> dict:  # type: ignore
        config = config or {}
        project_root = self._validate_project_path(project_path)
        commands = self._default_commands(str(project_root), language, config)
        results = {
            "lint": await self._run_step("LINT", commands.get("lint", ""), str(project_root)),
            "tests": await self._run_step("TEST", commands.get("test", ""), str(project_root)),
            "build": await self._run_step("BUILD", commands.get("build", ""), str(project_root)),
        }
        success = all(step.get("exit_code") == 0 for step in results.values())
        event_type = "BUILD_COMPLETE" if success else "BUILD_FAILED"
        emit = getattr(self, "emit_event", None)
        if callable(emit):
            await emit(event_type, {"project_path": str(project_root), "language": str(language or "python"), "results": results})
        return {"success": success, "project_path": str(project_root), "language": str(language or "python"), "results": results}

    async def run(self, payload) -> dict:
        if isinstance(payload, dict):
            project_path = str(payload.get("project_path") or payload.get("path") or ".").strip()
            language = str(payload.get("language") or "python").strip()
            config = payload.get("config") or {}
        else:
            project_path = str(payload or ".").strip()
            language = "python"
            config = {}
        try:
            result = await self.build(project_path=project_path, language=language, config=config)
            return {
                "status": "ok" if result.get("success") else "error",
                "agent": self.name,
                **result,
                "summary": f"Build {'succeeded' if result.get('success') else 'failed'} for {project_path} ({language}).",
                "quality_flags": ["lint_test_build_pipeline", "multi_language_support"],
            }
        except (FileNotFoundError, ValueError) as exc:
            return {"status": "error", "agent": self.name, "error": str(exc), "summary": str(exc)}

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return None
        if getattr(event, "event_type", None) == "BUILD_REQUEST":
            payload = getattr(event, "payload", {}) or {}
            await self.build(payload.get("project_path", "."), payload.get("language", "python"), payload.get("config"))

    async def shutdown(self) -> None:
        self._logger.info("BuildAgent shutting down.")
