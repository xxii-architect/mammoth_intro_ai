import asyncio

import pytest

import api_server
import mammoth_os.llm_client as llm_client
from mammoth_os.agent_loop import ToolContext
from mammoth_os.agents.mammoth_guide_agent import MammothGuideAgent


def test_guide_retrieves_late_matching_section_not_just_document_opening(tmp_path, monkeypatch):
    source = tmp_path / "guide.md"
    source.write_text("# Guide\nOpening only.\n" + "Unrelated overview.\n" * 100
                      + "\n## Recursive review costs\n"
                      + "RECURSIVE_SENTINEL: an admission refusal is not measured usage.\n"
                      + "\n## Unrelated\nPRIVATE_TAIL\n", encoding="utf-8")
    (tmp_path / "api_server.py").write_text("PRIVATE_PLATFORM_SOURCE", encoding="utf-8")
    monkeypatch.setattr(api_server, "ROOT", tmp_path)
    monkeypatch.setattr(api_server, "_PUBLIC_GUIDE_DOCS", ["guide.md"])

    snapshot = api_server._collect_public_docs_context("recursive review costs", max_snippets=1)
    assert snapshot["scope"] == "public_docs"
    assert len(snapshot["snippets"]) == 1
    snippet = snapshot["snippets"][0]
    assert "RECURSIVE_SENTINEL" in snippet["excerpt"]
    assert snippet["line"] > 100
    assert len(snippet["excerpt"]) <= 2400
    assert "PRIVATE_PLATFORM_SOURCE" not in str(snapshot)
    assert "PRIVATE_TAIL" not in str(snapshot)
    assert snapshot["search_hits"][0]["line"] == snippet["line"]


def test_guide_handbook_answers_relevant_feature_questions():
    for query, expected in [
        ("recursive review costs", "four model completions"),
        ("when not to use recursive review", "Leave it off"),
        ("Documents uploaded extracted indexed selected reviewed", "different milestones"),
        ("What remains planned", "not been independently reproduced"),
    ]:
        snapshot = api_server._collect_public_docs_context(query)
        excerpts = "\n".join(item["excerpt"] for item in snapshot["snippets"])
        assert expected in excerpts, query
        assert all(item["path"] in api_server._PUBLIC_GUIDE_DOCS for item in snapshot["snippets"])
        assert len(snapshot["snippets"]) <= 3


def test_guide_prompt_receives_actual_public_excerpts_and_not_phantom_repo_context(monkeypatch):
    prompts = []

    class Client:
        async def generate(self, prompt, **kwargs):
            prompts.append((prompt, kwargs))
            return "Source-grounded explanation."

    monkeypatch.setattr(llm_client, "get_llm_client", lambda: Client())
    context = {
        "scope": "public_docs", "branch": "published",
        "snippets": [{"path": "docs/public/example.md", "excerpt": "ACTUAL_SOURCE", "line": 25}],
        "search_hits": [],
    }
    result = MammothGuideAgent().run({"message": "Explain the feature", "repo_context": context})
    assert "ACTUAL_SOURCE" in prompts[0][0]
    assert "docs/public/example.md" in prompts[0][0]
    assert "source data" in prompts[0][1]["system_prompt"]
    assert result["model_status"] == "available"
    assert not result["repo_context_used"]
    assert all(step["file_ref"] is None or step["file_ref"].endswith(".md")
               for step in result["guide_steps"])
    assert "Repository Overview" not in str(result["guide_steps"])


def test_guide_provider_failure_discloses_unavailable_model_and_retains_source(monkeypatch, caplog):
    async def unavailable(*_args):
        raise RuntimeError("PRIVATE_PROVIDER_ERROR")

    monkeypatch.setattr(MammothGuideAgent, "_llm_guide", unavailable)
    result = MammothGuideAgent().run({
        "message": "Explain recursive review",
        "repo_context": {"scope": "public_docs", "branch": "published", "snippets": [
            {"path": "docs/public/example.md", "excerpt": "SAVED_SOURCE"}]},
    })
    assert result["model_status"] == "unavailable"
    assert "unavailable" in result["message"].lower()
    assert "PRIVATE_PROVIDER_ERROR" not in result["message"]
    assert "SAVED_SOURCE" in str(result["guide_steps"])
    assert "Guide model response unavailable" in caplog.text
    assert result["quality"]["status"] == "failed"


