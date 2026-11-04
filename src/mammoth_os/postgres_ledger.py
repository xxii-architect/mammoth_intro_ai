"""Shared private-login admission; preserves the existing runtime usage contract."""

from datetime import datetime, timezone
import uuid

from .postgres import database
from .runtime_ledger import RuntimeLimitReached, usage_snapshot
from .shared_state import StateUnavailable
from .token_admission import reported_tokens


class PostgresRuntimeLedger:
    def __init__(self, dsn, namespace, user_id):
        if not dsn or not namespace or not user_id:
            raise StateUnavailable("Shared private admission requires database, namespace and authenticated owner.")
        self.dsn, self.namespace, self.user_id = dsn, namespace, user_id

    def _ensure(self, connection):
        connection.execute(
            "INSERT INTO public.mammoth_private_runtime_policy(namespace,user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (self.namespace, self.user_id),
        )

    def _policy(self, connection, *, locked=False):
        self._ensure(connection)
        return connection.execute(
            "SELECT daily_tokens FROM public.mammoth_private_runtime_policy WHERE namespace=%s AND user_id=%s"
            + (" FOR UPDATE" if locked else ""), (self.namespace, self.user_id),
        ).fetchone()[0]

    def set_limit(self, limit):
        if limit is not None and (type(limit) is not int or not 0 <= limit <= 100_000_000):
            raise ValueError("Daily token ceiling must be null or an integer from 0 to 100000000.")
        with database(self.dsn) as connection, connection.transaction():
            self._policy(connection, locked=True)
            connection.execute(
                "UPDATE public.mammoth_private_runtime_policy SET daily_tokens=%s WHERE namespace=%s AND user_id=%s",
                (limit, self.namespace, self.user_id),
            )
        return self.snapshot()

    def reserve(self, provider, model, tokens, *, input_tokens=None, output_tokens=None):
        if type(tokens) is not int or tokens < 1:
            raise ValueError("A positive conservative token reservation is required.")
        timestamp = datetime.now(timezone.utc).isoformat()
        identity = uuid.uuid4().hex
        with database(self.dsn) as connection, connection.transaction():
            limit = self._policy(connection, locked=True)
            used = connection.execute(
                "SELECT coalesce(sum(coalesce(reported,reserved)),0) FROM public.mammoth_private_runtime_attempts "
                "WHERE namespace=%s AND user_id=%s AND day=%s", (self.namespace, self.user_id, timestamp[:10]),
            ).fetchone()[0]
            if limit is not None and used + tokens > limit:
                raise RuntimeLimitReached("Daily runtime token ceiling reached; no provider call was started.")
            connection.execute(
                "INSERT INTO public.mammoth_private_runtime_attempts"
                "(namespace,user_id,id,day,provider,model,started_at,reserved,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'pending')",
                (self.namespace, self.user_id, identity, timestamp[:10], provider, model, timestamp, tokens),
            )
        return identity

    def finish(self, identity, *, usage=None, failed=False):
        total = None
        if not failed:
            try:
                total = reported_tokens(usage or {})
            except ValueError:
                pass  # Unknown usage retains the reservation, matching the local ledger.
        status = "failed_unknown" if failed else "completed" if total is not None else "completed_unknown"
        with database(self.dsn) as connection, connection.transaction():
            self._policy(connection, locked=True)
            result = connection.execute(
                "UPDATE public.mammoth_private_runtime_attempts SET finished_at=%s,reported=%s,status=%s "
                "WHERE namespace=%s AND user_id=%s AND id=%s AND status='pending'",
                (datetime.now(timezone.utc).isoformat(), total, status, self.namespace, self.user_id, identity),
            )
            if result.rowcount != 1:
                raise ValueError("Provider attempt was already finalized or does not exist.")

    def abandon_unstarted(self, identity):
        with database(self.dsn) as connection, connection.transaction():
            self._policy(connection, locked=True)
            result = connection.execute(
                "DELETE FROM public.mammoth_private_runtime_attempts WHERE namespace=%s AND user_id=%s AND id=%s AND status='pending'",
                (self.namespace, self.user_id, identity),
            )
            if result.rowcount != 1:
                raise ValueError("Unstarted reservation is missing or already finalized.")

    def snapshot(self):
        now = datetime.now(timezone.utc)
        with database(self.dsn) as connection, connection.transaction():
            from psycopg.rows import dict_row

            limit = self._policy(connection, locked=True)
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT count(*) AS attempts,coalesce(sum(reported),0) AS reported_tokens,"
                    "coalesce(sum(reserved) FILTER (WHERE reported IS NULL),0) AS unresolved_reserved_tokens,"
                    "count(*) FILTER (WHERE reported IS NULL) AS unknown_attempts "
                    "FROM public.mammoth_private_runtime_attempts WHERE namespace=%s AND user_id=%s AND day=%s",
                    (self.namespace, self.user_id, now.date().isoformat()),
                )
                totals = cursor.fetchone()
                cursor.execute(
                    "SELECT DISTINCT ON (provider) provider,model,status,finished_at "
                    "FROM public.mammoth_private_runtime_attempts "
                    "WHERE namespace=%s AND user_id=%s AND finished_at IS NOT NULL ORDER BY provider,finished_at DESC,id DESC",
                    (self.namespace, self.user_id),
                )
                observations = cursor.fetchall()
        return usage_snapshot(limit, {key: int(value) for key, value in totals.items()}, observations, now)
