# mammoth_os/registry/agent_registry.py
# Mammoth OS — Unified Agent Registry
# Preserves lazy-loading for instantiation.
# Adds AgentManifest tracking, health checks, and status management.

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from mammoth_os.cortex.router import CortexRouter

logger = logging.getLogger("mammoth.registry.agents")
router = CortexRouter()


# ─────────────────────────────────────────────
# MANIFEST LAYER  (new — metadata & health)
# ─────────────────────────────────────────────

class AgentStatus(str, Enum):
    ACTIVE   = "ACTIVE"
    IDLE     = "IDLE"
    ERROR    = "ERROR"
    LOADING  = "LOADING"
    SHUTDOWN = "SHUTDOWN"


@dataclass
class AgentManifest:
    """Describes a registered agent within Mammoth OS."""
    agent_id:       str
    name:           str
    version:        str
    capabilities:   list[str]
    status:         AgentStatus
    level:          int
    dependencies:   list[str]
    endpoint:       str
    registered_at:  datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    last_heartbeat: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    metadata:       dict[str, Any]    = field(default_factory=dict)


class AgentRegistry:
    """
    Centralized manifest registry for all Mammoth OS agents.
    Handles health tracking, status, and discovery.
    Instantiation is still handled by load_agent() below.
    """

    def __init__(self, db_client=None):
        self._agents: dict[str, AgentManifest] = {}
        self._db = db_client
        self._lock = asyncio.Lock()
        logger.info("AgentRegistry initialized.")

    async def register(self, manifest: AgentManifest) -> bool:
        async with self._lock:
            self._agents[manifest.agent_id] = manifest
            if self._db:
                await self._db.upsert_agent(manifest)
            logger.info("Registered: %s v%s (level %d)", manifest.agent_id, manifest.version, manifest.level)
            return True

    async def deregister(self, agent_id: str) -> bool:
        async with self._lock:
            if agent_id not in self._agents:
                logger.warning("Deregister failed — not found: %s", agent_id)
                return False
            del self._agents[agent_id]
            if self._db:
                await self._db.delete_agent(agent_id)
            logger.info("Deregistered: %s", agent_id)
            return True

    async def get_agent(self, agent_id: str) -> Optional[AgentManifest]:
        return self._agents.get(agent_id)

    async def list_agents(
        self,
        level:      Optional[int]         = None,
        status:     Optional[AgentStatus] = None,
        capability: Optional[str]         = None,
    ) -> list[AgentManifest]:
        agents = list(self._agents.values())
        if level      is not None: agents = [a for a in agents if a.level == level]
        if status     is not None: agents = [a for a in agents if a.status == status]
        if capability is not None: agents = [a for a in agents if capability in a.capabilities]
        return agents

    async def update_heartbeat(self, agent_id: str) -> None:
        async with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].last_heartbeat = datetime.datetime.utcnow()

    async def health_check_all(self) -> dict[str, str]:
        """Ping every registered agent's /health endpoint."""
        import aiohttp # type: ignore
        results = {}
        async with aiohttp.ClientSession() as session:
            for agent_id, manifest in self._agents.items():
                try:
                    async with session.get(f"{manifest.endpoint}/health", timeout=5) as resp:
                        if resp.status == 200:
                            manifest.status = AgentStatus.ACTIVE
                            manifest.last_heartbeat = datetime.datetime.utcnow()
                            results[agent_id] = "ACTIVE"
                        else:
                            manifest.status = AgentStatus.ERROR
                            results[agent_id] = "ERROR"
                except Exception as exc:
                    manifest.status = AgentStatus.ERROR
                    results[agent_id] = f"UNREACHABLE: {exc}"
        return results


# Singleton — import this everywhere instead of creating new instances
agent_registry = AgentRegistry()


# ─────────────────────────────────────────────
# INSTANCE LOADER  (your existing code, unchanged)
# ─────────────────────────────────────────────

def load_agent(agent_name: str, router=None):
    """
    Dynamically import and instantiate an agent only when needed.
    Avoids circular imports and startup crashes.
    """
    if agent_name == "plant_the_seed":
        from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent
        return PlantTheSeedAgent()

    if agent_name == "field_ops":
        from mammoth_os.agents.field_ops_agent import FieldOpsAgent
        return FieldOpsAgent()

    if agent_name == "market_intel":
        from mammoth_os.agents.market_intel_agent import MarketIntelAgent
        return MarketIntelAgent()

    if agent_name == "reflection":
        from mammoth_os.agents.reflection_agent import ReflectionAgent
        return ReflectionAgent()

    if agent_name == "brand_voice":
        from mammoth_os.agents.brand_voice_agent import BrandVoiceAgent
        return BrandVoiceAgent()

    if agent_name == "visual_engine":
        from mammoth_os.agents.visual_engine_agent import VisualEngineAgent  # type: ignore
        return VisualEngineAgent()

    if agent_name == "community_engine":
        from mammoth_os.agents.community_engine_agent import CommunityEngineAgent
        return CommunityEngineAgent()

    if agent_name == "research":
        from mammoth_os.agents.research_agent import ResearchAgent
        return ResearchAgent()  # type: ignore

    if agent_name == "coding":
        from mammoth_os.agents.coding_agent import CodingAgent
        return CodingAgent(router) # type: ignore

    if agent_name == "custodial":
        from mammoth_os.agents.custodial_agent import CustodialAgent
        return CustodialAgent(router)

    raise ValueError(f"Unknown agent '{agent_name}'")


# ─────────────────────────────────────────────
# PUBLIC CALL INTERFACE  (your existing lambdas, fixed)
# ─────────────────────────────────────────────

AGENTS: Dict[str, Callable[[str], str]] = {
    "plant_the_seed":  lambda prompt: load_agent("plant_the_seed").run(prompt),       # type: ignore
    "field_ops":       lambda prompt: load_agent("field_ops").run(prompt),             # type: ignore
    "market_intel":    lambda prompt: load_agent("market_intel").run(prompt),          # type: ignore
    "reflection":      lambda prompt: load_agent("reflection").run(prompt),            # type: ignore
    "brand_voice":     lambda prompt: load_agent("brand_voice").run(prompt),           # type: ignore
    "visual_engine":   lambda prompt: load_agent("visual_engine").run(prompt),         # type: ignore
    "community_engine":lambda prompt: load_agent("community_engine").run(prompt),      # type: ignore
    "research":        lambda prompt: load_agent("research").run(prompt),              # type: ignore
    "coding":          lambda prompt: load_agent("coding", router).run(prompt),        # type: ignore
    "custodial":       lambda prompt: load_agent("custodial", router).run(prompt),     # type: ignore
}
