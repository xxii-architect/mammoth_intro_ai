from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import runpy

import pytest

import api_server
from mammoth_os.generated_artifacts import (
    MAX_FILE_BYTES, PostgresGeneratedArtifacts, read_staged, validate_filename,
)
from mammoth_os.postgres import database
from mammoth_os.shared_state import StateConflict, StateUnavailable
from test_postgres_run_store import postgres as postgres_fixture, stores as run_stores_fixture

postgres = postgres_fixture
stores = run_stores_fixture


@pytest.fixture
def artifacts(stores):
    store, _ = stores
    return PostgresGeneratedArtifacts(store.dsn, store.namespace)


@pytest.mark.parametrize("filename", [
    "../private.docx", "nested/file.docx", "nested\\file.docx", "x:y.docx", "x\r\n.docx",
    "x\0.docx", "x.txt", "", "a" * 241 + ".docx",
])
def test_generated_names_reject_traversal_and_header_injection(filename):
    with pytest.raises(ValueError):
        validate_filename(filename)


def test_generated_backend_never_silently_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("MAMMOTH_GENERATED_ARTIFACT_BACKEND", "unknown")
    with pytest.raises(StateUnavailable, match="Invalid generated"):
        api_server._generated_artifact_store()
    monkeypatch.setenv("MAMMOTH_GENERATED_ARTIFACT_BACKEND", "postgres")
    monkeypatch.delenv("MAMMOTH_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", "fixture")
    with pytest.raises(StateUnavailable, match="private database"):
        api_server._generated_artifact_store()
    (tmp_path / "report.docx").write_bytes(b"PK")
    monkeypatch.setattr(api_server, "GENERATED_DOCS_DIR", tmp_path)
    with pytest.raises(StateUnavailable):
        api_server._record_generated_doc_owner("report.docx")
    assert (tmp_path / "report.docx").read_bytes() == b"PK"


def test_staging_rejects_resolved_escape(tmp_path, monkeypatch):
    folder = tmp_path / "staging"
    folder.mkdir()
    path = folder / "report.docx"
    path.write_bytes(b"PK")
    resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda value, *args, **kwargs: (
        tmp_path / "elsewhere" / "report.docx" if value == path else resolve(value, *args, **kwargs)
    ))
    with pytest.raises(StateUnavailable, match="outside"):
        read_staged(folder, "report.docx")


def test_publication_reports_failure_without_losing_draft_or_exposing_internal_error(monkeypatch, caplog):
    def failed(filename):
        raise StateUnavailable("fixture internal failure")

    monkeypatch.setattr(api_server, "_record_generated_doc_owner", failed)
    output = {"status": "ok", "docx_filename": "report.docx", "sections": [{"content": "draft"}], "quality": {}}
    api_server._publish_generated_document(output)
    assert output["status"] == "partial" and output["docx_filename"] is None
    assert output["sections"][0]["content"] == "draft"
    assert output["quality"]["generated_document"] == {
        "status": "failed", "error_code": "artifact_storage_failed",
    }
    assert "fixture internal failure" not in json.dumps(output)
    assert "model work is not replayed" in caplog.text


def test_generated_bytes_and_immutable_ownership_survive_independent_instances(artifacts):
    artifacts.put("report.docx", "alice", b"PK first")
    fresh = PostgresGeneratedArtifacts(artifacts.dsn, artifacts.namespace)
    assert fresh.get("report.docx", "alice") == b"PK first"
    assert fresh.get("report.docx", "bob") is None
    assert fresh.get("missing.docx", "alice") is None
    assert fresh.get("report.docx", "", admin=True) == b"PK first"
    assert PostgresGeneratedArtifacts(artifacts.dsn, artifacts.namespace + "-other").get("report.docx", "alice") is None
    artifacts.put("report.docx", "alice", b"PK first")
    for owner, raw in (("bob", b"PK first"), ("alice", b"PK overwrite")):
        with pytest.raises(StateConflict):
            artifacts.put("report.docx", owner, raw)
    assert fresh.get("report.docx", "alice") == b"PK first"


