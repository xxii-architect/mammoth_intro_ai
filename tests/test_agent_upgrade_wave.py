import asyncio

import api_server
from mammoth_os import agent_registry as agent_registry_mod
from mammoth_os.agents import planner_agent as planner_agent_mod
from mammoth_os.agents.base_agent import BaseAgent
from mammoth_os.agents.cache_agent import CacheAgent
from mammoth_os.agents.classifier_agent import ClassifierAgent
from mammoth_os.agents.community_engine_agent import CommunityEngineAgent
from mammoth_os.agents.evolution_agent import EvolutionAgent
from mammoth_os.agents.orchestrator_agent import OrchestratorAgent
from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent
from mammoth_os.agents.search_agent import SearchAgent
from mammoth_os.agents.self_heal_agent import SelfHealAgent


def test_classifier_routes_guide_and_code_requests():
    agent = ClassifierAgent()

    guide_result = asyncio.run(agent.run({"text": "Give me a tour of the MammothOS architecture and SDK"}))
    code_result = asyncio.run(agent.run({"text": "Debug this failing build and patch the code"}))

    assert guide_result["target_agent"] == "mammoth_guide"
    assert guide_result["intent"] == "guide"
    assert code_result["target_agent"] == "coding"
    assert code_result["intent"] == "coding"


def test_orchestrator_run_returns_structured_summary(monkeypatch):
    async def fake_create_plan(self, goal, constraints=None):
        return {
            "plan_id": "plan-1",
            "goal": goal,
            "tasks": [{"task_id": "task-1", "agent": "tutor", "input": {"goal": goal}, "depends_on": []}],
            "estimated_duration_sec": 10,
        }

    async def fake_validate_plan(self, plan):
        return True, []

    monkeypatch.setattr(planner_agent_mod.PlannerAgent, "create_plan", fake_create_plan)
    monkeypatch.setattr(planner_agent_mod.PlannerAgent, "validate_plan", fake_validate_plan)

    result = asyncio.run(OrchestratorAgent().run({"goal": "Ship a guided lesson flow"}))

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert "valid plan" in result["summary"].lower()
    assert result["quality_flags"] == ["validated_plan"]


def test_lowest_rated_agents_now_score_strong_or_better():
    for agent_id in (
        "plant_the_seed_agent",
        "community_engine_agent",
        "classifier_agent",
        "orchestrator_agent",
        "cache_agent",
        "search_agent",
        "self_heal_agent",
        "evolution_agent",
    ):
        snapshot = api_server._agent_quality_snapshot(agent_id)
        assert snapshot["quality_score"] >= 84
        assert snapshot["quality_tier"] in {"strong", "top-tier"}


def test_seed_and_community_agents_use_base_agent_runtime():
    assert isinstance(PlantTheSeedAgent(), BaseAgent)
    assert isinstance(CommunityEngineAgent(), BaseAgent)


def test_registry_loads_classifier_and_orchestrator():
    assert isinstance(agent_registry_mod.load_agent("classifier"), ClassifierAgent)
    assert isinstance(agent_registry_mod.load_agent("orchestrator"), OrchestratorAgent)


def test_cache_search_self_heal_and_evolution_agents_are_usable():
    cache = CacheAgent()
    cache_result = asyncio.run(cache.run({"action": "set", "key": "alpha", "value": "beta", "ttl_sec": 60}))
    lookup_result = asyncio.run(cache.run({"action": "get", "key": "alpha"}))
    search_result = asyncio.run(SearchAgent().run({"query": "PlannerAgent"}))
    evolution_result = asyncio.run(EvolutionAgent().run({"action": "suggest"}))

    class StubRegistry:
        async def health_check_all(self):
            return {"coding": "ACTIVE", "guide": "ERROR"}

        async def get_agent(self, agent_id):
            class Manifest:
                status = None
                last_heartbeat = None
            return Manifest()

    self_heal_result = asyncio.run(SelfHealAgent(registry=StubRegistry()).run({"action": "monitor"}))

    assert cache_result["status"] == "ok"
    assert lookup_result["hit"] is True
    assert search_result["status"] == "ok"
    assert evolution_result["status"] == "ok"
    assert self_heal_result["status"] == "ok"
