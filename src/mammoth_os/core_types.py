# src/mammoth_os/core_types.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid import-time cycles; type checkers will resolve this.
    from mammoth_os.cortex.router import CortexRouter


# --- Risk level -------------------------------------------------------------
class RiskLevel(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


# --- Basic request / approval datatypes ------------------------------------
@dataclass
class ActionRequest:
    agent_name: str
    action_type: str
    target: Optional[str]
    details: Dict[str, Any]
    risk: RiskLevel


@dataclass
class ApprovalResult:
    approved: bool
    reason: Optional[str] = None


# --- Execution / audit types -----------------------------------------------
@dataclass
class AuditRecord:
    agent: str
    action: str
    target: Optional[str]
    start_time: float
    end_time: Optional[float]
    attempts: int
    risk_score: Optional[float]
    approved: Optional[bool]
    errors: List[str]


class StepDetails(TypedDict, total=False):
    """
    Optional per-step execution overrides.
    - _timeout: float seconds to wait before timing out the step
    - _retries: int number of retries (in addition to the first attempt)
    Other user-defined keys are allowed.
    """
    _timeout: float
    _retries: int


RiskScore = float


@dataclass
class ExecutionConfig:
    """
    Default execution configuration used by AutonomousTaskEngine and router wiring.
    """
    default_timeout: float = 10.0
    default_retries: int = 2
    backoff_factor: float = 1.5
    risk_threshold: float = 0.7


# --- Approval handler type (two supported shapes) --------------------------
# Supported handler shapes:
# 1) Full handler: Callable[[ActionRequest], ApprovalResult]
# 2) Simple handler: Callable[[agent_name: str, step: Dict[str, Any], router], bool]
ApprovalHandler = Union[
    Callable[[ActionRequest], ApprovalResult],
    Callable[[str, Dict[str, Any], "CortexRouter"], bool],
]
