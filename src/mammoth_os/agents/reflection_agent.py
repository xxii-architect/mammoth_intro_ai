# mammoth_os/agents/reflection_agent.py

import os
from typing import Dict, Any

from .base_agent import BaseAgent


class ReflectionAgent(BaseAgent):
    """
    ReflectionAgent (Minimalist OS tone)
    - Analyzes code
    - Generates diagnostic reports
    - Read-only operations (safe)
    """

    name = "ReflectionAgent"

    def __init__(self, router):
        super().__init__(router)


    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "analyze_code":
            return self._analyze_code(target)

        if action_type == "generate_report":
            return self._generate_report(target)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    # --- Analysis operations ------------------------------------------------

    def _analyze_code(self, target: str):
        """
        Analyze a code file.
        For now: simple static analysis placeholder.
        Later: integrate DeepSeek or your LLM analysis pipeline.
        """
        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        line_count = len(content.splitlines())
        char_count = len(content)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "analyze_code",
            "target": target,
            "metrics": {
                "lines": line_count,
                "characters": char_count,
            },
        }

    def _generate_report(self, target: str):
        """
        Generate a diagnostic report.
        For now: simple placeholder.
        Later: integrate deeper analysis.
        """
        exists = os.path.exists(target)

        report = {
            "file_exists": exists,
            "path": target,
            "notes": "ReflectionAgent diagnostic report.",
        }

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_report",
            "target": target,
            "report": report,
        }
