from .base_agent import BaseAgent


class OrchestratorAgent(BaseAgent):# type: ignore
    """
    Level 6 orchestrator. Receives high-level goals, delegates to
    PlannerAgent, dispatches tasks to appropriate agents, monitors
    execution, resolves conflicts, and synthesizes final results.
    """

    name = "OrchestratorAgent"

    def __init__(self, router=None):
        super().__init__(router)

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    def _normalize_payload(self, payload):  # type: ignore
        if isinstance(payload, dict):
            return {
                "goal": str(payload.get("goal") or payload.get("prompt") or "").strip(),
                "user_id": str(payload.get("user_id") or "").strip() or None,
                "constraints": payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {},
            }
        return {"goal": str(payload or "").strip(), "user_id": None, "constraints": {}}

    async def orchestrate(self, goal: str, user_id: str = None, constraints: dict | None = None) -> dict:# type: ignore
        """
        End-to-end orchestration of a complex multi-agent goal.

        Current implementation:
        - Generate plan via PlannerAgent
        - Validate plan via PlannerAgent.validate_plan
        - Attempt lightweight healing for diagnostics (register missing manifests)
        - Re-validate and return comprehensive result including diagnostics and actions taken
        """
        from mammoth_os.agents.planner_agent import PlannerAgent
        from mammoth_os.agent_registry import agent_registry, AgentManifest, AgentStatus

        actions_taken = []
        planner = PlannerAgent(router=getattr(self, "router", None))
        plan = await planner.create_plan(goal, constraints=constraints or {})
        valid, diagnostics = await planner.validate_plan(plan)

        if not valid:
            for task in plan.get("tasks", []):
                agent_name = task.get("agent")
                if not agent_name:
                    continue
                manifest = await agent_registry.get_agent(agent_name)
                if manifest is None:
                    try:
                        fallback_manifest = AgentManifest(
                            agent_id=agent_name,
                            name=agent_name,
                            version="0.0",
                            capabilities=[agent_name],
                            status=AgentStatus.ACTIVE,
                            level=1,
                            dependencies=[],
                            endpoint=f"http://{agent_name}.local",
                        )
                        await agent_registry.register(fallback_manifest)
                        actions_taken.append(f"Registered fallback agent manifest: {agent_name}")
                    except Exception as exc:
                        diagnostics.append(f"Failed to register fallback manifest '{agent_name}': {exc}")
            valid, diagnostics = await planner.validate_plan(plan)

        curriculum_grounded = any(
            isinstance(task.get("input"), dict) and "lesson" in task.get("input", {})
            for task in plan.get("tasks", [])
        )

        result = {
            "plan": plan,
            "valid": valid,
            "diagnostics": diagnostics,
            "actions_taken": actions_taken,
            "curriculum_grounded": curriculum_grounded,
        }
        await self.emit_event("ORCHESTRATE_RESULT", result)
        return result

    @staticmethod
    def _quality_flags_for_result(result: dict) -> list[str]:
        quality_flags: list[str] = ["validated_plan"] if result.get("valid") else ["needs_agent_repair"]
        if result.get("diagnostics"):
            quality_flags.append("has_diagnostics")
        if result.get("curriculum_grounded"):
            quality_flags.append("curriculum_grounded")
        return quality_flags

    def _build_summary(self, result: dict) -> str:
        plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
        task_count = len(plan.get("tasks", []) or [])
        if result.get("valid"):
            return f"Orchestration produced a valid plan with {task_count} tasks."
        diagnostic_count = len(result.get("diagnostics", []) or [])
        return f"Orchestration produced {task_count} tasks but still has {diagnostic_count} validation findings."

    async def run(self, payload):  # type: ignore
        normalized = self._normalize_payload(payload)
        goal = normalized["goal"]
        if not goal:
            return {
                "status": "needs_context",
                "agent": self.name,
                "summary": "Add a concrete goal before the orchestrator can route work.",
                "quality_flags": ["missing_goal"],
                "diagnostics": ["No orchestration goal was provided."],
                "plan": {"tasks": []},
            }
        result = await self.orchestrate(goal, normalized.get("user_id"), normalized.get("constraints"))
        diagnostics = result.get("diagnostics", []) if isinstance(result.get("diagnostics"), list) else []
        quality_flags = self._quality_flags_for_result(result)
        return {
            "status": "ok" if result.get("valid") else "warning",
            "agent": self.name,
            "goal": goal,
            "summary": self._build_summary(result),
            "quality_flags": quality_flags,
            **result,
        }

    async def emit_event(self, event_type: str, payload) -> None:  # type: ignore
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def resolve_conflict(self, outputs: list[dict]) -> dict:
        """When multiple agents return conflicting outputs, arbitrate."""
        if not outputs:
            return {"winner": None, "reason": "no outputs"}
        outputs_sorted = sorted(outputs, key=lambda item: item.get("confidence", 0), reverse=True)
        return {"winner": outputs_sorted[0], "reason": "highest confidence"}

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "ORCHESTRATE_REQUEST":
            await self.orchestrate(event.payload["goal"], event.payload.get("user_id"))

    async def shutdown(self) -> None:
        self.log("INFO", "OrchestratorAgent shutting down.")
