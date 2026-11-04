import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import runpy

from fastapi import UploadFile
import pytest

from mammoth_os.document_review import DocumentReviews
from mammoth_os.documents import DocumentError, DocumentLibrary
from mammoth_os.postgres import database
from mammoth_os.postgres_documents import PostgresDocumentLibrary
from test_document_review import Model, SynthesisModel
from test_postgres_run_store import postgres as postgres_fixture, stores as run_stores_fixture

postgres = postgres_fixture
stores = run_stores_fixture


@pytest.fixture
def library(stores, monkeypatch):
    from mammoth_os.documents import extract_document

    monkeypatch.setattr("mammoth_os.documents._extract_bounded", extract_document)
    monkeypatch.setattr("mammoth_os.postgres_documents._extract_bounded", extract_document)
    store, _ = stores
    return PostgresDocumentLibrary(store.dsn, store.namespace, "alice")


def upload(library, raw=b"A source explanation. " * 330, scope="chat"):
    return asyncio.run(library.upload(UploadFile(filename="source.txt", file=io.BytesIO(raw)), scope))


def test_shared_documents_own_binaries_index_and_metadata_atomically(library, monkeypatch):
    import api_server

    raw = b"First section.\n" * 800 + b"Late zebrafish cardiac regeneration."
    entry = upload(library, raw)
    assert "path" not in entry and "chunks_path" not in entry
    fresh = PostgresDocumentLibrary(library.dsn, library.namespace, "alice")
    other = PostgresDocumentLibrary(library.dsn, library.namespace, "bob")
    other_namespace = PostgresDocumentLibrary(library.dsn, library.namespace + "-other", "alice")
    saved = fresh.list("chat")[0]
    assert fresh.usage() == {"files": 1, "storage_bytes": len(raw)}
    assert "zebrafish" in fresh.sections(saved, "zebrafish")[0]["text"]
    assert other.list("chat") == other_namespace.list("chat") == []
    with pytest.raises(DocumentError):
        other._chunks(saved)
    with pytest.raises(DocumentError):
        fresh.delete("atlas", entry["file_id"])
    fresh.retag("chat", entry["file_id"], "reference")
    assert fresh.list("chat")[0]["tag"] == "reference"
    monkeypatch.setenv("MAMMOTH_DOCUMENT_BACKEND", "postgres")
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", library.dsn)
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", library.namespace)
    assert api_server._document_library("alice").list("chat")[0] == fresh.list("chat")[0]
    fresh.delete("chat", entry["file_id"])
    assert library.usage() == {"files": 0, "storage_bytes": 0}
    with database(library.dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_documents WHERE namespace=%s", (library.namespace,),
        ).fetchone()[0] == 0


def test_concurrent_document_quota_is_owner_serialized(library, monkeypatch):
    import mammoth_os.postgres_documents as module

    monkeypatch.setenv("MAMMOTH_UPLOAD_MAX_FILES", "1")
    monkeypatch.setattr(module, "_extract_bounded", lambda *args: {
        "status": "ready", "warnings": [], "extracted_chars": 6, "units_processed": 1,
        "chunks": [{"text": "source", "location": "section 1"}],
    })

    def attempt(_):
        try:
            return upload(library, b"source")["file_id"]
        except DocumentError as exc:
            assert exc.status_code in {413, 429}
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        identities = [identity for identity in pool.map(attempt, range(16)) if identity]
    assert len(identities) == library.usage()["files"] == 1
    assert library.usage()["storage_bytes"] == 6


def test_shared_document_preserves_actual_fifty_mib_boundary(library, monkeypatch):
    monkeypatch.setattr("mammoth_os.postgres_documents._extract_bounded", lambda *args: {
        "status": "partial", "warnings": ["Bounded fixture index."], "extracted_chars": 6, "units_processed": 1,
        "chunks": [{"text": "source", "location": "section 1"}],
    })
    maximum = 50 * 1024 * 1024
    result = upload(library, b"a" * maximum)
    assert result["size"] == maximum
    with pytest.raises(DocumentError) as error:
        upload(library, b"a" * (maximum + 1))
    assert error.value.status_code == 413
    assert library.usage() == {"files": 1, "storage_bytes": maximum}
    with database(library.dsn) as connection:
        assert connection.execute(
            "SELECT octet_length(raw_bytes) FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s",
            (library.namespace, library.user_id),
        ).fetchone()[0] == maximum


def test_parser_failure_leaves_no_document_or_quota_charge(library, monkeypatch):
    def broken(*args):
        raise DocumentError("Fixture parser rejected the input.")

    monkeypatch.setattr("mammoth_os.postgres_documents._extract_bounded", broken)
    with pytest.raises(DocumentError, match="parser rejected"):
        upload(library)
    assert library.usage() == {"files": 0, "storage_bytes": 0}
    assert library.list("chat") == []