def test_guide_deliverable_strips_reasoning_and_truncated_tail(monkeypatch):
    class Client:
        async def generate(self, prompt, **kwargs):
            return "<think>Separate model trace.</think>A complete source-grounded explanation. unfinished"

    monkeypatch.setattr(llm_client, "get_llm_client", lambda: Client())
    result = MammothGuideAgent().run({"message": "Explain the feature"})
    assert result["message"] == "A complete source-grounded explanation."
    assert "Separate model trace" in result["reasoning_trace"]
    assert result["quality"] == {"status": "ok", "reasoning_stripped": True, "trimmed": True}


def test_guide_refreshes_docs_and_caller_capabilities_without_private_metadata(tmp_path, monkeypatch):
    source = tmp_path / "guide.md"
    source.write_text("## Recursive review\nOriginal documented explanation.", encoding="utf-8")
    monkeypatch.setattr(api_server, "ROOT", tmp_path)
    monkeypatch.setattr(api_server, "_PUBLIC_GUIDE_DOCS", ["guide.md"])
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda *_args: "tenant-a")
    monkeypatch.setattr(api_server, "_require_workspace_tier_api", lambda *_args: object())
    context = ToolContext(user_id="tenant-a")
    observed_contexts = []
    tools = [{"name": "document_read", "tier": "read", "requires_approval": False,
              "description": "PRIVATE_DESCRIPTION", "input_schema": {"secret": "PRIVATE_SCHEMA"}}]

    def catalog(ctx):
        observed_contexts.append(ctx)
        return tools

    monkeypatch.setattr(api_server._AGENT_TOOLS, "catalog", catalog)
    monkeypatch.setattr(api_server._AGENT_MCP, "describe", lambda ctx: [{"url": "PRIVATE_MCP_URL"}])
    first = api_server._collect_public_docs_context("recursive", tool_context=context)
    source.write_text("## Recursive review\nUpdated documented explanation.", encoding="utf-8")
    tools.clear()
    second = api_server._collect_public_docs_context("recursive", tool_context=context)

    assert first["docs_revision"] != second["docs_revision"]
    assert "Updated documented explanation" in second["snippets"][0]["excerpt"]
    assert observed_contexts == [context, context]
    status = first["platform_status"]
    assert status["scope"] == "current_caller"
    assert status["verification"] == "configuration_only_not_health"
    assert status["observed_at"]
    assert not status["workspace_records_available"]
    assert not status["terminal_owner_access"]
    assert status["repository_scope"] == "none"
    assert len(status["tools"]) == 1
    assert second["platform_status"]["tools"] == []
    assert "PRIVATE_" not in str(first)


def test_anonymous_guide_never_collects_private_or_caller_status(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda *_args: "anonymous")

    def forbidden(*_args):
        raise AssertionError("Anonymous Guide tried to load caller capabilities or state")

    monkeypatch.setattr(api_server, "_agent_tool_context", forbidden)
    monkeypatch.setattr(api_server, "_load_atlas_state", forbidden)
    snapshot = api_server._guide_platform_status()
    assert snapshot["scope"] == "public_only"
    assert "tools" not in snapshot
    assert "workspace_records_available" not in snapshot


def test_guide_model_gets_fresh_status_even_with_selected_repository(monkeypatch):
    prompts = []

    class Client:
        async def generate(self, prompt, **kwargs):
            prompts.append(prompt)
            return "Capability availability is not health."

    monkeypatch.setattr(llm_client, "get_llm_client", lambda: Client())
    status = {"observed_at": "NOW", "verification": "configuration_only_not_health"}
    result = MammothGuideAgent().run({
        "message": "What is available?",
        "repo_context": {"branch": "selected-revision", "snippets": []},
        "guide_context": {"scope": "public_docs", "branch": "published",
                          "docs_revision": "CONTENT_FINGERPRINT", "platform_status": status,
                          "snippets": [{"path": "docs/public/example.md", "excerpt": "PUBLIC_EXPLANATION"}]},
    })
    assert "PUBLIC_EXPLANATION" in prompts[0]
    assert "CONTENT_FINGERPRINT" in prompts[0]
    assert "configuration_only_not_health" in prompts[0]
    assert result["platform_status"] == status
    assert result["docs_revision"] == "CONTENT_FINGERPRINT"


