# mammoth_os/agents/autonomous_task_engine.py

import asyncio
from typing import Dict, Any, List
from .base_agent import BaseAgent
from .autonomous_task_engine_v2_upgrade import WorkflowExecutor

class AutonomousTaskEngine(BaseAgent):
    name = "AutonomousTaskEngine"

    def __init__(self, router):
        super().__init__(router)
        self.cortex = router
        self.executor = WorkflowExecutor()
        self.executor.router = router  # wire router into executor for task delegation

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
        """Execute workflow using v2 WorkflowExecutor with dependency validation.
        
        v2 upgrade: Validates dependencies, detects cycles, and executes
        tasks in proper order with per-task timeouts and retry logic.
        """
        steps: List[Dict[str, Any]] = details.get("steps", [])
        
        # Convert steps to workflow format expected by executor
        tasks = {}
        for i, step in enumerate(steps):
            task_id = step.get("task_id") or f"task_{i}"
            tasks[task_id] = {
                "task_id": task_id,
                "agent_name": step.get("agent_name"),
                "action_type": step.get("action_type"),
                "target": step.get("target"),
                "details": step.get("details", {}),
                "depends_on": step.get("depends_on", []),
                "timeout": step.get("timeout", 300),
            }
        
        workflow = {
            "workflow_id": details.get("workflow_id", "default_workflow"),
            "tasks": list(tasks.values()),
        }
        
        # Use v2 executor to validate and execute
        try:
            result = asyncio.run(self.executor.execute_workflow(workflow))
            return result
        except Exception as e:
            # Fallback to synchronous execution if async fails
            return self._run_workflow_sync(steps)

    def _run_workflow_sync(self, steps: List[Dict[str, Any]]):
        """Synchronous fallback for workflow execution (no dependency validation)."""
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
    
    async def run(self, payload: Any) -> Dict[str, Any]:
        """Runtime entry point for async workflow execution."""
        if isinstance(payload, dict) and payload.get("workflow"):
            return await self.executor.execute_workflow(payload.get("workflow"))
        
        if isinstance(payload, dict) and payload.get("steps"):
            return self._run_workflow(payload)
        
        return {
            "status": "error",
            "agent": self.name,
            "message": "Payload must contain 'workflow' or 'steps' key",
        }
