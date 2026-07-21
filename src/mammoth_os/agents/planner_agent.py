class PlannerAgent(BaseAgent):# type: ignore
    """
    Converts high-level goals into structured execution plans represented
    as directed acyclic graphs (DAGs). Each node is a discrete task
    assigned to a specific agent. Plans are validated before execution.
    """

    async def create_plan(self, goal: str, constraints: dict = None) -> dict:# type: ignore
        """
        Generate an execution plan for a given goal.

        Returns:
            {
                "plan_id": str,
                "goal": str,
                "tasks": list[dict],  # Each: {task_id, agent, input, depends_on}
                "estimated_duration_sec": int,
            }
        """
        import uuid
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
        """Check the plan DAG for cycles and missing agent dependencies."""
        ...

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "PLAN_REQUEST":
            plan = await self.create_plan(event.payload["goal"], event.payload.get("constraints"))
            await self.emit_event("PLAN_READY", plan)

    async def shutdown(self) -> None:
        self.log("INFO", "PlannerAgent shutting down.")