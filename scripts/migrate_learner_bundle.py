"""Rehearse learner bundle import/export on an isolated test database only."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from scripts.backup_learner_source import (
    _account, _decode, _owner_slug, _read_record, _validate_state, _validated_backup, _write_new, write_backup,
)
from scripts.migrate_runtime_storage import (
    CONTRACT as RUNTIME_CONTRACT, OPERATION_FIELDS, _export_snapshot_in_transaction, _import_snapshot_in_transaction,
    validate as validate_runtime_backup,
)
from mammoth_os.postgres import database
from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle, migration_lock
from mammoth_os.shared_state import StateConflict

CONTROLS_REHEARSAL_CONTRACT = "mammoth.learner-controls-rehearsal.v2"
FULL_REHEARSAL_CONTRACT = "mammoth.learner-runtime-rehearsal.v1"
BATCH_REHEARSAL_CONTRACT = "mammoth.learner-runtime-batch-rehearsal.v1"
_FULL_TABLES = (
    "mammoth_learner_bundles", "mammoth_learning_policy", "mammoth_learning_usage",
    "mammoth_learning_operations", "mammoth_learner_operation_fences", "mammoth_agent_runs",
    "mammoth_private_runtime_policy", "mammoth_private_runtime_attempts",
)


def _validate_rehearsal_controls(user_id, controls, *, require_fences=False):
    fields = {"daily_limit", "usage", "operations"}
    if require_fences:
        fields.add("fences")
    if (not isinstance(controls, dict) or set(controls) != fields
            or not isinstance(controls["usage"], list) or not isinstance(controls["operations"], list)
            or any(not isinstance(row, dict) or set(row) != {"day", "admitted"} for row in controls["usage"])
            or any(not isinstance(row, dict) or set(row) != set(OPERATION_FIELDS) for row in controls["operations"])):
        raise ValueError("A complete supported learning-controls snapshot is required; unknown fields need review.")
    wrapper = {"contract": RUNTIME_CONTRACT, "user_id": user_id, "daily_tokens": None,
               "runs": [], "attempts": [],
               "learning_controls": {key: controls[key] for key in ("daily_limit", "usage", "operations")}}
    try:
        validate_runtime_backup(wrapper, user_id)
    except (KeyError, TypeError) as exc:
        raise ValueError("The reviewed learning controls have an invalid or incomplete structure.") from exc
    if any(row["status"] in {"running", "cancellation_requested"} or row["finished_at"] is None
           for row in controls["operations"]):
        raise ValueError("Unfinished learning operations require reconciliation before migration.")
    fences = controls.get("fences", [])
    if not isinstance(fences, list):
        raise ValueError("Learning operation fences must be a list.")
    operations = {row["id"] for row in controls["operations"]}
    seen = set()
    for row in fences:
        if (not isinstance(row, dict) or set(row) != {"operation_id", "fence"}
                or not isinstance(row["operation_id"], str) or row["operation_id"] not in operations
                or row["operation_id"] in seen or not isinstance(row["fence"], dict)):
            raise ValueError("Learning operation fences are invalid or lack a matching operation.")
        seen.add(row["operation_id"])
    try:
        encoded = json.dumps(fences, ensure_ascii=True, allow_nan=False)
        if json.loads(encoded) != fences:
            raise ValueError("Learning operation fences are not stable JSON.")
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Learning operation fences must be valid JSON.") from exc
    return wrapper


def import_backup(store, source, *, confirm_quiesced=False):
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    _, bundle = _validated_backup(source, store.user_id)
    encoded = [json.dumps(bundle[key], ensure_ascii=True, allow_nan=False)
               for key in ("state", "drafts", "models")]
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        inserted = connection.execute(
            "INSERT INTO public.mammoth_learner_bundles(namespace,user_id,state,drafts,models,revision) "
            "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,1) "
            "ON CONFLICT(namespace,user_id) DO NOTHING RETURNING revision",
            (store.namespace, store.user_id, *encoded),
        ).fetchone()
        if inserted is None:
            raise StateConflict("Destination already has learner data; no import was performed.")
    return inserted[0]


def import_with_controls_rehearsal(store, source, runtime_backup, *, confirm_quiesced=False):
    """Test-only atomic import; callers must stop all learner and controls writers."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    _, bundle = _validated_backup(source, store.user_id)
    try:
        validate_runtime_backup(runtime_backup, store.user_id)
    except (KeyError, TypeError) as exc:
        raise ValueError("The reviewed runtime backup has an invalid or incomplete structure.") from exc
    controls = runtime_backup.get("learning_controls")
    _validate_rehearsal_controls(store.user_id, controls)
    return _import_learner_and_controls(store, bundle, controls)


