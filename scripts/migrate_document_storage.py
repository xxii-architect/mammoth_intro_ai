"""Quiesced private per-owner document backup, import and fresh-directory rollback."""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re

from mammoth_os.documents import DocumentLibrary, capabilities
from mammoth_os.postgres import database
from mammoth_os.postgres_documents import PostgresDocumentLibrary

CONTRACT = "mammoth.document-storage-backup.v1"
IDENTITY = re.compile(r"[a-zA-Z0-9_-]{1,128}")


def write_new(path, raw):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def canonical_entry(entry):
    result = {key: value for key, value in entry.items() if key not in {"path", "chunks_path"}}
    if entry.get("chunks_path"):
        result["chunks_path"] = "postgres-index"
    return result


def backup(library, user_id, target):
    """Write the manifest last; an interrupted output is not an importable backup."""
    target.mkdir(mode=0o700)
    records = []
    for scope in ("chat", "atlas"):
        for entry in library.list(scope):
            identity = entry["file_id"]
            if not isinstance(identity, str) or IDENTITY.fullmatch(identity) is None:
                raise ValueError("Invalid stored document identity; operator repair required.")
            if isinstance(library, PostgresDocumentLibrary):
                with database(library.dsn) as connection:
                    row = connection.execute(
                        "SELECT raw_bytes FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s AND file_id=%s AND scope=%s",
                        (library.namespace, user_id, identity, scope),
                    ).fetchone()
                if row is None:
                    raise ValueError("Document disappeared during backup; stop writers.")
                raw = bytes(row[0])
            else:
                path = Path(entry["path"]).resolve(strict=True)
                allowed = {library.folder.resolve(), library.legacy_folders[scope].resolve()}
                if path.parent not in allowed:
                    raise ValueError("Stored binary path is outside reviewed private source folders.")
                raw = path.read_bytes()
            if len(raw) != entry["size"]:
                raise ValueError("Stored binary size differs from metadata; repair before migration.")
            chunks = library._chunks(entry)
            reviews = library.review_store().list(scope, identity)
            record = {"entry": canonical_entry(entry), "chunks": chunks, "reviews": reviews,
                      "sha256": hashlib.sha256(raw).hexdigest()}
            write_new(target / f"{identity}.bin", raw)
            write_new(target / f"{identity}.json", json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
            records.append(identity)
    manifest = {"contract": CONTRACT, "user_id": user_id, "documents": sorted(records)}
    if len(set(records)) != len(records):
        raise ValueError("Duplicate stored document identities; backup is not complete.")
    write_new(target / "manifest.json", json.dumps(manifest, indent=2).encode())
    return manifest


def read_backup(source, user_id):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("contract") != CONTRACT or manifest.get("user_id") != user_id:
        raise ValueError("Backup contract/owner does not match the explicit target.")
    identities = manifest["documents"]
    if (not isinstance(identities, list) or len(identities) != len(set(identities))
            or any(not isinstance(identity, str) or IDENTITY.fullmatch(identity) is None for identity in identities)):
        raise ValueError("Backup contains invalid/duplicate document identities.")
    return identities


def read_document(source, identity):
    record = json.loads((source / f"{identity}.json").read_text(encoding="utf-8"))
    entry, chunks = record["entry"], record["chunks"]
    if (entry["file_id"] != identity or entry["scope"] not in {"chat", "atlas"}
            or "path" in entry or entry.get("chunks_path") not in {None, "postgres-index"}
            or not isinstance(chunks, list) or any(
                not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str)
                or not isinstance(chunk.get("location"), str) for chunk in chunks)):
        raise ValueError("Invalid document metadata/index in backup.")
    raw = (source / f"{identity}.bin").read_bytes()
    if (type(entry["size"]) is not int or len(raw) != entry["size"]
            or hashlib.sha256(raw).hexdigest() != record["sha256"]):
        raise ValueError("Binary backup checksum/size mismatch; nothing may be activated.")
    reviews = record["reviews"]
    if not isinstance(reviews, list):
        raise ValueError("Invalid saved review collection.")
    for state in reviews:
        if (not isinstance(state, dict) or not isinstance(state.get("id"), str) or not state["id"]
                or state.get("file_id") != identity or state.get("scope") != entry["scope"]):
            raise ValueError("Saved review ownership does not match its document.")
    return record, raw


