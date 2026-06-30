# src/mammoth_os/cortex/router.py

from dataclasses import dataclass
from typing import Any, Dict, Optional
import datetime
import json
import os

from mammoth_os.core_types import (
    ActionRequest,
    ApprovalResult,
    ApprovalHandler,
    ExecutionConfig,
    RiskLevel,
)


class CortexRouter:
    """
    MammothOS Cortex Router
    - Routes tasks to agents
    - Enforces permissions
    - Triggers cinematic approval UI (via extension / API)
    - Logs everything
    """

    # Replace the existing __init__ method with this block
    def __init__(
        self,
        agents: Dict[str, Any],
        approval_mode: str = "vs_code_webview",  # later: "api"
        approval_handler: Optional[ApprovalHandler] = None,
        log_path: str = "mammoth_os/logs/cortex.log",
        execution_config: Optional[ExecutionConfig] = None,
    ) -> None:
        self.agents = agents
        self.approval_mode = approval_mode
        self.approval_handler = approval_handler
        self.log_path = log_path
        self.autonomy_mode = "semi"  # options: "semi" or "full"

        # ensure an ExecutionConfig is always available on the router
        self.execution_config = execution_config or ExecutionConfig()

        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

        # Hybrid permission matrix
        self.permissions = {
            "CurriculumAgent": {
                "allowed": ["write_file", "generate_content"],
                "requires_approval": ["create_directory", "overwrite_file"],
                "forbidden": ["modify_schema", "run_migration", "modify_rls"],
            },
            "CodingAgent": {
                "allowed": ["write_code", "refactor_code", "create_file"],
                "requires_approval": ["delete_file", "modify_schema", "run_migration", "modify_rls"],
                "forbidden": [],
            },
            "ReflectionAgent": {
                "allowed": ["analyze_code", "generate_report"],
                "requires_approval": [],
                "forbidden": ["write_file", "modify_schema", "run_migration", "modify_rls"],
            },
            "MarketIntelAgent": {
                "allowed": ["generate_insights", "generate_report"],
                "requires_approval": [],
                "forbidden": ["write_file", "modify_schema", "run_migration", "modify_rls"],
            },
            "BrandVoiceAgent": {
                "allowed": ["write_content", "generate_copy"],
                "requires_approval": ["overwrite_brand_file", "create_brand_directory"],
                "forbidden": ["modify_schema", "run_migration", "modify_rls"],
            },
            "AutonomousTaskEngine": {
                "allowed": ["plan_task", "route_subtasks"],
                "requires_approval": ["delete_file", "modify_schema", "run_migration", "modify_rls", "use_api_key"],
                "forbidden": [],
            },
        }

    # --- Public API ---------------------------------------------------------

    def handle_task(
        self,
        agent_name: str,
        action_type: str,
        target: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Main entry point: agents call this to perform actions.
        """
        details = details or {}
        risk = self._assess_risk(agent_name, action_type)

        request = ActionRequest(
            agent_name=agent_name,
            action_type=action_type,
            target=target,
            details=details,
            risk=risk,
        )

        self._log_event("REQUEST", request)

        # Permission check
        perm = self.permissions.get(agent_name)
        if not perm:
            return self._deny(request, reason=f"Unknown agent: {agent_name}")

        if action_type in perm["forbidden"]:
            return self._deny(request, reason=f"Action '{action_type}' forbidden for {agent_name}")

        if action_type in perm["requires_approval"] or risk == RiskLevel.HIGH:
            approval = self._request_approval(request)
            if not approval.approved:
                return self._deny(request, reason=approval.reason or "Denied by operator")

        # Medium risk: warn but proceed
        if risk == RiskLevel.MEDIUM:
            self._log_event("WARN", request, extra={"message": "Medium-risk action executed without approval"})

        # Route to agent
        agent = self.agents.get(agent_name)
        if not agent:
            return self._deny(request, reason=f"Agent '{agent_name}' not registered")

        result = agent.execute_action(action_type, target, details)
        self._log_event("EXECUTE", request, extra={"result": str(result)})
        return result

    # --- Risk assessment ----------------------------------------------------

    def _assess_risk(self, agent_name: str, action_type: str) -> RiskLevel:
        high_risk = {"modify_schema", "run_migration", "modify_rls", "delete_file", "use_api_key"}
        medium_risk = {"overwrite_file", "overwrite_brand_file", "create_directory", "create_brand_directory"}

        if action_type in high_risk:
            return RiskLevel.HIGH
        if action_type in medium_risk:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # --- Approval helper (boolean) -----------------------------------------
    def request_approval(self, agent_name: str, step: dict) -> bool:
        """
        Lightweight helper for agents/engines that want a boolean approval check.
        Returns True if approved, False otherwise.
        """
        if callable(self.approval_handler):
            try:
                # Many handlers will accept (agent_name, step, router)
                return bool(self.approval_handler(agent_name, step, self)) # type: ignore
            except TypeError:
                # If handler expects the full ActionRequest, caller should use _request_approval.
                try:
                    resp = self.approval_handler(ActionRequest(agent_name, step.get("action"), step.get("target"), step.get("details", {}), RiskLevel.LOW)) # type: ignore
                    if isinstance(resp, ApprovalResult):
                        return bool(resp.approved)
                    return bool(resp)
                except Exception:
                    return False
            except Exception:
                # If handler fails, deny for safety
                return False

        # default fallback behavior
        if getattr(self, "approval_mode", None) == "auto":
            return True
        return False
    # ---------------------------------------------------------------------

    # --- Approval handling --------------------------------------------------

    def _request_approval(self, request: ActionRequest) -> ApprovalResult:
        """
        Dispatch approval request to the active channel.
        For now: VS Code WebView (handled by extension).
        Later: API endpoint (Command Center v3).
        """
        self._log_event("APPROVAL_REQUEST", request)

        if getattr(self, "autonomy_mode", "semi") == "full":
            self._log_event("AUTO_APPROVED", request)
            return ApprovalResult(approved=True)

        if self.approval_handler:
            # Allow handlers that accept ActionRequest or the simplified signature.
            try:
                # If handler expects the full ActionRequest, call with it.
                resp = self.approval_handler(request) # type: ignore
            except TypeError:
                # Fallback: try the simplified signature (agent_name, step, router)
                try:
                    resp = self.approval_handler(
                        request.agent_name,
                        {
                            "agent": request.agent_name,
                            "action": request.action_type,
                            "target": request.target,
                            "details": request.details,
                            "risk": request.risk.name,
                        }, # type: ignore
                        self,
                    )
                except Exception as e:
                    self._log_event("APPROVAL_ERROR", request, extra={"error": str(e)})
                    return ApprovalResult(approved=False, reason="approval_handler_error")

            # Normalize handler return types
            if isinstance(resp, ApprovalResult):
                return resp
            try:
                return ApprovalResult(approved=bool(resp))
            except Exception:
                return ApprovalResult(approved=False, reason="invalid_approval_response")

        # Default: CLI fallback (until extension is wired)
        prompt = self._build_personality_prompt(request)
        print(prompt)
        answer = input("Approve? (yes/no): ").strip().lower()
        approved = answer in ("y", "yes")
        result = ApprovalResult(approved=approved, reason=None if approved else "Denied via CLI")
        self._log_event("APPROVAL_RESULT", request, extra={"approved": approved})
        return result

    def _build_personality_prompt(self, request: ActionRequest) -> str:
        """
        Hybrid personality prompts for cinematic UI.
        The VS Code extension will use this data to render the WebView.
        """
        base = {
            "agent": request.agent_name,
            "action": request.action_type,
            "target": request.target,
            "risk": request.risk.name,
        }

        if request.agent_name == "CodingAgent":
            # Wednesday persona
            return (
                f"…CodingAgent wants to perform '{request.action_type}' on {request.target}.\n"
                f"Risk: {request.risk.name}. I’m not thrilled.\n"
                f"Approve this mutation (yes/no)?"
            )
        elif request.agent_name == "CurriculumAgent":
            # Rugged MammothOS survival aesthetic
            return (
                f"🔥 CurriculumAgent is carving a new trail:\n"
                f"Action: {request.action_type}\nTarget: {request.target}\n"
                f"Risk: {request.risk.name}. Approve this move (yes/no)?"
            )
        elif request.agent_name == "BrandVoiceAgent":
            # Stylish, confident
            return (
                f"✨ BrandVoiceAgent wants to refine your narrative:\n"
                f"Action: {request.action_type}\nTarget: {request.target}\n"
                f"Risk: {request.risk.name}. Approve this creative adjustment (yes/no)?"
            )
        elif request.agent_name == "ReflectionAgent":
            # Minimalist OS tone
            return (
                f"[CORTEX] ReflectionAgent requests permission:\n"
                f"Action: {request.action_type}\nTarget: {request.target}\n"
                f"Risk: {request.risk.name}. Approve (yes/no)?"
            )
        elif request.agent_name == "MarketIntelAgent":
            # Calm, strategic
            return (
                f"📊 MarketIntelAgent suggests an update:\n"
                f"Action: {request.action_type}\nTarget: {request.target}\n"
                f"Risk: {request.risk.name}. Approve (yes/no)?"
            )
        elif request.agent_name == "AutonomousTaskEngine":
            # Serious system tone
            return (
                f"[SYSTEM] AutonomousTaskEngine is preparing a multi-step operation:\n"
                f"Action: {request.action_type}\nTarget: {request.target}\n"
                f"Risk: {request.risk.name}. Approval required to proceed (yes/no)."
            )

        # Default fallback
        return (
            f"[CORTEX] {request.agent_name} requests:\n"
            f"Action: {request.action_type}\nTarget: {request.target}\n"
            f"Risk: {request.risk.name}. Approve (yes/no)?"
        )

    # --- Logging ------------------------------------------------------------

    def _log_event(
        self,
        event_type: str,
        request: ActionRequest,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "agent": request.agent_name,
            "action": request.action_type,
            "target": request.target,
            "risk": request.risk.name,
            "details": request.details,
            "extra": extra or {},
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def _deny(self, request: ActionRequest, reason: str) -> Dict[str, Any]:
        self._log_event("DENY", request, extra={"reason": reason})
        return {
            "status": "denied",
            "reason": reason,
            "agent": request.agent_name,
            "action": request.action_type,
            "target": request.target,
        }