def _import_learner_and_controls(store, bundle, controls):
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        _import_owner_in_transaction(connection, store, bundle, controls)
    return 1


def _import_owner_in_transaction(connection, store, bundle, controls):
    encoded = [json.dumps(bundle[key], ensure_ascii=True, allow_nan=False)
               for key in ("state", "drafts", "models")]
    for table in ("mammoth_learner_bundles", "mammoth_learning_policy",
                  "mammoth_learning_usage", "mammoth_learning_operations",
                  "mammoth_learner_operation_fences"):
        if connection.execute(
            f"SELECT 1 FROM public.{table} WHERE namespace=%s AND user_id=%s LIMIT 1",
            (store.namespace, store.user_id),
        ).fetchone():
            raise StateConflict("Destination owner already has learner or control data; no import was performed.")
    connection.execute(
        "INSERT INTO public.mammoth_learner_bundles(namespace,user_id,state,drafts,models,revision) "
        "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,1)",
        (store.namespace, store.user_id, *encoded),
    )
    connection.execute(
        "INSERT INTO public.mammoth_learning_policy(namespace,user_id,daily_limit) VALUES(%s,%s,%s)",
        (store.namespace, store.user_id, controls["daily_limit"]),
    )
    for row in controls["usage"]:
        connection.execute(
            "INSERT INTO public.mammoth_learning_usage(namespace,user_id,day,admitted) VALUES(%s,%s,%s,%s)",
            (store.namespace, store.user_id, row["day"], row["admitted"]),
        )
    for row in controls["operations"]:
        connection.execute(
            "INSERT INTO public.mammoth_learning_operations"
            "(namespace,user_id,id,route,account_id,status,started_at,finished_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (store.namespace, store.user_id, *(row[field] for field in OPERATION_FIELDS)),
        )
    for row in controls.get("fences", []):
        connection.execute(
            "INSERT INTO public.mammoth_learner_operation_fences(namespace,user_id,operation_id,fence) "
            "VALUES(%s,%s,%s,%s::jsonb)",
            (store.namespace, store.user_id, row["operation_id"],
             json.dumps(row["fence"], ensure_ascii=True, allow_nan=False)),
        )


def _prepare_reviewed_batch(store, sources, confirm_quiesced):
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    if not isinstance(sources, list) or not sources:
        raise ValueError("A nonempty reviewed owner backup list is required.")
    prepared = []
    seen = set()
    slugs = set()
    for entry in sources:
        if not isinstance(entry, tuple) or len(entry) != 3:
            raise ValueError("Each reviewed entry must contain owner, learner backup and runtime backup.")
        user_id, source, runtime = entry
        owner_store = PostgresLearnerBundle(store.dsn, store.namespace, user_id)
        if user_id in seen:
            raise ValueError("Duplicate reviewed owner; no import was performed.")
        seen.add(user_id)
        slug = _owner_slug(user_id)
        if slug in slugs:
            raise ValueError("Reviewed owners collide under local filename normalization; no import was performed.")
        slugs.add(slug)
        _, bundle = _validated_backup(source, user_id)
        runtime = deepcopy(runtime)
        try:
            validate_runtime_backup(runtime, user_id)
        except (KeyError, TypeError) as exc:
            raise ValueError("The reviewed runtime backup has an invalid or incomplete structure.") from exc
        controls = runtime.get("learning_controls")
        _validate_rehearsal_controls(user_id, controls)
        prepared.append((owner_store, bundle, controls, runtime))
    return sorted(prepared, key=lambda item: item[0].user_id)


