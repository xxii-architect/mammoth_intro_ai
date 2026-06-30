# src/mammoth_os/cortex/__init__.py

from typing import Optional
from mammoth_os.cortex.router import CortexRouter
from mammoth_os.core_types import ExecutionConfig
from mammoth_os.agents.coding_agent import CodingAgent
from mammoth_os.agents.curriculum_agent import CurriculumAgent
from mammoth_os.agents.reflection_agent import ReflectionAgent
from mammoth_os.agents.market_intel_agent import MarketIntelAgent
from mammoth_os.agents.brand_voice_agent import BrandVoiceAgent
from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent
from mammoth_os.agents.field_ops_agent import FieldOpsAgent
from mammoth_os.agents.autonomous_task_engine import AutonomousTaskEngine

def build_cortex(
    approval_mode: str = "vs_code_webview",
    approval_handler=None,
    execution_config: Optional[ExecutionConfig] = None,
) -> CortexRouter:
    """
    Build and return a CortexRouter with all agents instantiated and registered.

    Parameters
    - approval_mode: "auto", "semi", "vs_code_webview", etc.
    - approval_handler: optional callable to handle approval requests
    - execution_config: optional ExecutionConfig to control timeouts/retries/risk
    """
    # create router first (empty agents dict for now)
    router = CortexRouter(
        agents={},
        approval_mode=approval_mode,
        approval_handler=approval_handler,
        execution_config=execution_config,
    )

    # instantiate agents with the router
    agents = {
        "CodingAgent": CodingAgent(router),
        "CurriculumAgent": CurriculumAgent(router),
        "ReflectionAgent": ReflectionAgent(router),
        "MarketIntelAgent": MarketIntelAgent(router),
        "BrandVoiceAgent": BrandVoiceAgent(router),
        "PlantTheSeedAgent": PlantTheSeedAgent(router),
        "FieldOpsAgent": FieldOpsAgent(router),
        "AutonomousTaskEngine": AutonomousTaskEngine(router),
    }

    # register agents on the router and return it
    router.agents = agents
    return router
