# mammoth_os/registry/agent_registry.py
# Mammoth OS — Unified Agent Registry
# Preserves lazy-loading for instantiation.
# Adds AgentManifest tracking, health checks, and status management.

from __future__ import annotations

import asyncio
import datetime
import inspect
import json
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
    registered_at:  datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    last_heartbeat: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
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
                self._agents[agent_id].last_heartbeat = datetime.datetime.now(datetime.timezone.utc)

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
                            manifest.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
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

    if agent_name in {"browser", "browser_agent"}:
        from mammoth_os.agents.browser_agent import BrowserAgent
        return BrowserAgent(router)

    if agent_name in {"task_queue", "task_queue_agent"}:
        from mammoth_os.agents.task_queue_agent import TaskQueueAgent
        return TaskQueueAgent(router)

    if agent_name == "research":
        from mammoth_os.agents.research_agent import ResearchAgent
        return ResearchAgent(router)  # type: ignore

    if agent_name in {"memory", "memory_agent"}:
        from mammoth_os.agents.memory_agent import MemoryAgent
        return MemoryAgent(router)  # type: ignore

    if agent_name in {"auth", "auth_agent"}:
        from mammoth_os.agents.auth_agent import AuthAgent
        return AuthAgent(router)

    if agent_name in {"build", "build_agent"}:
        from mammoth_os.agents.build_agent import BuildAgent
        return BuildAgent(router)

    if agent_name == "curriculum":
        from mammoth_os.agents.curriculum_agent import CurriculumAgent
        return CurriculumAgent(router)  # type: ignore

    if agent_name == "tutor":
        from mammoth_os.agents.tutor_agent import TutorAgent
        return TutorAgent(router=router)  # type: ignore

    if agent_name == "reasoning":
        from mammoth_os.agents.reasoning_agent import ReasoningAgent
        return ReasoningAgent(router)  # type: ignore

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

def _normalize_runtime_payload(agent_name: str, payload: Any) -> Any:
    if isinstance(payload, dict):
        if agent_name in {"browser", "browser_agent", "task_queue", "task_queue_agent"}:
            normalized = dict(payload)
            if agent_name in {"browser", "browser_agent"} and not normalized.get("url"):
                prompt_value = normalized.get("prompt") or normalized.get("target") or normalized.get("query")
                if isinstance(prompt_value, str) and prompt_value.strip():
                    prompt_value = prompt_value.strip()
                    if prompt_value.startswith(("http://", "https://")):
                        normalized["url"] = prompt_value
                    else:
                        normalized.setdefault("prompt", prompt_value)
            return normalized
        if agent_name in {"plant_the_seed", "market_intel", "reflection", "brand_voice", "community_engine", "tutor", "reasoning", "coding", "field_ops"}:
            normalized = dict(payload)
            if agent_name == "tutor" and isinstance(normalized.get("prompt"), str) and not normalized.get("topic"):
                normalized["topic"] = normalized["prompt"]
            elif agent_name == "reasoning" and isinstance(normalized.get("prompt"), str) and not normalized.get("problem"):
                normalized["problem"] = normalized["prompt"]
            elif "topic" not in normalized and isinstance(normalized.get("prompt"), str):
                normalized["topic"] = normalized["prompt"]
            if agent_name == "coding" and not normalized.get("prompt"):
                prompt_value = normalized.get("task") or normalized.get("description") or normalized.get("content")
                if isinstance(prompt_value, str):
                    normalized["prompt"] = prompt_value
            return normalized
        if agent_name in {"curriculum", "research", "custodial"}:
            if isinstance(payload.get("prompt"), str) and payload.get("prompt").strip():
                return payload["prompt"]
            if isinstance(payload.get("topic"), str) and payload.get("topic").strip():
                return payload["topic"]
            return json.dumps(payload)
    if isinstance(payload, str):
        return payload
    if payload is None:
        return ""
    return str(payload)


def run_agent(agent_name: str, payload: Any = None, router=None) -> Any:
    agent = load_agent(agent_name, router)
    normalized_payload = _normalize_runtime_payload(agent_name, payload)
    result = agent.run(normalized_payload)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


AGENTS: Dict[str, Callable[[Any], Any]] = {
    "plant_the_seed":  lambda prompt: run_agent("plant_the_seed", prompt),           # type: ignore
    "field_ops":       lambda prompt: run_agent("field_ops", prompt),                # type: ignore
    "market_intel":    lambda prompt: run_agent("market_intel", prompt),             # type: ignore
    "reflection":      lambda prompt: run_agent("reflection", prompt),               # type: ignore
    "brand_voice":     lambda prompt: run_agent("brand_voice", prompt),              # type: ignore
    "visual_engine":   lambda prompt: run_agent("visual_engine", prompt),            # type: ignore
    "community_engine":lambda prompt: run_agent("community_engine", prompt),         # type: ignore
    "browser":         lambda prompt: run_agent("browser", prompt),                  # type: ignore
    "task_queue":      lambda prompt: run_agent("task_queue", prompt),               # type: ignore
    "research":        lambda prompt: run_agent("research", prompt),                 # type: ignore
    "curriculum":      lambda prompt: run_agent("curriculum", prompt),               # type: ignore
    "tutor":           lambda prompt: run_agent("tutor", prompt),                    # type: ignore
    "reasoning":       lambda prompt: run_agent("reasoning", prompt, router),        # type: ignore
    "coding":          lambda prompt: run_agent("coding", prompt, router),           # type: ignore
    "custodial":       lambda prompt: run_agent("custodial", prompt, router),        # type: ignore
}


# ─────────────────────────────────────────────
# AUTO-DISCOVERY  — scan agents dir at import
# ─────────────────────────────────────────────

def _auto_register_agents() -> None:
    """
    Scan src/mammoth_os/agents/ for *_agent.py files and register each
    one into agent_registry with a sensible manifest.
    Called once at module import so list_agents() is never empty.
    """
    import datetime
    from pathlib import Path
    agents_dir = Path(__file__).parent / "agents"
    if not agents_dir.exists():
        return

    registered = []
    for fpath in sorted(agents_dir.glob("*_agent.py")):
        stem = fpath.stem  # e.g. "tutor_agent"
        if stem == "base_agent":
            continue
        agent_id = stem  # keep full name as id
        # pretty name: "tutor_agent" → "TutorAgent"
        name = "".join(w.title() for w in stem.split("_"))
        # infer capabilities from the filename
        caps = [stem.replace("_agent", "")]

        manifest = AgentManifest(
            agent_id=agent_id,
            name=name,
            version="v1.0.0",
            capabilities=caps,
            status=AgentStatus.IDLE,
            level=1,
            dependencies=[],
            endpoint=f"internal://{agent_id}",
            registered_at=datetime.datetime.now(datetime.timezone.utc),
            last_heartbeat=datetime.datetime.now(datetime.timezone.utc),
        )
        # Use a synchronous direct insert to avoid asyncio.run() at import time
        agent_registry._agents[agent_id] = manifest
        registered.append(agent_id)

    if registered:
        logger.info("Auto-registered %d agents: %s", len(registered), registered)


# Run auto-discovery immediately so any import of this module populates the registry
_auto_register_agents()