def import_reviewed_batch_rehearsal(store, sources, *, confirm_quiesced=False):
    """Atomically rehearse a reviewed multi-owner learner/control import."""
    prepared = _prepare_reviewed_batch(store, sources, confirm_quiesced)
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        for owner_store, bundle, controls, _ in prepared:
            _import_owner_in_transaction(connection, owner_store, bundle, controls)
    return len(prepared)


def import_full_batch_rehearsal(store, sources, *, confirm_quiesced=False):
    """Rehearse one atomic learner, controls and runtime import on a test database."""
    prepared = _prepare_reviewed_batch(store, sources, confirm_quiesced)
    for _, _, _, runtime in prepared:
        if (set(runtime) != {"contract", "user_id", "daily_tokens", "runs", "attempts", "learning_controls"}
                or any(not isinstance(record, dict) or set(record) != {"payload", "cancellation_requested"}
                       for record in runtime["runs"])):
            raise ValueError("Unknown runtime backup fields require review; no import was performed.")
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        for owner_store, bundle, controls, runtime in prepared:
            _import_owner_in_transaction(connection, owner_store, bundle, controls)
            runtime_only = {key: value for key, value in runtime.items() if key != "learning_controls"}
            _import_snapshot_in_transaction(connection, store.namespace, owner_store.user_id, runtime_only)
    return len(prepared)


def export_full_rehearsal(store, target, extra_accounts=(), *, confirm_quiesced=False):
    """Test-only snapshot of learner, controls, runs and token usage for one owner."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    with database(store.dsn) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (migration_lock(store.namespace),))
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            bundle, controls = _read_learner_controls_in_transaction(connection, store)
            runtime = _export_snapshot_in_transaction(
                connection, store.namespace, store.user_id, include_learning_controls=False,
            )
    return _write_full_rehearsal(store.user_id, target, bundle, controls, runtime, extra_accounts)


def _write_full_rehearsal(user_id, target, bundle, controls, runtime, extra_accounts):
    accounts = _validate_state(bundle["state"])
    accounts.update(_account(account) for account in extra_accounts)
    accounts.update(_account(account) for account in bundle["drafts"])
    accounts.update(_account(account) for account in bundle["models"])
    target.mkdir(mode=0o700)
    manifest = write_backup(target / "learner", user_id, bundle, sorted(accounts))
    marker = {"contract": FULL_REHEARSAL_CONTRACT, "user_id": user_id,
              "learner_sha256": manifest["sha256"],
              "learner_manifest_sha256": hashlib.sha256((target / "learner" / "manifest.json").read_bytes()).hexdigest(),
              "runtime_activation_supported": False}
    for name, value in (("controls", controls), ("runtime", runtime)):
        payload = json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False).encode("utf-8")
        _write_new(target / f"{name}.json", payload)
        if _read_record(target / f"{name}.json") != value:
            raise ValueError("Rehearsal backup verification failed; no completion marker was produced.")
        marker[f"{name}_sha256"] = hashlib.sha256(payload).hexdigest()
    _validated_backup(target / "learner", user_id)
    _write_new(target / "complete.json", json.dumps(marker, sort_keys=True).encode("utf-8"))
    return marker


def import_full_rehearsal(store, source, *, confirm_quiesced=False):
    """Test-only restore to an empty owner; never activates the restored data."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    bundle, controls, runtime = _read_full_rehearsal(store.user_id, source)
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        _import_owner_in_transaction(connection, store, bundle, controls)
        _import_snapshot_in_transaction(connection, store.namespace, store.user_id, runtime)
    return 1


