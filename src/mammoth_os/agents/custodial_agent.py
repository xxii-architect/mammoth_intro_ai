from __future__ import annotations

import base64
import datetime
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class CustodialAgent(BaseAgent):
    """
    CustodialAgent
    --------------
    Handles workspace hygiene, snapshots, and rollback-aware cleanup.
    Mutating actions require explicit approval in the details payload.
    """

    name = "CustodialAgent"

    CLEANUP_FILE_SUFFIXES = {
        ".bak",
        ".log",
        ".old",
        ".pyo",
        ".pyc",
        ".swp",
        ".swo",
        ".tmp",
    }

    CLEANUP_FILE_NAMES = {".DS_Store", "Thumbs.db"}

    CLEANUP_DIR_NAMES = {
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "coverage",
        "dist",
    }

    def __init__(self, router, storage_root: Optional[str] = None):
        super().__init__(router)
        self.storage_root = Path(storage_root).expanduser() if storage_root else self._repo_root() / ".mammoth" / "custodial"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.storage_root / "custodial_snapshots.json"

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _resolve_workspace(self, target: Optional[str] = None) -> Path:
        base = Path(target).expanduser() if target else Path.cwd()
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()
        return base

    def _load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {"snapshots": []}
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"snapshots": []}
        snapshots = data.get("snapshots")
        if not isinstance(snapshots, list):
            data["snapshots"] = []
        return data

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _is_cleanup_candidate(self, path: Path) -> bool:
        if path.name in self.CLEANUP_FILE_NAMES:
            return True
        if path.is_dir():
            return path.name in self.CLEANUP_DIR_NAMES
        if path.suffix.lower() in self.CLEANUP_FILE_SUFFIXES:
            return True
        return path.name.endswith("~")

    def _walk_cleanup_targets(self, workspace: Path) -> Dict[str, List[Path]]:
        files: List[Path] = []
        dirs: List[Path] = []
        for path in sorted(workspace.rglob("*"), key=lambda p: (len(p.parts), str(p))):
            if path.is_dir() and self._is_cleanup_candidate(path):
                dirs.append(path)
            elif path.is_file() and self._is_cleanup_candidate(path):
                files.append(path)
        dirs.sort(key=lambda p: len(p.parts), reverse=True)
        return {"files": files, "dirs": dirs}

    def _capture_file(self, workspace: Path, path: Path) -> Dict[str, Any]:
        relative_path = path.relative_to(workspace).as_posix()
        payload = path.read_bytes()
        return {
            "relative_path": relative_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "content_b64": base64.b64encode(payload).decode("ascii"),
            "size": len(payload),
        }

    def _create_snapshot(
        self,
        workspace: Path,
        files: List[Path],
        dirs: List[Path],
        label: str,
    ) -> Dict[str, Any]:
        manifest = self._load_manifest()
        snapshot_id = str(uuid.uuid4())
        snapshot = {
            "snapshot_id": snapshot_id,
            "label": label or snapshot_id,
            "workspace": str(workspace),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "files": [self._capture_file(workspace, path) for path in files],
            "dirs": [path.relative_to(workspace).as_posix() for path in dirs],
        }
        manifest.setdefault("snapshots", []).append(snapshot)
        self._save_manifest(manifest)
        return snapshot

    def _find_snapshot(self, snapshot_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not snapshot_id:
            return None
        manifest = self._load_manifest()
        for snapshot in manifest.get("snapshots", []):
            if snapshot.get("snapshot_id") == snapshot_id:
                return snapshot
        return None

    def _build_hygiene_report(self, workspace: Path) -> Dict[str, Any]:
        targets = self._walk_cleanup_targets(workspace)
        files = targets["files"]
        dirs = targets["dirs"]
        return {
            "workspace": str(workspace),
            "candidate_count": len(files) + len(dirs),
            "file_candidates": [path.relative_to(workspace).as_posix() for path in files[:25]],
            "dir_candidates": [path.relative_to(workspace).as_posix() for path in dirs[:25]],
            "guardrails": [
                "Mutating cleanup requires explicit approval.",
                "Only generated cache and build artifacts are targeted by default.",
                "Rollback captures deleted file contents before removal.",
            ],
        }

    def _approval_allowed(self, details: Dict[str, Any]) -> bool:
        return bool(details.get("approved") or details.get("allow_mutating") or details.get("force"))

    async def run(self, prompt: str) -> Dict[str, Any]:
        prompt_text = str(prompt or "").strip()
        intent = self._infer_intent(prompt_text)
        workspace = self._resolve_workspace(None)
        report = self._build_hygiene_report(workspace)

        return {
            "status": "ok",
            "agent": self.name,
            "mode": "custodial",
            "prompt": prompt_text,
            "intent": intent,
            "workspace": report["workspace"],
            "candidate_count": report["candidate_count"],
            "cleanup_candidates": report["file_candidates"][:5],
            "rollback_ready": True,
            "guardrails": report["guardrails"],
            "next_actions": [
                "Run a dry-run cleanup to review the candidate set.",
                "Approve a cleanup action before any file removal.",
                "Use a snapshot id to restore deleted workspace artifacts.",
            ],
        }

    def _infer_intent(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if any(token in prompt_lower for token in ("restore", "rollback", "undo")):
            return "restore"
        if any(token in prompt_lower for token in ("snapshot", "checkpoint", "backup")):
            return "snapshot"
        if any(token in prompt_lower for token in ("cleanup", "clean", "prune", "hygiene")):
            return "cleanup"
        if any(token in prompt_lower for token in ("audit", "inspect", "status", "health")):
            return "inspect"
        return "lifecycle"

    async def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        action = str(action_type or "").strip().lower()
        workspace = self._resolve_workspace(target or details.get("workspace"))

        if action in {"inspect", "status", "audit"}:
            return {
                "status": "ok",
                "agent": self.name,
                "action": action,
                "workspace": str(workspace),
                "report": self._build_hygiene_report(workspace),
            }

        if action in {"snapshot", "checkpoint"}:
            targets = self._walk_cleanup_targets(workspace)
            snapshot = self._create_snapshot(
                workspace,
                files=targets["files"],
                dirs=targets["dirs"],
                label=str(details.get("label") or details.get("reason") or action),
            )
            return {
                "status": "ok",
                "agent": self.name,
                "action": action,
                "workspace": str(workspace),
                "snapshot_id": snapshot["snapshot_id"],
                "files_captured": len(snapshot["files"]),
                "dirs_captured": len(snapshot["dirs"]),
            }

        if action in {"cleanup", "clean", "prune"}:
            dry_run = bool(details.get("dry_run"))
            approved = self._approval_allowed(details)
            report = self._build_hygiene_report(workspace)
            if dry_run or not approved:
                return {
                    "status": "pending_approval" if not approved else "planned",
                    "agent": self.name,
                    "action": action,
                    "workspace": str(workspace),
                    "report": report,
                    "requires_approval": not approved,
                }

            targets = self._walk_cleanup_targets(workspace)
            snapshot = self._create_snapshot(
                workspace,
                files=targets["files"],
                dirs=targets["dirs"],
                label=str(details.get("label") or details.get("reason") or "cleanup"),
            )

            removed_files: List[str] = []
            for path in targets["files"]:
                if path.exists():
                    path.unlink()
                    removed_files.append(path.relative_to(workspace).as_posix())

            removed_dirs: List[str] = []
            for path in targets["dirs"]:
                if path.exists():
                    shutil.rmtree(path)
                    removed_dirs.append(path.relative_to(workspace).as_posix())

            return {
                "status": "ok",
                "agent": self.name,
                "action": action,
                "workspace": str(workspace),
                "snapshot_id": snapshot["snapshot_id"],
                "removed_files": removed_files,
                "removed_dirs": removed_dirs,
            }

        if action in {"restore", "rollback"}:
            approved = self._approval_allowed(details)
            if not approved:
                snapshot_id = details.get("snapshot_id")
                snapshot = self._find_snapshot(snapshot_id)
                return {
                    "status": "pending_approval",
                    "agent": self.name,
                    "action": action,
                    "workspace": str(workspace),
                    "snapshot_id": snapshot_id,
                    "available": bool(snapshot),
                    "requires_approval": True,
                }

            snapshot_id = str(details.get("snapshot_id") or "").strip()
            snapshot = self._find_snapshot(snapshot_id)
            if snapshot is None:
                raise ValueError("snapshot_id is required and must reference an existing snapshot")

            restored_files: List[str] = []
            for file_entry in snapshot.get("files", []):
                relative_path = str(file_entry.get("relative_path") or "").strip()
                if not relative_path:
                    continue
                payload = base64.b64decode(str(file_entry.get("content_b64") or ""))
                target_path = workspace / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(payload)
                restored_files.append(relative_path)

            restored_dirs: List[str] = []
            for relative_dir in snapshot.get("dirs", []):
                dir_path = workspace / str(relative_dir)
                dir_path.mkdir(parents=True, exist_ok=True)
                restored_dirs.append(str(relative_dir))

            return {
                "status": "ok",
                "agent": self.name,
                "action": action,
                "workspace": str(workspace),
                "snapshot_id": snapshot_id,
                "restored_files": restored_files,
                "restored_dirs": restored_dirs,
            }

        if action in {"lifecycle", "health"}:
            return {
                "status": "ok",
                "agent": self.name,
                "action": action,
                "workspace": str(workspace),
                "report": self._build_hygiene_report(workspace),
            }

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "workspace": str(workspace),
        }
