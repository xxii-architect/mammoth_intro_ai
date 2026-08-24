from __future__ import annotations

import heapq
import inspect
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_agent import BaseAgent


class TaskQueueAgent(BaseAgent):
    """Durable priority task queue with retry and dead-letter tracking."""

    name = "TaskQueueAgent"

    def __init__(self, router, storage_root: str | None = None):
        super().__init__(router)
        self.storage_root = Path(storage_root) if storage_root else Path(__file__).resolve().parents[3] / ".mammoth"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._state_path = self.storage_root / "task_queue.json"
        self._heap: List[Tuple[int, int, Dict[str, Any]]] = []
        self._in_progress: Dict[str, Dict[str, Any]] = {}
        self._dead_letter: List[Dict[str, Any]] = []
        self._completed: List[Dict[str, Any]] = []
        self._sequence = 0
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_state()
            self._loaded = True

    def _load_state(self) -> None:
        self._heap.clear()
        self._in_progress.clear()
        self._dead_letter.clear()
        self._completed.clear()
        self._sequence = 0
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return

        if isinstance(data, dict):
            queued = data.get("queued") if isinstance(data.get("queued"), list) else []
            in_progress = data.get("in_progress") if isinstance(data.get("in_progress"), list) else []
            dead_letter = data.get("dead_letter") if isinstance(data.get("dead_letter"), list) else []
            completed = data.get("completed") if isinstance(data.get("completed"), list) else []
            sequence = data.get("sequence")
        elif isinstance(data, list):
            queued = data
            in_progress = []
            dead_letter = []
            completed = []
            sequence = None
        else:
            return

        for item in queued:
            task = self._normalize_task(item, status_default="queued")
            self._sequence += 1
            heapq.heappush(self._heap, (int(task.get("priority", 5)), self._sequence, task))
        for item in in_progress:
            task = self._normalize_task(item, status_default="in_progress")
            task_id = str(task.get("task_id") or "")
            if task_id:
                self._in_progress[task_id] = task
        for item in dead_letter:
            task = self._normalize_task(item, status_default="dead")
            self._dead_letter.append(task)
        for item in completed:
            task = self._normalize_task(item, status_default="completed")
            self._completed.append(task)
        if isinstance(sequence, int) and sequence >= 0:
            self._sequence = max(self._sequence, sequence)

    def _save_state(self) -> None:
        payload = {
            "sequence": self._sequence,
            "queued": [task for _, _, task in sorted(self._heap, key=lambda item: (item[0], item[1]))],
            "in_progress": list(self._in_progress.values()),
            "dead_letter": list(self._dead_letter),
            "completed": list(self._completed),
        }
        tmp_path = self._state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp_path.replace(self._state_path)

    def _normalize_task(self, task: Dict[str, Any], *, status_default: str = "queued") -> Dict[str, Any]:
        normalized = dict(task or {})
        task_id = str(normalized.get("task_id") or normalized.get("id") or uuid.uuid4()).strip()
        now = normalized.get("updated_at") or normalized.get("created_at") or ""
        if not now:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
        try:
            priority = int(normalized.get("priority", 5) or 5)
        except (TypeError, ValueError):
            priority = 5
        try:
            attempts = int(normalized.get("attempts", 0) or 0)
        except (TypeError, ValueError):
            attempts = 0
        normalized.update(
            {
                "task_id": task_id,
                "priority": priority,
                "attempts": attempts,
                "status": str(normalized.get("status") or status_default).upper(),
            }
        )
        normalized.setdefault("title", str(normalized.get("title") or "Untitled task").strip())
        normalized.setdefault("description", str(normalized.get("description") or "").strip())
        normalized.setdefault("dependencies", normalized.get("dependencies") or normalized.get("depends_on") or [])
        normalized.setdefault("created_at", now)
        normalized["updated_at"] = normalized.get("updated_at") or now
        return normalized

    async def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        handler = getattr(self, "emit_event", None)
        if callable(handler):
            result = handler(event_name, payload)
            if inspect.isawaitable(result):
                await result
            return
        router = getattr(self, "router", None)
        router_handler = getattr(router, "emit_event", None) if router is not None else None
        if callable(router_handler):
            result = router_handler(event_name, payload)
            if inspect.isawaitable(result):
                await result

    def _status_summary(self) -> Dict[str, Any]:
        queued = sorted(self._heap, key=lambda item: (item[0], item[1]))
        next_task = queued[0][2] if queued else None
        return {
            "status": "ok",
            "agent": self.name,
            "queue_depth": len(queued),
            "in_progress_count": len(self._in_progress),
            "dead_letter_count": len(self._dead_letter),
            "completed_count": len(self._completed),
            "next_task": dict(next_task) if isinstance(next_task, dict) else None,
        }

    async def enqueue(self, task: Dict[str, Any]) -> str:
        self._ensure_loaded()
        task = self._normalize_task(task)
        task_id = str(task.get("task_id") or uuid.uuid4()).strip()
        task["task_id"] = task_id
        task["status"] = "QUEUED"
        task["updated_at"] = task.get("updated_at")
        self._sequence += 1
        heapq.heappush(self._heap, (int(task.get("priority", 5)), self._sequence, task))
        self._save_state()
        await self._emit_event("TASK_ENQUEUED", {"task_id": task_id, "priority": task.get("priority", 5)})
        return task_id

    async def dequeue(self) -> dict | None:
        self._ensure_loaded()
        if not self._heap:
            return None
        _, _, task = heapq.heappop(self._heap)
        task = self._normalize_task(task, status_default="in_progress")
        task["status"] = "IN_PROGRESS"
        from datetime import datetime, timezone
        task["started_at"] = task.get("started_at") or datetime.now(timezone.utc).isoformat()
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._in_progress[task["task_id"]] = task
        self._save_state()
        return dict(task)

    async def complete(self, task_id: str, result: Any) -> None:
        self._ensure_loaded()
        task = self._in_progress.pop(task_id, None)
        if not task:
            return
        from datetime import datetime, timezone
        task["status"] = "COMPLETED"
        task["result"] = result
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["updated_at"] = task["completed_at"]
        self._completed.append(task)
        self._save_state()
        await self._emit_event("TASK_COMPLETED", {"task_id": task_id, "result": result})

    async def fail(self, task_id: str, error: str) -> None:
        self._ensure_loaded()
        task = self._in_progress.pop(task_id, None)
        if not task:
            return
        from datetime import datetime, timezone
        task = self._normalize_task(task, status_default="retry")
        task["attempts"] = int(task.get("attempts", 0) or 0) + 1
        task["last_error"] = error
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        max_retries = int(task.get("max_retries", 3) or 3)
        if task["attempts"] < max_retries:
            task["status"] = "RETRY"
            self._sequence += 1
            heapq.heappush(self._heap, (int(task.get("priority", 5)), self._sequence, task))
            self._save_state()
            await self._emit_event("TASK_RETRY", {"task_id": task_id, "attempt": task["attempts"]})
        else:
            task["status"] = "DEAD"
            self._dead_letter.append(task)
            self._save_state()
            await self._emit_event("TASK_DEAD_LETTER", {"task_id": task_id, "error": error})

    def run(self, prompt: Any) -> Dict[str, Any]:
        self._ensure_loaded()
        request = dict(prompt) if isinstance(prompt, dict) else {"action": "status", "prompt": str(prompt or "")}
        action = str(request.get("action") or request.get("operation") or "status").strip().lower()
        if action in {"enqueue", "submit"}:
            task_id = uuid.uuid4().hex[:8]
            payload = {
                "task_id": request.get("task_id") or f"task-{task_id}",
                "title": request.get("title") or request.get("prompt") or "Queued task",
                "description": request.get("description") or request.get("prompt") or "",
                "priority": request.get("priority", 5),
                "max_retries": request.get("max_retries", 3),
                "details": request.get("details") or {},
            }
            return {
                "status": "ok",
                "agent": self.name,
                "action": "enqueue",
                "task_id": asyncio_run(self.enqueue(payload)),
            }
        if action == "dequeue":
            task = asyncio_run(self.dequeue())
            return {"status": "ok", "agent": self.name, "action": "dequeue", "task": task}
        if action == "complete":
            task_id = str(request.get("task_id") or request.get("id") or "").strip()
            asyncio_run(self.complete(task_id, request.get("result")))
            return {"status": "ok", "agent": self.name, "action": "complete", "task_id": task_id}
        if action in {"fail", "dead_letter"}:
            task_id = str(request.get("task_id") or request.get("id") or "").strip()
            asyncio_run(self.fail(task_id, str(request.get("error") or request.get("message") or "task failed")))
            return {"status": "ok", "agent": self.name, "action": "fail", "task_id": task_id}
        return self._status_summary()

    async def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        payload = dict(details or {})
        payload.setdefault("action", action_type)
        payload.setdefault("target", target)
        if action_type in {"enqueue", "submit", "dequeue", "complete", "fail", "status"}:
            if action_type == "status":
                return self._status_summary()
            return self.run(payload)
        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event.event_type == "TASK_SUBMIT":
            await self.enqueue(event.payload)
        elif event.event_type == "TASK_COMPLETE":
            await self.complete(str(event.payload.get("task_id") or ""), event.payload.get("result"))
        elif event.event_type == "TASK_FAIL":
            await self.fail(str(event.payload.get("task_id") or ""), str(event.payload.get("error") or "task failed"))

    async def shutdown(self) -> None:
        self._save_state()
        self.log("INFO", "TaskQueueAgent shutting down. %d queued, %d in progress, %d dead.", len(self._heap), len(self._in_progress), len(self._dead_letter))


def asyncio_run(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    return asyncio.run(coro)
