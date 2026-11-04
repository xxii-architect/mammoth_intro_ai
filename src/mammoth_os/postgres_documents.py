"""Opt-in transactional private document storage, including bounded binary data."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from .documents import DocumentError, DocumentLibrary, _extract_bounded
from .postgres import database
from .shared_state import StateUnavailable

class PostgresDocumentLibrary(DocumentLibrary):
    def __init__(self, dsn, namespace, user_id):
        if (not dsn or not isinstance(namespace, str) or not 1 <= len(namespace) <= 128
                or not namespace.replace("-", "").replace("_", "").isalnum()
                or not isinstance(user_id, str) or not 1 <= len(user_id) <= 256):
            raise StateUnavailable("Shared documents require a private database, namespace and authenticated owner.")
        self.dsn, self.namespace, self.user_id = dsn, namespace, user_id

    def _connect(self):
        raise StateUnavailable("Shared documents do not expose a local SQLite connection.")

    def review_store(self):
        return PostgresReviewStore(self)

    def _owner(self, connection):
        connection.execute(
            "INSERT INTO public.mammoth_document_owners VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (self.namespace, self.user_id),
        )
        connection.execute(
            "SELECT user_id FROM public.mammoth_document_owners WHERE namespace=%s AND user_id=%s FOR UPDATE",
            (self.namespace, self.user_id),
        )

    def list(self, scope):
        with database(self.dsn) as connection:
            return [row[0] for row in connection.execute(
                "SELECT payload FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s AND scope=%s "
                "ORDER BY stored_at DESC,file_id DESC", (self.namespace, self.user_id, scope),
            ).fetchall()]

    def usage(self):
        with database(self.dsn) as connection:
            size, count = connection.execute(
                "SELECT coalesce(sum(octet_length(raw_bytes)),0),count(*) FROM public.mammoth_documents "
                "WHERE namespace=%s AND user_id=%s", (self.namespace, self.user_id),
            ).fetchone()
        return {"storage_bytes": int(size), "files": count}

    async def upload(self, upload, scope, tag="other"):
        if scope not in {"chat", "atlas"}:
            raise DocumentError("Use chat or atlas document scope.", 400)
        # The inherited bounded parser needs a temporary input, never durable local state.
        with tempfile.TemporaryDirectory(prefix="mammoth-document-") as directory:
            worker = PostgresDocumentLibrary(self.dsn, self.namespace, self.user_id)
            worker.folder = Path(directory)
            return await DocumentLibrary.upload(worker, upload, scope, tag)

    def _ingest(self, staging, file_id, name, size, scope, tag, policy):
        from psycopg.types.json import Jsonb

        extracted = _extract_bounded(staging, name)
        raw = staging.read_bytes()
        if len(raw) != size or size > policy["max_file_bytes"]:
            raise DocumentError("Upload changed during processing; no document was saved.", 409)
        entry = {
            "file_id": file_id, "name": name, "ext": Path(name).suffix.lower(), "size": size,
            "tag": tag, "scope": scope, "created_at": datetime.now(timezone.utc).isoformat(),
            "chunks_path": "postgres-index", "processing_status": extracted["status"], "warnings": extracted["warnings"],
            "extracted_chars": extracted["extracted_chars"], "units_processed": extracted["units_processed"],
            "chunk_count": len(extracted["chunks"]),
        }
        with database(self.dsn) as connection, connection.transaction():
            self._owner(connection)
            stored, count = connection.execute(
                "SELECT coalesce(sum(octet_length(raw_bytes)),0),count(*) FROM public.mammoth_documents "
                "WHERE namespace=%s AND user_id=%s", (self.namespace, self.user_id),
            ).fetchone()
            if count >= policy["max_files"] or stored + size > policy["max_storage_bytes"]:
                raise DocumentError("Private upload storage quota reached. Delete unused files before uploading.", 413)
            connection.execute(
                "INSERT INTO public.mammoth_documents(namespace,user_id,file_id,scope,payload,raw_bytes,chunks) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (self.namespace, self.user_id, file_id, scope, Jsonb(entry), raw, Jsonb(extracted["chunks"])),
            )
        preview = "\n\n".join(chunk["text"] for chunk in extracted["chunks"][:2])[:1200]
        return {"status": "ok", **self.public(entry), "text_preview": preview}

    def _chunks(self, entry):
        with database(self.dsn) as connection:
            row = connection.execute(
                "SELECT chunks FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s AND file_id=%s AND scope=%s",
                (self.namespace, self.user_id, entry["file_id"], entry["scope"]),
            ).fetchone()
        if row is None:
            raise DocumentError("File not found.", 404)
        chunks = row[0]
        if not isinstance(chunks, list) or not all(
            isinstance(chunk, dict) and isinstance(chunk.get("text"), str) and isinstance(chunk.get("location"), str)
            for chunk in chunks
        ):
            raise DocumentError("Document index is invalid; operator repair is required.", 503)
        return chunks

    def delete(self, scope, file_id):
        with database(self.dsn) as connection, connection.transaction():
            self._owner(connection)
            changed = connection.execute(
                "DELETE FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s AND file_id=%s AND scope=%s",
                (self.namespace, self.user_id, file_id, scope),
            )
            if changed.rowcount != 1:
                raise DocumentError("File not found.", 404)
        return {"status": "ok", "deleted": file_id}

    def retag(self, scope, file_id, tag):
        with database(self.dsn) as connection, connection.transaction():
            from psycopg.types.json import Jsonb

            row = connection.execute(
                "SELECT payload FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s AND file_id=%s AND scope=%s FOR UPDATE",
                (self.namespace, self.user_id, file_id, scope),
            ).fetchone()
            if row is None:
                raise DocumentError("File not found.", 404)
            entry = {**row[0], "tag": tag}
            connection.execute(
                "UPDATE public.mammoth_documents SET payload=%s WHERE namespace=%s AND user_id=%s AND file_id=%s",
                (Jsonb(entry), self.namespace, self.user_id, file_id),
            )
        return {"status": "ok", "file_id": file_id, "tag": tag}


class PostgresReviewStore:
    def __init__(self, library):
        self.library = library
        self.dsn, self.namespace, self.user_id = library.dsn, library.namespace, library.user_id

    def list(self, scope, file_id):
        with database(self.dsn) as connection:
            return [row[0] for row in connection.execute(
                "SELECT payload FROM public.mammoth_document_reviews WHERE namespace=%s AND user_id=%s "
                "AND scope=%s AND file_id=%s ORDER BY stored_at DESC,id DESC",
                (self.namespace, self.user_id, scope, file_id),
            ).fetchall()]

    def get(self, identity):
        with database(self.dsn) as connection:
            row = connection.execute(
                "SELECT payload FROM public.mammoth_document_reviews WHERE namespace=%s AND user_id=%s AND id=%s",
                (self.namespace, self.user_id, identity),
            ).fetchone()
        if row is None:
            raise DocumentError("Review not found.", 404)
        return row[0]

    def create(self, state):
        with database(self.dsn) as connection, connection.transaction():
            from psycopg.types.json import Jsonb

            self.library._owner(connection)
            if connection.execute(
                "SELECT count(*) FROM public.mammoth_document_reviews WHERE namespace=%s AND user_id=%s",
                (self.namespace, self.user_id),
            ).fetchone()[0] >= 20:
                raise DocumentError("Saved review limit reached (20). Delete an unused review first.", 409)
            if not connection.execute(
                "SELECT 1 FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s AND file_id=%s AND scope=%s FOR KEY SHARE",
                (self.namespace, self.user_id, state["file_id"], state["scope"]),
            ).fetchone():
                raise DocumentError("File not found.", 404)
            connection.execute(
                "INSERT INTO public.mammoth_document_reviews(namespace,user_id,id,file_id,scope,payload) VALUES(%s,%s,%s,%s,%s,%s)",
                (self.namespace, self.user_id, state["id"], state["file_id"], state["scope"], Jsonb(state)),
            )

    def delete(self, identity):
        with database(self.dsn) as connection:
            if connection.execute(
                "DELETE FROM public.mammoth_document_reviews WHERE namespace=%s AND user_id=%s AND id=%s",
                (self.namespace, self.user_id, identity),
            ).rowcount != 1:
                raise DocumentError("Review not found.", 404)

    def _save(self, connection, state):
        from psycopg.types.json import Jsonb

        if connection.execute(
            "UPDATE public.mammoth_document_reviews SET payload=%s WHERE namespace=%s AND user_id=%s AND id=%s",
            (Jsonb(state), self.namespace, self.user_id, state["id"]),
        ).rowcount != 1:
            raise DocumentError("Review or source was deleted. No further work can be saved.", 404)

    def save(self, state):
        with database(self.dsn) as connection:
            self._save(connection, state)

    @contextmanager
    def edit(self, identity):
        with database(self.dsn) as connection, connection.transaction():
            row = connection.execute(
                "SELECT payload FROM public.mammoth_document_reviews WHERE namespace=%s AND user_id=%s AND id=%s FOR UPDATE",
                (self.namespace, self.user_id, identity),
            ).fetchone()
            if row is None:
                raise DocumentError("Review not found.", 404)
            state = row[0]
            yield state
            self._save(connection, state)
