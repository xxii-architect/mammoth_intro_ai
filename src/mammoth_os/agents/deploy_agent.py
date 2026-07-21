class DeployAgent(BaseAgent):# type: ignore
    """
    Manages Docker and Kubernetes deployments with rollback support.
    Performs post-deployment health checks and emits DEPLOY_SUCCESS
    or DEPLOY_ROLLBACK events.
    """

    async def deploy_docker(self, image: str, service_name: str, env: dict = None) -> dict:# type: ignore
        cmd = f"docker service update --image {image} {service_name}"
        result = await self._run(cmd)
        if result["exit_code"] == 0:
            healthy = await self.health_check(service_name)
            if not healthy:
                await self.rollback(service_name)
                return {"success": False, "reason": "post-deploy health check failed"}
            await self.emit_event("DEPLOY_SUCCESS", {"service": service_name, "image": image})
            return {"success": True}
        await self.emit_event("DEPLOY_FAILED", {"service": service_name})
        return {"success": False, "reason": result["stderr"]}

    async def rollback(self, service_name: str) -> None:
        cmd = f"docker service rollback {service_name}"
        await self._run(cmd)
        await self.emit_event("DEPLOY_ROLLBACK", {"service": service_name})

    async def health_check(self, service_name: str, retries: int = 5) -> bool:
        for _ in range(retries):
            result = await self._run(f"docker service ps {service_name} --filter desired-state=running -q")
            if result["exit_code"] == 0 and result["stdout"].strip():
                return True
            await asyncio.sleep(3)# type: ignore
        return False

    async def _run(self, cmd: str) -> dict:
        ...  # Delegate to ShellAgent

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "DEPLOY_REQUEST":
            await self.deploy_docker(**event.payload)

    async def shutdown(self) -> None:
        self.log("INFO", "DeployAgent shutting down.")
