import asyncio
import json
import sys
import textwrap
from pathlib import Path

import pytest

from mammoth_os.agent_loop import (
    AgentRun,
    AgentRunner,
    MCPBridge,
    MCPServerConfig,
    RunStore,
    ToolContext,
    ToolRegistry,
    ToolSpec,
    parse_decision,
    register_repo_tools,
    validate_args,
)
from mammoth_os.agent_loop.mcp_client import load_mcp_registry


class ScriptedLLM:
    """Returns queued responses in order; records prompts."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.model = "scripted"

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        item = self.responses.pop(0) if self.responses else {"final": "fallback final"}
        return item if isinstance(item, str) else json.dumps(item)


def _collect(agen):
    async def _run():
        return [event async for event in agen]
    return asyncio.run(_run())


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    return root


def _runner(llm, tmp_path, registry=None, **kwargs):
    if registry is None:
        registry = ToolRegistry()
        register_repo_tools(registry)
    return AgentRunner(registry, lambda: llm, RunStore(tmp_path / "runs"), **kwargs), registry


def test_validate_args_subset():
    schema = {
        "type": "object",
        "properties": {"q": {"type": "string", "maxLength": 3}, "n": {"type": "integer", "minimum": 1}},
        "required": ["q"],
        "additionalProperties": False,
    }
    assert validate_args(schema, {"q": "abc", "n": 2}) == []
    errors = validate_args(schema, {"q": "abcd", "n": 0, "x": 1})
    assert any("longer" in e for e in errors)
    assert any("minimum" in e for e in errors)
    assert any("not allowed" in e for e in errors)
    assert validate_args(schema, {}) == ["args.q: required"]
    assert validate_args({"type": "integer"}, True) == ["args: expected integer"]


def test_parse_decision_handles_fences_and_prose():
    assert parse_decision('```json\n{"final": "ok"}\n```') == {"final": "ok"}
    assert parse_decision('Sure! {"tool": "x", "args": {}} done')["tool"] == "x"
    assert parse_decision("plain answer") is None
    assert parse_decision('{"other": 1}') is None


def test_run_reads_file_then_answers(tmp_path, repo):
    llm = ScriptedLLM([
        {"reasoning": "Need the source.", "plan": ["Read app.py", "Answer"], "tool": "repo_read_file", "args": {"path": "src/app.py"}},
        {"reasoning": "Have it.", "final": "hello() returns 'hi'."},
    ])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="What does hello return?")
    ctx = ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant", repo_slug="me/demo")
    events = _collect(runner.start(run, ctx))
    types = [e.type for e in events]
    assert types[0] == "run.started"
    assert "plan.updated" in types and "reasoning.summary" in types
    call = next(e for e in events if e.type == "tool.call")
    result = next(e for e in events if e.type == "tool.result")
    assert call.data["trace_kind"] == "read"
    assert "return 'hi'" in result.data["result"]["content"]
    assert types[-1] == "run.completed"
    assert events[-1].data["reply"] == "hello() returns 'hi'."
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert "return 'hi'" in llm.prompts[1]
    stored = runner.store.get(run.id, "u1")
    assert stored is not None and stored.status == "completed"
    assert runner.store.get(run.id, "someone-else") is None


def test_final_prompt_adapts_depth_and_includes_recent_conversation(tmp_path):
    llm = ScriptedLLM([])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(
        id=AgentRun.new_id(),
        user_id="u1",
        message="Compare the tradeoffs and give me a thorough migration plan.",
        request={"history_text": "user: We use PostgreSQL.\nassistant: Got it."},
    )

    prompt = runner._final_prompt(run)

    assert "simple requests get a brief, natural reply" in prompt
    assert "multi-part, technical, consequential, or explicitly thorough requests" in prompt
    assert "Do not reveal private chain-of-thought" in prompt
    assert "We use PostgreSQL." in prompt
    assert "Do not output JSON" in prompt


def test_prompts_state_connected_repo_context(tmp_path, repo):
    llm = ScriptedLLM([])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="What does this repo do?")

    platform_ctx = ToolContext(user_id="u1", is_admin=True, repo_root=repo, repo_scope="platform", repo_slug="platform")
    for prompt in (runner._build_prompt(run, platform_ctx), runner._final_prompt(run, platform_ctx)):
        assert "connected to MammothOS platform repository (owner only)" in prompt
        assert "proposal-only" in prompt

    tenant_ctx = ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant", repo_slug="me/demo")
    assert "connected to me/demo (scope=tenant)" in runner._final_prompt(run, tenant_ctx)

    none_ctx = ToolContext(user_id="u1")
    assert "No repository is connected" in runner._build_prompt(run, none_ctx)
    assert "No repository is connected" in runner._final_prompt(run, none_ctx)


def test_direct_final_answer_sees_repo_context(tmp_path, repo):
    llm = ScriptedLLM([{"reasoning": "Wrap up.", "tool": None, "final": None}, "It is a demo repo."])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="Do you have my repo?")
    ctx = ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant", repo_slug="me/demo")
    events = _collect(runner.start(run, ctx))
    assert events[-1].type == "run.completed"
    assert "connected to me/demo" in llm.prompts[-1]


@pytest.mark.parametrize("path", [".env", "../outside.txt", "/etc/passwd", "C:/Windows/win.ini", ".git/config"])
def test_repo_tools_refuse_secrets_and_escapes(tmp_path, repo, path):
    registry = ToolRegistry()
    register_repo_tools(registry)
    ctx = ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant")
    result = asyncio.run(registry.invoke("repo_read_file", {"path": path}, ctx))
    assert result["status"] == "error"


def test_repo_list_hides_secrets(tmp_path, repo):
    registry = ToolRegistry()
    register_repo_tools(registry)
    ctx = ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant")
    result = asyncio.run(registry.invoke("repo_list_files", {}, ctx))
    assert "src/app.py" in result["files"]
    assert ".env" not in result["files"]


def test_repo_tools_hidden_without_repo():
    registry = ToolRegistry()
    register_repo_tools(registry)
    ctx = ToolContext(user_id="u1")
    assert registry.catalog(ctx) == []
    result = asyncio.run(registry.invoke("repo_read_file", {"path": "x"}, ctx))
    assert result["code"] == "unknown_tool"


def test_propose_patch_returns_diff_without_writing(tmp_path, repo):
    llm = ScriptedLLM([
        {"tool": "repo_propose_patch", "args": {"title": "Change greeting", "files": [{"path": "src/app.py", "content": "def hello():\n    return 'hello'\n"}]}},
        {"final": "Proposed."},
    ])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="Change greeting")
    ctx = ToolContext(user_id="u1", is_admin=True, repo_root=repo, repo_scope="platform")
    events = _collect(runner.start(run, ctx))
    diff = next(e for e in events if e.type == "diff.proposed")
    assert "+    return 'hello'" in diff.data["diff"]
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == "def hello():\n    return 'hi'\n"


def test_admin_only_tool_hidden_from_tenants():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="ops", description="", input_schema={"type": "object"}, tier="exec", handler=lambda a, c: {}, admin_only=True))
    assert registry.catalog(ToolContext(user_id="u")) == []
    assert [t["name"] for t in registry.catalog(ToolContext(user_id="u", is_admin=True))] == ["ops"]


def test_exec_tool_requires_approval_then_resumes(tmp_path):
    calls = []
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="run_tests", description="Run tests", input_schema={"type": "object"}, tier="exec",
        handler=lambda a, c: calls.append(a) or {"status": "ok", "passed": True},
    ))
    llm = ScriptedLLM([
        {"reasoning": "Run tests.", "tool": "run_tests", "args": {}},
        {"final": "Tests pass."},
    ])
    runner, _ = _runner(llm, tmp_path, registry=registry)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="run tests")
    ctx = ToolContext(user_id="u1")
    events = _collect(runner.start(run, ctx))
    assert events[-1].type == "run.awaiting_approval"
    assert calls == []
    approval = next(e for e in events if e.type == "approval.requested").data

    bad = _collect(runner.resume(run, ctx, approval_id="apr-wrong", approved=True))
    assert bad[-1].type == "run.failed"

    resumed = _collect(runner.resume(run, ctx, approval_id=approval["id"], approved=True))
    types = [e.type for e in resumed]
    assert types[0] == "approval.resolved"
    assert "tool.result" in types and types[-1] == "run.completed"
    assert calls == [{}]


def test_rejected_approval_is_reported_to_model(tmp_path):
    registry = ToolRegistry()
    registry.register(ToolSpec(name="danger", description="", input_schema={"type": "object"}, tier="exec", handler=lambda a, c: {"status": "ok"}))
    llm = ScriptedLLM([{"tool": "danger", "args": {}}, {"final": "Okay, skipped."}])
    runner, _ = _runner(llm, tmp_path, registry=registry)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="x")
    ctx = ToolContext(user_id="u1")
    approval = next(e for e in _collect(runner.start(run, ctx)) if e.type == "approval.requested").data
    resumed = _collect(runner.resume(run, ctx, approval_id=approval["id"], approved=False, note="no"))
    assert resumed[-1].type == "run.completed"
    assert '"rejected"' in llm.prompts[-1]


def test_cancel_stops_before_next_step(tmp_path, repo):
    llm = ScriptedLLM([{"tool": "repo_list_files", "args": {}}, {"final": "never"}])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="x")
    ctx = ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant")

    async def _go():
        out = []
        async for event in runner.start(run, ctx):
            out.append(event)
            if event.type == "tool.result":
                runner.cancel(run)
        return out

    events = asyncio.run(_go())
    assert events[-1].type == "run.cancelled"


def test_step_budget_forces_final(tmp_path, repo):
    llm = ScriptedLLM([
        {"tool": "repo_list_files", "args": {"limit": 1}},
        {"tool": "repo_list_files", "args": {"limit": 2}},
        {"final": "Summary."},
    ])
    runner, _ = _runner(llm, tmp_path, max_steps=2)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="x")
    events = _collect(runner.start(run, ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant")))
    assert events[-1].type == "run.completed"
    assert events[-1].data["reply"] == "Summary."
    assert sum(1 for e in events if e.type == "tool.call") == 2
    assert "Do not output JSON" in llm.prompts[-1]


def test_repeated_identical_call_is_not_re_executed(tmp_path, repo):
    llm = ScriptedLLM([
        {"tool": "repo_read_file", "args": {"path": "README.md"}},
        {"tool": "repo_read_file", "args": {"path": "README.md"}},
        "The README is a demo heading.",
    ])
    runner, _ = _runner(llm, tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="x")
    events = _collect(runner.start(run, ToolContext(user_id="u1", repo_root=repo, repo_scope="tenant")))
    assert sum(1 for e in events if e.type == "tool.call") == 1
    assert events[-1].data["reply"] == "The README is a demo heading."


def test_offline_local_adapter_is_honest(tmp_path):
    runner, _ = _runner(ScriptedLLM(['[LOCAL_ADAPTER] {"final": "echo"}']), tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="hi")
    events = _collect(runner.start(run, ToolContext(user_id="u1")))
    assert events[-1].data["offline"] is True
    assert "No language model provider" in events[-1].data["reply"]


def test_non_json_reply_becomes_final(tmp_path):
    runner, _ = _runner(ScriptedLLM(["Just a plain answer."]), tmp_path)
    run = AgentRun(id=AgentRun.new_id(), user_id="u1", message="hi")
    events = _collect(runner.start(run, ToolContext(user_id="u1")))
    assert events[-1].data["reply"] == "Just a plain answer."


FAKE_MCP_SERVER = textwrap.dedent(
    """
    import json, sys
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        method = msg.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "0"}}
        elif method == "tools/list":
            result = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
        elif method == "tools/call":
            text = json.dumps(msg["params"]["arguments"])
            result = {"content": [{"type": "text", "text": "echo:" + text}]}
        else:
            result = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\\n")
        sys.stdout.flush()
    """
)


def test_mcp_bridge_calls_allowlisted_tool(tmp_path):
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_MCP_SERVER, encoding="utf-8")
    server = MCPServerConfig(id="fake", label="Fake", command=sys.executable, args=[str(script)], tools=["echo", "write_file"], access="admin")
    bridge = MCPBridge(tmp_path, servers=[server])
    registry = ToolRegistry()
    bridge.register(registry)

    tenant = ToolContext(user_id="u")
    admin = ToolContext(user_id="owner", is_admin=True)
    assert registry.catalog(tenant) == []
    names = {t["name"]: t for t in registry.catalog(admin)}
    assert names["mcp__fake__write_file"]["requires_approval"] is True
    assert names["mcp__fake__echo"]["requires_approval"] is False

    async def _call():
        try:
            return await registry.invoke("mcp__fake__echo", {"x": 1}, admin)
        finally:
            await bridge.close()

    result = asyncio.run(_call())
    assert result["status"] == "ok"
    assert result["content"] == 'echo:{"x": 1}'


def test_repo_mcp_configs_are_admin_only():
    root = Path(__file__).resolve().parents[1]
    servers = load_mcp_registry(root)
    assert servers, "mcp/index.json should load"
    assert all(s.access == "admin" for s in servers)


def test_repo_category_mcp_requires_platform_scope_and_never_pushes(tmp_path):
    server = MCPServerConfig(id="git", label="Git", command="git", tools=["git_status"], approval_required_tools=["git_commit", "git_push"], category="repo")
    registry = ToolRegistry()
    MCPBridge(tmp_path, servers=[server]).register(registry)
    assert "mcp__git__git_push" not in registry.names()
    owner_no_repo = ToolContext(user_id="owner", is_admin=True)
    owner_platform = ToolContext(user_id="owner", is_admin=True, repo_root=tmp_path, repo_scope="platform")
    owner_tenant = ToolContext(user_id="owner", is_admin=True, repo_root=tmp_path, repo_scope="tenant")
    assert registry.catalog(owner_no_repo) == []
    assert registry.catalog(owner_tenant) == []
    names = {t["name"]: t for t in registry.catalog(owner_platform)}
    assert set(names) == {"mcp__git__git_status", "mcp__git__git_commit"}
    assert names["mcp__git__git_commit"]["requires_approval"] is True
