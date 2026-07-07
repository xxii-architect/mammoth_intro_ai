# mammoth_os/agents/autonomous_task_engine.py

from typing import Dict, Any, List
from .base_agent import BaseAgent

class AutonomousTaskEngine(BaseAgent):
    name = "AutonomousTaskEngine"

    def __init__(self, router):
        super().__init__(router)
        self.cortex = router

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "run_workflow":
            return self._run_workflow(details)

        if action_type == "delegate":
            return self._delegate(details)
        
        if action_type == "apply_patch":
            return self.cortex.autonomous_engine.apply_patch(details)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    def _run_workflow(self, details: Dict[str, Any]):
        steps: List[Dict[str, Any]] = details.get("steps", [])
        results = []

        for i, step in enumerate(steps):
            agent_name = step.get("agent_name")
            action_type = step.get("action_type")
            target = step.get("target")
            step_details = step.get("details", {})

            result = self.cortex.handle_task(
                agent_name=agent_name,
                action_type=action_type,
                target=target,
                details=step_details
            )

            results.append({
                "step": i + 1,
                "agent": agent_name,
                "action": action_type,
                "target": target,
                "result": result
            })

        return {
            "status": "ok",
            "agent": self.name,
            "action": "run_workflow",
            "steps_completed": len(results),
            "results": results,
        }

    def _delegate(self, details: Dict[str, Any]):
        agent_name = details.get("agent_name")
        action_type = details.get("action_type")
        target = details.get("target")
        step_details = details.get("details", {})

        result = self.cortex.handle_task(
            agent_name=agent_name,
            action_type=action_type,
            target=target,
            details=step_details
        )

        return {
            "status": "ok",
            "agent": self.name,
            "action": "delegate",
            "delegated_to": agent_name,
            "result": result,
        }