def test_generated_actual_fifty_mib_boundary(artifacts, tmp_path):
    raw = b"a" * MAX_FILE_BYTES
    (tmp_path / "maximum.docx").write_bytes(raw)
    assert read_staged(tmp_path, "maximum.docx") == raw
    artifacts.put("maximum.docx", "alice", raw)
    assert artifacts.get("maximum.docx", "alice") == raw
    with pytest.raises(ValueError, match="50 MiB"):
        artifacts.put("over.docx", "alice", raw + b"a")
    (tmp_path / "maximum.docx").write_bytes(raw + b"a")
    with pytest.raises(ValueError, match="50 MiB"):
        read_staged(tmp_path, "maximum.docx")
    assert artifacts.get("over.docx", "alice") is None


def test_generated_quotas_serialize_competing_writers_without_pruning(artifacts, monkeypatch):
    monkeypatch.setattr("mammoth_os.generated_artifacts.MAX_OWNER_FILES", 1)

    def create(index):
        try:
            artifacts.put(f"report-{index}.docx", "alice", b"PK")
            return True
        except StateUnavailable as exc:
            assert "limit reached" in str(exc)
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(create, range(16))) == 1
    artifacts.put("bob.docx", "bob", b"PK")
    monkeypatch.setattr("mammoth_os.generated_artifacts.MAX_OWNER_FILES", 2000)
    monkeypatch.setattr("mammoth_os.generated_artifacts.MAX_OWNER_BYTES", 3)
    with pytest.raises(StateUnavailable, match="limit reached"):
        artifacts.put("more.docx", "alice", b"PK")
    with database(artifacts.dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM public.mammoth_generated_artifacts WHERE namespace=%s", (artifacts.namespace,),
        ).fetchone()[0] == 2


def test_concurrent_filename_collision_never_steals_ownership(artifacts):
    def claim(owner):
        try:
            artifacts.put("same.docx", owner, b"PK")
            return owner
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        winners = [owner for owner in pool.map(claim, [f"user-{index}" for index in range(12)]) if owner]
    assert len(winners) == 1
    for owner in (f"user-{index}" for index in range(12)):
        assert artifacts.get("same.docx", owner) == (b"PK" if owner == winners[0] else None)


def test_generated_route_publication_and_download_do_not_depend_on_local_bytes(artifacts, tmp_path, monkeypatch):
    monkeypatch.setenv("MAMMOTH_GENERATED_ARTIFACT_BACKEND", "postgres")
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", artifacts.dsn)
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", artifacts.namespace)
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "GENERATED_DOCS_DIR", tmp_path)
    monkeypatch.setattr(api_server, "GENERATED_DOC_OWNERS_FILE", tmp_path / "owners.json")
    user, admin = api_server._REQUEST_USER_ID.set("alice"), api_server._REQUEST_IS_ADMIN.set(False)
    try:
        name, raw = "r\u00e9sum\u00e9.docx", b"PK independent bytes"
        (tmp_path / name).write_bytes(raw)
        api_server._record_generated_doc_owner(name)
        assert not list(tmp_path.iterdir())
        response = api_server.download_docx_file(name)
        assert response.status_code == 200 and response.body == raw
        assert "%C3%A9" in response.headers["content-disposition"]
        api_server._REQUEST_USER_ID.set("bob")
        for filename in (name, "missing.docx"):
            denied = api_server.download_docx_file(filename)
            assert denied.status_code == 404 and denied.body == b'{"status":"error","error":"Document not found."}'
        api_server._REQUEST_IS_ADMIN.set(True)
        assert api_server.download_docx_file(name).body == raw
        api_server._REQUEST_USER_ID.set("anonymous")
        api_server._REQUEST_IS_ADMIN.set(False)
        assert api_server.download_docx_file(name).status_code == 401
    finally:
        api_server._REQUEST_USER_ID.reset(user)
        api_server._REQUEST_IS_ADMIN.reset(admin)


def migration():
    return runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "migrate_generated_artifacts.py"))


def local_backup(module, tmp_path, namespace):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("owned.docx", "legacy.docx"):
        (source / name).write_bytes(("PK " + name).encode())
    owners = tmp_path / "owners.json"
    owners.write_text(json.dumps({"owned.docx": "alice"}), encoding="utf-8")
    backup = tmp_path / "backup"
    module["local_backup"](source, owners, backup, namespace)
    return backup


