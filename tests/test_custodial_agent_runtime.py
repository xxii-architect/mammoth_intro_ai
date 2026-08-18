import asyncio
from pathlib import Path

from mammoth_os.agents.custodial_agent import CustodialAgent


def test_custodial_agent_reports_cleanup_candidates(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__" / "module.pyc").write_bytes(b"cached")
    (workspace / "keep.txt").write_text("keep", encoding="utf-8")

    agent = CustodialAgent(router=None, storage_root=str(tmp_path / "state"))
    report = asyncio.run(agent.execute_action("inspect", target=str(workspace), details={}))

    assert report["status"] == "ok"
    assert report["report"]["candidate_count"] == 2
    assert "keep.txt" not in report["report"]["file_candidates"]


def test_custodial_agent_requires_approval_for_cleanup(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".pytest_cache").mkdir()
    (workspace / ".pytest_cache" / "cache.log").write_text("cache", encoding="utf-8")

    agent = CustodialAgent(router=None, storage_root=str(tmp_path / "state"))
    blocked = asyncio.run(agent.execute_action("cleanup", target=str(workspace), details={"dry_run": False}))

    assert blocked["status"] == "pending_approval"
    assert (workspace / ".pytest_cache" / "cache.log").exists()


def test_custodial_agent_cleanup_and_restore_round_trip(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "__pycache__").mkdir()
    tracked_file = workspace / "__pycache__" / "module.pyc"
    tracked_file.write_bytes(b"compiled-bytes")
    other_file = workspace / "notes.log"
    other_file.write_text("temporary note", encoding="utf-8")

    agent = CustodialAgent(router=None, storage_root=str(tmp_path / "state"))
    cleanup = asyncio.run(
        agent.execute_action(
            "cleanup",
            target=str(workspace),
            details={"approved": True, "label": "test cleanup"},
        )
    )

    assert cleanup["status"] == "ok"
    assert sorted(cleanup["removed_files"]) == ["__pycache__/module.pyc", "notes.log"]
    assert not tracked_file.exists()
    assert not other_file.exists()

    snapshot_id = cleanup["snapshot_id"]
    restored = asyncio.run(
        agent.execute_action(
            "restore",
            target=str(workspace),
            details={"approved": True, "snapshot_id": snapshot_id},
        )
    )

    assert restored["status"] == "ok"
    assert (workspace / "__pycache__" / "module.pyc").read_bytes() == b"compiled-bytes"
    assert (workspace / "notes.log").read_text(encoding="utf-8") == "temporary note"
