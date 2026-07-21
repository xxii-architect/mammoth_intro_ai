# mammoth_os/agents/curriculum_agent.py

from typing import Dict, Any
from .base_agent import BaseAgent
import uuid
import re
from datetime import datetime


class CurriculumAgent(BaseAgent):
    """
    CurriculumAgent
    ----------------
    Generates structured curriculum tasks, lessons, and module plans.
    This is a lightweight version that avoids missing dependencies
    and ensures Mammoth OS can boot cleanly.
    """

    name = "CurriculumAgent"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for CurriculumAgent.
        Returns a structured curriculum object generated from a natural-language prompt.

        Lightweight generator: produces modules and lessons with simple heuristics so
        other agents (PlannerAgent, OrchestratorAgent) can consume structured output.
        """
        # Heuristic subject extraction: look for 'for <subject>' or before ':' or use full prompt
        match = re.search(r"for\s+([\w\s\-]+?)(?:[\.,]|$)", prompt, re.IGNORECASE)
        if match:
            subject = match.group(1).strip()
        else:
            # Try before a colon
            parts = prompt.split(":", 1)
            subject = parts[0].strip() if len(parts) > 1 else prompt.strip()
        subject = subject or "Untitled Subject"

        curriculum_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat() + "Z"

        # Generate 3 modules with simple lesson breakdown
        modules = []
        for m in range(1, 4):
            lessons = []
            for l in range(1, 4):
                lesson_id = f"{curriculum_id}-m{m}-l{l}"
                lessons.append({
                    "lesson_id": lesson_id,
                    "title": f"{subject} — Module {m} Lesson {l}",
                    "objectives": [f"Understand concept {m}.{l}", f"Practice problem {m}.{l}"],
                    "estimated_minutes": 15 + (m * 5) + (l * 2),
                })
            modules.append({
                "module_id": f"{curriculum_id}-m{m}",
                "title": f"Module {m}: {['Foundations','Core Skills','Application'][m-1]}",
                "lessons": lessons,
                "estimated_minutes": sum(l["estimated_minutes"] for l in lessons),
            })

        curriculum = {
            "curriculum_id": curriculum_id,
            "title": f"{subject} — Short Curriculum",
            "subject": subject,
            "generated_at": now,
            "modules": modules,
            "estimated_total_minutes": sum(m["estimated_minutes"] for m in modules),
        }

        return {
            "status": "ok",
            "agent": self.name,
            "prompt": prompt,
            "curriculum": curriculum,
        }

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        """
        Action handler for curriculum operations. Supports:
        - 'generate': details can include 'prompt' to create a curriculum
        - fallback: returns intent for manual handling
        """
        if action_type == "generate":
            gen_prompt = details.get("prompt") or target or ""
            return self.run(gen_prompt)

        return {
            "status": "intent",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "details": details,
        }
