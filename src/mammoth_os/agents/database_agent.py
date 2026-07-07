class DatabaseAgent(BaseAgent):# type: ignore
    """
    PostgreSQL interface with async connection pooling, query building,
    transaction management, and Alembic-backed migration support.
    """

    async def initialize(self) -> None:
        import asyncpg# type: ignore
        dsn = self.get_config("dsn") or "postgresql://mammoth:mammoth@localhost:5432/mammoth"
        self._pool = await asyncpg.create_pool(dsn, min_size=2, max_size=20)
        self.log("INFO", "DatabaseAgent connected to PostgreSQL.")

    async def query(self, sql: str, params: list = None) -> list[dict]:# type: ignore
        import time
        start = time.monotonic()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *(params or []))
        duration_ms = (time.monotonic() - start) * 1000
        self.log("DEBUG", "Query executed in %.2f ms: %s", duration_ms, sql[:80])
        return [dict(r) for r in rows]

    async def execute(self, sql: str, params: list = None) -> int:# type: ignore
        async with self._pool.acquire() as conn:
            result = await conn.execute(sql, *(params or []))
        return int(result.split()[-1]) if result else 0

    async def transaction(self, operations: list[tuple]) -> bool:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for sql, params in operations:
                    await conn.execute(sql, *params)
        return True

    async def run_migration(self, migration_dir: str) -> None:
        import subprocess
        subprocess.run(
            ["alembic", "-c", f"{migration_dir}/alembic.ini", "upgrade", "head"],
            check=True,
        )

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "DB_QUERY":
            return await self.query(event.payload["sql"], event.payload.get("params"))# type: ignore

    async def shutdown(self) -> None:
        await self._pool.close()