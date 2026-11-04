"""Private durable admission accounting, not an invoice or payment ledger."""

from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterator, Optional
import uuid

from .token_admission import reported_tokens

_CURRENT: ContextVar[Optional["RuntimeLedger"]] = ContextVar("runtime_ledger", default=None)


class RuntimeLimitReached(ValueError):
    pass


@contextmanager
def ledger_context(ledger: Optional["RuntimeLedger"]) -> Iterator[None]:
    token = _CURRENT.set(ledger)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def current_ledger() -> Optional["RuntimeLedger"]:
    return _CURRENT.get()


class RuntimeLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), daily_tokens INTEGER)")
            db.execute("INSERT OR IGNORE INTO policy VALUES (1,NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT, reserved INTEGER NOT NULL,
                reported INTEGER, status TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS attempts_day ON attempts(day)")
            db.commit()
            yield db

    def set_limit(self, limit: Optional[int]) -> Dict[str, Any]:
        if limit is not None and (type(limit) is not int or not 0 <= limit <= 100_000_000):
            raise ValueError("Daily token ceiling must be null or an integer from 0 to 100000000.")
        with self._db() as db:
            db.execute("UPDATE policy SET daily_tokens=? WHERE id=1", (limit,))
        return self.snapshot()

    def reserve(self, provider: str, model: str, tokens: int) -> str:
        if type(tokens) is not int or tokens < 1:
            raise ValueError("A positive conservative token reservation is required.")
        now = datetime.now(timezone.utc).isoformat()
        identity = uuid.uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            limit = db.execute("SELECT daily_tokens FROM policy WHERE id=1").fetchone()[0]
            used = db.execute("SELECT COALESCE(SUM(COALESCE(reported,reserved)),0) FROM attempts WHERE day=?",
                              (now[:10],)).fetchone()[0]
            if limit is not None and used + tokens > limit:
                raise RuntimeLimitReached("Daily runtime token ceiling reached; no provider call was started.")
            db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,NULL,?,NULL,'pending')",
                       (identity, now[:10], provider, model, now, tokens))
        return identity

    def finish(self, identity: str, *, usage: Optional[Dict[str, int]] = None, failed: bool = False) -> None:
        total = None
        if not failed:
            try:
                total = reported_tokens(usage or {})
            except ValueError:
                pass  # The full reservation remains charged when usage is unknown.
        with self._db() as db:
            changed = db.execute("""UPDATE attempts SET finished_at=?,reported=?,status=?
                WHERE id=? AND status='pending'""",
                (datetime.now(timezone.utc).isoformat(), total,
                 "failed_unknown" if failed else "completed" if total is not None else "completed_unknown", identity))
            if changed.rowcount != 1:
                raise ValueError("Provider attempt was already finalized or does not exist.")

    def snapshot(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        day = now.date().isoformat()
        with self._db() as db:
            limit = db.execute("SELECT daily_tokens FROM policy WHERE id=1").fetchone()[0]
            totals = db.execute("""SELECT COUNT(*) AS attempts,
                COALESCE(SUM(reported),0) AS reported_tokens,
                COALESCE(SUM(CASE WHEN reported IS NULL THEN reserved ELSE 0 END),0) AS unresolved_reserved_tokens,
                COALESCE(SUM(CASE WHEN reported IS NULL THEN 1 ELSE 0 END),0) AS unknown_attempts
                FROM attempts WHERE day=?""", (day,)).fetchone()
            observations = db.execute("""SELECT provider,model,status,finished_at FROM attempts
                WHERE finished_at IS NOT NULL AND id IN (
                    SELECT id FROM (SELECT id,ROW_NUMBER() OVER (
                        PARTITION BY provider ORDER BY finished_at DESC,id DESC) AS position
                        FROM attempts WHERE finished_at IS NOT NULL) WHERE position=1)""").fetchall()
        providers = []
        for row in observations:
            age = max(0, (now - datetime.fromisoformat(row["finished_at"])).total_seconds())
            providers.append({"provider": row["provider"], "model": row["model"],
                              "observed_at": row["finished_at"], "age_seconds": round(age),
                              "health": "stale" if age > 300 else "unavailable" if row["status"] == "failed_unknown" else "available",
                              "source": "completion_attempt", "ttl_seconds": 300})
        counted = totals["reported_tokens"] + totals["unresolved_reserved_tokens"]
        return {"contract": "mammoth.runtime-usage.v1", "day_utc": day,
                "scope": "authenticated_user_all_accounts", "daily_token_limit": limit,
                **dict(totals), "admission_tokens": counted,
                "remaining_tokens": None if limit is None else max(0, limit - counted),
                "accounting_status": "incomplete" if totals["unknown_attempts"] else "reported",
                "currency_spend": None, "invoice_verified": False, "providers": providers,
                "coverage": "leaf_calls_through_llm_completion_only",
                "unknown_outcomes": "retain_full_reservation_without_automatic_replay"}