def test_shared_reviews_assess_synthesize_and_recover_without_local_paths(library):
    uploaded = upload(library)
    first = DocumentReviews(library)
    state = first.create("chat", uploaded["file_id"], "Check every indexed section.")
    fresh = DocumentReviews(PostgresDocumentLibrary(library.dsn, library.namespace, "alice"))
    other = DocumentReviews(PostgresDocumentLibrary(library.dsn, library.namespace, "bob"))
    with pytest.raises(DocumentError):
        other.get(state["id"])
    model = Model()
    while state["status"] in {"ready", "partial"}:
        state = asyncio.run(fresh.advance(state["id"], lambda: model))
    assert state["review_complete"] and model.indices == list(range(state["total_sections"]))
    synthesis = SynthesisModel()
    state = asyncio.run(fresh.synthesize(state["id"], lambda: synthesis))
    while state["synthesis"]["status"] == "partial":
        state = asyncio.run(first.synthesize(state["id"], lambda: synthesis))
    assert state["synthesis"]["status"] == "completed"
    assert fresh.get(state["id"])["synthesis"] == state["synthesis"]
    library.delete("chat", uploaded["file_id"])
    with pytest.raises(DocumentError):
        fresh.get(state["id"])
    with pytest.raises(DocumentError, match="deleted"):
        first._save(state)


def test_shared_review_claim_and_unknown_call_never_replay(library):
    uploaded = upload(library)
    first = DocumentReviews(library)
    state = first.create("chat", uploaded["file_id"], "Review.")
    second = DocumentReviews(PostgresDocumentLibrary(library.dsn, library.namespace, "alice"))
    started = asyncio.Event()
    calls = []

    class Waiting:
        model = "fixture"

        async def generate_completion(self, *args, **kwargs):
            calls.append(1)
            started.set()
            await asyncio.Event().wait()

    async def verify():
        task = asyncio.create_task(first.advance(state["id"], Waiting))
        await started.wait()
        try:
            with pytest.raises(DocumentError, match="replayed"):
                await second.advance(state["id"], Waiting)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(verify())
    recovered = second.get(state["id"])
    assert recovered["status"] == "blocked" and recovered["inflight_section"] == 0
    with pytest.raises(DocumentError):
        second.extend_budget(state["id"], 64000, 128000)
    with pytest.raises(DocumentError):
        asyncio.run(second.advance(state["id"], Waiting))
    assert calls == [1]


def test_shared_review_quota_and_expected_budget_updates_are_atomic(library):
    uploaded = upload(library)
    reviews = DocumentReviews(library)

    def create(index):
        try:
            return DocumentReviews(PostgresDocumentLibrary(library.dsn, library.namespace, "alice")).create(
                "chat", uploaded["file_id"], f"Review {index}.",
            )["id"]
        except DocumentError as exc:
            assert exc.status_code == 409
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        identities = [identity for identity in pool.map(create, range(24)) if identity]
    assert len(identities) == len(reviews.list("chat", uploaded["file_id"])) == 20

    def extend(_):
        try:
            reviews.extend_budget(identities[0], 64000, 128000)
            return True
        except DocumentError as exc:
            assert exc.status_code == 409
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(extend, range(8))) == 1
    assert len(reviews.get(identities[0])["budget_extensions"]) == 1
    reviews.delete(identities[-1])
    assert len(reviews.list("chat", uploaded["file_id"])) == 19


def test_document_backup_import_and_fresh_local_rollback_preserve_unknown_review(library, tmp_path):
    migration = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "migrate_document_storage.py"))
    local = DocumentLibrary(tmp_path / "source", {"chat": tmp_path / "old-chat", "atlas": tmp_path / "old-atlas"})
    uploaded = upload(local)
    review = DocumentReviews(local).create("chat", uploaded["file_id"], "Keep evidence.")
    review.update(status="active", inflight_section=0)
    DocumentReviews(local)._save(review)
    backup = tmp_path / "backup"
    migration["backup"](local, "alice", backup)
    migration["import_backup"](library, backup)
    fresh = tmp_path / "fresh"
    migration["backup"](library, "alice", fresh)
    assert {path.name: path.read_bytes() for path in backup.iterdir()} == {
        path.name: path.read_bytes() for path in fresh.iterdir()}
    with pytest.raises(ValueError, match="already has"):
        migration["import_backup"](library, backup)
    restored_path = tmp_path / "restored"
    migration["restore_backup"](fresh, "alice", restored_path)
    restored = DocumentLibrary(restored_path, {"chat": restored_path, "atlas": restored_path})
    assert DocumentReviews(restored).get(review["id"])["inflight_section"] == 0
    rollback = tmp_path / "rollback"
    migration["backup"](restored, "alice", rollback)
    assert {path.name: path.read_bytes() for path in rollback.iterdir()} == {
        path.name: path.read_bytes() for path in backup.iterdir()}
    with pytest.raises(FileExistsError):
        migration["restore_backup"](fresh, "alice", restored_path)
    with pytest.raises(ValueError, match="owner"):
        migration["read_backup"](fresh, "bob")


def test_document_import_rejects_tampering_and_rolls_back_all_files(library, tmp_path):
    migration = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "migrate_document_storage.py"))
    local = DocumentLibrary(tmp_path / "source", {"chat": tmp_path, "atlas": tmp_path})
    for raw in (b"first source", b"second source"):
        upload(local, raw)
    target = tmp_path / "backup"
    manifest = migration["backup"](local, "alice", target)
    (target / f"{manifest['documents'][-1]}.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        migration["import_backup"](library, target)
    assert library.usage()["files"] == 0


def test_document_tables_deny_public_sql_clients(postgres):  # noqa: F811
    for role in ("anon", "authenticated"):
        for table in ("mammoth_document_owners", "mammoth_documents", "mammoth_document_reviews"):
            result = postgres(f"SET ROLE {role}; SELECT * FROM public.{table}", check=False)
            assert result.returncode != 0 and "permission denied" in result.stderr
