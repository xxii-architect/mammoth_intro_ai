from __future__ import annotations

import asyncio
import subprocess
import time
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class DeployAgent(BaseAgent):  # type: ignore
    """
    Manages Docker and systemd deployments with health-check and rollback support.
    Emits DEPLOY_SUCCESS, DEPLOY_FAILED, or DEPLOY_ROLLBACK events.
    """

    name = "DeployAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._deploy_log: List[Dict[str, Any]] = []

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    async def _run_cmd(self, cmd: str, timeout: int = 120) -> Dict[str, Any]:
        import datetime
        self.log("INFO", f"Running: {cmd}")
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            result = {
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "command": cmd,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        except subprocess.TimeoutExpired:
            result = {"exit_code": 124, "stdout": "", "stderr": "Command timed out.", "command": cmd}
        except Exception as exc:
            result = {"exit_code": 1, "stdout": "", "stderr": str(exc), "command": cmd}
        self._deploy_log.append(result)
        return result

    async def health_check(self, service_name: str, retries: int = 5, delay_sec: int = 3) -> bool:
        for attempt in range(retries):
            result = await self._run_cmd(f"docker service ps {service_name} --filter desired-state=running -q")
            if result["exit_code"] == 0 and result["stdout"].strip():
                return True
            if attempt < retries - 1:
                await asyncio.sleep(delay_sec)
        return False

    async def rollback(self, service_name: str) -> Dict[str, Any]:
        result = await self._run_cmd(f"docker service rollback {service_name}")
        event_payload = {"service": service_name, "rolled_back": result["exit_code"] == 0}
        await self.emit_event("DEPLOY_ROLLBACK", event_payload)
        return {"status": "ok" if result["exit_code"] == 0 else "error", "agent": self.name, "action": "rollback", "service": service_name, **result}

    async def deploy_docker(self, image: str, service_name: str, env: Optional[dict] = None) -> Dict[str, Any]:
        env_flags = " ".join(f"-e {k}={v}" for k, v in (env or {}).items())
        cmd = f"docker service update --image {image} {env_flags} {service_name}".strip()
        result = await self._run_cmd(cmd)
        if result["exit_code"] == 0:
            healthy = await self.health_check(service_name)
            if healthy:
                await self.emit_event("DEPLOY_SUCCESS", {"service": service_name, "image": image})
                return {"status": "ok", "agent": self.name, "action": "deploy_docker", "service": service_name, "image": image, "healthy": True, "summary": f"Deployed {image} to {service_name} successfully."}
            await self.rollback(service_name)
            return {"status": "error", "agent": self.name, "action": "deploy_docker", "service": service_name, "image": image, "healthy": False, "summary": "Deployment failed health check. Rolled back."}
        await self.emit_event("DEPLOY_FAILED", {"service": service_name})
        return {"status": "error", "agent": self.name, "action": "deploy_docker", "service": service_name, "image": image, "stderr": result["stderr"], "summary": f"Deploy command failed for {service_name}."}

    async def deploy_systemd(self, service_name: str, git_pull: bool = True, restart: bool = True) -> Dict[str, Any]:
        steps = []
        if git_pull:
            pull = await self._run_cmd("git -C /opt/mammothos/mammoth_intro_ai pull origin main")
            steps.append({"step": "git_pull", **pull})
        if restart:
            restart_result = await self._run_cmd(f"sudo systemctl restart {service_name}")
            steps.append({"step": "systemctl_restart", **restart_result})
            status_result = await self._run_cmd(f"sudo systemctl is-active {service_name}")
            is_active = status_result["stdout"].strip() == "active"
            steps.append({"step": "health_check", "active": is_active, **status_result})
            if is_active:
                await self.emit_event("DEPLOY_SUCCESS", {"service": service_name, "type": "systemd"})
                return {"status": "ok", "agent": self.name, "action": "deploy_systemd", "service": service_name, "steps": steps, "summary": f"{service_name} restarted and is active."}
            return {"status": "error", "agent": self.name, "action": "deploy_systemd", "service": service_name, "steps": steps, "summary": f"{service_name} did not become active after restart."}
        return {"status": "ok", "agent": self.name, "action": "deploy_systemd", "service": service_name, "steps": steps, "summary": "Deploy steps completed."}

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            action = str(payload.get("action") or "status").strip().lower()
            service = str(payload.get("service") or payload.get("service_name") or "").strip()
            image = str(payload.get("image") or "").strip()
            env = payload.get("env") or {}
        else:
            action = "status"
            service = ""
            image = ""
            env = {}

        if action == "deploy_docker":
            if not image or not service:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide image and service_name for Docker deploy."}
            return await self.deploy_docker(image=image, service_name=service, env=env)

        if action in ("deploy_systemd", "systemd"):
            if not service:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide service name for systemd deploy."}
            return await self.deploy_systemd(service_name=service)

        if action == "rollback":
            if not service:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide service name to rollback."}
            return await self.rollback(service_name=service)

        if action == "health_check":
            if not service:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide service name for health check."}
            healthy = await self.health_check(service)
            return {"status": "ok", "agent": self.name, "action": "health_check", "service": service, "healthy": healthy, "summary": f"{service} is {'healthy' if healthy else 'unhealthy'}."}

        return {
            "status": "ok",
            "agent": self.name,
            "action": "status",
            "deploy_log_count": len(self._deploy_log),
            "summary": "DeployAgent is active and ready.",
            "quality_flags": ["docker_deploy", "systemd_deploy", "health_check", "rollback_support"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        if getattr(event, "event_type", None) == "DEPLOY_REQUEST":
            payload = getattr(event, "payload", {}) or {}
            await self.run(payload)

    async def shutdown(self) -> None:
        self.log("INFO", f"DeployAgent shutting down. {len(self._deploy_log)} deploy ops logged.")

