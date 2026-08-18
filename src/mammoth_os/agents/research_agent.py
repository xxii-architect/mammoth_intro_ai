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
        evidence = self._build_evidence(objective, focus)
        citations = self._build_citations(objective, focus)
        confidence = self._estimate_confidence(focus, objective, evidence)
        return {
            "status": "ok",
            "agent": self.name,
            "prompt": objective,
            "focus": focus,
            "summary": self._build_summary(objective, focus),
            "considerations": considerations,
            "next_actions": next_actions,
            "evidence": evidence,
            "citations": citations,
            "sources": [
                {
                    "type": "direct_prompt",
                    "label": "Current objective",
                    "summary": objective,
                }
            ],
            "confidence": confidence,
            "research_questions": self._build_research_questions(objective, focus),
            "assumptions": self._build_assumptions(focus),
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

    def _estimate_confidence(self, focus: str, prompt: str, evidence: List[str]) -> float:
        base = 0.62
        if focus == "curriculum":
            base += 0.08
        elif focus == "coding":
            base += 0.12
        elif focus == "market_intel":
            base += 0.1
        elif focus == "field_ops":
            base += 0.06
        if evidence:
            base += min(0.18, len(evidence) * 0.04)
        if "verify" in prompt.lower() or "test" in prompt.lower():
            base += 0.06
        return round(min(0.96, max(0.45, base)), 2)

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

    def _build_evidence(self, prompt: str, focus: str) -> List[str]:
        evidence = [
            "The objective is specific enough to turn into an actionable brief.",
            "The intended workflow can be mapped to concrete next steps and verification checks.",
        ]
        if focus == "curriculum":
            evidence.extend([
                "Lesson scope should be tied to learner progress and outcome checkpoints.",
                "Examples and reflection prompts strengthen retention without overloading the learner.",
            ])
        if focus == "field_ops":
            evidence.extend([
                "Operational work requires safety constraints, observable checkpoints, and clear failure criteria.",
                "Evidence of conditions and changes should be captured before and after action.",
            ])
        if focus == "market_intel":
            evidence.extend([
                "The recommendation should separate user demand from assumptions about pricing or adoption.",
                "Evidence gaps are a primary input to the next market validation step.",
            ])
        if focus == "coding":
            evidence.extend([
                "The implementation should be narrowed to the smallest integration surface with a real validation path.",
                "Code changes should be traceable to tests, smoke checks, or explicit acceptance criteria.",
            ])
        if "verify" in prompt.lower() or "test" in prompt.lower():
            evidence.append("Verification steps are explicit and should be used as the decision gate before closure.")
        return evidence

    def _build_citations(self, prompt: str, focus: str) -> List[Dict[str, str]]:
        return [
            {
                "label": "Objective",
                "source": "direct prompt",
                "quote": prompt[:180],
                "why_it_matters": f"This is the anchor for a {focus} research brief and the execution route.",
            },
            {
                "label": "Workflow check",
                "source": "agent brief",
                "quote": "Evidence should be explicit, testable, and tied to a concrete next action.",
                "why_it_matters": "It keeps the output grounded instead of relying on general commentary.",
            },
        ]

    def _build_research_questions(self, prompt: str, focus: str) -> List[str]:
        base = [
            f"What is the true goal behind {prompt}?",
            "Which assumptions need explicit validation before we proceed?",
        ]
        if focus == "curriculum":
            return base + [
                "What learning checkpoint best indicates the learner is ready for the next step?",
                "Which examples are most likely to reduce confusion instead of adding noise?",
            ]
        if focus == "field_ops":
            return base + [
                "What safety or environmental constraints could invalidate the plan?",
                "Which observations confirm whether the field plan is succeeding?",
            ]
        if focus == "market_intel":
            return base + [
                "What user problem is being solved, and what evidence proves it?",
                "Which market signal is strongest versus the weakest assumption?",
            ]
        if focus == "coding":
            return base + [
                "What is the smallest working implementation path?",
                "What validation run proves the integration is safe?",
            ]
        return base + [
            "What is the clearest measurable outcome for this task?",
        ]

    def _build_assumptions(self, focus: str) -> List[str]:
        assumptions = [
            "The task has enough clarity to justify an execution brief without extra discovery work.",
            "Validation should be lighter than full research if the question is narrow and operational.",
        ]
        if focus == "curriculum":
            return assumptions + [
                "Learner readiness and progression matter more than raw content volume.",
            ]
        if focus == "coding":
            return assumptions + [
                "A smaller, testable patch is better than a large speculative refactor.",
            ]
        return assumptions

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
