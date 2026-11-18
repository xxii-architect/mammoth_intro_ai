"""Create a reviewed, offline learner-source backup; does not activate or import it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from mammoth_os.learner_model import LearnerStorageError, validate_saved_learner_model
from mammoth_os.learning_workspace import WorkspaceStorageError, validate_workspace_record


CONTRACT = "mammoth.learner-source-backup.v1"


def _decode(raw):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key.")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON value.")

    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def _read_record(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular, non-symlink file: {path.name}")
    try:
        return _decode(path.read_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError(f"Source record is unreadable or invalid: {path.name}") from exc


def _account(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError("Account identifiers must be explicit canonical workspace account IDs.")
    return value


def _validate_state(state):
    if not isinstance(state, dict):
        raise ValueError("Learner state must be an object.")
    accounts = set()
    for field in ("accounts", "account_sessions"):
        collection = state.get(field, {})
        if not isinstance(collection, dict) or any(not isinstance(value, dict) for value in collection.values()):
            raise ValueError(f"Invalid {field} collection.")
        accounts.update(_account(key) for key in collection)
    if any("profile" in entry and not isinstance(entry["profile"], dict)
           for entry in state.get("accounts", {}).values()):
        raise ValueError("Invalid account profile.")
    active = state.get("active_account_id") or state.get("current_account_id") or "default"
    accounts.add(_account(active))
    records = state.get("learner_erasure", {})
    if not isinstance(records, dict):
        raise ValueError("Invalid learner erasure records.")
    for account, record in records.items():
        accounts.add(_account(account))
        if (not isinstance(record, dict) or set(record) != {"epoch", "status"}
                or not isinstance(record["epoch"], str) or not re.fullmatch(r"[a-f0-9]{32}", record["epoch"])
                or record["status"] not in ("pending", "complete")):
            raise ValueError("Invalid learner erasure fence.")
    return accounts


def _validate_owner(user_id):
    if (not isinstance(user_id, str) or not 1 <= len(user_id) <= 256
            or user_id in {"anonymous", "local"} or any(ord(char) < 32 for char in user_id)):
        raise ValueError("An explicit authenticated owner is required.")


def _owner_slug(user_id):
    _validate_owner(user_id)
    slug = re.sub(r"[^a-z0-9_-]+", "-", user_id.strip().lower()).strip("-")
    if not slug:
        raise ValueError("A reviewed owner has no usable local storage key.")
    return slug


def collect_source(state_path, user_id, extra_accounts=()):
    slug = _owner_slug(user_id)
    if state_path.name != f"atlas_state_{slug}.json":
        raise ValueError("State filename does not match the reviewed owner.")
    state = _read_record(state_path)
    accounts = _validate_state(state)
    accounts.update(_account(account) for account in extra_accounts)
    drafts, models = {}, {}
    expected_drafts = set()
    for account in sorted(accounts):
        digest = hashlib.sha256(account.encode("utf-8")).hexdigest()
        draft_path = state_path.with_name(f"{state_path.stem}_workspace_{digest}.json")
        expected_drafts.add(draft_path.name)
        if draft_path.exists() or draft_path.is_symlink():
            draft = _read_record(draft_path)
            try:
                validate_workspace_record(draft)
            except WorkspaceStorageError as exc:
                raise ValueError(f"Invalid saved draft for account {account}.") from exc
            drafts[account] = draft
        scope = hashlib.sha256(json.dumps([user_id, f"workspace:{account}"],
                                           ensure_ascii=True).encode("utf-8")).hexdigest()
        model_dir = state_path.parent / "learner_models" / scope
        model_path = model_dir / "atlas_learner_model.json"
        if model_dir.is_symlink() or model_dir.parent.is_symlink():
            raise ValueError("Learner model directory must not be a symlink.")
        if model_dir.exists():
            if not model_dir.is_dir() or any(
                path.name not in {"atlas_learner_model.json", "atlas_learner_model.lock"}
                or path.is_symlink() or not path.is_file()
                for path in model_dir.iterdir()
            ):
                raise ValueError("Unrecognized model files require operator review before backup.")
        if model_path.exists() or model_path.is_symlink():
            model = _read_record(model_path)
            try:
                validate_saved_learner_model(model, f"workspace:{account}")
            except LearnerStorageError as exc:
                raise ValueError(f"Invalid saved model for account {account}.") from exc
            models[account] = model
    unknown_drafts = {path.name for path in state_path.parent.glob(f"{state_path.stem}_workspace_*.json")} - expected_drafts
    if unknown_drafts:
        raise ValueError("Unidentified draft files exist; review and provide their account IDs before backup.")
    return {"state": state, "drafts": drafts, "models": models}, sorted(accounts)


def review_source_inventory(root, owners, *, reviewed_curricula=(), confirm_quiesced=False):
    """Check a reviewed owner/account inventory against one local learner root."""
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence before inventory.")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("A regular, explicitly reviewed learner-state directory is required.")
    if not isinstance(owners, dict) or not owners:
        raise ValueError("A nonempty reviewed owner-to-account inventory is required.")
    state_paths, drafts, model_scopes, controls, curricula = {}, set(), {}, set(), set()
    accounts_by_owner = {}
    for owner, supplied in owners.items():
        _validate_owner(owner)
        if not isinstance(supplied, list):
            raise ValueError("Each reviewed owner needs a list of distinct account IDs.")
        for account in supplied:
            _account(account)
        if len(set(supplied)) != len(supplied):
            raise ValueError("Each reviewed owner needs a list of distinct account IDs.")
        slug = _owner_slug(owner)
        filename = f"atlas_state_{slug}.json"
        if filename in state_paths:
            raise ValueError("Reviewed owners collide under local filename normalization.")
        state_paths[filename] = owner
        _, accounts = collect_source(root / filename, owner, supplied)
        accounts_by_owner[owner] = accounts
        stem = f"atlas_state_{slug}"
        controls.add(f"{stem}_controls.sqlite3")
        curricula.add(f"{stem}_curricula.json")
        for account in accounts:
            digest = hashlib.sha256(account.encode("utf-8")).hexdigest()
            drafts.add(f"{stem}_workspace_{digest}.json")
            scope = hashlib.sha256(json.dumps([owner, f"workspace:{account}"],
                                                ensure_ascii=True).encode("utf-8")).hexdigest()
            if scope in model_scopes:
                raise ValueError("Reviewed learner-model identities collide.")
            model_scopes[scope] = (owner, account)
    if set(state_paths) & (drafts | curricula):
        raise ValueError("An owner state filename collides with a draft or curriculum filename.")
    if (not isinstance(reviewed_curricula, (list, tuple))
            or any(not isinstance(name, str) or name not in curricula for name in reviewed_curricula)
            or len(set(reviewed_curricula)) != len(reviewed_curricula)):
        raise ValueError("Reviewed curriculum filenames must be distinct and belong to listed owners.")
    allowed_json = set(state_paths) | drafts | set(reviewed_curricula)
    for path in root.glob("atlas_state_*.json"):
        if path.name not in allowed_json:
            raise ValueError("Unidentified learner state, draft or curriculum file requires review.")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Learner inventory files must be regular files, not symlinks.")
    for path in root.glob("atlas_state_*_controls.sqlite3*"):
        if path.name not in controls or path.is_symlink() or not path.is_file():
            raise ValueError("Unidentified or active learning-controls files require review.")
    model_root = root / "learner_models"
    if model_root.is_symlink() or (model_root.exists() and not model_root.is_dir()):
        raise ValueError("Learner model root must be a regular directory, not a symlink.")
    if model_root.exists():
        for path in model_root.iterdir():
            if path.name not in model_scopes or path.is_symlink() or not path.is_dir():
                raise ValueError("Unidentified learner model directory or file requires review.")
    return {
        "contract": "mammoth.learner-source-inventory-review.v1",
        "owners": accounts_by_owner,
        "state_files": len(state_paths),
        "model_directories": sum((model_root / scope).is_dir() for scope in model_scopes),
        "controls_files": sum((root / name).is_file() for name in controls),
        "ownership": "operator_supplied_not_verified",
        "external_sources": "not_inventoried",
        "runtime_activation_supported": False,
    }


def _write_new(path, data):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def backup_source(state_path, target, user_id, extra_accounts=(), *, confirm_quiesced=False):
    if not confirm_quiesced:
        raise ValueError("Stop all writers and explicitly confirm quiescence before backup.")
    bundle, accounts = collect_source(state_path, user_id, extra_accounts)
    return write_backup(target, user_id, bundle, accounts)


def _validate_records(bundle, accounts):
    if (not isinstance(accounts, list) or any(_account(account) != account for account in accounts)
            or sorted(set(accounts)) != accounts
            or not isinstance(bundle, dict) or set(bundle) != {"state", "drafts", "models"}
            or not isinstance(bundle["drafts"], dict) or not isinstance(bundle["models"], dict)
            or not _validate_state(bundle["state"]).issubset(accounts)
            or not set(bundle["drafts"]).issubset(accounts) or not set(bundle["models"]).issubset(accounts)):
        raise ValueError("Learner backup accounts or bundle shape are invalid.")
    try:
        for draft in bundle["drafts"].values():
            validate_workspace_record(draft)
        for account, model in bundle["models"].items():
            validate_saved_learner_model(model, f"workspace:{account}")
    except (WorkspaceStorageError, LearnerStorageError) as exc:
        raise ValueError("Learner backup contains an invalid draft or model.") from exc


def write_backup(target, user_id, bundle, accounts):
    _validate_owner(user_id)
    _validate_records(bundle, accounts)
    payload = json.dumps(bundle, ensure_ascii=True, sort_keys=True, allow_nan=False).encode("utf-8")
    manifest = {
        "contract": CONTRACT, "user_id": user_id, "accounts": accounts,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "ownership": "operator_reviewed_not_proven_by_filename",
        "orphan_models": "not_discoverable_without_operator_supplied_account_ids",
        "runtime_activation_supported": False,
    }
    target.mkdir(mode=0o700)
    _write_new(target / "learner.json", payload)
    _write_new(target / "manifest.json", json.dumps(manifest, sort_keys=True).encode("utf-8"))
    return manifest


def _validated_backup(target, user_id):
    _validate_owner(user_id)
    manifest_path, payload_path = target / "manifest.json", target / "learner.json"
    manifest = _read_record(manifest_path)
    if (not isinstance(manifest, dict)
            or set(manifest) != {"contract", "user_id", "accounts", "sha256", "ownership",
                                 "orphan_models", "runtime_activation_supported"}
            or manifest["contract"] != CONTRACT or manifest["user_id"] != user_id
            or manifest["ownership"] != "operator_reviewed_not_proven_by_filename"
            or manifest["orphan_models"] != "not_discoverable_without_operator_supplied_account_ids"
            or manifest["runtime_activation_supported"] is not False):
        raise ValueError("Learner backup manifest or owner is invalid.")
    if payload_path.is_symlink() or not payload_path.is_file():
        raise ValueError("Learner backup payload is missing or not a regular file.")
    raw = payload_path.read_bytes()
    if (not isinstance(manifest["sha256"], str)
            or hashlib.sha256(raw).hexdigest() != manifest["sha256"]):
        raise ValueError("Learner backup checksum mismatch.")
    try:
        bundle = _decode(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Learner backup payload is invalid JSON.") from exc
    _validate_records(bundle, manifest["accounts"])
    return manifest, bundle


def verify_backup(target, user_id):
    return _validated_backup(target, user_id)[0]


def restore_fresh(backup, target, user_id):
    manifest, bundle = _validated_backup(backup, user_id)
    slug = _owner_slug(user_id)
    target.mkdir(mode=0o700)
    state_path = target / f"atlas_state_{slug}.json"

    def write_json(path, value):
        _write_new(path, json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False).encode("utf-8"))

    write_json(state_path, bundle["state"])
    for account, draft in bundle["drafts"].items():
        digest = hashlib.sha256(account.encode("utf-8")).hexdigest()
        write_json(target / f"{state_path.stem}_workspace_{digest}.json", draft)
    for account, model in bundle["models"].items():
        scope = hashlib.sha256(json.dumps([user_id, f"workspace:{account}"],
                                           ensure_ascii=True).encode("utf-8")).hexdigest()
        model_dir = target / "learner_models" / scope
        model_dir.mkdir(mode=0o700, parents=True)
        write_json(model_dir / "atlas_learner_model.json", model)
    restored, accounts = collect_source(state_path, user_id, manifest["accounts"])
    if restored != bundle or accounts != manifest["accounts"]:
        raise ValueError("Restored learner source did not match the reviewed backup.")
    receipt = {"contract": CONTRACT, "user_id": user_id, "sha256": manifest["sha256"],
               "runtime_activation_supported": False}
    write_json(target / "restore-complete.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("backup", "verify", "restore-fresh", "inventory"))
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--inventory-file", type=Path)
    parser.add_argument("--user-id")
    parser.add_argument("--account-id", action="append", default=[])
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--restore-dir", type=Path)
    parser.add_argument("--confirm-quiesced", action="store_true")
    args = parser.parse_args()
    if args.direction == "inventory":
        if (args.state_dir is None or args.inventory_file is None or args.state_file is not None
                or args.user_id is not None or args.backup is not None or args.restore_dir is not None
                or args.account_id):
            parser.error("Inventory requires --state-dir and --inventory-file only, plus --confirm-quiesced.")
        inventory = _read_record(args.inventory_file)
        if (not isinstance(inventory, dict) or set(inventory) != {"owners", "reviewed_curricula"}):
            raise ValueError("Inventory must contain only owners and reviewed_curricula.")
        review = review_source_inventory(args.state_dir, inventory["owners"],
                                         reviewed_curricula=inventory["reviewed_curricula"],
                                         confirm_quiesced=args.confirm_quiesced)
        print(f"Reviewed {review['state_files']} state files and {review['model_directories']} model directories. "
              "Ownership is operator-supplied; external sources and production activation remain unverified.")
        return
    if args.user_id is None or args.backup is None or args.state_dir is not None or args.inventory_file is not None:
        parser.error("Backup, verification and restore require --user-id and --backup; inventory options are not accepted.")
    if args.direction == "backup":
        if args.state_file is None or args.restore_dir is not None:
            parser.error("Backup requires --state-file and does not accept --restore-dir.")
        backup_source(args.state_file, args.backup, args.user_id, args.account_id,
                      confirm_quiesced=args.confirm_quiesced)
        print("Source backup created. Ownership and orphan-model completeness require operator review; activation is not supported.")
    elif args.direction == "verify":
        if args.state_file is not None or args.account_id or args.confirm_quiesced or args.restore_dir is not None:
            parser.error("Verification does not accept source or quiescence options.")
        verify_backup(args.backup, args.user_id)
        print("Backup checksum and record shapes verified. Ownership and completeness are not established.")
    else:
        if args.restore_dir is None or args.state_file is not None or args.account_id or args.confirm_quiesced:
            parser.error("Fresh restore requires --restore-dir and does not accept source or quiescence options.")
        restore_fresh(args.backup, args.restore_dir, args.user_id)
        print("Fresh restore verified. Ownership and completeness are not established; activation is not supported.")


if __name__ == "__main__":
    main()
