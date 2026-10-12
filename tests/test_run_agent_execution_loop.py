import asyncio

import api_server
import mammoth_os.agent_registry as agent_registry_mod


class _DummyManifest:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.name = agent_id
        self.status = "IDLE"
        self.capabilities = []
        self.level = 1
        self.endpoint = "internal://demo"
        self.last_heartbeat = None
        self.metadata = {}


class _DummyRegistry:
    async def get_agent(self, agent_id: str):
        return _DummyManifest(agent_id)


def test_run_agent_execution_loop_retries_until_contract_passes(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", _DummyRegistry())

    attempts = {"count": 0}

    def fake_registry_run_agent(agent_name, payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {"status": "ok", "summary": "happy to help"}
        return {
            "status": "ok",
            "summary": "Captured browser execution with replay-ready output.",
            "execution": {"stage": "verify", "passed": True},
        }

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "browse_web",
                "agent_id": "browser_agent",
                "payload": {"prompt": "https://example.com"},
                "execution_policy": {"max_attempts": 2},
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["status"] == "ok"
    assert response["result"]["execution_loop"]["verification"]["passed"] is True
    assert len(response["result"]["execution_loop"]["attempts"]) == 2
    assert attempts["count"] == 2


def test_run_agent_execution_loop_marks_failed_when_output_stays_generic(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", _DummyRegistry())
    monkeypatch.setattr(api_server, "registry_run_agent", lambda agent_name, payload: "happy to help")

    response = asyncio.run(
        api_server.run_agent(
            {
                "intent": "lesson_coaching",
                "agent_id": "tutor_agent",
                "payload": {"prompt": "Coach me"},
                "execution_policy": {"max_attempts": 1, "required_fields": ["status"]},
            }
        )
    )

    assert response["status"] == "ok"
    assert response["result"]["status"] == "error"
    verification = response["result"]["execution_loop"]["verification"]
    assert verification["passed"] is False
    failed_checks = {item["name"] for item in verification["failed_checks"]}
    assert "structured_output" in failed_checks


def test_run_auto_save_keeps_full_content_type_provenance_and_distinct_runs(monkeypatch):
    state = {}
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1]})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_record_generated_doc_owner", lambda filename: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", _DummyRegistry())
    content = "Detailed evidence from the source. " * 200
    monkeypatch.setattr(api_server, "registry_run_agent", lambda name, payload: {
        "status": "partial", "artifact_type": "long_form_research", "title": "Same report title",
        "executive_summary": "A substantial summary of a research report whose incomplete sections must remain visible.",
        "sections": [{"heading": "Evidence", "content": content}], "docx_filename": "report.docx",
    })
    for trace in ("run-one", "run-two"):
        asyncio.run(api_server.run_agent({
            "intent": "research_long_form", "agent_id": "research_agent", "trace_id": trace,
            "payload": {"prompt": "Investigate evidence"}, "execution_policy": {"max_attempts": 1, "required_fields": ["status", "sections"]},
        }))
    artifacts = state["workspace_artifacts"]
    assert len(artifacts) == 2
    assert len({item["id"] for item in artifacts}) == 2
    for artifact in artifacts:
        assert content.strip() in artifact["body"]
        assert artifact["category"] == "research"
        assert artifact["artifact_status"] == "draft"
        assert artifact["agent_id"] == "research_agent"
        assert artifact["origin"]["page"] == "agent"
        assert artifact["origin"]["trace_id"] in {"run-one", "run-two"}
        assert artifact["docx_filename"] == "report.docx"
        assert "output_contract" in artifact["verification"]
        assert artifact["lineage"] == {}
        assert artifact["revision"] == 1


def test_run_auto_save_retains_supplied_repo_snapshot_and_revisions(monkeypatch):
    state = {}
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1]})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry_mod, "agent_registry", _DummyRegistry())
    output = {"status": "ok", "summary": "A source-grounded proposal. " * 10, "diff": "Proposed diff",
              "quality": {"ready": False}, "lineage": {"repo": "invented/repo"},
              "validation": {"checks": [{"status": "passed", "name": "python_syntax"}], "tests": "not_run"}}
    monkeypatch.setattr(api_server, "registry_run_agent", lambda name, payload: dict(output))
    body = {"intent": "generate_code", "agent_id": "coding_agent", "trace_id": "repeat-trace",
            "payload": {"prompt": "Generate a proposal", "context": {"repo_context": {
                "requested_root": "alice/project", "source_id": "source-one", "branch": "feature", "base_sha": "a" * 40,
            }}}, "execution_policy": {"max_attempts": 1, "required_fields": ["status", "summary"]}}
    asyncio.run(api_server.run_agent(body))
    output["summary"] = "Revised source-grounded proposal. " * 10
    asyncio.run(api_server.run_agent(body))
    artifact = state["workspace_artifacts"][0]
    assert len(state["workspace_artifacts"]) == 1
    assert artifact["lineage"] == {"repo": "alice/project", "source_id": "source-one", "branch": "feature", "base_sha": "a" * 40}
    assert artifact["revision"] == 2
    assert artifact["verification"]["validation"] == output["validation"]
    assert "A source-grounded proposal." in artifact["revisions"][0]["body"]