def _read_full_rehearsal(user_id, source):
    marker = _read_record(source / "complete.json")
    if (not isinstance(marker, dict) or set(marker) != {
            "contract", "user_id", "learner_sha256", "learner_manifest_sha256", "controls_sha256", "runtime_sha256",
            "runtime_activation_supported"} or marker["contract"] != FULL_REHEARSAL_CONTRACT
            or marker["user_id"] != user_id or marker["runtime_activation_supported"] is not False):
        raise ValueError("Full rehearsal backup marker or owner is invalid.")
    manifest, bundle = _validated_backup(source / "learner", user_id)
    if (manifest["sha256"] != marker["learner_sha256"]
            or hashlib.sha256((source / "learner" / "manifest.json").read_bytes()).hexdigest()
            != marker["learner_manifest_sha256"]):
        raise ValueError("Full rehearsal learner backup checksum mismatch.")
    values = {}
    for name in ("controls", "runtime"):
        path = source / f"{name}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("Full rehearsal backup payload is missing or not a regular file.")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != marker[f"{name}_sha256"]:
            raise ValueError("Full rehearsal backup checksum mismatch.")
        try:
            values[name] = _decode(raw)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Full rehearsal backup payload is invalid JSON.") from exc
    controls, runtime = values["controls"], values["runtime"]
    _validate_rehearsal_controls(user_id, controls, require_fences=True)
    if (not isinstance(runtime, dict)
            or set(runtime) != {"contract", "user_id", "daily_tokens", "runs", "attempts"}
            or not isinstance(runtime["runs"], list)
            or any(not isinstance(record, dict) or set(record) != {"payload", "cancellation_requested"}
                   for record in runtime["runs"])):
        raise ValueError("Unsupported runtime backup fields require review; no import was performed.")
    try:
        validate_runtime_backup(runtime, user_id)
    except (KeyError, TypeError) as exc:
        raise ValueError("Runtime backup has an invalid or incomplete structure.") from exc
    return bundle, controls, runtime


def export_full_namespace_rehearsal(store, target, reviewed_owners, *, confirm_quiesced=False):
    """Rehearse a complete reviewed namespace snapshot, not platform-wide backup."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    if not isinstance(reviewed_owners, dict) or not reviewed_owners:
        raise ValueError("A nonempty reviewed owner-to-account inventory is required.")
    owners = {}
    for user_id, accounts in reviewed_owners.items():
        owner_store = PostgresLearnerBundle(store.dsn, store.namespace, user_id)
        if not isinstance(accounts, list):
            raise ValueError("Each reviewed owner needs a list of distinct account IDs.")
        for account in accounts:
            _account(account)
        if len(accounts) != len(set(accounts)):
            raise ValueError("Each reviewed owner needs a list of distinct account IDs.")
        owners[user_id] = (owner_store, accounts[:])
    snapshots = []
    with database(store.dsn) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (migration_lock(store.namespace),))
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            for table in _FULL_TABLES:
                present = {row[0] for row in connection.execute(
                    f"SELECT DISTINCT user_id FROM public.{table} WHERE namespace=%s", (store.namespace,),
                ).fetchall()}
                if not present.issubset(owners):
                    raise ValueError("Unreviewed owner records exist in the source namespace; no backup was produced.")
            for user_id, (owner_store, accounts) in sorted(owners.items()):
                bundle, controls = _read_learner_controls_in_transaction(connection, owner_store)
                runtime = _export_snapshot_in_transaction(
                    connection, store.namespace, user_id, include_learning_controls=False,
                )
                snapshots.append((user_id, accounts, bundle, controls, runtime))
    target.mkdir(mode=0o700)
    entries = []
    for user_id, accounts, bundle, controls, runtime in snapshots:
        name = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        owner_path = target / name
        _write_full_rehearsal(user_id, owner_path, bundle, controls, runtime, accounts)
        _read_full_rehearsal(user_id, owner_path)
        entries.append({"user_id": user_id, "directory": name,
                        "marker_sha256": hashlib.sha256((owner_path / "complete.json").read_bytes()).hexdigest()})
    marker = {"contract": BATCH_REHEARSAL_CONTRACT, "source_namespace": store.namespace,
              "owners": entries, "runtime_activation_supported": False}
    _write_new(target / "complete.json", json.dumps(marker, ensure_ascii=True, sort_keys=True).encode("utf-8"))
    return marker


def import_full_namespace_rehearsal(store, source, *, confirm_quiesced=False):
    """Atomically restore a reviewed rehearsal into a fresh namespace."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Namespace rehearsal backup must be a regular directory.")
    marker = _read_record(source / "complete.json")
    if (not isinstance(marker, dict) or set(marker) != {
            "contract", "source_namespace", "owners", "runtime_activation_supported"}
            or marker["contract"] != BATCH_REHEARSAL_CONTRACT
            or marker["runtime_activation_supported"] is not False
            or not isinstance(marker["owners"], list) or not marker["owners"]
            or marker["source_namespace"] == store.namespace):
        raise ValueError("Namespace rehearsal marker is invalid or destination is not fresh.")
    PostgresLearnerBundle(store.dsn, marker["source_namespace"], store.user_id)
    prepared, seen = [], set()
    for entry in marker["owners"]:
        if not isinstance(entry, dict) or set(entry) != {"user_id", "directory", "marker_sha256"}:
            raise ValueError("Namespace rehearsal owner entry is invalid.")
        user_id = entry["user_id"]
        owner_store = PostgresLearnerBundle(store.dsn, store.namespace, user_id)
        directory = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        if (user_id in seen or entry["directory"] != directory
                or not isinstance(entry["marker_sha256"], str)):
            raise ValueError("Namespace rehearsal owner entry is invalid or duplicated.")
        seen.add(user_id)
        owner_path = source / directory
        if (owner_path.is_symlink() or not owner_path.is_dir()
                or (owner_path / "learner").is_symlink()):
            raise ValueError("Namespace rehearsal owner backup is missing or not a regular directory.")
        marker_path = owner_path / "complete.json"
        _read_record(marker_path)
        if hashlib.sha256(marker_path.read_bytes()).hexdigest() != entry["marker_sha256"]:
            raise ValueError("Namespace rehearsal owner marker checksum mismatch.")
        bundle, controls, runtime = _read_full_rehearsal(user_id, owner_path)
        prepared.append((owner_store, bundle, controls, runtime))
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        for table in _FULL_TABLES:
            if connection.execute(
                f"SELECT 1 FROM public.{table} WHERE namespace=%s LIMIT 1", (store.namespace,),
            ).fetchone():
                raise StateConflict("Destination namespace contains data; no restore was performed.")
        for owner_store, bundle, controls, runtime in sorted(prepared, key=lambda item: item[0].user_id):
            _import_owner_in_transaction(connection, owner_store, bundle, controls)
            _import_snapshot_in_transaction(connection, store.namespace, owner_store.user_id, runtime)
    return len(prepared)


