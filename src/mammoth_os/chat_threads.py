"""Atomic owner-scoped chat threads; deleted identities cannot be recreated."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re

from .postgres import database
from .shared_state import StateConflict, StateUnavailable

MAX_THREADS = 200
MAX_MESSAGES = 120
MAX_RECORD_BYTES = 4 * 1024 * 1024


def validate_identity(value, *, owner=False):
    if (not isinstance(value, str) or not value or len(value) > (256 if owner else 128)
            or value == "anonymous" or any(ord(char) < 32 for char in value)):
        raise ValueError("An explicit valid chat owner/thread identity is required.")


def validate_record(entry, messages):
    if (not isinstance(entry, dict) or not isinstance(messages, list)
            or any(not isinstance(item, dict) for item in messages)):
        raise ValueError("Chat thread metadata/messages have an invalid shape.")
    validate_identity(entry.get("id"))
    if len(messages) > MAX_MESSAGES:
        raise ValueError("Chat thread exceeds the 120-message retention limit.")
    if len(json.dumps([entry, messages], ensure_ascii=True).encode()) > MAX_RECORD_BYTES:
        raise ValueError("Chat thread exceeds the 4 MiB record limit.")


def migration_lock(namespace):
    return int.from_bytes(hashlib.sha256(("mammoth.chat-threads:" + namespace).encode()).digest()[:8],
                          "big", signed=True)


class PostgresChatThreads:
    def __init__(self, dsn, namespace, user_id):
        validate_identity(user_id, owner=True)
        if (not isinstance(namespace, str) or len(namespace) > 128
                or re.fullmatch(r"[a-zA-Z0-9_-]+", namespace) is None or not dsn):
            raise StateUnavailable("Shared chat requires a private database connection and explicit safe namespace.")
        self.dsn, self.namespace, self.user_id = dsn, namespace, user_id

    @contextmanager
    def _owner(self):
        with database(self.dsn) as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (migration_lock(self.namespace),))
            connection.execute(
                "INSERT INTO public.mammoth_chat_owners(namespace,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (self.namespace, self.user_id),
            )
            connection.execute(
                "SELECT user_id FROM public.mammoth_chat_owners WHERE namespace=%s AND user_id=%s FOR UPDATE",
                (self.namespace, self.user_id),
            )
            yield connection

    def _row(self, connection, thread_id):
        validate_identity(thread_id)
        return connection.execute(
            "SELECT entry,messages,revision,deleted FROM public.mammoth_chat_threads "
            "WHERE namespace=%s AND user_id=%s AND thread_id=%s",
            (self.namespace, self.user_id, thread_id),
        ).fetchone()

    def get(self, thread_id):
        with database(self.dsn) as connection:
            row = self._row(connection, thread_id)
        if row is None or row[3]:
            return None
        validate_record(row[0], row[1])
        return {"entry": row[0], "messages": row[1], "revision": row[2]}

    def list(self):
        with database(self.dsn) as connection:
            rows = connection.execute(
                "SELECT entry FROM public.mammoth_chat_threads WHERE namespace=%s AND user_id=%s AND NOT deleted "
                "ORDER BY entry->>'updated_at' DESC,thread_id",
                (self.namespace, self.user_id),
            ).fetchall()
        return [row[0] for row in rows]

    def create(self, thread_id, title, agent_id):
        now = datetime.now(timezone.utc).isoformat()
        entry = {"id": thread_id, "title": title, "agent_id": agent_id, "created_at": now,
                 "updated_at": now, "message_count": 0}
        validate_record(entry, [])
        with self._owner() as connection:
            if self._row(connection, thread_id) is not None:
                raise StateConflict("Chat thread identity already exists or was deleted.")
            count = connection.execute(
                "SELECT count(*) FROM public.mammoth_chat_threads WHERE namespace=%s AND user_id=%s AND NOT deleted",
                (self.namespace, self.user_id),
            ).fetchone()[0]
            if count >= MAX_THREADS:
                raise StateUnavailable("Chat thread limit reached; no conversations were silently pruned.")
            connection.execute(
                "INSERT INTO public.mammoth_chat_threads(namespace,user_id,thread_id,entry,messages) "
                "VALUES (%s,%s,%s,%s::jsonb,'[]'::jsonb)",
                (self.namespace, self.user_id, thread_id, json.dumps(entry)),
            )

    def _save(self, connection, thread_id, entry, messages, revision):
        validate_record(entry, messages)
        connection.execute(
            "UPDATE public.mammoth_chat_threads SET entry=%s::jsonb,messages=%s::jsonb,revision=revision+1 "
            "WHERE namespace=%s AND user_id=%s AND thread_id=%s AND revision=%s AND NOT deleted",
            (json.dumps(entry), json.dumps(messages), self.namespace, self.user_id, thread_id, revision),
        )

    def rename(self, thread_id, title):
        with self._owner() as connection:
            row = self._row(connection, thread_id)
            if row is None or row[3]:
                return False
            entry, messages, revision, _ = row
            if title:
                entry["title"] = title
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(connection, thread_id, entry, messages, revision)
        return True

    def delete(self, thread_id):
        validate_identity(thread_id)
        with self._owner() as connection:
            connection.execute(
                "INSERT INTO public.mammoth_chat_threads(namespace,user_id,thread_id,entry,messages,deleted) "
                "VALUES (%s,%s,%s,'{}'::jsonb,'[]'::jsonb,true) "
                "ON CONFLICT(namespace,user_id,thread_id) DO UPDATE "
                "SET entry='{}'::jsonb,messages='[]'::jsonb,deleted=true,revision=mammoth_chat_threads.revision+1",
                (self.namespace, self.user_id, thread_id),
            )

    def save_messages(self, thread_id, messages, *, revision, title):
        with self._owner() as connection:
            row = self._row(connection, thread_id)
            if row is None or row[3] or row[2] != revision:
                raise StateConflict("Chat thread changed or was deleted; the generated response was not replayed.")
            entry = row[0]
            entry.update(updated_at=datetime.now(timezone.utc).isoformat(), message_count=len(messages))
            if title:
                entry["title"] = title
            self._save(connection, thread_id, entry, messages[-MAX_MESSAGES:], revision)

    def save_exchange(self, thread_id, exchange):
        if (not isinstance(exchange, list) or len(exchange) != 2
                or any(not isinstance(item, dict) for item in exchange)
                or not isinstance(exchange[1].get("run_id"), str) or not exchange[1]["run_id"]):
            raise ValueError("A keyed user/assistant run exchange is required.")
        with self._owner() as connection:
            row = self._row(connection, thread_id)
            if row is None or row[3]:
                raise StateConflict("Chat thread is missing or deleted; a late response cannot recreate it.")
            entry, messages, revision, _ = row
            existing = next((index for index, item in enumerate(messages)
                             if item.get("role") == "assistant" and item.get("run_id") == exchange[1]["run_id"]), None)
            if existing is None:
                messages.extend(exchange)
            else:
                messages[existing] = exchange[1]
            messages = messages[-MAX_MESSAGES:]
            entry.update(updated_at=datetime.now(timezone.utc).isoformat(), message_count=len(messages))
            self._save(connection, thread_id, entry, messages, revision)
