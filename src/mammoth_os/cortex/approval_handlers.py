# src/mammoth_os/cortex/approval_handlers.py

from typing import Any, Dict
from mammoth_os.core_types import ApprovalResult

def simple_console_approval(request_or_agent: Any, maybe_step: Dict[str, Any] = None, maybe_router: Any = None): # type: ignore
    """
    Flexible approval handler for development:
    - If called with an ActionRequest, it prints a short summary and prompts.
    - If called with (agent_name, step, router) it prints the step and prompts.
    Returns True/False (or ApprovalResult-like) depending on user input.
    """
    try:
        # Full ActionRequest shape
        agent = getattr(request_or_agent, "agent_name", None) or getattr(request_or_agent, "agent", None)
        action = getattr(request_or_agent, "action_type", None) or getattr(request_or_agent, "action", None)
        target = getattr(request_or_agent, "target", None) or getattr(request_or_agent, "target", None)
        risk = getattr(request_or_agent, "risk", None)
        details = getattr(request_or_agent, "details", None)
        if agent:
            prompt = f"[APPROVAL] {agent} -> {action} on {target} (risk={getattr(risk,'name',risk)})\nDetails: {details}\nApprove? (y/n): "
            ans = input(prompt).strip().lower()
            approved = ans in ("y", "yes")
            return ApprovalResult(approved=approved, reason=None if approved else "Denied via console")
    except Exception:
        pass

    # Fallback: simple (agent_name, step, router) shape
    try:
        agent_name = request_or_agent
        step = maybe_step or {}
        prompt = f"[APPROVAL] {agent_name} -> {step.get('action')} on {step.get('target')} (risk={step.get('risk')})\nDetails: {step.get('details')}\nApprove? (y/n): "
        ans = input(prompt).strip().lower()
        return ans in ("y", "yes")
    except Exception:
        return False
