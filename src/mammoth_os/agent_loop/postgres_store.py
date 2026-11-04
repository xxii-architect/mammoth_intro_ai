"""PostgreSQL run checkpoints and session-released execution leases.

Use direct or session-mode connections, never a transaction pooler. A lost
connection stops writes; it is never reconnected underneath an active lease.
"""

import hashlib
import json
import threading

from mammoth_os.shared_state import StateUnavailable
from mammoth_os.postgres import database, open_database

from . import events as ev
from .lease import RunBusyError
from .runner import AgentRun, RUN_ID_RE, RunStore


class PostgresRunLease:
    def __init__(self, store, run, connection):
        self.store, self.run, self.connection = store, run, connection
        self.closed = False

    def close(self):
        with self.store._lock:
            if self.closed:
                return
            self.closed = True
            identity = (self.run.user_id, self.run.id)
            if self.store._leases.get(identity) is self:
                del self.store._leases[identity]
            self.connection.close()


class PostgresRunStore(RunStore):
    def __init__(self, dsn, namespace, *, keep_per_user=50):
        if not isinstance(namespace, str) or not 1 <= len(namespace) <= 128 or not namespace.replace("-", "").replace("_", "").isalnum():
            raise StateUnavailable("PostgreSQL runs require an explicit deployment namespace.")
        if not dsn:
            raise StateUnavailable("PostgreSQL runs require a private session-mode database connection.")
        if type(keep_per_user) is not int or keep_per_user < 1:
            raise ValueError("Run retention must be a positive whole number.")
        self.dsn, self.namespace, self.keep_per_user = dsn, namespace, keep_per_user
        self._lock = threading.RLock()
        self._leases = {}

    def _user_dir(self, user_id):
        raise StateUnavailable("PostgreSQL run state has no local directory; use the run-store API.")

    @staticmethod
    def _validate(run_id, user_id):
        if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
            raise ValueError("Invalid run identity")
        if not isinstance(user_id, str) or not 1 <= len(user_id) <= 256:
            raise ValueError("Invalid run owner")

    def _key(self, run_id, user_id):
        raw = json.dumps([self.namespace, user_id, run_id], separators=(",", ":")).encode()
        return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)

    def _open(self):
        return open_database(self.dsn)

    def _database(self):
        return database(self.dsn)

    def _read(self, connection, run_id, user_id):
        row = connection.execute(
            "SELECT revision,payload,cancellation_requested FROM public.mammoth_agent_runs "
            "WHERE namespace=%s AND user_id=%s AND id=%s", (self.namespace, user_id, run_id),
        ).fetchone()
        if row is None:
            return None
        revision, payload, cancelled = row
        try:
            run = AgentRun.from_dict(payload)
        except (ValueError, TypeError, AttributeError) as exc:
            raise StateUnavailable("Saved PostgreSQL run is invalid; operator repair is required.") from exc
        if run.id != run_id or run.user_id != user_id or run.storage_revision != revision:
            raise StateUnavailable("Saved PostgreSQL run identity/revision does not match its record.")
        run.cancel_requested = run.cancel_requested or cancelled
        return run

    def get(self, run_id, user_id):
        if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
            return None
        self._validate(run_id, user_id)
        with self._database() as connection:
            return self._read(connection, run_id, user_id)

    def _claim(self, run, *, refresh):
        self._validate(run.id, run.user_id)
        identity = (run.user_id, run.id)
        with self._lock:
            if identity in self._leases:
                raise RunBusyError("This run is already active or its state is being updated")
            connection = self._open()
            import psycopg

            try:
                if not connection.execute("SELECT pg_try_advisory_lock(%s)", (self._key(run.id, run.user_id),)).fetchone()[0]:
                    raise RunBusyError("This run is already active or its state is being updated")
                if refresh:
                    saved = self._read(connection, run.id, run.user_id)
                    if saved:
                        run.__dict__.update(saved.__dict__)
                lease = PostgresRunLease(self, run, connection)
                self._leases[identity] = lease
                return lease
            except psycopg.Error as exc:
                connection.close()
                raise StateUnavailable("PostgreSQL run lease could not be acquired; no local fallback was used.") from exc
            except BaseException:
                connection.close()
                raise

    def reserve(self, run):
        return self._claim(run, refresh=True)

    def save(self, run):
        self._validate(run.id, run.user_id)
        with self._lock:
            lease = self._leases.get((run.user_id, run.id))
            if lease and lease.run is not run:
                raise RunBusyError("Another execution owns this run; reload after it finishes.")
            temporary = lease is None
            if temporary:
                lease = self._claim(run, refresh=False)
            import psycopg
            from psycopg.types.json import Jsonb

            try:
                if lease.closed or lease.connection.closed:
                    raise StateUnavailable("Run lease connection was lost; execution cannot reconnect or replay.")
                revision = run.storage_revision + 1
                timestamp = ev.utc_now()
                payload = {**run.to_dict(), "storage_revision": revision, "updated_at": timestamp}
                if run.storage_revision == 0:
                    row = lease.connection.execute(
                        "INSERT INTO public.mammoth_agent_runs(namespace,user_id,id,revision,payload,cancellation_requested) "
                        "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING revision",
                        (self.namespace, run.user_id, run.id, revision, Jsonb(payload), run.cancel_requested),
                    ).fetchone()
                else:
                    row = lease.connection.execute(
                        "UPDATE public.mammoth_agent_runs SET revision=%s,payload=%s,updated_at=clock_timestamp(),"
                        "cancellation_requested=cancellation_requested OR %s "
                        "WHERE namespace=%s AND user_id=%s AND id=%s AND revision=%s RETURNING revision",
                        (revision, Jsonb(payload), run.cancel_requested, self.namespace, run.user_id, run.id, run.storage_revision),
                    ).fetchone()
                if row is None:
                    raise ValueError("Saved run changed or was removed; reload authoritative state before further work")
                run.storage_revision, run.updated_at = revision, timestamp
                self._retain(lease.connection, run)
            except psycopg.Error as exc:
                raise StateUnavailable("PostgreSQL run checkpoint failed; unknown outcomes must not be replayed.") from exc
            finally:
                if temporary:
                    lease.close()

    def _retain(self, connection, run):
        rows = connection.execute(
            "SELECT id,revision FROM public.mammoth_agent_runs WHERE namespace=%s AND user_id=%s "
            "ORDER BY updated_at DESC,id DESC OFFSET %s",
            (self.namespace, run.user_id, self.keep_per_user),
        ).fetchall()
        for identity, revision in rows:
            if identity == run.id:
                continue
            key = self._key(identity, run.user_id)
            if not connection.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()[0]:
                continue
            try:
                connection.execute(
                    "DELETE FROM public.mammoth_agent_runs WHERE namespace=%s AND user_id=%s AND id=%s "
                    "AND revision=%s AND payload->>'status' NOT IN ('running','awaiting_approval')",
                    (self.namespace, run.user_id, identity, revision),
                )
            finally:
                connection.execute("SELECT pg_advisory_unlock(%s)", (key,))

    def list(self, user_id, limit=20):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Run list limit must be a whole number from 1 to 1000.")
        with self._database() as connection:
            rows = connection.execute(
                "SELECT payload FROM public.mammoth_agent_runs WHERE namespace=%s AND user_id=%s "
                "ORDER BY updated_at DESC,id DESC LIMIT %s", (self.namespace, user_id, limit),
            ).fetchall()
            return [{key: row[0].get(key) for key in
                     ("id", "message", "agent_id", "status", "created_at", "updated_at", "steps")} for row in rows]

    def request_cancel(self, run):
        self._validate(run.id, run.user_id)
        with self._database() as connection:
            row = connection.execute(
                "UPDATE public.mammoth_agent_runs SET cancellation_requested=true "
                "WHERE namespace=%s AND user_id=%s AND id=%s RETURNING id",
                (self.namespace, run.user_id, run.id),
            ).fetchone()
            if row is None:
                raise ValueError("Run not found; cancellation was not confirmed.")

    def cancellation_requested(self, run):
        self._validate(run.id, run.user_id)
        with self._database() as connection:
            row = connection.execute(
                "SELECT cancellation_requested FROM public.mammoth_agent_runs "
                "WHERE namespace=%s AND user_id=%s AND id=%s", (self.namespace, run.user_id, run.id),
            ).fetchone()
            if row is None:
                raise StateUnavailable("Saved run disappeared; execution must stop.")
            return row[0]


def configured_run_store(base_dir):
    import os

    backend = os.environ.get("MAMMOTH_RUN_BACKEND", "local")
    if backend == "local":
        return RunStore(base_dir)
    if backend != "postgres" or os.environ.get("MAMMOTH_POSTGRES_SESSION_MODE") != "direct":
        raise StateUnavailable("PostgreSQL runs require the postgres backend and explicit direct/session connection mode.")
    return PostgresRunStore(os.environ.get("MAMMOTH_POSTGRES_DSN"), os.environ.get("MAMMOTH_STATE_NAMESPACE"))
