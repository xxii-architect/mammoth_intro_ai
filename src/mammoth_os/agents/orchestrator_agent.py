from .base_agent import BaseAgent

class OrchestratorAgent(BaseAgent):# type: ignore
    """
    Level 6 orchestrator. Receives high-level goals, delegates to
    PlannerAgent, dispatches tasks to appropriate agents, monitors
    execution, resolves conflicts, and synthesizes final results.
    """

    async def orchestrate(self, goal: str, user_id: str = None) -> dict:# type: ignore
        """
        End-to-end orchestration of a complex multi-agent goal.

        Current implementation (focused):
        - Generate plan via PlannerAgent
        - Validate plan via PlannerAgent.validate_plan
        - Attempt basic healing for diagnostics (register mock agents)
        - Re-validate and return comprehensive result including diagnostics and actions taken

        Returns dict with keys: plan, valid (bool), diagnostics (list), actions_taken (list)
        """
        from mammoth_os.agents.planner_agent import PlannerAgent
        from mammoth_os.agent_registry import agent_registry, AgentManifest, AgentStatus

        actions_taken = []
        planner = PlannerAgent(router=getattr(self, "router", None))

        # 1) Create plan
        plan = await planner.create_plan(goal, constraints={})

        # 2) Validate plan
        valid, diagnostics = await planner.validate_plan(plan)

        # 3) If invalid due to unknown agents, attempt lightweight healing by registering mock agents
        if not valid:
            # Discover unknown agents from tasks
            for t in plan.get("tasks", []):
                agent_name = t.get("agent")
                if not agent_name:
                    continue
                manifest = await agent_registry.get_agent(agent_name)
                if manifest is None:
                    # Register a lightweight mock manifest
                    try:
                        mock_manifest = AgentManifest(
                            agent_id=agent_name,
                            name=agent_name,
                            version="0.0",
                            capabilities=[agent_name],
                            status=AgentStatus.ACTIVE,
                            level=1,
                            dependencies=[],
                            endpoint=f"http://{agent_name}.local",
                        )
                        await agent_registry.register(mock_manifest)
                        actions_taken.append(f"Registered mock agent: {agent_name}")
                    except Exception as exc:
                        diagnostics.append(f"Failed to register mock agent '{agent_name}': {exc}")

            # Re-run validation after healing attempts
            valid, diagnostics = await planner.validate_plan(plan)

        result = {
            "plan": plan,
            "valid": valid,
            "diagnostics": diagnostics,
            "actions_taken": actions_taken,
        }

        # Emit an orchestration result event for downstream consumers
        await self.emit_event("ORCHESTRATE_RESULT", result)
        return result

    async def resolve_conflict(self, outputs: list[dict]) -> dict:
        """When multiple agents return conflicting outputs, arbitrate."""
        # Simple majority / fallback strategy placeholder
        if not outputs:
            return {"winner": None, "reason": "no outputs"}
        # Prefer outputs with higher confidence field if present
        outputs_sorted = sorted(outputs, key=lambda o: o.get("confidence", 0), reverse=True)
        return {"winner": outputs_sorted[0], "reason": "highest confidence"}

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "ORCHESTRATE_REQUEST":
            result = await self.orchestrate(event.payload["goal"], event.payload.get("user_id"))
            # ORCHESTRATE_RESULT already emitted inside orchestrate; keep compatibility
            return

    async def shutdown(self) -> None:
        self.log("INFO", "OrchestratorAgent shutting down.")
