import asyncio

import api_server


def test_get_autonomous_runs_merges_runtime_and_atlas_history(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_load_tasks",
        lambda: [
            {
                "id": "plan-abc123",
                "title": "plan+execute run",
                "status": "completed",
                "description": "Runtime objective",
                "created_at": "2026-08-03T20:00:00+00:00",
                "updated_at": "2026-08-03T20:02:00+00:00",
                "details": {
                    "objective": "Runtime objective",
                    "plan_profile": "autonomous",
                    "total": 6,
                    "executed": 6,
                    "completed": 6,
                    "pending_approval": 0,
                    "failed": 0,
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
                    "created_at": "2026-08-03T20:10:00+00:00",
                    "progress": {"total": 5, "executed": 4, "completed": 3, "pending_approval": 1, "failed": 0},
                }
            ]
        },
    )

    result = asyncio.run(api_server.get_autonomous_runs())

    assert result["status"] == "ok"
    assert result["contract_version"] == "v1"
    assert "autonomous" in result["profiles"]
    sources = {run["source"] for run in result["runs"]}
    assert "plan_execute" in sources
    assert "atlas_plan" in sources
    assert result["summary"]["total_runs"] == 2


def test_execute_approval_record_supports_non_coding_mutation_ops(monkeypatch):
    monkeypatch.setattr(api_server, "_apply_atlas_onboarding_update", lambda body: {"status": "ok", "kind": "onboard", "body": body})
    monkeypatch.setattr(api_server, "_apply_atlas_learner_reset", lambda: {"status": "ok", "kind": "learner_reset"})
    monkeypatch.setattr(api_server, "_apply_atlas_session_reset", lambda: {"status": "ok", "kind": "session_reset"})

    onboard_result = api_server._execute_approval_record(
        {"operation": "atlas_onboard_update", "payload": {"onboarding": {"experience_level": "beginner"}}}
    )
    learner_result = api_server._execute_approval_record({"operation": "atlas_learner_reset", "payload": {}})
    session_result = api_server._execute_approval_record({"operation": "atlas_session_reset", "payload": {}})

    assert onboard_result["kind"] == "onboard"
    assert learner_result["kind"] == "learner_reset"
    assert session_result["kind"] == "session_reset"