def _read_learner_controls_in_transaction(connection, store):
    owner = (store.namespace, store.user_id)
    row = connection.execute(
        "SELECT state,drafts,models FROM public.mammoth_learner_bundles WHERE namespace=%s AND user_id=%s",
        owner,
    ).fetchone()
    policy = connection.execute(
        "SELECT daily_limit FROM public.mammoth_learning_policy WHERE namespace=%s AND user_id=%s", owner,
    ).fetchone()
    if row is None or policy is None:
        raise ValueError("Both learner bundle and learning controls must exist; no backup was produced.")
    bundle = {"state": row[0], "drafts": row[1], "models": row[2]}
    usage = connection.execute(
        "SELECT day::text,admitted FROM public.mammoth_learning_usage "
        "WHERE namespace=%s AND user_id=%s ORDER BY day", owner,
    ).fetchall()
    operations = connection.execute(
        "SELECT id,route,account_id,status,started_at,finished_at FROM public.mammoth_learning_operations "
        "WHERE namespace=%s AND user_id=%s ORDER BY started_at,id", owner,
    ).fetchall()
    fences = connection.execute(
        "SELECT operation_id,fence FROM public.mammoth_learner_operation_fences "
        "WHERE namespace=%s AND user_id=%s ORDER BY operation_id", owner,
    ).fetchall()
    controls = {"daily_limit": policy[0], "usage": [dict(zip(("day", "admitted"), item)) for item in usage],
                "operations": [dict(zip(OPERATION_FIELDS, item)) for item in operations],
                "fences": [dict(zip(("operation_id", "fence"), item)) for item in fences]}
    _validate_rehearsal_controls(store.user_id, controls, require_fences=True)
    return bundle, controls


