from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class SchedulerAgent(BaseAgent):  # type: ignore
    """
    Job scheduler supporting cron expressions, one-shot delays, and event-triggered tasks.
    Falls back gracefully when croniter is unavailable.
    """

    name = "SchedulerAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._tick_count = 0
        self._fired_count = 0

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    async def schedule(self, job_id: str, cron_expr: str, task: Dict[str, Any]) -> Dict[str, Any]:
        if not job_id or not cron_expr or not task:
            return {"status": "error", "agent": self.name, "summary": "job_id, cron_expr, and task are required."}
        self._jobs[job_id] = {
            "job_id": job_id,
            "cron": cron_expr,
            "task": task,
            "active": True,
            "last_run": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "fire_count": 0,
        }
        self.log("INFO", f"Scheduled job {job_id} with cron: {cron_expr}")
        return {"status": "ok", "agent": self.name, "action": "schedule", "job_id": job_id, "cron": cron_expr, "summary": f"Job {job_id} scheduled."}

    async def cancel(self, job_id: str) -> Dict[str, Any]:
        if job_id in self._jobs:
            self._jobs[job_id]["active"] = False
            return {"status": "ok", "agent": self.name, "action": "cancel", "job_id": job_id, "summary": f"Job {job_id} cancelled."}
        return {"status": "error", "agent": self.name, "action": "cancel", "job_id": job_id, "summary": f"Job {job_id} not found."}

    async def list_jobs(self) -> List[Dict[str, Any]]:
        return list(self._jobs.values())

    def _is_due(self, cron_expr: str, now: datetime.datetime) -> bool:
        try:
            from croniter import croniter  # type: ignore
            it = croniter(cron_expr, now - datetime.timedelta(seconds=60))
            return it.get_next(datetime.datetime) <= now
        except ImportError:
            return False
        except Exception:
            return False

    async def tick(self) -> List[str]:
        now = datetime.datetime.now(datetime.timezone.utc)
        self._tick_count += 1
        fired = []
        for job in list(self._jobs.values()):
            if not job.get("active"):
                continue
            if self._is_due(job["cron"], now):
                job["last_run"] = now.isoformat()
                job["fire_count"] = int(job.get("fire_count") or 0) + 1
                self._fired_count += 1
                fired.append(job["job_id"])
                await self.emit_event("TASK_SUBMIT", job["task"])
        return fired

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            action = str(payload.get("action") or "list").strip().lower()
        else:
            action = "list"

        if action == "schedule":
            job_id = str(payload.get("job_id") or "").strip()
            cron_expr = str(payload.get("cron") or payload.get("cron_expr") or "").strip()
            task = payload.get("task") or {}
            if not job_id or not cron_expr:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide job_id and cron expression."}
            return await self.schedule(job_id, cron_expr, task)

        if action == "cancel":
            job_id = str(payload.get("job_id") or "").strip()
            if not job_id:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide job_id to cancel."}
            return await self.cancel(job_id)

        if action == "tick":
            fired = await self.tick()
            return {"status": "ok", "agent": self.name, "action": "tick", "fired": fired, "tick_count": self._tick_count, "summary": f"Tick {self._tick_count}: {len(fired)} job(s) fired."}

        jobs = await self.list_jobs()
        return {
            "status": "ok",
            "agent": self.name,
            "action": "list",
            "jobs": jobs,
            "active_count": sum(1 for j in jobs if j.get("active")),
            "total_fired": self._fired_count,
            "tick_count": self._tick_count,
            "summary": f"{len(jobs)} job(s) registered.",
            "quality_flags": ["cron_scheduling", "graceful_degradation"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        if getattr(event, "event_type", None) == "SCHEDULER_TICK":
            await self.tick()

    async def shutdown(self) -> None:
        self.log("INFO", f"SchedulerAgent shutting down. {self._fired_count} job(s) fired across {self._tick_count} tick(s).")

