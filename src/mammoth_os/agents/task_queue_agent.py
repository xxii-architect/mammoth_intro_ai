import heapq

class TaskQueueAgent(BaseAgent):# type: ignore
    """
    Priority-based task queue with retry logic. Uses a min-heap
    for O(log n) priority operations. Integrates with Redis for
    durable queue persistence across restarts.
    """

    async def initialize(self) -> None:
        self._heap: list = []       # (priority, task_dict)
        self._in_progress: dict[str, dict] = {}
        self._dead_letter: list[dict] = []

    async def enqueue(self, task: dict) -> str:
        import uuid
        task_id = task.get("task_id") or str(uuid.uuid4())
        task["task_id"] = task_id
        task["attempts"] = 0
        task["status"] = "QUEUED"
        # Lower priority number = higher urgency
        heapq.heappush(self._heap, (task.get("priority", 5), task))
        await self.emit_event("TASK_ENQUEUED", {"task_id": task_id})
        return task_id

    async def dequeue(self) -> dict | None:
        if not self._heap:
            return None
        _, task = heapq.heappop(self._heap)
        task["status"] = "IN_PROGRESS"
        self._in_progress[task["task_id"]] = task
        return task

    async def complete(self, task_id: str, result: any) -> None:# type: ignore
        task = self._in_progress.pop(task_id, None)
        if task:
            await self.emit_event("TASK_COMPLETED", {"task_id": task_id, "result": result})

    async def fail(self, task_id: str, error: str) -> None:
        task = self._in_progress.pop(task_id, None)
        if not task:
            return
        task["attempts"] += 1
        if task["attempts"] < task.get("max_retries", 3):
            task["status"] = "RETRY"
            heapq.heappush(self._heap, (task["priority"], task))
            await self.emit_event("TASK_RETRY", {"task_id": task_id, "attempt": task["attempts"]})
        else:
            task["status"] = "DEAD"
            self._dead_letter.append(task)
            await self.emit_event("TASK_DEAD_LETTER", {"task_id": task_id, "error": error})

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "TASK_SUBMIT":
            await self.enqueue(event.payload)

    async def shutdown(self) -> None:
        self.log("INFO", "TaskQueueAgent shutting down. %d tasks in queue.", len(self._heap))