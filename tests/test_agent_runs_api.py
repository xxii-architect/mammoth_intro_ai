import asyncio
import json

import pytest

import api_server
from mammoth_os.agent_loop import AgentRunner, RunStore


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.model = "scripted"

    async def generate(self, prompt, **kwargs):
        return json.dumps(self.responses.pop(0) if self.responses else {"final": "done"})


async def _drain(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))
    events = []
    for block in "".join(chunks).split("\n\n"):
        data = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
        if data:
            events.append(json.loads("".join(data)))
    return events


@pytest.fixture()
def isolated(monkeypatch, tmp_path):
    state = {}
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_active_account_id", lambda payload: "default")
    monkeypatch.setattr(api_server, "_AGENT_RUNS", RunStore(tmp_path / "runs"))

    def use_llm(responses):
        llm = ScriptedLLM(responses)
        runner = AgentRunner(api_server._AGENT_TOOLS, lambda: llm, api_server._AGENT_RUNS)
        monkeypatch.setattr(api_server, "_AGENT_RUNNER", runner)
        return llm

    return state, use_llm


@pytest.fixture()
def as_user(monkeypatch):
    tokens = []

    def _set(user_id, is_admin=False):
        monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
        tokens.append((api_server._REQUEST_USER_ID, api_server._REQUEST_USER_ID.set(user_id)))
        tokens.append((api_server._REQUEST_IS_ADMIN, api_server._REQUEST_IS_ADMIN.set(is_admin)))

    yield _set
    for var, token in reversed(tokens):
        var.reset(token)


def test_run_streams_typed_events_and_persists_history(isolated, as_user):
    state, use_llm = isolated
    as_user("tenant-a")
    use_llm([{"reasoning": "Simple question.", "final": "Hello from Mammoth Mind."}])
    response = asyncio.run(api_server.mammoth_agent_run_start({"message": "hi"}))
    events = asyncio.run(_drain(response))
    assert [e["type"] for e in events] == ["run.started", "reasoning.summary", "message.delta", "message.completed", "run.completed"]
    assert all(e["contract"] == "mammoth.run.v1" for e in events)
    assert events[0]["data"]["repo"] is None
    run_id = events[0]["run_id"]
    history = state["mammoth_chat_history"]
    assert history[-1]["message"] == "Hello from Mammoth Mind." and history[-1]["run_id"] == run_id

    fetched = asyncio.run(api_server.mammoth_agent_run_get(run_id))
    assert fetched["run"]["status"] == "completed"
    assert "request" not in fetched["run"]


def test_run_is_private_to_its_owner(isolated, as_user):
    _, use_llm = isolated
    as_user("tenant-a")
    use_llm([{"final": "secret answer"}])
    events = asyncio.run(_drain(asyncio.run(api_server.mammoth_agent_run_start({"message": "hi"}))))
    run_id = events[0]["run_id"]
    as_user("tenant-b")
    assert asyncio.run(api_server.mammoth_agent_run_get(run_id)).status_code == 404
    assert asyncio.run(api_server.mammoth_agent_run_cancel(run_id)).status_code == 404
    assert asyncio.run(api_server.mammoth_agent_run_approval(run_id, {"decision": "approve"})).status_code == 404


def test_non_admin_cannot_target_platform_repo(isolated, as_user):
    _, use_llm = isolated
    as_user("tenant-a")
    use_llm([{"final": "x"}])
    response = asyncio.run(api_server.mammoth_agent_run_start({"message": "read api_server.py", "repo_context": {"root": "platform"}}))
    assert response.status_code == 403


def test_tool_catalog_hides_repo_and_mcp_tools_from_tenants(isolated, as_user):
    as_user("tenant-a")
    catalog = asyncio.run(api_server.mammoth_agent_tools())
    names = {t["name"] for t in catalog["tools"]}
    assert "docs_search" in names and "web_fetch" in names
    assert not any(n.startswith("repo_") or n.startswith("mcp__") for n in names)
    assert catalog["mcp_servers"] == []


def test_admin_sees_platform_repo_tools(isolated, as_user):
    as_user("owner", is_admin=True)
    catalog = asyncio.run(api_server.mammoth_agent_tools(repo="platform"))
    names = {t["name"] for t in catalog["tools"]}
    assert "repo_read_file" in names
    assert catalog["repo"]["scope"] == "platform"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/api/admin",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/",
    "http://[::1]/",
    "file:///etc/passwd",
])
def test_web_fetch_blocks_private_hosts(url):
    result = api_server._internet_fetch_url(url)
    assert result["status"] == "error"
