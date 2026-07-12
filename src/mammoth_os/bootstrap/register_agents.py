# mammoth_os/bootstrap/register_agents.py
# Mammoth OS — Agent Registry Bootstrap
# Registers all core agents with AgentRegistry at startup.

from __future__ import annotations

import asyncio
import datetime
import logging

from mammoth_os.registry.agent_registry import agent_registry
from mammoth_os.registry.agent_manifest import AgentManifest, AgentStatus

logger = logging.getLogger("uvicorn.error")


# ─────────────────────────────────────────────
# Core agent manifest definitions
# ─────────────────────────────────────────────

def build_core_manifests() -> list[AgentManifest]:
    """
    Define all core Mammoth OS agents here.
    These should mirror your load_agent()/AGENTS mapping.
    """
    now = datetime.datetime.utcnow

    return [
        AgentManifest(
            agent_id="plant_the_seed",
            name="PlantTheSeedAgent",
            version="1.0.0",
            capabilities=["ideation", "campaign_seed", "story_seed"],
            status=AgentStatus.ACTIVE,
            level=2,
            dependencies=[],
            endpoint="local://plant_the_seed",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Brand and campaign ideation engine."},
        ),
        AgentManifest(
            agent_id="field_ops",
            name="FieldOpsAgent",
            version="1.0.0",
            capabilities=["tasks", "checklists", "ops_flows"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://field_ops",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Operational workflows and field procedures."},
        ),
        AgentManifest(
            agent_id="market_intel",
            name="MarketIntelAgent",
            version="1.0.0",
            capabilities=["research", "competitive_analysis", "trend_scan"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://market_intel",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Market research and intelligence."},
        ),
        AgentManifest(
            agent_id="reflection",
            name="ReflectionAgent",
            version="1.0.0",
            capabilities=["postmortem", "retro", "learning_capture"],
            status=AgentStatus.ACTIVE,
            level=2,
            dependencies=[],
            endpoint="local://reflection",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Reflection and learning capture."},
        ),
        AgentManifest(
            agent_id="brand_voice",
            name="BrandVoiceAgent",
            version="1.0.0",
            capabilities=["tone", "copy", "voice_guides"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://brand_voice",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Brand voice and copy generation."},
        ),
        AgentManifest(
            agent_id="visual_engine",
            name="VisualEngineAgent",
            version="1.0.0",
            capabilities=["visual_briefs", "storyboards", "asset_prompts"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://visual_engine",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Visual concept and asset prompt engine."},
        ),
        AgentManifest(
            agent_id="community_engine",
            name="CommunityEngineAgent",
            version="1.0.0",
            capabilities=["community_programs", "engagement_flows"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://community_engine",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Community and engagement design."},
        ),
        AgentManifest(
            agent_id="research",
            name="ResearchAgent",
            version="1.0.0",
            capabilities=["deep_research", "summaries", "reports"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://research",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Deep research and reporting."},
        ),
        AgentManifest(
            agent_id="coding",
            name="CodingAgent",
            version="1.0.0",
            capabilities=[
                "generate_code",
                "refactor",
                "analyze_codebase",
                "run_tests",
                "write_docs",
                "commit_changes",
            ],
            status=AgentStatus.ACTIVE,
            level=5,
            dependencies=[],
            endpoint="local://coding",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Full-stack code intelligence flagship agent."},
        ),
        AgentManifest(
            agent_id="custodial",
            name="CustodialAgent",
            version="1.0.0",
            capabilities=["cleanup", "maintenance", "housekeeping"],
            status=AgentStatus.ACTIVE,
            level=2,
            dependencies=[],
            endpoint="local://custodial",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "System maintenance and cleanup."},
        ),
    ]


# ─────────────────────────────────────────────
# Bootstrap entrypoint
# ─────────────────────────────────────────────

async def bootstrap_agents() -> None:
    """
    Register all core agents with the AgentRegistry.
    Safe to call at Mammoth OS startup.
    """
    manifests = build_core_manifests()

    logger.info("🦣 Bootstrapping Mammoth OS agents...")
    for manifest in manifests:
        await agent_registry.register(manifest) # type: ignore
        logger.info(
            "Registered agent: %s (%s) level=%d capabilities=%s",
            manifest.agent_id,
            manifest.name,
            manifest.level,
            manifest.capabilities,
        )

    logger.info("🦣 AgentRegistry bootstrap complete.")


def main() -> None:
    """
    Synchronous wrapper so this can be run as a script:
    python -m mammoth_os.bootstrap.register_agents
    """
    asyncio.run(bootstrap_agents())


if __name__ == "__main__":
    main()

