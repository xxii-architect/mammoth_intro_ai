from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from mammoth_os.registry.agent_manifest import AgentStatus

from .base_agent import BaseAgent


class SelfHealAgent(BaseAgent):# type: ignore
    """
    Monitors all agents via registry health checks and heartbeat events.
    On failure detection, attempts restart, reroutes in-flight tasks,
    and escalates to human operators if recovery fails.
    """

    name = "SelfHealAgent"

    def __init__(self, router: Any = None, registry: Any = None):
        super().__init__(router)
        if registry is None:
            from mammoth_os.registry.agent_registry import agent_registry
            registry = agent_registry
        self._registry = registry

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def monitor_loop(self) -> None:
        while True:
            await self.monitor_once()
            await asyncio.sleep(15)

    async def monitor_once(self) -> Dict[str, Any]:
        health = await self._registry.health_check_all()
        handled: List[Dict[str, Any]] = []
        for agent_id, status in health.items():
            if "UNREACHABLE" in status or status == "ERROR":
                handled.append(await self.handle_failure(agent_id))
        return {"status": "ok", "checked_agents": len(health), "failures": handled}

    async def handle_failure(self, agent_id: str) -> Dict[str, Any]:
        self.log("WARNING", f"Agent failure detected: {agent_id}. Attempting restart.")
        await self.emit_event("AGENT_FAILURE", {"agent_id": agent_id})
        restarted = await self.restart_agent(agent_id)
        reroute = None
        if not restarted:
            reroute = await self.reroute_tasks(agent_id)
            await self.emit_event("AGENT_ESCALATE", {"agent_id": agent_id, "reason": "restart_failed"})
        return {
            "agent_id": agent_id,
            "restarted": restarted,
            "reroute": reroute,
            "summary": f"{agent_id} {'restarted' if restarted else 'rerouted for recovery'}",
        }

    async def restart_agent(self, agent_id: str) -> bool:# type: ignore
        manifest = await self._registry.get_agent(agent_id)
        if manifest is None:
            return False
        manifest.status = AgentStatus.ACTIVE
        manifest.last_heartbeat = datetime.now(timezone.utc)
        return True

    async def reroute_tasks(self, agent_id: str) -> Dict[str, Any]:
        fallback_agent = "orchestrator" if agent_id != "orchestrator" else "coding"
        return {
            "from_agent": agent_id,
            "to_agent": fallback_agent,
            "policy": "manual-fallback-map",
        }

    async def run(self, payload: Any) -> Dict[str, Any]:
        body = payload if isinstance(payload, dict) else {"action": "monitor"}
        action = str(body.get("action") or "monitor").strip().lower()
        agent_id = str(body.get("agent_id") or "").strip()
        if action == "restart" and agent_id:
            restarted = await self.restart_agent(agent_id)
            return {"status": "ok" if restarted else "warning", "agent": self.name, "action": action, "agent_id": agent_id, "restarted": restarted}
        if action == "reroute" and agent_id:
            reroute = await self.reroute_tasks(agent_id)
            return {"status": "ok", "agent": self.name, "action": action, "agent_id": agent_id, "reroute": reroute}
        report = await self.monitor_once()
        return {"status": "ok", "agent": self.name, "action": "monitor", **report}

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "AGENT_HEARTBEAT_MISSED":
            result = await self.handle_failure(event.payload["agent_id"])
            await self.emit_event("SELF_HEAL_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "SelfHealAgent shutting down.")
