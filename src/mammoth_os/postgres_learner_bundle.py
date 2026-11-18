"""Unwired owner-scoped CAS primitive for future shared learner persistence."""

from contextlib import contextmanager
import hashlib
import json
import re

from .postgres import database
from .shared_state import StateConflict, StateUnavailable


def migration_lock(namespace):
    return int.from_bytes(
        hashlib.sha256(("mammoth.learner-bundles:" + namespace).encode()).digest()[:8],
        "big", signed=True,
    )


def _validate_bundle(bundle):
    if (not isinstance(bundle, dict) or set(bundle) != {"state", "drafts", "models"}
            or any(not isinstance(bundle[key], dict) for key in ("state", "drafts", "models"))):
        raise ValueError("Learner bundle must contain state, drafts and models objects.")
    try:
        encoded = json.dumps(bundle, ensure_ascii=True, allow_nan=False)
        if json.loads(encoded) != bundle:
            raise ValueError("Learner bundle contains values that change during JSON encoding.")
        return encoded
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Learner bundle must contain valid JSON.") from exc


class PostgresLearnerBundle:
    """Atomic whole-owner snapshots only; domain validation belongs to the caller."""

    def __init__(self, dsn, namespace, user_id):
        if (not dsn or not isinstance(namespace, str) or len(namespace) > 128
                or re.fullmatch(r"[a-zA-Z0-9_-]+", namespace) is None):
            raise StateUnavailable("Shared learner storage requires a private database and explicit safe namespace.")
        if (not isinstance(user_id, str) or not 1 <= len(user_id) <= 256
                or user_id in {"anonymous", "local"} or any(ord(char) < 32 for char in user_id)):
            raise ValueError("An explicit authenticated learner owner is required.")
        self.dsn, self.namespace, self.user_id = dsn, namespace, user_id

    @contextmanager
    def _transaction(self):
        with database(self.dsn) as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (migration_lock(self.namespace),))
            yield connection

    def read(self):
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state,drafts,models,revision FROM public.mammoth_learner_bundles "
                "WHERE namespace=%s AND user_id=%s",
                (self.namespace, self.user_id),
            ).fetchone()
        if row is None:
            return {"state": {}, "drafts": {}, "models": {}}, 0
        bundle = {"state": row[0], "drafts": row[1], "models": row[2]}
        try:
            _validate_bundle(bundle)
        except ValueError as exc:
            raise StateUnavailable("Shared learner storage contains an invalid bundle; no reset was performed.") from exc
        if type(row[3]) is not int or row[3] < 1:
            raise StateUnavailable("Shared learner storage has an invalid revision; no reset was performed.")
        return bundle, row[3]

    def write(self, bundle, *, revision):
        if type(revision) is not int or revision < 0:
            raise ValueError("Learner bundle revision must be a nonnegative integer.")
        snapshot = json.loads(_validate_bundle(bundle))
        parts = [json.dumps(snapshot[key], ensure_ascii=True, allow_nan=False)
                 for key in ("state", "drafts", "models")]
        with self._transaction() as connection:
            if revision == 0:
                row = connection.execute(
                    "INSERT INTO public.mammoth_learner_bundles(namespace,user_id,state,drafts,models,revision) "
                    "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,1) "
                    "ON CONFLICT(namespace,user_id) DO NOTHING RETURNING revision",
                    (self.namespace, self.user_id, *parts),
                ).fetchone()
            else:
                row = connection.execute(
                    "UPDATE public.mammoth_learner_bundles SET state=%s::jsonb,drafts=%s::jsonb,"
                    "models=%s::jsonb,revision=revision+1 WHERE namespace=%s AND user_id=%s "
                    "AND revision=%s RETURNING revision",
                    (*parts, self.namespace, self.user_id, revision),
                ).fetchone()
            if row is None:
                raise StateConflict("Learner bundle changed; reload without replaying prior work.")
        return row[0]
