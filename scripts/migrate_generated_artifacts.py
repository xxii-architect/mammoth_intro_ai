"""Quiesced namespace-wide generated DOCX backup, import and fresh-path rollback."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from mammoth_os.generated_artifacts import (
    MAX_OWNER_BYTES, MAX_OWNER_FILES, PostgresGeneratedArtifacts, migration_lock,
    read_staged, validate_filename, validate_owner,
)
from mammoth_os.postgres import database

CONTRACT = "mammoth.generated-artifacts-backup.v1"


def write_new(path, raw):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def write_record(target, filename, owner, raw):
    validate_filename(filename)
    validate_owner(owner, allow_legacy=True)
    write_new(target / filename, raw)
    return {"filename": filename, "user_id": owner, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def finish_backup(target, namespace, records):
    manifest = {"contract": CONTRACT, "namespace": namespace, "artifacts": records}
    write_new(target / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
    return manifest


def local_backup(folder, owners_file, target, namespace):
    # The explicit ownership file must be an authoritative quiesced snapshot.
    owners = json.loads(owners_file.read_text(encoding="utf-8"))
    if not isinstance(owners, dict):
        raise ValueError("The reviewed ownership snapshot must be an object.")
    for filename, owner in owners.items():
        validate_filename(filename)
        validate_owner(owner)
    names = sorted(path.name for path in folder.iterdir() if path.name.endswith(".docx"))
    if set(owners) - set(names):
        raise ValueError("Ownership references missing binaries; repair the snapshot before migration.")
    target.mkdir(mode=0o700)
    records = [write_record(target, name, owners.get(name), read_staged(folder, name)) for name in names]
    return finish_backup(target, namespace, records)


def export_backup(store, target):
    target.mkdir(mode=0o700)
    records = []
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        filenames = connection.execute(
            "SELECT filename FROM public.mammoth_generated_artifacts WHERE namespace=%s ORDER BY filename",
            (store.namespace,),
        ).fetchall()
        for (filename,) in filenames:
            owner, raw, digest = connection.execute(
                "SELECT user_id,raw_bytes,sha256 FROM public.mammoth_generated_artifacts WHERE namespace=%s AND filename=%s",
                (store.namespace, filename),
            ).fetchone()
            if hashlib.sha256(bytes(raw)).hexdigest() != digest:
                raise ValueError("Saved generated document checksum mismatch; repair before migration.")
            records.append(write_record(target, filename, owner, bytes(raw)))
    return finish_backup(target, store.namespace, records)


def read_manifest(source, namespace):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("contract") != CONTRACT or manifest.get("namespace") != namespace:
        raise ValueError("Backup contract/namespace does not match the explicit target.")
    records = manifest.get("artifacts")
    if not isinstance(records, list):
        raise ValueError("Invalid generated document collection.")
    identities, quotas = set(), {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid generated document record.")
        name, owner = record.get("filename"), record.get("user_id")
        validate_filename(name)
        validate_owner(owner, allow_legacy=True)
        if name in identities:
            raise ValueError("Duplicate generated document identity.")
        identities.add(name)
        size = record.get("size")
        digest = record.get("sha256")
        if (type(size) is not int or size < 1 or not isinstance(digest, str)
                or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError("Invalid generated document size/checksum.")
        files, total = quotas.get(owner, (0, 0))
        quotas[owner] = files + 1, total + size
        if files + 1 > MAX_OWNER_FILES or total + size > MAX_OWNER_BYTES:
            raise ValueError("Backup exceeds generated document owner quota.")
    return records


def read_record(source, record):
    raw = read_staged(source, record["filename"])
    if len(raw) != record["size"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Generated document backup checksum/size mismatch; do not activate.")
    return raw


def import_backup(store, source):
    records = read_manifest(source, store.namespace)
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        existing = connection.execute(
            "SELECT 1 FROM public.mammoth_generated_artifacts WHERE namespace=%s LIMIT 1", (store.namespace,),
        ).fetchone()
        if existing:
            raise ValueError("Destination namespace already contains generated documents.")
        for record in records:
            raw, owner = read_record(source, record), record["user_id"]
            if owner is not None:
                connection.execute(
                    "INSERT INTO public.mammoth_generated_owners(namespace,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    (store.namespace, owner),
                )
            connection.execute(
                "INSERT INTO public.mammoth_generated_artifacts(namespace,filename,user_id,raw_bytes,sha256) "
                "VALUES (%s,%s,%s,%s,%s)",
                (store.namespace, record["filename"], owner, raw, record["sha256"]),
            )
    return len(records)


def restore_local(source, target, namespace):
    records = read_manifest(source, namespace)
    target.mkdir(mode=0o700)
    folder = target / "generated_docs"
    folder.mkdir(mode=0o700)
    owners = {}
    for record in records:
        write_new(folder / record["filename"], read_record(source, record))
        if record["user_id"] is not None:
            owners[record["filename"]] = record["user_id"]
    write_new(target / "generated_doc_owners.json", json.dumps(owners, indent=2, sort_keys=True).encode("utf-8"))
    write_new(target / "restore-complete.json", json.dumps({
        "contract": CONTRACT, "namespace": namespace, "artifacts": len(records),
    }).encode("utf-8"))
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("local-export", "import", "export", "restore-local"))
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--generated-dir", type=Path)
    parser.add_argument("--owners-file", type=Path)
    parser.add_argument("--restore-dir", type=Path)
    parser.add_argument("--confirm-quiesced", action="store_true", required=True)
    args = parser.parse_args()
    if args.direction == "local-export":
        if args.generated_dir is None or args.owners_file is None:
            parser.error("local-export requires explicit --generated-dir and authoritative --owners-file")
        result = len(local_backup(args.generated_dir, args.owners_file, args.backup, args.namespace)["artifacts"])
    elif args.direction == "restore-local":
        if args.restore_dir is None:
            parser.error("restore-local requires a new --restore-dir")
        result = restore_local(args.backup, args.restore_dir, args.namespace)
    else:
        store = PostgresGeneratedArtifacts(os.environ.get("MAMMOTH_POSTGRES_DSN", ""), args.namespace)
        result = (import_backup(store, args.backup) if args.direction == "import"
                  else len(export_backup(store, args.backup)["artifacts"]))
    print(json.dumps({"contract": CONTRACT, "direction": args.direction, "artifacts": result}))


if __name__ == "__main__":
    main()