def test_generated_checksums_ownership_and_admin_only_legacy_round_trip(artifacts, tmp_path):
    module = migration()
    backup = local_backup(module, tmp_path, artifacts.namespace)
    assert module["import_backup"](artifacts, backup) == 2
    assert artifacts.get("owned.docx", "alice") == b"PK owned.docx"
    assert artifacts.get("legacy.docx", "alice") is None
    assert artifacts.get("legacy.docx", "", admin=True) == b"PK legacy.docx"
    with pytest.raises(StateConflict):
        artifacts.put("legacy.docx", "alice", b"PK legacy.docx")
    with pytest.raises(ValueError, match="already contains"):
        module["import_backup"](artifacts, backup)
    exported = tmp_path / "exported"
    module["export_backup"](artifacts, exported)
    assert (exported / "manifest.json").read_bytes() == (backup / "manifest.json").read_bytes()
    rollback = tmp_path / "rollback"
    assert module["restore_local"](exported, rollback, artifacts.namespace) == 2
    assert (rollback / "restore-complete.json").is_file()
    assert json.loads((rollback / "generated_doc_owners.json").read_text()) == {"owned.docx": "alice"}
    assert (rollback / "generated_docs" / "legacy.docx").read_bytes() == b"PK legacy.docx"
    with pytest.raises(FileExistsError):
        module["restore_local"](exported, rollback, artifacts.namespace)


def test_generated_tamper_rolls_back_whole_import_and_blocks_rollback_activation(artifacts, tmp_path):
    module = migration()
    backup = local_backup(module, tmp_path, artifacts.namespace)
    # owned.docx follows legacy.docx: the first inserted row must roll back too.
    (backup / "owned.docx").write_bytes(b"PK tampered")
    with pytest.raises(ValueError, match="checksum"):
        module["import_backup"](artifacts, backup)
    assert artifacts.get("legacy.docx", "", admin=True) is None
    rollback = tmp_path / "rollback"
    with pytest.raises(ValueError, match="checksum"):
        module["restore_local"](backup, rollback, artifacts.namespace)
    assert not (rollback / "restore-complete.json").exists()
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest["artifacts"][0]["filename"] = "../escape.docx"
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid generated"):
        module["import_backup"](artifacts, backup)


def test_generated_schema_denies_tenant_sql_and_service_updates(artifacts, postgres):
    artifacts.put("private.docx", "alice", b"PK")
    for role in ("anon", "authenticated"):
        for table in ("mammoth_generated_owners", "mammoth_generated_artifacts"):
            result = postgres(f"SET ROLE {role}; SELECT * FROM public.{table}", check=False)
            assert result.returncode != 0 and "permission denied" in result.stderr
            assert postgres(
                "SELECT bool_and(relrowsecurity) FROM pg_class WHERE relname IN "
                "('mammoth_generated_owners','mammoth_generated_artifacts')",
            ) == "t"
    result = postgres("SET ROLE service_role; UPDATE public.mammoth_generated_artifacts SET user_id='bob'", check=False)
    assert result.returncode != 0 and "permission denied" in result.stderr
    with database(artifacts.dsn) as connection:
        saved = connection.execute(
            "SELECT sha256 FROM public.mammoth_generated_artifacts WHERE namespace=%s", (artifacts.namespace,),
        ).fetchone()[0]
    assert saved == hashlib.sha256(b"PK").hexdigest()


def test_corrupt_database_bytes_are_not_served_or_normalized_into_a_valid_backup(artifacts, tmp_path):
    artifacts.put("report.docx", "alice", b"PK")
    with database(artifacts.dsn) as connection:
        connection.execute(
            "UPDATE public.mammoth_generated_artifacts SET raw_bytes=%s WHERE namespace=%s",
            (b"tampered", artifacts.namespace),
        )
    with pytest.raises(StateUnavailable, match="checksum"):
        artifacts.get("report.docx", "alice")
    output = tmp_path / "export"
    with pytest.raises(ValueError, match="checksum"):
        migration()["export_backup"](artifacts, output)
    assert not (output / "manifest.json").exists()
