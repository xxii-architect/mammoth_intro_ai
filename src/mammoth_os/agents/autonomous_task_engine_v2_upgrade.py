# autonomous_task_engine_v2_upgrade.py
# Wave 3: Basic workflow execution, step ordering, and safe delegation

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime, timezone


class WorkflowExecutor:
    """Execute ordered task workflows with dependency tracking and error recovery."""
    
    def __init__(self, router=None, max_retries: int = 2, timeout_sec: float = 300.0):
        self.router = router
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec
        self._execution_log: List[Dict[str, Any]] = []
    
    async def execute_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a workflow definition.
        
        Workflow format:
        {
            "workflow_id": str,
            "name": str,
            "tasks": [
                {
                    "task_id": str,
                    "agent": str,
                    "action": str,
                    "input": Dict,
                    "depends_on": List[str],
                    "timeout_sec": Optional[float],
                    "retries": Optional[int],
                }
            ],
            "metadata": Dict,
        }
        """
        workflow_id = workflow.get("workflow_id") or "unknown"
        tasks = workflow.get("tasks", [])
        
        if not tasks:
            return {
                "status": "ok",
                "workflow_id": workflow_id,
                "summary": "Empty workflow — no tasks to execute",
                "tasks_completed": 0,
                "results": [],
                "errors": [],
            }
        
        # Build dependency graph and validate
        task_map = {t.get("task_id"): t for t in tasks if t.get("task_id")}
        dep_errors = self._validate_dependencies(task_map)
        if dep_errors:
            return {
                "status": "error",
                "workflow_id": workflow_id,
                "summary": "Workflow has dependency errors",
                "diagnostics": dep_errors,
                "tasks_completed": 0,
                "results": [],
                "errors": dep_errors,
            }
        
        # Execute tasks in dependency order
        completed: Dict[str, Dict[str, Any]] = {}
        execution_order: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []
        errors: List[str] = []
        
        for task in tasks:
            task_id = task.get("task_id")
            deps = task.get("depends_on", [])
            
            # Wait for dependencies
            for dep_id in deps:
                if dep_id not in completed:
                    errors.append(f"Task {task_id} depends on unresolved {dep_id}")
                    continue
            
            # Execute task
            try:
                task_result = await self._execute_task(task)
                execution_order.append({
                    "task_id": task_id,
                    "status": task_result.get("status", "unknown"),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                })
                results.append(task_result)
                completed[task_id] = task_result
            except Exception as exc:
                err_msg = f"Task {task_id} failed: {exc}"
                errors.append(err_msg)
                execution_order.append({
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(exc),
                })
        
        return {
            "status": "ok" if not errors else "warning",
            "workflow_id": workflow_id,
            "summary": f"Workflow executed {len(execution_order)} tasks" + (f" with {len(errors)} errors" if errors else ""),
            "tasks_completed": len(completed),
            "execution_order": execution_order,
            "results": results,
            "errors": errors,
        }
    
    async def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single task with timeout and retry logic."""
        task_id = task.get("task_id")
        agent_name = task.get("agent")
        action = task.get("action")
        task_input = task.get("input", {})
        timeout_sec = task.get("timeout_sec", self.timeout_sec)
        retries = task.get("retries", self.max_retries)
        
        for attempt in range(1, retries + 2):
            try:
                # Try to delegate to router if available
                if self.router and hasattr(self.router, "handle_task"):
                    async def _execute():
                        return await self.router.handle_task(
                            agent_name=agent_name,
                            action_type=action,
                            target=task_id,
                            details=task_input,
                        )
                else:
                    # Fallback: direct agent invocation
                    from mammoth_os.agent_registry import load_agent
                    agent = load_agent(agent_name)
                    async def _execute():
                        if hasattr(agent, 'run'):
                            return await agent.run(task_input) if asyncio.iscoroutinefunction(agent.run) else agent.run(task_input)
                        return {"status": "error", "message": f"Agent {agent_name} has no run() method"}
                
                result = await asyncio.wait_for(_execute(), timeout=timeout_sec)
                return {
                    "task_id": task_id,
                    "status": "ok",
                    "agent": agent_name,
                    "action": action,
                    "result": result,
                    "attempt": attempt,
                }
            except asyncio.TimeoutError:
                if attempt <= retries:
                    continue
                return {
                    "task_id": task_id,
                    "status": "timeout",
                    "agent": agent_name,
                    "action": action,
                    "error": f"Task timed out after {timeout_sec}s",
                    "attempts": attempt,
                }
            except Exception as exc:
                if attempt <= retries:
                    continue
                return {
                    "task_id": task_id,
                    "status": "error",
                    "agent": agent_name,
                    "action": action,
                    "error": str(exc),
                    "attempts": attempt,
                }
        
        return {
            "task_id": task_id,
            "status": "error",
            "message": f"Task failed after {retries + 1} attempts",
        }
    
    @staticmethod
    def _validate_dependencies(task_map: Dict[str, Dict[str, Any]]) -> List[str]:
        """Validate that all dependencies exist and no cycles present."""
        errors: List[str] = []
        
        for task_id, task in task_map.items():
            deps = task.get("depends_on", [])
            for dep_id in deps:
                if dep_id not in task_map:
                    errors.append(f"Task {task_id} depends on undefined {dep_id}")
        
        # Check for cycles (simple DFS)
        visited = set()
        rec_stack = set()
        
        def has_cycle(task_id):
            visited.add(task_id)
            rec_stack.add(task_id)
            
            for dep_id in task_map.get(task_id, {}).get("depends_on", []):
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
            
            rec_stack.discard(task_id)
            return False
        
        for task_id in task_map:
            if task_id not in visited:
                if has_cycle(task_id):
                    errors.append(f"Cycle detected involving {task_id}")
        
        return errors


__all__ = ["WorkflowExecutor"]
