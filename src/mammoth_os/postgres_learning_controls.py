"""Shared private learning request ceilings and cancellation; no automatic replay."""

from datetime import datetime, timezone
import uuid

from .learning_controls import LearningLimitReached, controls_snapshot
from .postgres import database
from .shared_state import StateUnavailable


class PostgresLearningControls:
    def __init__(self, dsn, namespace, user_id):
        if (not dsn or not isinstance(namespace, str) or not 1 <= len(namespace) <= 128
                or not namespace.replace("-", "").replace("_", "").isalnum()
                or not isinstance(user_id, str) or not 1 <= len(user_id) <= 256):
            raise StateUnavailable("Shared learning controls require a private database, namespace and authenticated owner.")
        self.dsn, self.namespace, self.user_id = dsn, namespace, user_id

    def _policy(self, connection):
        connection.execute(
            "INSERT INTO public.mammoth_learning_policy(namespace,user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (self.namespace, self.user_id),
        )
        return connection.execute(
            "SELECT daily_limit FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s FOR UPDATE",
            (self.namespace, self.user_id),
        ).fetchone()[0]

    def snapshot(self):
        day = datetime.now(timezone.utc).date().isoformat()
        with database(self.dsn) as connection, connection.transaction():
            from psycopg.rows import dict_row

            limit = self._policy(connection)
            row = connection.execute(
                "SELECT admitted FROM public.mammoth_learning_usage WHERE namespace=%s AND user_id=%s AND day=%s",
                (self.namespace, self.user_id, day),
            ).fetchone()
            used = row[0] if row else 0
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT id,route,account_id,status,started_at,finished_at FROM public.mammoth_learning_operations "
                    "WHERE namespace=%s AND user_id=%s AND finished_at IS NULL UNION ALL "
                    "(SELECT id,route,account_id,status,started_at,finished_at FROM public.mammoth_learning_operations "
                    "WHERE namespace=%s AND user_id=%s AND finished_at IS NOT NULL "
                    "ORDER BY started_at DESC,id DESC LIMIT 100) ORDER BY started_at DESC,id DESC",
                    (self.namespace, self.user_id, self.namespace, self.user_id),
                )
                operations = cursor.fetchall()
        return controls_snapshot(day, limit, used, operations)

    def set_limit(self, limit):
        if limit is not None and (type(limit) is not int or not 0 <= limit <= 100_000):
            raise ValueError("Daily request limit must be null or an integer from 0 to 100000.")
        with database(self.dsn) as connection, connection.transaction():
            self._policy(connection)
            connection.execute(
                "UPDATE public.mammoth_learning_policy SET daily_limit=%s WHERE namespace=%s AND user_id=%s",
                (limit, self.namespace, self.user_id),
            )
        return self.snapshot()

    def begin(self, route, account_id):
        timestamp = datetime.now(timezone.utc).isoformat()
        day, identity = timestamp[:10], uuid.uuid4().hex
        with database(self.dsn) as connection, connection.transaction():
            limit = self._policy(connection)
            used = connection.execute(
                "SELECT admitted FROM public.mammoth_learning_usage WHERE namespace=%s AND user_id=%s AND day=%s",
                (self.namespace, self.user_id, day),
            ).fetchone()
            if limit is not None and (used[0] if used else 0) >= limit:
                raise LearningLimitReached(
                    "Your chosen daily learning request limit has been reached. Change the limit or wait until the next UTC day."
                )
            connection.execute(
                "INSERT INTO public.mammoth_learning_usage VALUES(%s,%s,%s,1) "
                "ON CONFLICT(namespace,user_id,day) DO UPDATE SET admitted=mammoth_learning_usage.admitted+1",
                (self.namespace, self.user_id, day),
            )
            connection.execute(
                "DELETE FROM public.mammoth_learning_usage WHERE namespace=%s AND user_id=%s AND day < %s::date - 31",
                (self.namespace, self.user_id, day),
            )
            connection.execute(
                "INSERT INTO public.mammoth_learning_operations VALUES(%s,%s,%s,%s,%s,'running',%s,NULL)",
                (self.namespace, self.user_id, identity, route, account_id, timestamp),
            )
            connection.execute(
                "DELETE FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s "
                "AND finished_at IS NOT NULL AND id NOT IN "
                "(SELECT id FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s "
                "AND finished_at IS NOT NULL ORDER BY started_at DESC,id DESC LIMIT 100)",
                (self.namespace, self.user_id, self.namespace, self.user_id),
            )
        return identity

    def cancel(self, operation_id):
        with database(self.dsn) as connection, connection.transaction():
            connection.execute(
                "UPDATE public.mammoth_learning_operations SET status='cancellation_requested' "
                "WHERE namespace=%s AND user_id=%s AND id=%s AND status='running'",
                (self.namespace, self.user_id, operation_id),
            )
            row = connection.execute(
                "SELECT status FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s AND id=%s",
                (self.namespace, self.user_id, operation_id),
            ).fetchone()
            if row is None:
                raise LookupError("Learning request not found.")
            return row[0]

    def cancel_account(self, account_id):
        with database(self.dsn) as connection:
            connection.execute(
                "UPDATE public.mammoth_learning_operations SET status='cancellation_requested' "
                "WHERE namespace=%s AND user_id=%s AND account_id=%s AND status='running'",
                (self.namespace, self.user_id, account_id),
            )

    def is_cancelled(self, operation_id):
        with database(self.dsn) as connection:
            row = connection.execute(
                "SELECT status FROM public.mammoth_learning_operations WHERE namespace=%s AND user_id=%s AND id=%s",
                (self.namespace, self.user_id, operation_id),
            ).fetchone()
            if row is None:
                raise RuntimeError("Learning operation record is missing.")
            return row[0] == "cancellation_requested"

    def finish(self, operation_id, status):
        if status not in {"finished", "failed", "cancelled_at_boundary"}:
            raise ValueError("Invalid learning operation completion status.")
        with database(self.dsn) as connection:
            changed = connection.execute(
                "UPDATE public.mammoth_learning_operations SET status=%s,finished_at=%s "
                "WHERE namespace=%s AND user_id=%s AND id=%s",
                (status, datetime.now(timezone.utc).isoformat(), self.namespace, self.user_id, operation_id),
            )
            if changed.rowcount != 1:
                raise RuntimeError("Learning operation record is missing; completion was not confirmed.")
