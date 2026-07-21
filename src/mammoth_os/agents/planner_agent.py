from .base_agent import BaseAgent

class PlannerAgent(BaseAgent):# type: ignore
    """
    Converts high-level goals into structured execution plans represented
    as directed acyclic graphs (DAGs). Each node is a discrete task
    assigned to a specific agent. Plans are validated before execution.
    """

    async def create_plan(self, goal: str, constraints: dict = None) -> dict:# type: ignore
        """
        Generate an execution plan for a given goal.

        If no curriculum is provided in constraints, attempt to generate one
        via CurriculumAgent (safe, best-effort). Then decompose into tasks.

        Returns:
            {
                "plan_id": str,
                "goal": str,
                "tasks": list[dict],  # Each: {task_id, agent, input, depends_on}
                "estimated_duration_sec": int,
            }
        """
        import uuid
        # Ensure constraints is a dict to mutate
        if constraints is None:
            constraints = {}

        # Best-effort: if no curriculum provided, try to generate one using CurriculumAgent
        if "curriculum" not in constraints:
            try:
                from mammoth_os.agent_registry import load_agent
                curriculum_agent = load_agent("curriculum", None)
                # CurriculumAgent.run is synchronous and returns a dict
                cur_res = curriculum_agent.run(goal)
                if isinstance(cur_res, dict) and cur_res.get("status") == "ok":
                    constraints["curriculum"] = cur_res.get("curriculum")
            except Exception:
                # Fail silently — planner can still produce fallback plan
                pass

        tasks = await self._decompose_to_tasks(goal, constraints)
        return {
            "plan_id": str(uuid.uuid4()),
            "goal": goal,
            "tasks": tasks,
            "estimated_duration_sec": len(tasks) * 10,
        }

    async def _decompose_to_tasks(self, goal: str, constraints: dict) -> list[dict]:
        """Decompose a goal into an ordered task list.

        If `constraints` contains a 'curriculum' dict (as produced by
        CurriculumAgent), convert modules and lessons into discrete tasks.
        Otherwise, return a single fallback task representing the goal.
        """
        import uuid

        curriculum = None
        if constraints and isinstance(constraints, dict):
            curriculum = constraints.get("curriculum")

        # Support both raw curriculum dict and wrapper {"status":..., "curriculum": {...}}
        if isinstance(curriculum, dict) and "curriculum" in curriculum and isinstance(curriculum.get("curriculum"), dict):
            curriculum = curriculum.get("curriculum")

        tasks: list[dict] = []
        if curriculum and isinstance(curriculum, dict):
            prev_task_id = None
            for module in curriculum.get("modules", []):
                module_id = module.get("module_id")
                for lesson in module.get("lessons", []):
                    task_id = lesson.get("lesson_id") or str(uuid.uuid4())
                    task = {
                        "task_id": task_id,
                        "agent": "tutor",  # suggested consumer agent
                        "input": {"module_id": module_id, "lesson": lesson},
                        "depends_on": [prev_task_id] if prev_task_id else [],
                    }
                    tasks.append(task)
                    prev_task_id = task_id
            return tasks

        # Fallback: single high-level task
        return [
            {
                "task_id": str(uuid.uuid4()),
                "agent": "curriculum",
                "input": {"goal": goal},
                "depends_on": [],
            }
        ]

    async def validate_plan(self, plan: dict) -> tuple[bool, list[str]]:
        """Check the plan DAG for cycles and ensure agent availability for tasks.

        Returns (is_valid: bool, diagnostics: list[str]). Diagnostics contains
        human-readable reasons when validation fails (missing refs, cycles, agent issues).
        """
        from mammoth_os.agent_registry import agent_registry, AgentStatus

        diagnostics: list[str] = []
        tasks = plan.get("tasks", [])
        task_map = {t["task_id"]: t for t in tasks}

        # Check for missing dependency references
        for t in tasks:
            for dep in t.get("depends_on", []) or []:
                if dep is None:
                    continue
                if dep not in task_map:
                    diagnostics.append(
                        f"Missing dependency reference: task '{t['task_id']}' depends on unknown task '{dep}'"
                    )

        # Detect cycles using DFS
        visiting = set()
        visited = set()
        cycle_found = False

        def has_cycle(node_id, path=None):
            nonlocal cycle_found
            if path is None:
                path = []
            if node_id in visited:
                return False
            if node_id in visiting:
                # Found a cycle; capture the cycle path
                cycle_path = " -> ".join(path + [node_id])
                diagnostics.append(f"Cycle detected in tasks: {cycle_path}")
                cycle_found = True
                return True
            visiting.add(node_id)
            node = task_map.get(node_id)
            if not node:
                visiting.remove(node_id)
                visited.add(node_id)
                return False
            for dep in node.get("depends_on", []) or []:
                if dep is None:
                    continue
                if has_cycle(dep, path + [node_id]):
                    return True
            visiting.remove(node_id)
            visited.add(node_id)
            return False

        for tid in task_map:
            if has_cycle(tid):
                # continue checking to collect diagnostics
                pass

        # Ensure agents are available (best-effort via AgentRegistry)
        # If an agent referenced by a task is not registered or in error, add diagnostic
        for t in tasks:
            agent_name = t.get("agent")
            if not agent_name:
                diagnostics.append(f"Task '{t.get('task_id')}' has no agent specified")
                continue
            manifest = await agent_registry.get_agent(agent_name)
            if manifest is None:
                diagnostics.append(f"Unknown agent referenced by task '{t.get('task_id')}': '{agent_name}'")
                continue
            if manifest.status in (AgentStatus.ERROR, AgentStatus.SHUTDOWN):
                diagnostics.append(
                    f"Agent '{agent_name}' referenced by task '{t.get('task_id')}' is unavailable (status={manifest.status})"
                )

        is_valid = len(diagnostics) == 0 and not cycle_found
        return is_valid, diagnostics

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "PLAN_REQUEST":
            plan = await self.create_plan(event.payload["goal"], event.payload.get("constraints"))
            await self.emit_event("PLAN_READY", plan)

    async def shutdown(self) -> None:
        self.log("INFO", "PlannerAgent shutting down.")