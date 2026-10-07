"""Typed run events emitted by the Mammoth Mind agent loop.

Every event is emitted at the moment the underlying action happens; nothing is
replayed or simulated. The same envelope is used for SSE streaming, persisted
run records, and the Workspace SDK.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

EVENT_CONTRACT_VERSION = "mammoth.run.v1"

RUN_STARTED = "run.started"
PLAN_UPDATED = "plan.updated"
REASONING_SUMMARY = "reasoning.summary"
TOOL_CALL = "tool.call"
TOOL_RESULT = "tool.result"
APPROVAL_REQUESTED = "approval.requested"
APPROVAL_RESOLVED = "approval.resolved"
DIFF_PROPOSED = "diff.proposed"
MESSAGE_DELTA = "message.delta"
MESSAGE_COMPLETED = "message.completed"
RUN_AWAITING_APPROVAL = "run.awaiting_approval"
RUN_COMPLETED = "run.completed"
RUN_FAILED = "run.failed"
RUN_CANCELLED = "run.cancelled"
RUN_PARTIAL = "run.partial"
RUN_CONTINUED = "run.continued"
MODEL_COMPLETED = "model.completed"
RUN_RECOVERING = "run.recovering"

EVENT_TYPES = (
    RUN_STARTED,
    PLAN_UPDATED,
    REASONING_SUMMARY,
    TOOL_CALL,
    TOOL_RESULT,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    DIFF_PROPOSED,
    MESSAGE_DELTA,
    MESSAGE_COMPLETED,
    RUN_AWAITING_APPROVAL,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_CANCELLED,
    RUN_PARTIAL,
    RUN_CONTINUED,
    MODEL_COMPLETED,
    RUN_RECOVERING,
)

TERMINAL_EVENT_TYPES = frozenset({RUN_COMPLETED, RUN_FAILED, RUN_CANCELLED, RUN_AWAITING_APPROVAL, RUN_PARTIAL})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunEvent:
    run_id: str
    seq: int
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"Unknown run event type: {self.type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": EVENT_CONTRACT_VERSION,
            "run_id": self.run_id,
            "seq": self.seq,
            "type": self.type,
            "ts": self.ts,
            "data": self.data,
        }

    def to_sse(self) -> str:
        payload = json.dumps(self.to_dict(), default=str)
        return f"id: {self.seq}\nevent: {self.type}\ndata: {payload}\n\n"
