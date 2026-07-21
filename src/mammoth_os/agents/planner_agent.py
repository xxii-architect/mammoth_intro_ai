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

    async def validate_plan(self, plan: dict) -> bool:
        """Check the plan DAG for cycles and ensure agent availability for tasks.

        Returns True if plan is valid, False otherwise.
        """
        from mammoth_os.agent_registry import agent_registry, AgentStatus

        tasks = plan.get("tasks", [])
        task_map = {t["task_id"]: t for t in tasks}

        # Check for missing dependency references
        for t in tasks:
            for dep in t.get("depends_on", []) or []:
                if dep is None:
                    continue
                if dep not in task_map:
                    return False

        # Detect cycles using DFS
        visiting = set()
        visited = set()

        def has_cycle(node_id):
            if node_id in visited:
                return False
            if node_id in visiting:
                return True
            visiting.add(node_id)
            node = task_map.get(node_id)
            for dep in node.get("depends_on", []) or []:
                if dep is None:
                    continue
                if has_cycle(dep):
                    return True
            visiting.remove(node_id)
            visited.add(node_id)
            return False

        for tid in task_map:
            if has_cycle(tid):
                return False

        # Ensure agents are available (best-effort via AgentRegistry)
        # If an agent referenced by a task is not registered or in error, mark invalid
        for t in tasks:
            agent_name = t.get("agent")
            if not agent_name:
                return False
            manifest = await agent_registry.get_agent(agent_name)
            if manifest is None:
                # No manifest — treat as unavailable
                return False
            if manifest.status == AgentStatus.ERROR or manifest.status == AgentStatus.SHUTDOWN:
                return False

        return True

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

    async def validate_plan(self, plan: dict) -> bool:
        """Check the plan DAG for cycles and missing agent dependencies."""
        ...

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "PLAN_REQUEST":
            plan = await self.create_plan(event.payload["goal"], event.payload.get("constraints"))
            await self.emit_event("PLAN_READY", plan)

    async def shutdown(self) -> None:
        self.log("INFO", "PlannerAgent shutting down.")