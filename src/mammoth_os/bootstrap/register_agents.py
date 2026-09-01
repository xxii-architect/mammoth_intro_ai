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
            agent_id="classifier",
            name="ClassifierAgent",
            version="1.0.0",
            capabilities=["intent_classification", "routing", "labeling"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://classifier",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Intent routing and structured request labeling."},
        ),
        AgentManifest(
            agent_id="orchestrator",
            name="OrchestratorAgent",
            version="1.0.0",
            capabilities=["multi_agent_routing", "plan_validation", "conflict_resolution"],
            status=AgentStatus.ACTIVE,
            level=6,
            dependencies=["planner", "classifier"],
            endpoint="local://orchestrator",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Top-level cognitive coordinator for multi-agent work."},
        ),
        AgentManifest(
            agent_id="cache",
            name="CacheAgent",
            version="1.0.0",
            capabilities=["cache_get", "cache_set", "cache_invalidate"],
            status=AgentStatus.ACTIVE,
            level=2,
            dependencies=[],
            endpoint="local://cache",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Cache operations with safe fallback storage."},
        ),
        AgentManifest(
            agent_id="search",
            name="SearchAgent",
            version="1.0.0",
            capabilities=["workspace_search", "search_ranking", "summaries"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://search",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Grounded search across provided and workspace sources."},
        ),
        AgentManifest(
            agent_id="self_heal",
            name="SelfHealAgent",
            version="1.0.0",
            capabilities=["health_monitoring", "restart_attempts", "task_rerouting"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://self_heal",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Runtime recovery and reroute coordination."},
        ),
        AgentManifest(
            agent_id="evolution",
            name="EvolutionAgent",
            version="1.0.0",
            capabilities=["upgrade_analysis", "ab_test_planning", "regression_detection"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://evolution",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Measures agent maturity and recommends improvement work."},
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
        AgentManifest(
            agent_id="planner",
            name="PlannerAgent",
            version="2.0.0",
            capabilities=["goal_planning", "dag_creation", "plan_validation"],
            status=AgentStatus.ACTIVE,
            level=5,
            dependencies=["curriculum"],
            endpoint="local://planner",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Converts goals into validated DAG execution plans."},
        ),
        AgentManifest(
            agent_id="auth",
            name="AuthAgent",
            version="2.0.0",
            capabilities=["jwt_auth", "token_issue", "scope_enforcement", "session_tracking"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://auth",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "JWT-based authentication and permission scope enforcement."},
        ),
        AgentManifest(
            agent_id="build",
            name="BuildAgent",
            version="2.0.0",
            capabilities=["lint", "test", "build", "multi_language_support"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://build",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Full build pipeline: lint, compile, test, package."},
        ),
        AgentManifest(
            agent_id="executor",
            name="ExecutorAgent",
            version="2.0.0",
            capabilities=["code_execution", "sandboxed_exec", "timeout_enforced"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://executor",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Executes code in isolated subprocesses with timeout enforcement."},
        ),
        AgentManifest(
            agent_id="filesystem",
            name="FileSystemAgent",
            version="2.0.0",
            capabilities=["read", "write", "delete", "index", "path_traversal_protection"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://filesystem",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Scoped file system operations with audit log."},
        ),
        AgentManifest(
            agent_id="deploy",
            name="DeployAgent",
            version="2.0.0",
            capabilities=["docker_deploy", "systemd_deploy", "health_check", "rollback_support"],
            status=AgentStatus.ACTIVE,
            level=5,
            dependencies=[],
            endpoint="local://deploy",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Docker and systemd deployments with health checks and rollback."},
        ),
        AgentManifest(
            agent_id="database",
            name="DatabaseAgent",
            version="2.0.0",
            capabilities=["async_pool", "query", "execute", "transaction", "migration_support"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://database",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "PostgreSQL interface with fallback in-memory store."},
        ),
        AgentManifest(
            agent_id="vector_store",
            name="VectorStoreAgent",
            version="2.0.0",
            capabilities=["cosine_similarity", "privacy_scoped_collections", "ttl_support", "tag_filtering"],
            status=AgentStatus.ACTIVE,
            level=4,
            dependencies=[],
            endpoint="local://vector_store",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Embedding storage and semantic search with privacy scoping."},
        ),
        AgentManifest(
            agent_id="scheduler",
            name="SchedulerAgent",
            version="2.0.0",
            capabilities=["cron_scheduling", "graceful_degradation", "job_management"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://scheduler",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Cron-based job scheduler with graceful fallback."},
        ),
        AgentManifest(
            agent_id="snapshot",
            name="SnapshotAgent",
            version="2.0.0",
            capabilities=["versioned_snapshots", "structured_diff", "registry_capture"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://snapshot",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Versioned state snapshots with diff and restore support."},
        ),
        AgentManifest(
            agent_id="config_manager",
            name="ConfigManagerAgent",
            version="2.0.0",
            capabilities=["hot_reload", "scoped_config", "event_driven_updates"],
            status=AgentStatus.ACTIVE,
            level=3,
            dependencies=[],
            endpoint="local://config_manager",
            registered_at=now(),
            last_heartbeat=now(),
            metadata={"description": "Global and per-agent configuration management."},
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
