"""
Mammoth OS — FieldOpsAgent
Generates hands-on field exercises, wildlife observations, terrain challenges,
and practical survival tasks for Monday fieldwork and learning modules.
"""

from typing import Any, Dict, List


class FieldOpsAgent:
    """
    Produces rugged, outdoors-focused practice tasks with concrete criteria.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Any) -> Dict[str, Any]:
        """
        Accepts either a prompt string or a structured payload.
        """
        if isinstance(payload, dict):
            prompt = str(payload.get("prompt") or payload.get("topic") or "").strip()
            topic = str(payload.get("topic") or payload.get("subject") or "general fieldcraft").strip()
            environment = str(payload.get("environment") or "outdoors").strip()
            difficulty = str(payload.get("difficulty") or "easy").strip().lower()
            objective = str(payload.get("objective") or payload.get("mission") or "").strip()
            duration_minutes = self._coerce_int(payload.get("duration_minutes"), default=20)
            hazards = self._normalize_list(payload.get("hazards") or payload.get("risk_notes"))
            mode = str(payload.get("mode") or payload.get("format") or "field_task").strip() or "field_task"
            audience = str(payload.get("audience") or "operator").strip() or "operator"
            constraints = self._normalize_list(payload.get("constraints") or payload.get("guardrails"))
            approval_contract = self._normalize_contract(payload.get("approval_contract"))
        else:
            prompt = str(payload or "").strip()
            topic = self._infer_topic(prompt)
            environment = self._infer_environment(prompt)
            difficulty = self._infer_difficulty(prompt)
            objective = ""
            duration_minutes = 20
            hazards = []
            mode = "field_task"
            audience = "operator"
            constraints = []
            approval_contract = {}

        mission = objective or self._generate_mission(topic, environment, difficulty)
        skill_focus = self._skill_focus(topic)
        checklist = self._generate_checklist(topic, environment)
        completion_criteria = self._completion_criteria(topic, environment, difficulty, duration_minutes)
        safety_notes = self._safety_notes(environment, hazards)
        risk_level = self._risk_level(environment, difficulty, hazards)
        risk_score = self._risk_score(environment, difficulty, hazards)
        safety_gate = self._safety_gate(risk_level, hazards, constraints)

        return {
            "agent": "field_ops",
            "status": "ok",
            "structured_output_version": "v2",
            "approval_safe": True,
            "topic": topic,
            "environment": environment,
            "difficulty": difficulty,
            "duration_minutes": duration_minutes,
            "prompt": prompt,
            "mode": mode,
            "audience": audience,
            "constraints": constraints,
            "approval_contract": approval_contract,
            "mission": mission,
            "skill_focus": skill_focus,
            "checklist": checklist,
            "completion_criteria": completion_criteria,
            "hazards": hazards,
            "safety_notes": safety_notes,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "safety_gate": safety_gate,
            "next_actions": self._next_actions(topic, environment, difficulty),
            "task_card": {
                "title": f"Field ops: {topic}",
                "summary": mission,
                "skill_focus": skill_focus,
                "difficulty": difficulty,
                "environment": environment,
                "completion_criteria": completion_criteria[:3],
            },
            "observability": {
                "structured_output_version": "v2",
                "topic": topic,
                "environment": environment,
                "difficulty": difficulty,
                "duration_minutes": duration_minutes,
                "hazard_count": len(hazards),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "safety_gate": safety_gate,
            },
        }

    def _infer_topic(self, prompt: str) -> str:
        p = prompt.lower()
        if "navigation" in p:
            return "navigation"
        if "plant" in p and "identification" in p:
            return "plant identification"
        if "tracking" in p:
            return "wildlife tracking"
        if "fire" in p or "firecraft" in p:
            return "firecraft"
        return "general fieldcraft"

    def _infer_environment(self, prompt: str) -> str:
        p = prompt.lower()
        if "forest" in p:
            return "forest"
        if "desert" in p:
            return "desert"
        if "mountain" in p:
            return "mountain"
        if "urban" in p:
            return "urban"
        return "outdoors"

    def _infer_difficulty(self, prompt: str) -> str:
        p = prompt.lower()
        if "hard" in p:
            return "hard"
        if "medium" in p:
            return "medium"
        return "easy"

    def _coerce_int(self, value: Any, default: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    def _normalize_list(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        items: List[str] = []
        for entry in value:
            text = str(entry or "").strip()
            if text:
                items.append(text)
        return list(dict.fromkeys(items))

    def _normalize_contract(self, value: Any) -> Dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return dict(value)
        return {"value": str(value)}

    def _generate_mission(self, topic: str, environment: str, difficulty: str) -> str:
        base = f"Head into the {environment} and complete a {difficulty} {topic} exercise."

        if topic.lower() == "navigation":
            return (
                f"{base} Choose a landmark, plot a bearing, and travel to it without checking your phone. "
                f"Log obstacles and terrain changes."
            )

        if topic.lower() == "plant identification":
            return (
                f"{base} Locate three plants you can positively identify. "
                f"Record leaf structure, scent, habitat, and any medicinal or survival uses."
            )

        if topic.lower() == "wildlife tracking":
            return (
                f"{base} Find fresh tracks or signs. Document gait, direction, feeding behavior, and any nearby water sources."
            )

        if topic.lower() == "firecraft":
            return (
                f"{base} Gather tinder, kindling, and fuel. Build a stable fire lay and note moisture levels, wind direction, and ignition success."
            )

        return (
            f"{base} Perform a practical field task and record observations that relate to real-world survival or outdoors skills."
        )

    def _skill_focus(self, topic: str) -> str:
        mapping = {
            "navigation": "Situational awareness + bearing discipline",
            "plant identification": "Pattern recognition + ecological literacy",
            "wildlife tracking": "Movement analysis + environmental reading",
            "firecraft": "Resource assessment + controlled ignition",
        }
        return mapping.get(topic.lower(), "General fieldcraft fundamentals")

    def _generate_checklist(self, topic: str, environment: str) -> Dict[str, bool]:
        if topic.lower() == "navigation":
            return {
                "selected_landmark": False,
                "plotted_bearing": False,
                "terrain_notes_recorded": False,
                "distance_estimated": False,
            }

        if topic.lower() == "plant identification":
            return {
                "three_plants_found": False,
                "leaf_structure_noted": False,
                "habitat_logged": False,
                "medicinal_value_checked": False,
            }

        if topic.lower() == "wildlife tracking":
            return {
                "tracks_found": False,
                "direction_logged": False,
                "behavior_inferred": False,
                "water_sources_noted": False,
            }

        if topic.lower() == "firecraft":
            return {
                "tinder_collected": False,
                "kindling_prepared": False,
                "fire_lay_built": False,
                "ignition_attempted": False,
            }

        return {
            "observation_made": False,
            "notes_recorded": False,
            "environment_assessed": False,
        }

    def _completion_criteria(self, topic: str, environment: str, difficulty: str, duration_minutes: int) -> List[str]:
        return [
            f"Finish a {difficulty} {topic} task in the {environment}.",
            f"Capture at least one observation per {max(5, duration_minutes // 4)} minute segment.",
            "Record what worked, what did not, and what should be tried next.",
        ]

    def _safety_notes(self, environment: str, hazards: List[str]) -> List[str]:
        notes = [
            f"Confirm the {environment} conditions are safe before starting.",
            "Keep one eye on weather, visibility, and your exit path.",
        ]
        for hazard in hazards[:2]:
            notes.append(f"Mitigate hazard: {hazard}")
        return notes

    def _risk_level(self, environment: str, difficulty: str, hazards: List[str]) -> str:
        score = 0
        if environment in {"desert", "mountain", "forest"}:
            score += 1
        if difficulty == "medium":
            score += 1
        if difficulty == "hard":
            score += 2
        score += min(2, len(hazards))
        if score <= 1:
            return "low"
        if score <= 3:
            return "moderate"
        return "high"

    def _risk_score(self, environment: str, difficulty: str, hazards: List[str]) -> float:
        score = 0.25
        if environment in {"desert", "mountain", "forest"}:
            score += 0.15
        if difficulty == "medium":
            score += 0.15
        elif difficulty == "hard":
            score += 0.25
        score += min(0.2, len(hazards) * 0.05)
        return round(min(1.0, score), 2)

    def _safety_gate(self, risk_level: str, hazards: List[str], constraints: List[str]) -> Dict[str, Any]:
        requires_review = risk_level == "high" or len(hazards) >= 3 or len(constraints) >= 2
        return {
            "requires_review": requires_review,
            "risk_level": risk_level,
            "hazards": hazards[:3],
            "constraint_count": len(constraints),
            "reason": "elevated field risk" if requires_review else "safe to proceed",
        }

    def _next_actions(self, topic: str, environment: str, difficulty: str) -> List[str]:
        actions = [
            f"Pick a safe {environment} route or observation point.",
            f"Set a timer for a {difficulty} {topic} rep and keep notes concise.",
        ]
        if topic.lower() == "navigation":
            actions.append("Verify your route with a compass or map before leaving.")
        elif topic.lower() == "firecraft":
            actions.append("Collect materials in order of tinder, kindling, then fuel.")
        else:
            actions.append("Write one short field log entry after the task.")
        return actions[:3]
