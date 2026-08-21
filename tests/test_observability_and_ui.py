import asyncio
import json

import api_server


def test_get_observability_runs_merges_tasks_and_plans(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_load_tasks",
        lambda: [
            {
                "id": "task-1",
                "title": "Coding run",
                "status": "completed",
                "description": "Implement UI contract",
                "created_at": "2026-08-03T20:00:00+00:00",
                "updated_at": "2026-08-03T20:01:00+00:00",
                "details": {
                    "source": "plan_execute",
                    "trace_id": "run-abc123",
                    "plan_profile": "coding",
                    "objective": "Implement UI contract",
                    "replay": {"approval_mode": True},
                },
            }
        ],
    )
    monkeypatch.setattr(
        api_server,
        "_load_atlas_state",
        lambda: {
            "plan_history": [
                {
                    "plan_id": "atlas-plan-1",
                    "objective": "Atlas objective",
                    "plan_profile": "atlas",
                    "plan_status": "pending_approval",
                    "trace_id": "atlas-trace-1",
                    "created_at": "2026-08-03T20:10:00+00:00",
                    "progress": {"total": 5, "executed": 4, "completed": 3, "pending_approval": 1, "failed": 0},
                    "synthesis": {"learner_summary": "Atlas summary"},
                }
            ]
        },
    )
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [{"id": "a1", "message": "hello", "created_at": "2026-08-03T20:02:00+00:00"}])
    monkeypatch.setattr(api_server, "_load_approvals", lambda: [{"id": "p1", "operation": "write_file"}])
    monkeypatch.setattr(api_server, "_load_snapshots", lambda: [{"id": "s1", "file_path": "src/App.jsx"}])

    result = asyncio.run(api_server.get_observability_runs())

    assert result["status"] == "ok"
    assert result["contract_version"] == "v2"
    assert result["summary"]["run_count"] == 2
    assert any(run["trace_id"] == "run-abc123" for run in result["runs"])
    assert any(run["source"] == "atlas_plan" for run in result["runs"])
    assert result["activities"][0]["message"] == "hello"
    assert result["approvals"][0]["operation"] == "write_file"


def test_get_active_ui_project_reports_active_path(monkeypatch, tmp_path):
    mammoth_dir = tmp_path / ".mammoth"
    mammoth_dir.mkdir()
    active_ui = tmp_path / "ui" / "command-center"
    active_ui.mkdir(parents=True)
    (mammoth_dir / "atlas_ui_state.json").write_text(
        json.dumps({"active_ui_project": str(active_ui)}),
        encoding="utf-8",
    )

    monkeypatch.setattr(api_server, "MAMMOTH_DIR", mammoth_dir)

    result = asyncio.run(api_server.get_active_ui_project())

    assert result["status"] == "ok"
    assert result["exists"] is True
    assert result["active_ui_project"] == str(active_ui.resolve())


def test_delete_approval_record_removes_pending_request(monkeypatch, tmp_path):
    mammoth_dir = tmp_path / ".mammoth"
    mammoth_dir.mkdir()
    approvals_file = mammoth_dir / "approvals.json"
    approvals_file.write_text(
        json.dumps([
            {"id": "approval-1", "status": "pending", "operation": "write_file", "target": "src/App.jsx"},
            {"id": "approval-2", "status": "pending", "operation": "write_file", "target": "src/Other.jsx"},
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(api_server, "MAMMOTH_DIR", mammoth_dir)

    result = api_server._delete_approval_record("approval-1")

    assert result["status"] == "ok"
    remaining = json.loads(approvals_file.read_text(encoding="utf-8"))
    assert [item["id"] for item in remaining] == ["approval-2"]
