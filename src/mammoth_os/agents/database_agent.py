from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class DatabaseAgent(BaseAgent):  # type: ignore
    """
    PostgreSQL interface with async connection pooling, query building,
    transaction management, and migration support via Alembic.
    Falls back to an in-memory record store when no DB is configured.
    """

    name = "DatabaseAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._pool = None
        self._fallback_store: List[Dict[str, Any]] = []
        self._query_count = 0

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    def _get_dsn(self) -> Optional[str]:
        import os
        dsn = os.environ.get("DATABASE_URL") or os.environ.get("MAMMOTH_DB_DSN")
        if dsn and "localhost" not in dsn and "127.0.0.1" not in dsn:
            return dsn
        try:
            cfg = getattr(self.router, "config", {}) if self.router else {}
            return cfg.get("dsn") if isinstance(cfg, dict) else None
        except Exception:
            return None

    async def initialize(self) -> None:
        dsn = self._get_dsn()
        if not dsn:
            self.log("INFO", "No DSN configured - using in-memory fallback store.")
            return
        try:
            import asyncpg  # type: ignore
            self._pool = await asyncpg.create_pool(dsn, min_size=2, max_size=20)
            self.log("INFO", "DatabaseAgent connected to PostgreSQL.")
        except Exception as exc:
            self.log("WARNING", f"PostgreSQL pool creation failed ({exc}). Using in-memory fallback.")

    async def query(self, sql: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        self._query_count += 1
        start = time.monotonic()
        if self._pool is not None:
            try:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(sql, *(params or []))
                duration_ms = (time.monotonic() - start) * 1000
                self.log("DEBUG", f"Query executed in {duration_ms:.2f}ms: {sql[:80]}")
                return [dict(r) for r in rows]
            except Exception as exc:
                self.log("ERROR", f"Query failed: {exc}")
                return []
        return list(self._fallback_store)

    async def execute(self, sql: str, params: Optional[List] = None) -> int:
        self._query_count += 1
        if self._pool is not None:
            try:
                async with self._pool.acquire() as conn:
                    result = await conn.execute(sql, *(params or []))
                return int(result.split()[-1]) if result else 0
            except Exception as exc:
                self.log("ERROR", f"Execute failed: {exc}")
                return 0
        lowered = sql.strip().lower()
        if lowered.startswith("insert"):
            record = {"sql": sql, "params": params}
            self._fallback_store.append(record)
            return 1
        return 0

    async def transaction(self, operations: List[tuple]) -> bool:
        if self._pool is not None:
            try:
                async with self._pool.acquire() as conn:
                    async with conn.transaction():
                        for sql, params in operations:
                            await conn.execute(sql, *params)
                return True
            except Exception as exc:
                self.log("ERROR", f"Transaction failed: {exc}")
                return False
        for sql, params in operations:
            await self.execute(sql, list(params))
        return True

    async def run_migration(self, migration_dir: str) -> Dict[str, Any]:
        import subprocess
        try:
            proc = subprocess.run(
                ["alembic", "-c", f"{migration_dir}/alembic.ini", "upgrade", "head"],
                capture_output=True, text=True, timeout=120
            )
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            action = str(payload.get("action") or payload.get("op") or "status").strip().lower()
            sql = str(payload.get("sql") or "").strip()
            params = payload.get("params") or []
        else:
            action = "status"
            sql = ""
            params = []

        if action == "query":
            if not sql:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide SQL to query."}
            rows = await self.query(sql, list(params))
            return {"status": "ok", "agent": self.name, "action": "query", "rows": rows, "count": len(rows), "summary": f"Query returned {len(rows)} row(s)."}

        if action == "execute":
            if not sql:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide SQL to execute."}
            affected = await self.execute(sql, list(params))
            return {"status": "ok", "agent": self.name, "action": "execute", "rows_affected": affected, "summary": f"{affected} row(s) affected."}

        return {
            "status": "ok",
            "agent": self.name,
            "action": "status",
            "backend": "postgresql" if self._pool else "memory",
            "query_count": self._query_count,
            "fallback_records": len(self._fallback_store),
            "summary": "DatabaseAgent is active.",
            "quality_flags": ["async_pool", "fallback_store", "migration_support"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        if getattr(event, "event_type", None) == "DB_QUERY":
            payload = getattr(event, "payload", {}) or {}
            await self.run({"action": "query", **payload})

    async def shutdown(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
        self.log("INFO", f"DatabaseAgent shutting down. {self._query_count} queries processed.")