def export_with_controls_rehearsal(store, target, extra_accounts=(), *, confirm_quiesced=False):
    """Test-only fresh backup of one quiesced bundle and its controls."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    with database(store.dsn) as connection:
        # A transaction-level lock query would establish the snapshot before waiting.
        connection.execute("SELECT pg_advisory_lock(%s)", (migration_lock(store.namespace),))
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            bundle, controls = _read_learner_controls_in_transaction(connection, store)
    accounts = _validate_state(bundle["state"])
    accounts.update(_account(account) for account in extra_accounts)
    accounts.update(_account(account) for account in bundle["drafts"])
    accounts.update(_account(account) for account in bundle["models"])
    target.mkdir(mode=0o700)
    learner_manifest = write_backup(target / "learner", store.user_id, bundle, sorted(accounts))
    payload = json.dumps(controls, ensure_ascii=True, sort_keys=True, allow_nan=False).encode("utf-8")
    _write_new(target / "controls.json", payload)
    marker = {"contract": CONTROLS_REHEARSAL_CONTRACT, "user_id": store.user_id,
              "learner_sha256": learner_manifest["sha256"],
              "controls_sha256": hashlib.sha256(payload).hexdigest(),
              "runtime_activation_supported": False}
    _validated_backup(target / "learner", store.user_id)
    if _decode((target / "controls.json").read_bytes()) != controls:
        raise ValueError("Rehearsal controls backup verification failed; no completion marker was produced.")
    _write_new(target / "complete.json", json.dumps(marker, sort_keys=True).encode("utf-8"))
    return marker


def import_combined_rehearsal(store, source, *, confirm_quiesced=False):
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    marker = _read_record(source / "complete.json")
    if (not isinstance(marker, dict) or set(marker) != {
            "contract", "user_id", "learner_sha256", "controls_sha256", "runtime_activation_supported"}
            or marker["contract"] != CONTROLS_REHEARSAL_CONTRACT or marker["user_id"] != store.user_id
            or marker["runtime_activation_supported"] is not False):
        raise ValueError("Rehearsal backup marker or owner is invalid.")
    manifest, bundle = _validated_backup(source / "learner", store.user_id)
    path = source / "controls.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Rehearsal controls are missing or not a regular file.")
    raw = path.read_bytes()
    if (manifest["sha256"] != marker["learner_sha256"]
            or hashlib.sha256(raw).hexdigest() != marker["controls_sha256"]):
        raise ValueError("Rehearsal backup checksum mismatch.")
    try:
        controls = _decode(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Rehearsal controls are invalid JSON.") from exc
    _validate_rehearsal_controls(store.user_id, controls, require_fences=True)
    return _import_learner_and_controls(store, bundle, controls)


def export_backup(store, target, extra_accounts=(), *, confirm_quiesced=False):
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence.")
    with database(store.dsn) as connection, connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (migration_lock(store.namespace),))
        row = connection.execute(
            "SELECT state,drafts,models FROM public.mammoth_learner_bundles "
            "WHERE namespace=%s AND user_id=%s",
            (store.namespace, store.user_id),
        ).fetchone()
        if row is None:
            raise ValueError("No learner bundle exists for this owner; no backup was produced.")
        bundle = {"state": row[0], "drafts": row[1], "models": row[2]}
    accounts = _validate_state(bundle["state"])
    accounts.update(_account(account) for account in extra_accounts)
    accounts.update(_account(account) for account in bundle["drafts"])
    accounts.update(_account(account) for account in bundle["models"])
    return write_backup(target, store.user_id, bundle, sorted(accounts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("import", "export"))
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--account-id", action="append", default=[])
    parser.add_argument("--confirm-quiesced", action="store_true")
    parser.add_argument("--confirm-test-only", action="store_true")
    args = parser.parse_args()
    if not args.confirm_test_only:
        parser.error("This experimental tool is for isolated test databases only; pass --confirm-test-only.")
    if args.direction == "import" and args.account_id:
        parser.error("Account IDs are taken from the reviewed backup during import.")
    store = PostgresLearnerBundle(os.environ.get("MAMMOTH_POSTGRES_DSN"), args.namespace, args.user_id)
    if args.direction == "import":
        import_backup(store, args.backup, confirm_quiesced=args.confirm_quiesced)
    else:
        export_backup(store, args.backup, args.account_id, confirm_quiesced=args.confirm_quiesced)
    print("Test operation completed. Runtime activation and production use are not supported.")


if __name__ == "__main__":
    main()
