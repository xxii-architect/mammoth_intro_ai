import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import backup_learner_source
from scripts.backup_learner_source import (
    backup_source, collect_source, restore_fresh, review_source_inventory, verify_backup,
)
from mammoth_os.learning_workspace import workspace_snapshot


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "atlas_state"
    root.mkdir()
    path = root / "atlas_state_tenant-a.json"
    state = {
        "active_account_id": "default",
        "accounts": {"default": {"profile": {"display_name": "A"}}, "second": {}},
        "account_sessions": {"default": {}, "second": {}},
        "learner_erasure": {"second": {"epoch": "a" * 32, "status": "pending"}},
        "unknown": {"preserve": "exactly"},
    }
    path.write_text(json.dumps(state), encoding="utf-8")
    snapshot = workspace_snapshot({"active_account_id": "default"})
    draft = {"exercise_key": snapshot["exercise_key"], "revision": 4,
             "values": snapshot["values"], "saved_at": "fixture", "extension": "preserve"}
    digest = hashlib.sha256(b"default").hexdigest()
    draft_path = root / f"{path.stem}_workspace_{digest}.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    owner = "tenant-a"
    key = hashlib.sha256(json.dumps([owner, "workspace:second"], ensure_ascii=True).encode()).hexdigest()
    model_path = root / "learner_models" / key / "atlas_learner_model.json"
    model_path.parent.mkdir(parents=True)
    model = {"user_id": "workspace:second", "mastery": {"x": 0.5},
             "unknown_extension": {"preserve": True}}
    model_path.write_text(json.dumps(model), encoding="utf-8")
    return path, state, draft_path, draft, model_path, model


