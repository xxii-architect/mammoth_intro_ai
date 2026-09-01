# mammoth_os/agents/base_agent.py

from typing import Any, Dict, Optional
import inspect


class BaseAgent:
    """
    Universal compatibility base class for Mammoth OS agents.
    Supports both legacy sync agents and modern async agents.
    """

    name: str = "BaseAgent"

    def __init__(self, router: Any):
        self.router = router

    # ---------------------------------------------------------
    # Modern async run()
    # ---------------------------------------------------------
    async def run(self, prompt: str) -> Dict[str, Any]:
        """
        Modern agents override this.
        Legacy agents may override sync run(), which we detect below.
        """
        # If the agent defines a sync run(), call it automatically
        sync_run = getattr(self, "_legacy_run", None)
        if sync_run:
            return sync_run(prompt)

        return {
            "status": "error",
            "agent": self.name,
            "message": f"Agent '{self.name}' has no run() implementation."
        }

    # ---------------------------------------------------------
    # Legacy sync run() support
    # ---------------------------------------------------------
    def _legacy_run(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Internal wrapper: if the agent defines a sync run(), call it.
        """
        method = getattr(self, "run_sync", None)
        if callable(method):
            return method(prompt)# type: ignore

        # Some older agents used run() without async
        method = getattr(self, "run_legacy", None)
        if callable(method):
            return method(prompt)# type: ignore

        return None

    # ---------------------------------------------------------
    # Legacy process() support
    # ---------------------------------------------------------
    async def process(self, prompt: str) -> Dict[str, Any]:
        """
        Some older agents used process() instead of run().
        """
        method = getattr(self, "process_sync", None)
        if callable(method):
            return method(prompt)# type: ignore

        return {
            "status": "error",
            "agent": self.name,
            "message": "process() not implemented."
        }

    # ---------------------------------------------------------
    # Legacy handle() support
    # ---------------------------------------------------------
    async def handle(self, prompt: str) -> Dict[str, Any]:
        """
        Some mid-generation agents used handle() instead of run().
        """
        method = getattr(self, "handle_sync", None)
        if callable(method):
            return method(prompt)# type: ignore

        return {
            "status": "error",
            "agent": self.name,
            "message": "handle() not implemented."
        }

    # ---------------------------------------------------------
    # Observability — run health signal (Sweep 4)
    # ---------------------------------------------------------
    def _record_run_health(self, result: Optional[Dict[str, Any]], duration_ms: float = 0.0) -> None:
        """Post a structured health signal after a run completes. Non-blocking, safe."""
        try:
            from mammoth_os.audit_engine import get_audit_engine
            engine = get_audit_engine()
            status = "ok"
            if isinstance(result, dict):
                if result.get("status") in ("error", "failed"):
                    status = result["status"]
            engine.record(
                event_type="agent_run",
                agent=self.name,
                outcome=status,
                severity="INFO" if status == "ok" else "WARNING",
                details={"duration_ms": round(duration_ms, 2)},
                tags=["health"],
            )
        except Exception:
            pass  # never let audit failure propagate

    # ---------------------------------------------------------
    # Modern action handler
    # ---------------------------------------------------------
    async def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        """
        Modern agents override this.
        Legacy agents may define sync_execute_action().
        """
        method = getattr(self, "sync_execute_action", None)
        if callable(method):
            return method(action_type, target, details)

        return {
            "status": "error",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "message": "execute_action() not implemented."
        }
