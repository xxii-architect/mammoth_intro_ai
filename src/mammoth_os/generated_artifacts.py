"""Private immutable generated documents, optionally shared through PostgreSQL."""

import hashlib
import re
from pathlib import Path

from .postgres import database
from .shared_state import StateConflict, StateUnavailable

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_OWNER_BYTES = 2 * 1024 * 1024 * 1024
MAX_OWNER_FILES = 2000
MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def validate_filename(filename):
    if (not isinstance(filename, str) or not filename or len(filename) > 240
            or not filename.endswith(".docx") or ".." in filename
            or any(char in filename for char in '/\\:\r\n\0')
            or any(ord(char) < 32 or ord(char) == 127 for char in filename)):
        raise ValueError("Invalid generated document name.")
    return filename


def read_staged(folder, filename):
    path = Path(folder) / validate_filename(filename)
    if path.is_symlink() or path.resolve(strict=True).parent != Path(folder).resolve(strict=True):
        raise StateUnavailable("Generated document is outside its private staging directory.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    validate_raw(raw)
    return raw


def validate_raw(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_FILE_BYTES:
        raise ValueError("Generated document must contain 1 byte to 50 MiB.")


def validate_owner(owner, *, allow_legacy=False):
    if allow_legacy and owner is None:
        return
    if not isinstance(owner, str) or not owner or len(owner) > 256 or owner == "anonymous":
        raise ValueError("An explicit signed-in document owner is required.")


def migration_lock(namespace):
    return int.from_bytes(hashlib.sha256(
        ("mammoth.generated-artifacts:" + namespace).encode(),
    ).digest()[:8], "big", signed=True)


class PostgresGeneratedArtifacts:
    def __init__(self, dsn, namespace):
        if (not isinstance(namespace, str) or len(namespace) > 128
                or re.fullmatch(r"[a-zA-Z0-9_-]+", namespace) is None):
            raise StateUnavailable("Shared generated documents require an explicit safe namespace.")
        if not dsn:
            raise StateUnavailable("Shared generated documents require a private database connection.")
        self.dsn, self.namespace = dsn, namespace

    def put(self, filename, owner, raw):
        validate_filename(filename)
        validate_owner(owner)
        validate_raw(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with database(self.dsn) as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (migration_lock(self.namespace),))
            connection.execute(
                "INSERT INTO public.mammoth_generated_owners(namespace,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (self.namespace, owner),
            )
            connection.execute(
                "SELECT user_id FROM public.mammoth_generated_owners WHERE namespace=%s AND user_id=%s FOR UPDATE",
                (self.namespace, owner),
            )
            existing = connection.execute(
                "SELECT user_id,sha256 FROM public.mammoth_generated_artifacts WHERE namespace=%s AND filename=%s",
                (self.namespace, filename),
            ).fetchone()
            if existing is not None:
                if existing != (owner, digest):
                    raise StateConflict("Generated document identity already exists with different ownership or content.")
                return
            files, size = connection.execute(
                "SELECT count(*),coalesce(sum(octet_length(raw_bytes)),0) FROM public.mammoth_generated_artifacts "
                "WHERE namespace=%s AND user_id=%s", (self.namespace, owner),
            ).fetchone()
            if files >= MAX_OWNER_FILES or size + len(raw) > MAX_OWNER_BYTES:
                raise StateUnavailable("Generated document storage limit reached; no existing documents were pruned.")
            inserted = connection.execute(
                "INSERT INTO public.mammoth_generated_artifacts(namespace,filename,user_id,raw_bytes,sha256) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING filename",
                (self.namespace, filename, owner, raw, digest),
            ).fetchone()
            if inserted is None:
                raise StateConflict("Generated document identity was claimed concurrently; inspect before retrying.")

    def get(self, filename, owner, *, admin=False):
        validate_filename(filename)
        if not admin:
            validate_owner(owner)
        with database(self.dsn) as connection:
            row = connection.execute(
                "SELECT raw_bytes,sha256 FROM public.mammoth_generated_artifacts "
                "WHERE namespace=%s AND filename=%s AND (%s OR user_id=%s)",
                (self.namespace, filename, admin, owner),
            ).fetchone()
        if row is None:
            return None
        raw = bytes(row[0])
        if hashlib.sha256(raw).hexdigest() != row[1]:
            raise StateUnavailable("Saved generated document checksum mismatch; operator repair is required.")
        return raw
