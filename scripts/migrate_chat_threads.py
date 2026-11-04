"""Quiesced explicit-owner chat backup, shared import and fresh-directory rollback."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from mammoth_os.chat_threads import MAX_THREADS, PostgresChatThreads, migration_lock, validate_identity, validate_record
from mammoth_os.postgres import database

CONTRACT = "mammoth.chat-threads-backup.v1"


def write_new(path, raw):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def legacy_name(identity):
    return re.sub(r"[^a-z0-9_-]", "-", identity.strip().lower()).strip("-") or "unknown"


def write_backup(target, user_id, records):
    validate_identity(user_id, owner=True)
    target.mkdir(mode=0o700)
    payload = json.dumps(records, ensure_ascii=True, sort_keys=True, indent=2).encode()
    write_new(target / "threads.json", payload)
    manifest = {"contract": CONTRACT, "user_id": user_id, "threads": len(records),
                "sha256": hashlib.sha256(payload).hexdigest()}
    write_new(target / "manifest.json", json.dumps(manifest, sort_keys=True).encode())
    return manifest


def local_backup(folder, target, user_id):
    # Caller must explicitly verify the legacy directory's ownership; never infer it.
    index = json.loads((folder / "_index.json").read_text(encoding="utf-8"))
    deleted_path = folder / "_deleted.json"
    deleted = json.loads(deleted_path.read_text(encoding="utf-8")) if deleted_path.exists() else {}
    if not isinstance(index, list) or not isinstance(deleted, dict):
        raise ValueError("Invalid legacy chat index/tombstones; repair before migration.")
    records, used_names = [], set()
    for entry in index:
        if not isinstance(entry, dict):
            raise ValueError("Invalid legacy chat metadata.")
        identity = entry.get("id")
        validate_identity(identity)
        name = legacy_name(identity) + ".json"
        if name in used_names or name in {"_index.json", "_deleted.json"} or identity in deleted:
            raise ValueError("Colliding/deleted legacy thread identity; explicit operator repair required.")
        used_names.add(name)
        path = folder / name
        if path.is_symlink() or path.resolve(strict=True).parent != folder.resolve(strict=True):
            raise ValueError("Legacy thread messages escape the reviewed directory.")
        messages = json.loads(path.read_text(encoding="utf-8"))
        validate_record(entry, messages)
        records.append({"id": identity, "entry": entry, "messages": messages, "revision": 1, "deleted": False})
    for identity in deleted:
        validate_identity(identity)
        records.append({"id": identity, "entry": {}, "messages": [], "revision": 1, "deleted": True})
    extra = {path.name for path in folder.glob("*.json")} - used_names - {
        "_index.json", "_deleted.json", "restore-complete.json",
    }
    if extra:
        raise ValueError("Unindexed legacy messages exist; reconcile ownership/index before migrating.")
    return write_backup(target, user_id, records)


def export_backup(store, target):
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        rows = connection.execute(
            "SELECT thread_id,entry,messages,revision,deleted FROM public.mammoth_chat_threads "
            "WHERE namespace=%s AND user_id=%s ORDER BY thread_id", (store.namespace, store.user_id),
        ).fetchall()
    records = [{"id": row[0], "entry": row[1], "messages": row[2], "revision": row[3], "deleted": row[4]}
               for row in rows]
    return write_backup(target, store.user_id, records)


def read_backup(source, user_id):
    manifest = json.loads((source / "manifest.json").read_text())
    raw = (source / "threads.json").read_bytes()
    if (manifest.get("contract") != CONTRACT or manifest.get("user_id") != user_id
            or hashlib.sha256(raw).hexdigest() != manifest.get("sha256")):
        raise ValueError("Chat backup contract/owner/checksum mismatch.")
    records = json.loads(raw)
    if not isinstance(records, list) or manifest.get("threads") != len(records):
        raise ValueError("Invalid chat backup record count.")
    identities, active = set(), 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid chat backup record.")
        identity = record.get("id")
        validate_identity(identity)
        if identity in identities or type(record.get("revision")) is not int or record["revision"] < 1:
            raise ValueError("Invalid/duplicate chat backup identity/revision.")
        identities.add(identity)
        if type(record.get("deleted")) is not bool:
            raise ValueError("Invalid chat deletion fence.")
        if record["deleted"]:
            if record.get("entry") != {} or record.get("messages") != []:
                raise ValueError("Deleted chat backup retains content.")
        else:
            validate_record(record.get("entry"), record.get("messages"))
            if record["entry"]["id"] != identity:
                raise ValueError("Chat metadata identity mismatch.")
            active += 1
    if active > MAX_THREADS:
        raise ValueError("Chat backup exceeds the active thread limit.")
    return records


def import_backup(store, source):
    records = read_backup(source, store.user_id)
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        existing = connection.execute(
            "SELECT 1 FROM public.mammoth_chat_threads WHERE namespace=%s AND user_id=%s LIMIT 1",
            (store.namespace, store.user_id),
        ).fetchone()
        if existing:
            raise ValueError("Destination already has chat records or deletion fences.")
        connection.execute(
            "INSERT INTO public.mammoth_chat_owners(namespace,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (store.namespace, store.user_id),
        )
        for record in records:
            connection.execute(
                "INSERT INTO public.mammoth_chat_threads(namespace,user_id,thread_id,entry,messages,revision,deleted) "
                "VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)",
                (store.namespace, store.user_id, record["id"], json.dumps(record["entry"]),
                 json.dumps(record["messages"]), record["revision"], record["deleted"]),
            )
    return len(records)


def restore_local(source, target, user_id):
    records = read_backup(source, user_id)
    names = [legacy_name(record["id"]) + ".json" for record in records]
    if len(set(names)) != len(names) or set(names) & {"_index.json", "_deleted.json"}:
        raise ValueError("Legacy filename normalization would collide; local rollback is unsafe.")
    target.mkdir(mode=0o700)
    index, deleted = [], {}
    for record, name in zip(records, names):
        if record["deleted"]:
            deleted[record["id"]] = True
        else:
            index.append(record["entry"])
            write_new(target / name, json.dumps(record["messages"], ensure_ascii=True).encode())
    write_new(target / "_index.json", json.dumps(index, ensure_ascii=True).encode())
    write_new(target / "_deleted.json", json.dumps(deleted).encode())
    write_new(target / "restore-complete.json", json.dumps({"contract": CONTRACT, "user_id": user_id}).encode())
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("local-export", "import", "export", "restore-local"))
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--namespace")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--local-dir", type=Path)
    parser.add_argument("--confirm-quiesced", action="store_true", required=True)
    parser.add_argument("--confirm-legacy-owner", action="store_true")
    args = parser.parse_args()
    if args.direction == "local-export":
        if args.local_dir is None or not args.confirm_legacy_owner:
            parser.error("local-export requires --local-dir and --confirm-legacy-owner after explicit ownership review")
        count = local_backup(args.local_dir, args.backup, args.user_id)["threads"]
    elif args.direction == "restore-local":
        if args.local_dir is None:
            parser.error("restore-local requires a new --local-dir")
        count = restore_local(args.backup, args.local_dir, args.user_id)
    else:
        store = PostgresChatThreads(os.environ.get("MAMMOTH_POSTGRES_DSN", ""), args.namespace, args.user_id)
        count = (import_backup(store, args.backup) if args.direction == "import"
                 else export_backup(store, args.backup)["threads"])
    print(json.dumps({"contract": CONTRACT, "direction": args.direction, "threads": count}))


if __name__ == "__main__":
    main()
