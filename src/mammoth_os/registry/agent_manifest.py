# mammoth_os/registry/agent_manifest.py
# Defines AgentManifest + AgentStatus for Mammoth OS

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    ACTIVE   = "ACTIVE"
    IDLE     = "IDLE"
    ERROR    = "ERROR"
    LOADING  = "LOADING"
    SHUTDOWN = "SHUTDOWN"


@dataclass
class AgentManifest:
    """
    Metadata describing a registered Mammoth OS agent.
    Used by the AgentRegistry for discovery, health, and capability tracking.
    """
    agent_id:       str
    name:           str
    version:        str
    capabilities:   list[str]
    status:         AgentStatus
    level:          int
    dependencies:   list[str]
    endpoint:       str
    registered_at:  datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    last_heartbeat: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    metadata:       dict[str, Any]    = field(default_factory=dict)
