# mammoth_os/agents/research_agent.py

from typing import Dict, Any, List
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
        Returns a structured research brief the workflow can consume directly.
        """
        objective = str(prompt or "").strip() or "current objective"
        focus = self._infer_focus(objective)
        considerations = self._build_considerations(objective, focus)
        next_actions = self._build_next_actions(focus)
        return {
            "status": "ok",
            "agent": self.name,
            "prompt": objective,
            "focus": focus,
            "summary": self._build_summary(objective, focus),
            "considerations": considerations,
            "next_actions": next_actions,
            "workflow_hints": {
                "needs_validation": "verify" in objective.lower() or "test" in objective.lower(),
                "supports_curriculum": "lesson" in objective.lower() or "curriculum" in objective.lower(),
                "supports_fieldwork": any(token in objective.lower() for token in ("survival", "plant", "field", "outdoor")),
            },
        }

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        prompt = str(details.get("prompt") or target or "").strip()
        return {
            **self.run(prompt),
            "action": action_type,
            "target": target,
            "details": details,
        }

    def _infer_focus(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if any(token in prompt_lower for token in ("lesson", "curriculum", "module", "learner")):
            return "curriculum"
        if any(token in prompt_lower for token in ("survival", "plant", "field", "navigation", "weather")):
            return "field_ops"
        if any(token in prompt_lower for token in ("gear", "compare", "market", "audience", "pricing")):
            return "market_intel"
        if any(token in prompt_lower for token in ("code", "build", "implement", "feature", "ui")):
            return "coding"
        return "general"

    def _build_summary(self, prompt: str, focus: str) -> str:
        if focus == "curriculum":
            return f"Frame {prompt} as a staged lesson flow with clear constraints, outcomes, and coaching checkpoints."
        if focus == "field_ops":
            return f"Treat {prompt} as an operational drill with safety, observation discipline, and a documented checklist."
        if focus == "market_intel":
            return f"Evaluate {prompt} through user value, differentiation, and evidence needed before committing resources."
        if focus == "coding":
            return f"Break {prompt} into implementation scope, integration risk, and targeted verification steps."
        return f"Clarify {prompt} into a concise brief with constraints, assumptions, and next actions."

    def _build_considerations(self, prompt: str, focus: str) -> List[str]:
        base = [
            "Define the desired outcome before execution.",
            "Capture assumptions that could break the workflow later.",
        ]
        if focus == "curriculum":
            return base + [
                "Keep the lesson progression aligned to the learner's current module and difficulty.",
                "Prefer practical, safety-aware examples over abstract exposition.",
            ]
        if focus == "field_ops":
            return base + [
                "Surface environmental and safety constraints first.",
                "Use observable checkpoints so the learner can verify progress in the field.",
            ]
        if focus == "market_intel":
            return base + [
                "Separate evidence from aspiration when describing user demand.",
                "Note what should be validated before monetization claims expand.",
            ]
        if focus == "coding":
            return base + [
                "Identify the smallest integration surface that proves the workflow works end to end.",
                "Tie recommendations to targeted tests or build validation.",
            ]
        return base + [
            "Convert the brief into concrete next actions the downstream agent can execute.",
        ]

    def _build_next_actions(self, focus: str) -> List[str]:
        mapping = {
            "curriculum": [
                "Generate a module-aware lesson brief.",
                "Draft learner checkpoints and reflection prompts.",
            ],
            "field_ops": [
                "Prepare an operational checklist.",
                "Record validation and safety checkpoints.",
            ],
            "market_intel": [
                "Document the target user and pain point.",
                "List the highest-value evidence gaps.",
            ],
            "coding": [
                "Draft an implementation checklist.",
                "Select the smallest targeted validation run.",
            ],
            "general": [
                "Summarize the brief in plain language.",
                "Route the outcome to the next best agent.",
            ],
        }
        return mapping.get(focus, mapping["general"])
