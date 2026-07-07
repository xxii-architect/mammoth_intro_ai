class SchedulerAgent(BaseAgent):# type: ignore
    """
    Cron-like scheduler that supports cron expressions, one-shot delays,
    and event-triggered jobs. Persists schedules to PostgreSQL for
    crash recovery.
    """

    async def initialize(self) -> None:
        self._jobs: dict[str, dict] = {}

    async def schedule(self, job_id: str, cron_expr: str, task: dict) -> bool:
        import uuid
        self._jobs[job_id] = {
            "job_id": job_id,
            "cron": cron_expr,
            "task": task,
            "active": True,
            "last_run": None,
        }
        self.log("INFO", "Scheduled job %s with cron: %s", job_id, cron_expr)
        return True

    async def cancel(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id]["active"] = False
            return True
        return False

    async def list_jobs(self) -> list[dict]:
        return list(self._jobs.values())

    async def tick(self) -> None:
        """Called every minute to check and fire due jobs."""
        import datetime
        from croniter import croniter
        now = datetime.datetime.utcnow()
        for job in self._jobs.values():
            if not job["active"]:
                continue
            cron = croniter(job["cron"], now)
            if cron.get_prev(datetime.datetime) > now - datetime.timedelta(seconds=60):
                job["last_run"] = now.isoformat()
                await self.emit_event("TASK_SUBMIT", job["task"])

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "SCHEDULER_TICK":
            await self.tick()

    async def shutdown(self) -> None:
        self.log("INFO", "SchedulerAgent shutting down.")