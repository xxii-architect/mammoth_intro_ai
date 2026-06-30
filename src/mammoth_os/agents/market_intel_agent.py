# mammoth_os/agents/market_intel_agent.py

import os
from typing import Dict, Any
from .base_agent import BaseAgent


class MarketIntelAgent(BaseAgent):
    """
    MarketIntelAgent
    - Generates market insights
    - Produces reports
    - Reads data files (safe)
    - Writes intel reports (approval-gated)
    """

    name = "MarketIntelAgent"

    def __init__(self, router):
        super().__init__(router)


    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "generate_insight":
            return self._generate_insight(target, details)

        if action_type == "write_report":
            return self._write_report(target, details)

        if action_type == "read_data":
            return self._read_data(target)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    # --- Core intel operations ---------------------------------------------

    def _generate_insight(self, target: str, details: Dict[str, Any]):
        """
        Generate a market insight.
        Placeholder until connected to your intel engine.
        """
        topic = details.get("topic", "General Market")
        insight = f"Insight for {topic}: demand is steady, opportunities emerging."

        os.makedirs(os.path.dirname(target), exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(insight)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_insight",
            "target": target,
            "insight": insight,
        }

    def _write_report(self, target: str, details: Dict[str, Any]):
        """
        Write a market intelligence report.
        Approval-gated by Cortex.
        """
        content = details.get("content")
        if content is None:
            return {"status": "error", "reason": "Missing 'content' in details"}

        os.makedirs(os.path.dirname(target), exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "write_report",
            "target": target,
        }

    def _read_data(self, target: str):
        """
        Read a data file (safe, read-only).
        """
        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "status": "ok",
            "agent": self.name,
            "action": "read_data",
            "target": target,
            "content_preview": content[:250],
        }
