# mammoth_os/agents/field_ops_agent.py

import os
from typing import Dict, Any
from .base_agent import BaseAgent


class FieldOpsAgent(BaseAgent):
    """
    FieldOpsAgent
    - Handles field-day content (Monday ops)
    - Wildlife notes, plant notes, terrain notes
    - Generates field prompts
    - Writes field logs (approval-gated)
    - Safe read-only operations for reviewing logs
    """

    name = "FieldOpsAgent"

    def __init__(self, router):
        super().__init__(router)


    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "generate_field_prompt":
            return self._generate_field_prompt(target, details)

        if action_type == "write_field_log":
            return self._write_field_log(target, details)

        if action_type == "read_field_log":
            return self._read_field_log(target)

        if action_type == "generate_plant_note":
            return self._generate_plant_note(target, details)

        if action_type == "generate_wildlife_note":
            return self._generate_wildlife_note(target, details)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    # --- Core operations ----------------------------------------------------

    def _generate_field_prompt(self, target: str, details: Dict[str, Any]):
        """
        Generate a Monday field-day prompt.
        """
        season = details.get("season", "summer")
        prompt = (
            f"Field Ops — {season.capitalize()} Run.\n"
            "Capture 2–3 observations:\n"
            "- A plant with a survival or medicinal angle\n"
            "- A wildlife behavior or track\n"
            "- A terrain feature that teaches a skill\n"
            "Keep it rugged. Keep it real. Keep it True XXII."
        )

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(prompt)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_field_prompt",
            "target": target,
            "prompt": prompt,
        }

    def _write_field_log(self, target: str, details: Dict[str, Any]):
        """
        Write a field log entry.
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
            "action": "write_field_log",
            "target": target,
        }

    def _read_field_log(self, target: str):
        """
        Read field logs (safe, read-only).
        """
        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "status": "ok",
            "agent": self.name,
            "action": "read_field_log",
            "target": target,
            "content_preview": content[:300],
        }

    def _generate_plant_note(self, target: str, details: Dict[str, Any]):
        """
        Generate a plant identification note.
        """
        plant = details.get("plant", "Unknown plant")
        note = (
            f"Plant Note — {plant}\n"
            "Identify structure, leaves, scent, and habitat.\n"
            "If medicinal: note traditional uses.\n"
            "If survival-relevant: note fire, cordage, or first-aid value."
        )

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(note)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_plant_note",
            "target": target,
            "note": note,
        }

    def _generate_wildlife_note(self, target: str, details: Dict[str, Any]):
        """
        Generate a wildlife observation note.
        """
        animal = details.get("animal", "Unknown animal")
        note = (
            f"Wildlife Note — {animal}\n"
            "Observe movement, tracks, feeding signs, and behavior.\n"
            "Note any survival-relevant patterns (water sources, shelter, danger)."
        )

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(note)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_wildlife_note",
            "target": target,
            "note": note,
        }
