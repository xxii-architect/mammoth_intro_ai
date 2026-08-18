import asyncio
from pathlib import Path

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


def test_get_autonomous_runs_exposes_lane_and_replay_details(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_load_tasks",
        lambda: [
            {
                "id": "plan-xyz",
                "title": "plan+execute run",
                "status": "pending_approval",
                "description": "Ship the release update",
                "created_at": "2026-08-03T20:00:00+00:00",
                "updated_at": "2026-08-03T20:02:00+00:00",
                "details": {
                    "objective": "Ship the release update",
                    "plan_profile": "coding",
                    "coding_intent": "patch_existing",
                    "total": 4,
                    "executed": 3,
                    "completed": 2,
                    "pending_approval": 1,
                    "failed": 0,
                    "current_lane": {
                        "step_id": "coding-step",
                        "title": "Patch the release notes",
                        "agent_id": "coding_agent",
                        "status": "pending_approval",
                    },
                    "approvals_needed": [
                        {
                            "step_id": "coding-step",
                            "title": "Patch the release notes",
                            "agent_id": "coding_agent",
                            "operation": "write_file",
                        }
                    ],
                    "approvals_needed_count": 1,
                    "replay": {
                        "execution_mode": "plan",
                        "objective": "Ship the release update",
                        "plan_profile": "coding",
                        "coding_intent": "patch_existing",
                        "approval_mode": True,
                    },
                },
            }
        ],
    )
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: {"plan_history": []})

    result = asyncio.run(api_server.get_autonomous_runs())

    run = result["runs"][0]
    assert run["current_lane"]["agent_id"] == "coding_agent"
    assert run["approvals_needed_count"] == 1
    assert run["replay"]["approval_mode"] is True
    assert result["summary"]["awaiting_approval"] == 1


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


def test_execute_approval_record_supports_custodial_cleanup_and_restore(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path / ".mammoth")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    cache_dir = workspace / ".pytest_cache"
    cache_dir.mkdir()
    tracked = cache_dir / "cache.log"
    tracked.write_text("cache", encoding="utf-8")

    cleanup_result = api_server._execute_approval_record(
        {
            "id": "approval-cleanup",
            "agent_id": "custodial_agent",
            "operation": "custodial_cleanup",
            "payload": {"workspace": str(workspace), "label": "test cleanup"},
        }
    )

    assert cleanup_result["status"] == "ok"
    assert cleanup_result["removed_files"] == [".pytest_cache/cache.log"]
    assert not tracked.exists()

    restored_result = api_server._execute_approval_record(
        {
            "id": "approval-restore",
            "agent_id": "custodial_agent",
            "operation": "custodial_restore",
            "payload": {"workspace": str(workspace), "snapshot_id": cleanup_result["snapshot_id"]},
        }
    )

    assert restored_result["status"] == "ok"
    assert tracked.read_text(encoding="utf-8") == "cache"


def test_run_agent_queues_custodial_cleanup_for_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_agent_registry_ok", False)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path / ".mammoth")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".pytest_cache").mkdir()
    (workspace / ".pytest_cache" / "cache.log").write_text("cache", encoding="utf-8")

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "cleanup",
                "agent_id": "custodial_agent",
                "approval_mode": True,
                "payload": {
                    "prompt": "Cleanup the workspace safely",
                    "workspace": str(workspace),
                    "action": "cleanup",
                },
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["status"] == "pending_approval"
    assert response["result"]["preview"]["requires_approval"] is True
    assert response["result"]["approval"]["operation"] == "custodial_cleanup"


def test_run_agent_queues_brand_voice_content_for_approval(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)

    def fake_registry_run_agent(agent_name, payload):
        return {
            "status": "ok",
            "agent": agent_name,
            "mode": payload.get("mode"),
            "output": payload.get("content"),
        }

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "brand_voice",
                "agent_id": "brand_voice_agent",
                "approval_mode": True,
                "payload": {
                    "content": "Announce the release in a rugged brand voice.",
                    "mode": "stakeholder_summary",
                    "tone": "rugged",
                    "audience": "operator",
                    "approval_contract": {
                        "operation": "brand_voice_publish",
                        "target": "brand/release-note",
                    },
                },
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["status"] == "pending_approval"
    assert response["result"]["operation"] == "brand_voice_publish"
    assert response["result"]["approval"]["target"] == "brand/release-note"
    assert response["result"]["preview"]["operation"] == "brand_voice_publish"


def test_execute_plan_steps_halts_after_community_approval(monkeypatch):
    calls = []
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)

    def fake_registry_run_agent(agent_name, payload):
        calls.append(agent_name)
        return {
            "status": "ok",
            "agent": agent_name,
            "output": payload.get("prompt"),
        }

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    steps = [
        {
            "id": "community",
            "title": "Community update",
            "agent_id": "community_engine_agent",
            "intent": "summarize",
            "prompt": "Draft a community update for the latest release.",
            "approval_contract": {
                "operation": "community_publish",
                "target": "community/update",
            },
        },
        {
            "id": "brand",
            "title": "Brand follow-up",
            "agent_id": "brand_voice_agent",
            "intent": "brand_voice",
            "prompt": "Write the follow-up brand note.",
            "approval_contract": {
                "operation": "brand_voice_publish",
                "target": "brand/follow-up",
            },
        },
    ]

    results = asyncio.run(
        api_server._execute_plan_steps(
            plan_id="plan-approval",
            steps=steps,
            objective="Publish a release update",
            temperature=0.3,
            approval_mode=True,
            stop_on_failure=True,
            activity_agent_id="orchestrator",
        )
    )

    assert [step["status"] for step in results] == ["pending_approval"]
    assert calls == ["community_engine"]
