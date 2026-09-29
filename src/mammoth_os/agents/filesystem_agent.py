from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class FileSystemAgent(BaseAgent):  # type: ignore
    """
    Abstracts all file system operations: read, write, delete, index, and watch.
    Provides a scoped virtual file layer. Emits FILESYSTEM_CHANGED events on mutations.
    Private paths (user personal data) are never mixed with shared workspace context.
    """

    name = "FileSystemAgent"

    def __init__(self, router: Any = None, base_path: Optional[str] = None):
        super().__init__(router)
        self._base_path = str(base_path or os.environ.get("MAMMOTH_WORKSPACE", "/mammoth/workspace"))
        self._watchers: Dict[str, bool] = {}
        self._op_log: List[Dict[str, Any]] = []

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    def _resolve(self, path: str) -> str:
        resolved = os.path.realpath(os.path.join(self._base_path, path.lstrip("/")))
        if not resolved.startswith(os.path.realpath(self._base_path)):
            raise PermissionError(f"Path traversal denied: {path}")
        return resolved

    def _record_op(self, op: str, path: str, extra: Optional[dict] = None) -> None:
        import datetime
        entry = {"op": op, "path": path, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if extra:
            entry.update(extra)
        self._op_log.append(entry)
        if len(self._op_log) > 500:
            self._op_log = self._op_log[-500:]

    async def read(self, path: str) -> str:
        full = self._resolve(path)
        with open(full, "r", encoding="utf-8") as f:
            content = f.read()
        self._record_op("read", path)
        return content

    async def write(self, path: str, content: str) -> None:
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        self._record_op("write", path, {"size_bytes": len(content.encode())})
        await self.emit_event("FILESYSTEM_CHANGED", {"path": path, "action": "write"})

    async def delete(self, path: str) -> None:
        full = self._resolve(path)
        os.remove(full)
        self._record_op("delete", path)
        await self.emit_event("FILESYSTEM_CHANGED", {"path": path, "action": "delete"})

    async def exists(self, path: str) -> bool:
        try:
            return os.path.exists(self._resolve(path))
        except PermissionError:
            return False

    async def index_directory(self, path: str, recursive: bool = True) -> List[str]:
        files: List[str] = []
        root_path = self._resolve(path)
        for dirpath, _dirs, filenames in os.walk(root_path):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                files.append(os.path.relpath(full, self._base_path))
            if not recursive:
                break
        return files

    async def watch(self, path: str) -> None:
        self._watchers[path] = True
        self.log("INFO", f"Watching path: {path}")

    async def audit_log(self) -> List[Dict[str, Any]]:
        return list(self._op_log)

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            op = str(payload.get("op") or payload.get("operation") or payload.get("action") or "").strip().lower()
            path = str(payload.get("path") or "").strip()
            content = payload.get("content")
            recursive = bool(payload.get("recursive", True))
        else:
            op = "status"
            path = ""
            content = None
            recursive = True

        if op == "read":
            if not path:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide a path to read."}
            try:
                text = await self.read(path)
                return {"status": "ok", "agent": self.name, "op": "read", "path": path, "content": text, "size_bytes": len(text.encode()), "summary": f"Read {len(text)} chars from {path}."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "op": "read", "path": path, "error": str(exc), "summary": f"Read failed for {path}."}

        if op == "write":
            if not path or content is None:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide path and content to write."}
            try:
                await self.write(path, str(content))
                return {"status": "ok", "agent": self.name, "op": "write", "path": path, "size_bytes": len(str(content).encode()), "summary": f"Wrote {len(str(content))} chars to {path}."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "op": "write", "path": path, "error": str(exc)}

        if op == "delete":
            if not path:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide a path to delete."}
            try:
                await self.delete(path)
                return {"status": "ok", "agent": self.name, "op": "delete", "path": path, "summary": f"Deleted {path}."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "op": "delete", "path": path, "error": str(exc)}

        if op == "index":
            try:
                files = await self.index_directory(path or ".", recursive=recursive)
                return {"status": "ok", "agent": self.name, "op": "index", "path": path, "files": files, "count": len(files), "summary": f"Indexed {len(files)} file(s)."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "op": "index", "path": path, "error": str(exc)}

        if op == "audit":
            return {"status": "ok", "agent": self.name, "op": "audit", "entries": await self.audit_log(), "summary": f"{len(self._op_log)} operation(s) logged."}

        return {
            "status": "ok",
            "agent": self.name,
            "op": "status",
            "base_path": self._base_path,
            "watched_paths": list(self._watchers.keys()),
            "ops_logged": len(self._op_log),
            "summary": "FileSystemAgent is active.",
            "quality_flags": ["path_traversal_protection", "op_audit_log"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        et = getattr(event, "event_type", None)
        payload = getattr(event, "payload", {}) or {}
        if et == "FILESYSTEM_OP":
            await self.run({**payload, "op": payload.get("operation", "")})

    async def shutdown(self) -> None:
        self.log("INFO", f"FileSystemAgent shutting down. {len(self._op_log)} ops logged.")