def import_backup(library, source):
    identities = read_backup(source, library.user_id)
    policy = capabilities()
    if len(identities) > policy["max_files"]:
        raise ValueError("Backup exceeds configured file quota; do not silently drop documents.")
    with database(library.dsn) as connection, connection.transaction():
        from psycopg.types.json import Jsonb

        library._owner(connection)
        if connection.execute(
            "SELECT 1 FROM public.mammoth_documents WHERE namespace=%s AND user_id=%s LIMIT 1",
            (library.namespace, library.user_id),
        ).fetchone():
            raise ValueError("Import refused: destination already has documents. Nothing was overwritten.")
        stored, review_ids = 0, set()
        for identity in identities:
            record, raw = read_document(source, identity)
            entry = record["entry"]
            stored += len(raw)
            if len(raw) > policy["max_file_bytes"] or stored > policy["max_storage_bytes"]:
                raise ValueError("Backup exceeds configured binary quotas; import was rolled back.")
            connection.execute(
                "INSERT INTO public.mammoth_documents(namespace,user_id,file_id,scope,payload,raw_bytes,chunks,stored_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (library.namespace, library.user_id, identity, entry["scope"], Jsonb(entry), raw,
                 Jsonb(record["chunks"]), entry["created_at"]),
            )
            for state in record["reviews"]:
                if state["id"] in review_ids or len(review_ids) >= 20:
                    raise ValueError("Duplicate or excessive saved reviews; import was rolled back.")
                review_ids.add(state["id"])
                connection.execute(
                    "INSERT INTO public.mammoth_document_reviews(namespace,user_id,id,file_id,scope,payload,stored_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (library.namespace, library.user_id, state["id"], identity, entry["scope"], Jsonb(state), state["created_at"]),
                )


def restore_backup(source, user_id, target):
    identities = read_backup(source, user_id)
    target.mkdir(mode=0o700)
    library = DocumentLibrary(target, {"chat": target, "atlas": target})
    for identity in identities:
        record, raw = read_document(source, identity)
        entry = dict(record["entry"])
        binary = target / f"{identity}.bin"
        write_new(binary, raw)
        entry["path"] = str(binary)
        if entry.get("chunks_path"):
            chunks_path = target / f"{identity}.chunks.json"
            write_new(chunks_path, json.dumps(record["chunks"], ensure_ascii=False).encode("utf-8"))
            entry["chunks_path"] = str(chunks_path)
        with closing(library._connect()) as connection, connection:
            connection.execute("INSERT INTO files VALUES(?,?,?)", (identity, entry["scope"], json.dumps(entry)))
            for state in record["reviews"]:
                connection.execute("INSERT INTO document_reviews VALUES(?,?,?,?)",
                                   (state["id"], entry["scope"], identity, json.dumps(state)))
    write_new(target / "restore-complete.json", json.dumps({"contract": CONTRACT, "user_id": user_id}).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("local-export", "import", "export", "restore-local"))
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--local-dir", type=Path)
    parser.add_argument("--legacy-chat-dir", type=Path)
    parser.add_argument("--legacy-atlas-dir", type=Path)
    parser.add_argument("--confirm-quiesced", action="store_true")
    args = parser.parse_args()
    if not args.confirm_quiesced:
        parser.error("Stop every document/review writer and confirm --confirm-quiesced.")
    if args.direction == "local-export":
        paths = (args.local_dir, args.legacy_chat_dir, args.legacy_atlas_dir)
        if any(path is None or not path.is_dir() for path in paths):
            parser.error("All explicit reviewed local/legacy source directories must exist.")
        backup(DocumentLibrary(args.local_dir, {"chat": args.legacy_chat_dir, "atlas": args.legacy_atlas_dir}),
               args.user_id, args.backup_dir)
    elif args.direction == "restore-local":
        if args.local_dir is None:
            parser.error("A fresh --local-dir output is required.")
        restore_backup(args.backup_dir, args.user_id, args.local_dir)
    else:
        library = PostgresDocumentLibrary(os.getenv("MAMMOTH_POSTGRES_DSN"),
                                          os.getenv("MAMMOTH_STATE_NAMESPACE"), args.user_id)
        if args.direction == "import":
            import_backup(library, args.backup_dir)
        else:
            backup(library, args.user_id, args.backup_dir)
    print("Document storage operation completed. Retain private backups and verify before activation.")


if __name__ == "__main__":
    main()
