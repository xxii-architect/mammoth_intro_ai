# Mammoth OS — Agent Registry (Lazy Loading)
# Prevents circular imports by loading agents only when they are actually used.

from typing import Callable, Dict

from mammoth_os.cortex.router import CortexRouter
router = CortexRouter()

def load_agent(agent_name: str, router=None):
    """
    Dynamically import and instantiate an agent only when needed.
    This avoids circular imports and startup crashes.
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
        from mammoth_os.agents.visual_engine_agent import VisualEngineAgent # type: ignore
        return VisualEngineAgent()

    if agent_name == "community_engine":
        from mammoth_os.agents.community_engine_agent import CommunityEngineAgent
        return CommunityEngineAgent()

    if agent_name == "research":
        from mammoth_os.agents.research_agent import ResearchAgent
        return ResearchAgent() # type: ignore
    
    if agent_name == "coding":
        from mammoth_os.agents.coding_agent import CodingAgent
        return CodingAgent(router)
    if agent_name == "custodial":
        from mammoth_os.agents.custodial_agent import CustodialAgent
        return CustodialAgent(router)


    raise ValueError(f"Unknown agent '{agent_name}'")


# Public registry — lazy wrappers
AGENTS: Dict[str, Callable[[str], str]] = {
    "plant_the_seed": lambda prompt: load_agent("plant_the_seed").run(prompt), # type: ignore
    "field_ops": lambda prompt: load_agent("field_ops").run(prompt), # type: ignore
    "market_intel": lambda prompt: load_agent("market_intel").run(prompt),# type: ignore
    "reflection": lambda prompt: load_agent("reflection").run(prompt),# type: ignore
    "brand_voice": lambda prompt: load_agent("brand_voice").run(prompt),# type: ignore
    "visual_engine": lambda prompt: load_agent("visual_engine").run(prompt),# type: ignore
    "community_engine": lambda prompt: load_agent("community_engine").run(prompt),# type: ignore
    "research": lambda prompt: load_agent("research").run(prompt),# type: ignore
    "coding": lambda prompt: load_agent("coding", router).run(prompt), # type: ignore
    "custodial": lambda prompt: load_agent("custodial", router).run(prompt), # type: ignore
 load_agent("coding", router).run(prompt), # type: ignore
} # type: ignore
