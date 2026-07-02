# mammoth_os/agents/research_agent.py

from typing import Dict, Any
from .base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    """
    ResearchAgent
    -------------
    Lightweight research agent used by the Cortex router.
    Provides structured responses for research-related prompts.
    """

    name = "ResearchAgent"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for ResearchAgent.
        Returns a structured research intent for the router to handle.
        """
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "ResearchAgent received the prompt. Implement deeper research logic later."
        }

    # Optional: extend with specific research actions later
    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        return {
            "status": "intent",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "details": details,
        }
