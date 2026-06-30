# mammoth_os/agents/plant_the_seed_agent.py

import os
from typing import Dict, Any
from .base_agent import BaseAgent


class PlantTheSeedAgent(BaseAgent):
    """
    PlantTheSeedAgent
    - Growth engine for MammothOS + True XXII Supply
    - Generates motivational content
    - Creates onboarding messages
    - Writes progression logs (approval-gated)
    - Safe read-only operations for checking progress
    """

    name = "PlantTheSeedAgent"

    def __init__(self, router):
        super().__init__(router)


    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "generate_motivation":
            return self._generate_motivation(target, details)

        if action_type == "write_progress_log":
            return self._write_progress_log(target, details)

        if action_type == "read_progress":
            return self._read_progress(target)

        if action_type == "generate_daily_seed":
            return self._generate_daily_seed(target)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    # --- Core operations ----------------------------------------------------

    def _generate_motivation(self, target: str, details: Dict[str, Any]):
        """
        Generate a motivational message aligned with True XXII Supply.
        """
        theme = details.get("theme", "growth")
        message = (
            f"Plant the Seed — {theme.capitalize()}.\n"
            "Even small steps compound. Keep moving, keep building, "
            "and trust the process. The work you do today grows roots "
            "you’ll stand on tomorrow."
        )

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(message)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_motivation",
            "target": target,
            "message": message,
        }

    def _write_progress_log(self, target: str, details: Dict[str, Any]):
        """
        Write a progression log entry.
        Approval-gated by Cortex.
        """
        entry = details.get("entry")
        if entry is None:
            return {"status": "error", "reason": "Missing 'entry' in details"}

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

        return {
            "status": "ok",
            "agent": self.name,
            "action": "write_progress_log",
            "target": target,
        }

    def _read_progress(self, target: str):
        """
        Read progress logs (safe, read-only).
        """
        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "status": "ok",
            "agent": self.name,
            "action": "read_progress",
            "target": target,
            "content_preview": content[:300],
        }

    def _generate_daily_seed(self, target: str):
        """
        Generate a daily 'seed' — a small actionable step.
        """
        seed = (
            "Daily Seed:\n"
            "- Learn one new thing.\n"
            "- Build one small piece.\n"
            "- Move one step forward.\n"
            "Small seeds grow into big roots."
        )

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(seed)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_daily_seed",
            "target": target,
            "seed": seed,
        }
