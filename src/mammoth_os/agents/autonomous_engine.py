"""
Mammoth OS — Autonomous Engine
Central executor for agent-driven tasks.
"""

from typing import Any, Dict
from mammoth_os.agent_registry import create_agent


class AutonomousEngine:
    """
    High-level interface for running tasks through Mammoth OS agents.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run_task(
        self,
        agent_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run a single task through the specified agent.

        Args:
            agent_name: Name of the agent in the registry.
            payload: Dict of task parameters.

        Returns:
            Dict with standardized result:
            {
                "agent": str,
                "ok": bool,
                "data": Any,
                "error": str | None
            }
        """
        try:
            agent = create_agent(agent_name, user_id=self.user_id)
            result = agent.run(payload)

            return {
                "agent": agent_name,
                "ok": True,
                "data": result,
                "error": None,
            }
        except Exception as e:
            return {
                "agent": agent_name,
                "ok": False,
                "data": None,
                "error": str(e),
            }
