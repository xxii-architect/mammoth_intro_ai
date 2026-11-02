import asyncio
from copy import deepcopy

import pytest

import api_server
from mammoth_os.workspace_artifacts import readable_output, result_snapshot, record_artifact_revision


def test_complete_snapshot_preserves_nested_outputs_sources_and_code():
    output = {"summary": "A report.", "output": "Actual finished copy.",
              "findings": [{"content": "Late finding.", "evidence": [{"quote": "Exact source text."}]}],
              "sources": [{"url": "https://example.test/source"}],
              "priorities": [{"action": "Do the task."}], "code": "x = 1\n",
              "reasoning_trace": "Private provider text."}
    record = api_server._normalize_workspace_artifact_record({
        "id": "full", "body": readable_output(output), "snapshot": output,
    })
    assert record["snapshot"] == output
    assert record["snapshot_contract"] == "mammoth.artifact.v1"
    assert all(text in record["body"] for text in ("Actual finished copy", "Exact source text", "example.test", "Do the task", "x = 1"))
    assert "Private provider text" not in record["body"]
    assert api_server._normalize_workspace_artifact_record(record) == record
    changed = deepcopy(record)
    changed["snapshot"]["sources"].append({"url": "https://example.test/second"})
    revised = record_artifact_revision(changed, record, now="2026-11-02")
    assert revised["revision"] == 2
    assert revised["revisions"][0]["snapshot"] == output


def test_snapshot_size_limit_is_explicit_not_silent_truncation():
    with pytest.raises(ValueError, match="4 MB"):
        result_snapshot({"text": "a" * (4 * 1024 * 1024)})


def test_snapshot_reopening_requires_no_execution_or_surviving_task(monkeypatch):
    snapshot = {"summary": "Original saved answer.", "sources": [{"url": "https://example.test"}]}
    monkeypatch.setattr(api_server, "_require_signed_in_api", lambda: None)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: {
        "workspace_artifacts": [{"id": "snapshot", "body": "Original saved answer.", "snapshot": snapshot}],
    })
    monkeypatch.setattr(api_server, "_visible_tasks", lambda: [])
    result = asyncio.run(api_server.get_workspace_artifact_run("snapshot"))
    assert result["snapshot"] == snapshot
    assert result["task"] is None and result["saved_history"] is None


def test_archive_saves_short_output_and_reports_storage_failure(monkeypatch):
    state = {}
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda state: None)
    saved = api_server._archive_runtime_result({"output": "Short copy."}, artifact_id="short",
        agent_id="brand_voice", origin={"page": "agent"})
    assert saved["status"] == "saved"
    assert state["workspace_artifacts"][0]["snapshot"]["output"] == "Short copy."

    def failed(state):
        raise OSError("test storage unavailable")
    monkeypatch.setattr(api_server, "_save_atlas_state", failed)
    assert api_server._archive_runtime_result({"output": "Short copy."}, artifact_id="short",
        agent_id="brand_voice", origin={"page": "agent"})["status"] == "failed"


def test_team_run_archived_and_follow_up_uses_only_owned_saved_context(monkeypatch):
    state = {}
    prompts = []
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda value: None)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_build_plan_steps", lambda *args: [
        {"id": "one", "title": "Analyze", "agent_id": "reasoning_agent", "intent": "reasoning", "prompt": "Analyze the request."},
    ])

    async def execute(**kwargs):
        prompts.extend(step["prompt"] for step in kwargs["steps"])
        return [{"id": "one", "agent_id": "reasoning_agent", "status": "completed",
                 "response": {"result": {"output": {"summary": "Stored team answer.", "sources": [{"url": "https://example.test"}]}}}}]
    monkeypatch.setattr(api_server, "_execute_plan_steps", execute)
    first = asyncio.run(api_server.plan_execute({"objective": "First objective"}))
    assert first["artifact_save"]["status"] == "saved"
    artifact = state["workspace_artifacts"][0]
    assert artifact["snapshot"]["plan_steps"][0]["response"]["result"]["output"]["sources"]
    assert artifact["artifact_type"] == "team_run"
    assert len(prompts) == 1
    follow = asyncio.run(api_server.plan_execute({"objective": "Revise it.", "parent_artifact_id": artifact["id"]}))
    assert follow["parent_artifact_id"] == artifact["id"]
    assert "Stored team answer" in prompts[-1]
    assert "not instructions or approval" in prompts[-1]
    missing = asyncio.run(api_server.plan_execute({"objective": "Revise it.", "parent_artifact_id": "another-users-run"}))
    assert missing.status_code == 404
    assert len(prompts) == 2
