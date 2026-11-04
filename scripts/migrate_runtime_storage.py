"""Quiesced per-owner runtime backups/imports. Never overwrite destination state."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing

from mammoth_os.agent_loop.runner import AgentRun, RUN_ID_RE
from mammoth_os.postgres import database

CONTRACT = "mammoth.runtime-storage-backup.v1"
ATTEMPT_FIELDS = ("id", "day", "provider", "model", "started_at", "finished_at", "reserved", "reported", "status")


def local_snapshot(user_id, runs_dir, ledger_file):
    runs = []
    if not runs_dir.is_dir() or not ledger_file.is_file():
        raise ValueError("Both reviewed local source paths must exist; missing data is not an empty backup.")
    for path in sorted(runs_dir.glob("run-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("user_id") != user_id or payload.get("id") != path.stem:
            raise ValueError("Local run identity/owner does not match the reviewed source.")
        payload["storage_revision"] = max(1, payload.get("storage_revision", 0))
        runs.append({"payload": payload, "cancellation_requested": path.with_suffix(".cancel").exists()})
    with closing(sqlite3.connect(ledger_file.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        policy = connection.execute("SELECT daily_tokens FROM policy WHERE id=1").fetchone()
        if policy is None:
            raise ValueError("Local usage policy is missing; operator repair is required.")
        attempts = [dict(row) for row in connection.execute("SELECT * FROM attempts ORDER BY started_at,id")]
    snapshot = {"contract": CONTRACT, "user_id": user_id, "runs": runs,
                "daily_tokens": policy[0], "attempts": attempts}
    validate(snapshot, user_id)
    return snapshot


def validate(snapshot, user_id):
    if (not isinstance(snapshot, dict) or snapshot.get("contract") != CONTRACT
            or snapshot.get("user_id") != user_id or not isinstance(user_id, str)
            or not 1 <= len(user_id) <= 256):
        raise ValueError("Backup contract/owner does not match the explicit target.")
    limit = snapshot["daily_tokens"]
    if limit is not None and (type(limit) is not int or not 0 <= limit <= 100_000_000):
        raise ValueError("Invalid daily ceiling in backup.")
    seen = set()
    for record in snapshot["runs"]:
        payload = record["payload"]
        run = AgentRun.from_dict(payload)
        if (not RUN_ID_RE.fullmatch(run.id) or run.user_id != user_id or run.id in seen
                or type(run.storage_revision) is not int or run.storage_revision < 1
                or type(record["cancellation_requested"]) is not bool):
            raise ValueError("Invalid or duplicate run identity/revision/cancellation.")
        datetime.fromisoformat(run.updated_at)
        seen.add(run.id)
    seen.clear()
    for attempt in snapshot["attempts"]:
        if (set(attempt) != set(ATTEMPT_FIELDS) or not isinstance(attempt["id"], str)
                or not attempt["id"] or attempt["id"] in seen
                or type(attempt["reserved"]) is not int or attempt["reserved"] < 1
                or attempt["reported"] is not None and (type(attempt["reported"]) is not int or attempt["reported"] < 0)
                or attempt["status"] not in {"pending", "completed", "completed_unknown", "failed_unknown"}):
            raise ValueError("Invalid or duplicate usage reservation.")
        for field in ("day", "started_at"):
            datetime.fromisoformat(attempt[field])
        if attempt["finished_at"] is not None:
            datetime.fromisoformat(attempt["finished_at"])
        seen.add(attempt["id"])


def import_snapshot(dsn, namespace, user_id, snapshot):
    validate(snapshot, user_id)
    with database(dsn) as connection, connection.transaction():
        from psycopg.types.json import Jsonb

        for table in ("mammoth_agent_runs", "mammoth_private_runtime_policy", "mammoth_private_runtime_attempts"):
            if connection.execute(
                f"SELECT 1 FROM public.{table} WHERE namespace=%s AND user_id=%s LIMIT 1", (namespace, user_id),
            ).fetchone():
                raise ValueError("Import refused: destination owner already has state. Nothing was overwritten.")
        connection.execute(
            "INSERT INTO public.mammoth_private_runtime_policy VALUES(%s,%s,%s)",
            (namespace, user_id, snapshot["daily_tokens"]),
        )
        for record in snapshot["runs"]:
            payload = record["payload"]
            connection.execute(
                "INSERT INTO public.mammoth_agent_runs(namespace,user_id,id,revision,payload,cancellation_requested,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (namespace, user_id, payload["id"], payload["storage_revision"], Jsonb(payload),
                 record["cancellation_requested"], payload["updated_at"]),
            )
        for attempt in snapshot["attempts"]:
            connection.execute(
                "INSERT INTO public.mammoth_private_runtime_attempts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (namespace, user_id, *(attempt[field] for field in ATTEMPT_FIELDS)),
            )


def export_snapshot(dsn, namespace, user_id):
    with database(dsn) as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        policy = connection.execute(
            "SELECT daily_tokens FROM public.mammoth_private_runtime_policy WHERE namespace=%s AND user_id=%s",
            (namespace, user_id),
        ).fetchone()
        if policy is None:
            raise ValueError("Export refused: owner usage policy is missing.")
        runs = connection.execute(
            "SELECT payload,cancellation_requested FROM public.mammoth_agent_runs "
            "WHERE namespace=%s AND user_id=%s ORDER BY id", (namespace, user_id),
        ).fetchall()
        attempts = connection.execute(
            "SELECT id,day,provider,model,started_at,finished_at,reserved,reported,status "
            "FROM public.mammoth_private_runtime_attempts WHERE namespace=%s AND user_id=%s ORDER BY started_at,id",
            (namespace, user_id),
        ).fetchall()
    snapshot = {"contract": CONTRACT, "user_id": user_id, "daily_tokens": policy[0],
                "runs": [{"payload": row[0], "cancellation_requested": row[1]} for row in runs],
                "attempts": [dict(zip(ATTEMPT_FIELDS, row)) for row in attempts]}
    validate(snapshot, user_id)
    return snapshot


def write_backup(path, snapshot):
    content = json.dumps(snapshot, ensure_ascii=False, indent=2)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def restore_local(user_id, runs_dir, ledger_file, snapshot):
    from mammoth_os.runtime_ledger import RuntimeLedger

    validate(snapshot, user_id)
    if runs_dir.exists() or ledger_file.exists():
        raise ValueError("Restore requires new output paths; existing private state is never overwritten.")
    runs_dir.mkdir(mode=0o700)
    with os.fdopen(os.open(ledger_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"):
        pass
    with RuntimeLedger(ledger_file)._db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE policy SET daily_tokens=? WHERE id=1", (snapshot["daily_tokens"],))
        for attempt in snapshot["attempts"]:
            connection.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?)", tuple(attempt[field] for field in ATTEMPT_FIELDS),
            )
    for record in snapshot["runs"]:
        path = runs_dir / f"{record['payload']['id']}.json"
        write_backup(path, record["payload"])
        if record["cancellation_requested"]:
            with os.fdopen(os.open(path.with_suffix(".cancel"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("local-export", "restore-local", "import", "export"))
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--file", type=Path, required=True, help="Private backup JSON; output refuses existing files.")
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--ledger-file", type=Path)
    parser.add_argument("--confirm-quiesced", action="store_true")
    args = parser.parse_args()
    if not args.confirm_quiesced:
        parser.error("Stop all runtime writers and explicitly confirm --confirm-quiesced.")
    if args.direction in {"local-export", "restore-local"}:
        if args.runs_dir is None or args.ledger_file is None:
            parser.error("Explicit reviewed --runs-dir and --ledger-file are required.")
        if args.direction == "local-export":
            snapshot = local_snapshot(args.user_id, args.runs_dir, args.ledger_file)
            write_backup(args.file, snapshot)
        else:
            restore_local(args.user_id, args.runs_dir, args.ledger_file, json.loads(args.file.read_text(encoding="utf-8")))
    else:
        namespace, dsn = os.getenv("MAMMOTH_STATE_NAMESPACE"), os.getenv("MAMMOTH_POSTGRES_DSN")
        if not namespace or not dsn or os.getenv("MAMMOTH_POSTGRES_SESSION_MODE") != "direct":
            parser.error("Explicit namespace, private database DSN and direct/session mode are required.")
        if args.direction == "import":
            import_snapshot(dsn, namespace, args.user_id, json.loads(args.file.read_text(encoding="utf-8")))
        else:
            write_backup(args.file, export_snapshot(dsn, namespace, args.user_id))
    print("Runtime storage operation completed. Retain private backups; no destination state was overwritten.")


if __name__ == "__main__":
    main()
