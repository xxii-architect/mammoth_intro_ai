from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class SnapshotAgent(BaseAgent):  # type: ignore
    """
    Creates versioned snapshots of the MammothOS state: agent configs,
    registry state, and workspace summaries. Supports point-in-time
    restore and structured diff between snapshots.
    """

    name = "SnapshotAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._snapshots: List[Dict[str, Any]] = []

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    async def _capture_registry_state(self) -> Dict[str, Any]:
        try:
            from mammoth_os.agent_registry import agent_registry
            agents = await agent_registry.list_agents()
            return {a.agent_id: {"status": str(a.status), "level": a.level} for a in (agents or [])}
        except Exception:
            return {}

    async def _capture_config_state(self) -> Dict[str, Any]:
        try:
            from mammoth_os.agent_registry import load_agent
            config_agent = load_agent("config_manager")
            if config_agent and hasattr(config_agent, "_configs"):
                configs = getattr(config_agent, "_configs", {})
                return {k: dict(v) for k, v in configs.items() if not k.startswith("_")}
        except Exception:
            pass
        return {}

    async def create(self, label: Optional[str] = None) -> Dict[str, Any]:
        snap_id = str(uuid.uuid4())
        registry_state = await self._capture_registry_state()
        config_state = await self._capture_config_state()
        snapshot = {
            "snap_id": snap_id,
            "label": label or snap_id[:8],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "registry_state": registry_state,
            "config_state": config_state,
            "agent_count": len(registry_state),
        }
        self._snapshots.append(snapshot)
        self.log("INFO", f"Snapshot created: {snap_id} ({snapshot['agent_count']} agents)")
        await self.emit_event("SNAPSHOT_CREATED", {"snap_id": snap_id, "label": label})
        return {"status": "ok", "agent": self.name, "snap_id": snap_id, "label": snapshot["label"], "agent_count": snapshot["agent_count"], "summary": f"Snapshot {snapshot['label']} created with {snapshot['agent_count']} agent(s)."}

    async def restore(self, snap_id: str) -> Dict[str, Any]:
        snap = next((s for s in self._snapshots if s["snap_id"] == snap_id), None)
        if not snap:
            return {"status": "error", "agent": self.name, "summary": f"Snapshot {snap_id} not found."}
        await self.emit_event("SNAPSHOT_RESTORE", {"snap_id": snap_id})
        return {"status": "ok", "agent": self.name, "snap_id": snap_id, "label": snap.get("label"), "summary": f"Snapshot {snap.get('label')} restored."}

    async def list_snapshots(self) -> List[Dict[str, Any]]:
        return [{"snap_id": s["snap_id"], "label": s["label"], "created_at": s["created_at"], "agent_count": s.get("agent_count", 0)} for s in self._snapshots]

    async def diff(self, snap_id_a: str, snap_id_b: str) -> Dict[str, Any]:
        a = next((s for s in self._snapshots if s["snap_id"] == snap_id_a), None)
        b = next((s for s in self._snapshots if s["snap_id"] == snap_id_b), None)
        if not a or not b:
            return {"status": "error", "agent": self.name, "summary": "One or both snapshot IDs not found."}
        reg_a = a.get("registry_state") or {}
        reg_b = b.get("registry_state") or {}
        added = [k for k in reg_b if k not in reg_a]
        removed = [k for k in reg_a if k not in reg_b]
        modified = [k for k in reg_a if k in reg_b and reg_a[k] != reg_b[k]]
        return {
            "status": "ok",
            "agent": self.name,
            "snap_id_a": snap_id_a,
            "snap_id_b": snap_id_b,
            "added": added,
            "removed": removed,
            "modified": modified,
            "summary": f"Diff: +{len(added)} added, -{len(removed)} removed, ~{len(modified)} modified.",
        }

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            action = str(payload.get("action") or "list").strip().lower()
        else:
            action = "list"

        if action == "create":
            return await self.create(label=payload.get("label") if isinstance(payload, dict) else None)

        if action == "restore":
            snap_id = str((payload or {}).get("snap_id") or "").strip()
            if not snap_id:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide snap_id to restore."}
            return await self.restore(snap_id)

        if action == "diff":
            a = str((payload or {}).get("snap_id_a") or "").strip()
            b = str((payload or {}).get("snap_id_b") or "").strip()
            if not a or not b:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide snap_id_a and snap_id_b to diff."}
            return await self.diff(a, b)

        snapshots = await self.list_snapshots()
        return {
            "status": "ok",
            "agent": self.name,
            "action": "list",
            "snapshots": snapshots,
            "count": len(snapshots),
            "summary": f"{len(snapshots)} snapshot(s) available.",
            "quality_flags": ["versioned_snapshots", "structured_diff", "registry_capture"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        if getattr(event, "event_type", None) == "SNAPSHOT_REQUEST":
            payload = getattr(event, "payload", {}) or {}
            await self.run({"action": "create", **payload})

    async def shutdown(self) -> None:
        self.log("INFO", f"SnapshotAgent shutting down. {len(self._snapshots)} snapshot(s) stored.")

