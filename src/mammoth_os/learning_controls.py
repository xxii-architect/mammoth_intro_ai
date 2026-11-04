"""Private request-count controls; not a token ledger or provider cancellation API."""

import asyncio
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Protocol
import uuid


class LearningCancellation(Protocol):
    def is_cancelled(self, operation_id: str) -> bool: ...


_CURRENT: ContextVar[tuple[LearningCancellation, str] | None] = ContextVar("learning_generation", default=None)


class LearningCancelled(asyncio.CancelledError):
    pass


class LearningLimitReached(ValueError):
    pass


def check_cancelled() -> None:
    current = _CURRENT.get()
    if current and current[0].is_cancelled(current[1]):
        raise LearningCancelled("Learning cancellation reached a safe boundary.")


def has_operation() -> bool:
    return _CURRENT.get() is not None


@contextmanager
def operation_context(store: LearningCancellation, operation_id: str) -> Iterator[None]:
    token = _CURRENT.set((store, operation_id))
    try:
        check_cancelled()
        yield
    finally:
        _CURRENT.reset(token)


class LearningControls:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), daily_limit INTEGER)")
            db.execute("INSERT OR IGNORE INTO policy VALUES (1, NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, admitted INTEGER NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, route TEXT NOT NULL, account_id TEXT NOT NULL,
                status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT)""")
            db.commit()
            yield db

    def snapshot(self) -> dict[str, Any]:
        day = datetime.now(timezone.utc).date().isoformat()
        with self._db() as db:
            limit = db.execute("SELECT daily_limit FROM policy WHERE id=1").fetchone()[0]
            row = db.execute("SELECT admitted FROM usage WHERE day=?", (day,)).fetchone()
            used = row[0] if row else 0
            operations = [dict(row) for row in db.execute("""
                SELECT * FROM operations WHERE finished_at IS NULL
                UNION ALL SELECT * FROM (
                    SELECT * FROM operations WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 100
                ) ORDER BY started_at DESC""")]
        return controls_snapshot(day, limit, used, operations)

    def set_limit(self, limit: int | None) -> dict[str, Any]:
        if limit is not None and (type(limit) is not int or not 0 <= limit <= 100_000):
            raise ValueError("Daily request limit must be null or an integer from 0 to 100000.")
        with self._db() as db:
            db.execute("UPDATE policy SET daily_limit=? WHERE id=1", (limit,))
        return self.snapshot()

    def begin(self, route: str, account_id: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        day = now[:10]
        operation_id = uuid.uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            limit = db.execute("SELECT daily_limit FROM policy WHERE id=1").fetchone()[0]
            row = db.execute("SELECT admitted FROM usage WHERE day=?", (day,)).fetchone()
            if limit is not None and (row[0] if row else 0) >= limit:
                raise LearningLimitReached("Your chosen daily learning request limit has been reached. Change the limit or wait until the next UTC day.")
            db.execute("INSERT INTO usage VALUES (?,1) ON CONFLICT(day) DO UPDATE SET admitted=admitted+1", (day,))
            db.execute("DELETE FROM usage WHERE day < date(?, '-31 days')", (day,))
            db.execute("INSERT INTO operations VALUES (?,?,?,'running',?,NULL)",
                       (operation_id, route, account_id, now))
            db.execute("""DELETE FROM operations WHERE finished_at IS NOT NULL AND id NOT IN
                (SELECT id FROM operations WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 100)""")
        return operation_id

    def cancel(self, operation_id: str) -> str:
        with self._db() as db:
            db.execute("""UPDATE operations SET status='cancellation_requested'
                WHERE id=? AND status='running'""", (operation_id,))
            row = db.execute("SELECT status FROM operations WHERE id=?", (operation_id,)).fetchone()
            if row is None:
                raise LookupError("Learning request not found.")
            return str(row[0])

    def cancel_account(self, account_id: str) -> None:
        with self._db() as db:
            db.execute("""UPDATE operations SET status='cancellation_requested'
                WHERE account_id=? AND status='running'""", (account_id,))

    def is_cancelled(self, operation_id: str) -> bool:
        with self._db() as db:
            row = db.execute("SELECT status FROM operations WHERE id=?", (operation_id,)).fetchone()
            if row is None:
                raise RuntimeError("Learning operation record is missing.")
            return row[0] == "cancellation_requested"

    def finish(self, operation_id: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as db:
            db.execute("UPDATE operations SET status=?, finished_at=? WHERE id=?", (status, now, operation_id))


def controls_snapshot(day, limit, used, operations):
    return {
        "contract": "mammoth.learning-controls.v1", "day_utc": day,
        "daily_request_limit": limit, "admitted_requests": used,
        "remaining_requests": None if limit is None else max(0, limit - used),
        "operations": operations, "price_estimate": None,
        "unit": "admitted_http_requests_not_model_calls_or_dollars",
    }
