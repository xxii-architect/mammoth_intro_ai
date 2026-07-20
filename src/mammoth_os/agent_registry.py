"""
Mammoth OS — Agent Registry
Central lookup table for all autonomous agents.
"""

from typing import Dict, Type, Any

# Import agents
from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent
from mammoth_os.agents.field_ops_agent import FieldOpsAgent
from mammoth_os.agents.market_intel_agent import MarketIntelAgent
from mammoth_os.agents.reflection_agent import ReflectionAgent
from mammoth_os.agents.brand_voice_agent import BrandVoiceAgent
from mammoth_os.agents.visual_engine_agent import VisualEngineAgent # type: ignore
from mammoth_os.agents.community_engine_agent import CommunityEngineAgent # type: ignore


# ----------------------------------------
# REGISTRY
# ----------------------------------------

AGENT_REGISTRY: Dict[str, Type[Any]] = {
    "plant_the_seed": PlantTheSeedAgent,
    "field_ops": FieldOpsAgent,
    "market_intel": MarketIntelAgent,
    "reflection": ReflectionAgent,
    "brand_voice": BrandVoiceAgent,
    "visual_engine": VisualEngineAgent,
    "community_engine": CommunityEngineAgent,
}


# ----------------------------------------
# LOOKUP
# ----------------------------------------

def get_agent(agent_name: str):
    """
    Return an agent class by name.
    Raises KeyError if not found.
    """
    if agent_name not in AGENT_REGISTRY:
        raise KeyError(f"Agent '{agent_name}' is not registered.")
    return AGENT_REGISTRY[agent_name]


def list_agents() -> Dict[str, Type[Any]]:
    """
    Return the full agent registry.
    """
    return AGENT_REGISTRY.copy()


# ----------------------------------------
# INSTANTIATION
# ----------------------------------------

def create_agent(agent_name: str, **kwargs):
    """
    Instantiate an agent with optional kwargs.
    """
    agent_cls = get_agent(agent_name)
    return agent_cls(**kwargs)