def test_docs_tool_includes_request_scoped_status(monkeypatch):
    ctx = ToolContext(user_id="tenant-a")
    calls = []

    def collect(query, **kwargs):
        calls.append((query, kwargs))
        return {"snippets": [], "search_hits": [], "docs_revision": "v1",
                "platform_status": {"scope": "current_caller"}}

    monkeypatch.setattr(api_server, "_collect_public_docs_context", collect)
    result = api_server._agent_tool_docs("recursive", ctx)
    assert calls == [("recursive", {"max_snippets": 2, "tool_context": ctx})]
    assert result["platform_status"]["scope"] == "current_caller"
    assert result["docs_revision"] == "v1"


def test_missing_public_docs_report_unavailable_not_successful_empty_search(tmp_path, monkeypatch):
    monkeypatch.setattr(api_server, "ROOT", tmp_path)
    monkeypatch.setattr(api_server, "_PUBLIC_GUIDE_DOCS", ["missing.md"])
    result = api_server._agent_tool_docs("recursive", ToolContext(user_id="tenant-a"))
    assert result["status"] == "error"
    assert "unavailable" in result["error"]
    assert result["snippets"] == []


def test_guide_rejects_allowlisted_paths_outside_public_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "private.md").write_text("PRIVATE_OUTSIDE_SOURCE", encoding="utf-8")
    (root / "guide.md").write_text("## Guide\nPublic explanation.", encoding="utf-8")
    monkeypatch.setattr(api_server, "ROOT", root)
    monkeypatch.setattr(api_server, "_PUBLIC_GUIDE_DOCS", [str(tmp_path / "private.md"), "guide.md"])
    snapshot = api_server._collect_public_docs_context("private source")
    assert "PRIVATE_OUTSIDE_SOURCE" not in str(snapshot)
    assert [item["path"] for item in snapshot["snippets"]] == ["guide.md"]


@pytest.mark.parametrize("message_key", ["message", "prompt"])
def test_direct_guide_dispatch_replaces_client_supplied_status_and_excerpts(monkeypatch, message_key):
    observed = []
    canonical = {"scope": "public_docs", "docs_revision": "SERVER_REVISION",
                 "platform_status": {"verification": "configuration_only_not_health"}}

    async def no_manifest(_agent_id):
        return None

    def generate(_agent, payload):
        observed.append(payload)
        return {"message": "A source-grounded explanation from server-owned context.",
                "guide_steps": []}

    monkeypatch.setattr(api_server, "_runtime_status_snapshot", lambda: {"state": "ready"})
    monkeypatch.setattr(api_server, "_upsert_task", lambda _id, title, **kwargs: {"title": title})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_archive_runtime_result", lambda *args, **kwargs: {})
    monkeypatch.setattr(api_server, "_wrap_response_with_trust", lambda response, **kwargs: response)
    monkeypatch.setattr(api_server.agent_registry, "get_agent", no_manifest)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "registry_run_agent", generate)
    monkeypatch.setattr(api_server, "_collect_public_docs_context", lambda *args, **kwargs: canonical)
    result = asyncio.run(api_server.run_agent({
        "agent_id": "mammoth_guide", "intent": "guide_platform",
        "payload": {message_key: "Explain the platform", "guide_context": {"docs_revision": "FORGED"},
                    "repo_context": {"snippets": [{"excerpt": "FORGED_SOURCE"}]}},
    }))
    assert result["result"]["status"] == "ok"
    assert observed
    assert observed[0]["guide_context"] == canonical
    assert observed[0]["repo_context"] == canonical
    assert "FORGED" not in str(observed)
