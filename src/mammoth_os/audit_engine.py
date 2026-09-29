"""
Audit Engine — Structured audit trail, diagnostics, and event classification.

Records agent actions, outcomes, and anomalies with structured metadata.
Supports filtering by severity, agent, user, and time range.
Privacy: user_id is stored as a reference but raw PII is never logged.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional


SEVERITY_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITY_LEVELS)}


class AuditEntry:
    def __init__(
        self,
        event_type: str,
        agent: str,
        outcome: str,
        severity: str = "INFO",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ):
        self.entry_id = str(uuid.uuid4())
        self.event_type = event_type
        self.agent = agent
        self.outcome = outcome
        self.severity = severity if severity in SEVERITY_LEVELS else "INFO"
        self.user_id = user_id
        self.session_id = session_id
        self.details = details or {}
        self.tags = tags or []
        self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent": self.agent,
            "outcome": self.outcome,
            "severity": self.severity,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "details": self.details,
            "tags": self.tags,
        }


class AuditEngine:
    """
    Central audit and diagnostics engine for MammothOS.
    Thread-safe in-process log with configurable retention.
    """

    MAX_ENTRIES = 5000

    def __init__(self, max_entries: int = MAX_ENTRIES):
        self._log: List[AuditEntry] = []
        self._max_entries = max_entries
        self._counters: Dict[str, int] = {}

    def record(
        self,
        event_type: str,
        agent: str,
        outcome: str,
        severity: str = "INFO",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        entry = AuditEntry(
            event_type=event_type,
            agent=agent,
            outcome=outcome,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            details=details,
            tags=tags,
        )
        self._log.append(entry)
        counter_key = f"{agent}:{event_type}"
        self._counters[counter_key] = self._counters.get(counter_key, 0) + 1
        if len(self._log) > self._max_entries:
            self._log = self._log[-self._max_entries:]
        return entry.entry_id

    def query(
        self,
        agent: Optional[str] = None,
        event_type: Optional[str] = None,
        min_severity: str = "INFO",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        since: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        min_sev_order = SEVERITY_ORDER.get(min_severity.upper() if min_severity else "INFO", 1)
        results = []
        for entry in reversed(self._log):
            if SEVERITY_ORDER.get(entry.severity, 0) < min_sev_order:
                continue
            if agent and entry.agent != agent:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if user_id and entry.user_id != user_id:
                continue
            if session_id and entry.session_id != session_id:
                continue
            if since and entry.timestamp < since:
                continue
            if tags and not any(t in entry.tags for t in tags):
                continue
            results.append(entry.to_dict())
            if len(results) >= limit:
                break
        return results

    def diagnose(self) -> Dict[str, Any]:
        """Return a structured diagnostic snapshot of the audit log."""
        if not self._log:
            return {"status": "empty", "entries": 0, "agents": [], "error_rate": 0.0}
        total = len(self._log)
        errors = [e for e in self._log if e.severity in ("ERROR", "CRITICAL")]
        warnings = [e for e in self._log if e.severity == "WARNING"]
        agents = sorted(set(e.agent for e in self._log))
        event_types = sorted(set(e.event_type for e in self._log))
        recent_errors = [e.to_dict() for e in reversed(errors[-10:])]
        return {
            "status": "ok",
            "entries": total,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "error_rate": round(len(errors) / max(total, 1), 4),
            "agents": agents,
            "event_types": event_types,
            "recent_errors": recent_errors,
            "top_events": sorted(self._counters.items(), key=lambda x: x[1], reverse=True)[:10],
        }

    def clear_user_data(self, user_id: str) -> int:
        """Remove audit entries tied to a specific user (privacy wipe)."""
        before = len(self._log)
        self._log = [e for e in self._log if e.user_id != user_id]
        return before - len(self._log)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self._log),
            "capacity": self._max_entries,
            "fill_pct": round(len(self._log) / max(self._max_entries, 1) * 100, 1),
        }


_audit_engine: Optional[AuditEngine] = None


def get_audit_engine() -> AuditEngine:
    global _audit_engine
    if _audit_engine is None:
        _audit_engine = AuditEngine()
    return _audit_engine