def test_backup_preserves_source_fields_fences_and_checksum(source, tmp_path):
    path, state, draft_path, draft, model_path, model = source
    before = [item.read_bytes() for item in (path, draft_path, model_path)]
    target = tmp_path / "backup"
    manifest = backup_source(path, target, "tenant-a", confirm_quiesced=True)
    raw = (target / "learner.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["sha256"]
    assert json.loads(raw) == {"state": state, "drafts": {"default": draft}, "models": {"second": model}}
    assert json.loads((target / "manifest.json").read_bytes()) == manifest
    assert manifest["accounts"] == ["default", "second"]
    assert manifest["runtime_activation_supported"] is False
    assert manifest["orphan_models"] == "not_discoverable_without_operator_supplied_account_ids"
    assert verify_backup(target, "tenant-a") == manifest
    assert [item.read_bytes() for item in (path, draft_path, model_path)] == before


def test_unknown_draft_must_be_accounted_for_explicitly(source, tmp_path):
    path, _, draft_path, draft, _, _ = source
    extra = hashlib.sha256(b"removed").hexdigest()
    orphan = path.with_name(f"{path.stem}_workspace_{extra}.json")
    orphan.write_text(json.dumps(draft), encoding="utf-8")
    target = tmp_path / "backup"
    with pytest.raises(ValueError, match="Unidentified draft"):
        backup_source(path, target, "tenant-a", confirm_quiesced=True)
    assert not target.exists()
    bundle, accounts = collect_source(path, "tenant-a", ["removed"])
    assert "removed" in accounts and bundle["drafts"]["removed"] == draft


def test_reviewed_inventory_detects_orphan_models_without_claiming_ownership(source):
    path, _, _, _, model_path, model = source
    root = path.parent
    owner = "tenant-a"
    key = hashlib.sha256(json.dumps([owner, "workspace:removed"], ensure_ascii=True).encode()).hexdigest()
    orphan = root / "learner_models" / key
    orphan.mkdir()
    (orphan / "atlas_learner_model.json").write_text(
        json.dumps({**model, "user_id": "workspace:removed"}), encoding="utf-8")
    with pytest.raises(ValueError, match="quiescence"):
        review_source_inventory(root, {owner: ["removed"]})
    with pytest.raises(ValueError, match="Unidentified learner model"):
        review_source_inventory(root, {owner: []}, confirm_quiesced=True)
    review = review_source_inventory(root, {owner: ["removed"]}, confirm_quiesced=True)
    assert review["owners"] == {owner: ["default", "removed", "second"]}
    assert review["model_directories"] == 2 and review["state_files"] == 1
    assert review["ownership"] == "operator_supplied_not_verified"
    assert review["external_sources"] == "not_inventoried"
    assert review["runtime_activation_supported"] is False
    assert model_path.is_file()


def test_reviewed_inventory_requires_explicit_curriculum_classification(source):
    path, *_ = source
    name = "atlas_state_tenant-a_curricula.json"
    (path.parent / name).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unidentified"):
        review_source_inventory(path.parent, {"tenant-a": []}, confirm_quiesced=True)
    review = review_source_inventory(path.parent, {"tenant-a": []},
                                     reviewed_curricula=[name], confirm_quiesced=True)
    assert review["runtime_activation_supported"] is False
    with pytest.raises(ValueError, match="curriculum filenames"):
        review_source_inventory(path.parent, {"tenant-a": []},
                                reviewed_curricula=["atlas_state_other_curricula.json"], confirm_quiesced=True)


@pytest.mark.parametrize("damage", ["owner_collision", "missing_state", "unlisted_state", "unknown_model",
                                   "unknown_controls", "active_controls", "invalid_accounts"])
def test_reviewed_inventory_fails_closed_for_incomplete_or_ambiguous_sources(source, damage):
    path, *_ = source
    root = path.parent
    owners = {"tenant-a": []}
    if damage == "owner_collision":
        owners["TENANT-A"] = []
    elif damage == "missing_state":
        owners["tenant-b"] = []
    elif damage == "unlisted_state":
        (root / "atlas_state_other.json").write_text("{}", encoding="utf-8")
    elif damage == "unknown_model":
        (root / "learner_models" / "unknown").mkdir()
    elif damage == "unknown_controls":
        (root / "atlas_state_other_controls.sqlite3").write_bytes(b"fixture")
    elif damage == "active_controls":
        (root / "atlas_state_tenant-a_controls.sqlite3-wal").write_bytes(b"fixture")
    else:
        owners["tenant-a"] = [None]
    with pytest.raises(ValueError):
        review_source_inventory(root, owners, confirm_quiesced=True)


@pytest.mark.parametrize("kind", ["duplicate", "bad_fence", "wrong_model", "bad_draft", "extra_model"])
def test_invalid_sources_never_produce_a_backup(source, tmp_path, kind):
    path, state, draft_path, draft, model_path, model = source
    if kind == "duplicate":
        path.write_text('{"active_account_id":"default","active_account_id":"second"}', encoding="utf-8")
    elif kind == "bad_fence":
        state["learner_erasure"]["second"]["status"] = "unknown"
        path.write_text(json.dumps(state), encoding="utf-8")
    elif kind == "wrong_model":
        model["user_id"] = "workspace:other"
        model_path.write_text(json.dumps(model), encoding="utf-8")
    elif kind == "bad_draft":
        draft["revision"] = True
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
    else:
        (model_path.parent / "unknown.json").write_text("{}", encoding="utf-8")
    target = tmp_path / "backup"
    with pytest.raises(ValueError):
        backup_source(path, target, "tenant-a", confirm_quiesced=True)
    assert not target.exists()


def test_quiescence_and_owner_are_explicit_and_existing_destination_is_untouched(source, tmp_path):
    path, *_ = source
    target = tmp_path / "backup"
    with pytest.raises(ValueError, match="quiescence"):
        backup_source(path, target, "tenant-a")
    with pytest.raises(ValueError, match="filename"):
        backup_source(path, target, "tenant-b", confirm_quiesced=True)
    assert not target.exists()
    target.mkdir()
    sentinel = target / "keep"
    sentinel.write_text("unchanged", encoding="utf-8")
    with pytest.raises(FileExistsError):
        backup_source(path, target, "tenant-a", confirm_quiesced=True)
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_backup_verification_rejects_tampering_and_wrong_owner(source, tmp_path):
    path, *_ = source
    target = tmp_path / "backup"
    manifest = backup_source(path, target, "tenant-a", confirm_quiesced=True)
    with pytest.raises(ValueError, match="owner"):
        verify_backup(target, "tenant-b")
    payload_path = target / "learner.json"
    payload = json.loads(payload_path.read_bytes())
    payload["models"]["second"]["user_id"] = "workspace:other"
    raw = json.dumps(payload).encode()
    payload_path.write_bytes(raw)
    with pytest.raises(ValueError, match="checksum"):
        verify_backup(target, "tenant-a")
    manifest["sha256"] = hashlib.sha256(raw).hexdigest()
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid draft or model"):
        verify_backup(target, "tenant-a")


def test_failed_manifest_write_never_verifies_as_complete(source, tmp_path, monkeypatch):
    path, *_ = source
    target = tmp_path / "backup"
    original = backup_learner_source._write_new

    def fail_manifest(path, data):
        if path.name == "manifest.json":
            raise OSError("fixture disk failure")
        original(path, data)

    monkeypatch.setattr(backup_learner_source, "_write_new", fail_manifest)
    with pytest.raises(OSError, match="fixture disk failure"):
        backup_source(path, target, "tenant-a", confirm_quiesced=True)
    assert (target / "learner.json").is_file()
    assert not (target / "manifest.json").exists()
    with pytest.raises(ValueError):
        verify_backup(target, "tenant-a")


def test_fresh_restore_round_trips_records_and_refuses_existing_destination(source, tmp_path):
    path, state, _, draft, _, model = source
    target, restore = tmp_path / "backup", tmp_path / "restored"
    manifest = backup_source(path, target, "tenant-a", confirm_quiesced=True)
    receipt = restore_fresh(target, restore, "tenant-a")
    assert receipt["sha256"] == manifest["sha256"]
    assert receipt["runtime_activation_supported"] is False
    assert json.loads((restore / "restore-complete.json").read_bytes()) == receipt
    restored, accounts = collect_source(restore / path.name, "tenant-a", manifest["accounts"])
    assert restored == {"state": state, "drafts": {"default": draft}, "models": {"second": model}}
    assert accounts == manifest["accounts"]
    with pytest.raises(FileExistsError):
        restore_fresh(target, restore, "tenant-a")
    assert (restore / "restore-complete.json").is_file()


def test_incomplete_restore_has_no_success_marker(source, tmp_path, monkeypatch):
    path, *_ = source
    target, restore = tmp_path / "backup", tmp_path / "restored"
    backup_source(path, target, "tenant-a", confirm_quiesced=True)
    original = backup_learner_source._write_new

    def fail_draft(path, data):
        if "_workspace_" in path.name:
            raise OSError("fixture disk failure")
        original(path, data)

    monkeypatch.setattr(backup_learner_source, "_write_new", fail_draft)
    with pytest.raises(OSError, match="fixture disk failure"):
        restore_fresh(target, restore, "tenant-a")
    assert restore.is_dir()
    assert not (restore / "restore-complete.json").exists()


def test_offline_cli_backup_and_verify(source, tmp_path):
    path, *_ = source
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "backup_learner_source.py"
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    target = tmp_path / "cli-backup"
    common = ["--user-id", "tenant-a", "--backup", str(target)]
    backup = subprocess.run(
        [sys.executable, str(script), "backup", *common, "--state-file", str(path), "--confirm-quiesced"],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert backup.returncode == 0, backup.stderr
    verified = subprocess.run(
        [sys.executable, str(script), "verify", *common],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert verified.returncode == 0, verified.stderr
    assert "ownership and completeness are not established" in verified.stdout.lower()
    restored = subprocess.run(
        [sys.executable, str(script), "restore-fresh", *common, "--restore-dir", str(tmp_path / "restored")],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert restored.returncode == 0, restored.stderr
    assert (tmp_path / "restored" / "restore-complete.json").exists()


def test_offline_inventory_cli_requires_review_and_quiescence(source, tmp_path):
    path, *_ = source
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "backup_learner_source.py"
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    inventory = tmp_path / "reviewed-owners.json"
    inventory.write_text(json.dumps({"owners": {"tenant-a": []}, "reviewed_curricula": []}), encoding="utf-8")
    args = [sys.executable, str(script), "inventory", "--state-dir", str(path.parent),
            "--inventory-file", str(inventory)]
    unconfirmed = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert unconfirmed.returncode != 0
    assert "quiescence" in unconfirmed.stderr.lower()
    checked = subprocess.run(args + ["--confirm-quiesced"], env=env, capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    assert "ownership is operator-supplied" in checked.stdout.lower()
    assert "tenant-a" not in checked.stdout
