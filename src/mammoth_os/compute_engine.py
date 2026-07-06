class ComputeEngine:
    """
    CPU/GPU job dispatcher with parallel task execution using
    asyncio workers or process pools for CPU-bound tasks.
    """

    def __init__(self, config: dict):
        from concurrent.futures import ProcessPoolExecutor
        self.max_workers = config.get("max_workers", 8)
        self.gpu_enabled = config.get("gpu_enabled", False)
        self.timeout = config.get("timeout_per_job", 120)
        self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self._jobs: dict[str, "asyncio.Future"] = {}# type: ignore

    async def submit(self, fn: callable, *args, job_id: str = None, **kwargs) -> str:# type: ignore
        """Submit a CPU-bound job. Returns job_id."""
        import uuid
        job_id = job_id or str(uuid.uuid4())
        loop = asyncio.get_event_loop()# type: ignore
        future = loop.run_in_executor(self._executor, fn, *args)
        self._jobs[job_id] = future
        return job_id

    async def cancel(self, job_id: str) -> bool:
        """Cancel a submitted job if not yet started."""
        future = self._jobs.pop(job_id, None)
        return future.cancel() if future else False

    async def get_status(self, job_id: str) -> str:
        future = self._jobs.get(job_id)
        if not future:
            return "NOT_FOUND"
        if future.done():
            return "COMPLETE"
        return "RUNNING"

    async def drain(self) -> None:
        """Wait for all current jobs to complete."""
        await asyncio.gather(*self._jobs.values(), return_exceptions=True)# type: ignore
        self._jobs.clear()