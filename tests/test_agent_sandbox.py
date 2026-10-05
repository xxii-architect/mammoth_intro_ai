"""Non-admin callers must never read, scan, or execute anything on the MammothOS host
through the Coding or Browser agents, and browser sessions must not cross users."""

import asyncio
from types import SimpleNamespace

import pytest
import requests

import api_server
from mammoth_os.agents import browser_agent as browser_mod
from mammoth_os.agents.browser_agent import BlockedURLError, BrowserAgent, _assert_public_url
from mammoth_os.agents.coding_agent import _HOST_ACCESS, CodingAgent


class _RecordingLLM:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        return "```python\nprint('ok')\n```"

    async def embed(self, _texts):
        raise AssertionError("sandboxed runs must not query the shared vector store")


@pytest.fixture()
def secret_file(tmp_path):
    path = tmp_path / "platform_secret.py"
    path.write_text("PLATFORM_SECRET = 'do-not-leak'\n", encoding="utf-8")
    return path


@pytest.fixture()
def llm(monkeypatch):
    client = _RecordingLLM()
    monkeypatch.setattr("mammoth_os.agents.coding_agent.get_llm_client", lambda: client)
    return client


# ── CodingAgent ─────────────────────────────────────────────────────────────

def test_sandboxed_refactor_never_reads_host_file(llm, secret_file):
    result = CodingAgent().run({"prompt": f"refactor {secret_file}", "target": str(secret_file), "host_access": False})
    assert "do-not-leak" not in str(result)
    assert all("do-not-leak" not in prompt for prompt in llm.prompts)


def test_owner_refactor_still_reads_host_file(llm, secret_file):
    CodingAgent().run({"prompt": f"refactor {secret_file}", "target": str(secret_file)})
    assert any("do-not-leak" in prompt for prompt in llm.prompts)


@pytest.mark.parametrize("intent", ["analyze_codebase", "run_tests"])
def test_sandboxed_host_ops_denied(intent, monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError(f"{intent} must not touch the host")

    monkeypatch.setattr(CodingAgent, "analyze_codebase", _boom)
    monkeypatch.setattr(CodingAgent, "run_tests", _boom)
    result = CodingAgent().run({"prompt": "check it", "coding_intent": intent, "host_access": False})
    assert result["status"] == "error"
    assert result["code"] == "owner_required"


def test_sandboxed_test_keyword_does_not_run_host_tests(llm, monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("run_tests must not run for sandboxed callers")

    monkeypatch.setattr(CodingAgent, "run_tests", _boom)
    monkeypatch.setattr(CodingAgent, "analyze_codebase", _boom)
    result = CodingAgent().run(
        {"prompt": "write a pytest test for: def add(a, b): return a + b", "context": {"source": "def add(a, b): return a + b"}, "host_access": False}
    )
    assert result.get("task_kind") != "test"


def test_sandboxed_read_helpers_are_inert(secret_file):
    agent = CodingAgent()

    async def _probe():
        token = _HOST_ACCESS.set(False)
        try:
            return await agent._read_file(str(secret_file)), agent._host_path_exists(str(secret_file)), await agent.run_tests(str(secret_file.parent))
        finally:
            _HOST_ACCESS.reset(token)

    text, exists, tests = asyncio.run(_probe())
    assert text == ""
    assert exists is False
    assert tests["passed"] is False and "owner-only" in tests["error"]


# ── BrowserAgent ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/api/health",
        "http://localhost/",
        "http://169.254.169.254/metadata/v1/user-data",
        "http://10.0.0.5/",
        "http://[::1]/",
        "file:///etc/passwd",
        "--chrome-flags=x",
    ],
)
def test_assert_public_url_blocks_non_public(url):
    with pytest.raises(BlockedURLError):
        _assert_public_url(url)


def test_sandboxed_browser_blocks_loopback(tmp_path, monkeypatch):
    def _no_network(*_a, **_k):
        raise AssertionError("blocked URL must not be requested")

    monkeypatch.setattr(requests.Session, "request", _no_network)
    agent = BrowserAgent(router=None, storage_root=str(tmp_path))
    result = agent.run({"url": "http://127.0.0.1:8000/api/health", "allow_private_network": False})
    assert result["status"] == "error"


def test_sandboxed_browser_blocks_redirect_to_metadata(tmp_path, monkeypatch):
    calls = []

    def _fake_request(self, method, url, **kwargs):
        calls.append(url)
        assert kwargs.get("allow_redirects") is False
        return SimpleNamespace(
            is_redirect=True,
            status_code=302,
            headers={"location": "http://169.254.169.254/metadata/v1/user-data"},
            url=url,
            text="",
        )

    monkeypatch.setattr(requests.Session, "request", _fake_request)
    monkeypatch.setattr(browser_mod, "_assert_public_url", lambda u: (_ for _ in ()).throw(BlockedURLError(u)) if "169.254" in u else None)
    agent = BrowserAgent(router=None, storage_root=str(tmp_path))
    result = agent.run({"url": "https://example.com/redirect", "allow_private_network": False})
    assert result["status"] == "error"
    assert calls == ["https://example.com/redirect"]


def test_sandboxed_site_audit_skips_external_tools(tmp_path, monkeypatch):
    agent = BrowserAgent(router=None, storage_root=str(tmp_path))
    monkeypatch.setattr(agent, "_run_lighthouse", lambda _u: (_ for _ in ()).throw(AssertionError("lighthouse must not run")))
    monkeypatch.setattr(agent, "_run_playwright_mcp", lambda _r: (_ for _ in ()).throw(AssertionError("playwright must not run")))
    result = agent.run({"action": "site_audit", "url": "http://127.0.0.1/", "allow_private_network": False})
    assert result["status"] == "error"


def test_browser_replays_are_scoped_per_user(tmp_path):
    agent = BrowserAgent(router=None, storage_root=str(tmp_path))
    state = agent._default_state()
    token = browser_mod._SESSION_SCOPE.set("user:alice")
    try:
        replay_id = agent._record_replay(state, session_id="s1", actions=[{"action": "snapshot", "url": "https://example.com"}], request_action="snapshot")
        assert agent._find_replay(state, replay_id) is not None
    finally:
        browser_mod._SESSION_SCOPE.reset(token)
    agent._save_state(state)

    result = agent.run({"action": "replay", "replay_id": replay_id, "session_scope": "user:mallory", "allow_private_network": False})
    assert result["status"] == "error"
    assert "not found" in result["message"]


# ── API enforcement ─────────────────────────────────────────────────────────

@pytest.fixture()
def capture_dispatch(monkeypatch):
    captured = {}

    def _fake_registry_run(agent_name, payload):
        captured["agent"] = agent_name
        captured["payload"] = payload
        return {"status": "ok", "summary": "captured"}

    monkeypatch.setattr(api_server, "registry_run_agent", _fake_registry_run)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *a, **k: {"title": "t"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *a, **k: None)
    return captured


def _as_user(monkeypatch, *, is_admin):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    return api_server._REQUEST_USER_ID.set("tenant-user"), api_server._REQUEST_IS_ADMIN.set(is_admin)


def _reset(tokens):
    api_server._REQUEST_USER_ID.reset(tokens[0])
    api_server._REQUEST_IS_ADMIN.reset(tokens[1])


@pytest.mark.parametrize("is_admin", [False, True])
def test_api_forces_coding_host_access(capture_dispatch, monkeypatch, is_admin):
    tokens = _as_user(monkeypatch, is_admin=is_admin)
    try:
        asyncio.run(api_server.run_agent({"agent_id": "coding_agent", "intent": "generate_code", "payload": {"prompt": "refactor api_server.py", "host_access": True}}))
    finally:
        _reset(tokens)
    assert capture_dispatch["agent"] == "coding"
    assert capture_dispatch["payload"]["host_access"] is is_admin


@pytest.mark.parametrize("is_admin", [False, True])
def test_api_forces_search_host_access(capture_dispatch, monkeypatch, is_admin):
    tokens = _as_user(monkeypatch, is_admin=is_admin)
    try:
        asyncio.run(api_server.run_agent({"agent_id": "search_agent", "intent": "search", "payload": {"query": "api_server", "host_access": True}}))
    finally:
        _reset(tokens)
    assert capture_dispatch["agent"] == "search"
    assert capture_dispatch["payload"]["host_access"] is is_admin


@pytest.mark.parametrize("is_admin", [False, True])
def test_api_forces_browser_sandbox(capture_dispatch, monkeypatch, is_admin):
    tokens = _as_user(monkeypatch, is_admin=is_admin)
    try:
        asyncio.run(
            api_server.run_agent(
                {"agent_id": "browser_agent", "intent": "browse", "payload": {"url": "http://127.0.0.1:8000/", "allow_private_network": True, "session_scope": ""}}
            )
        )
    finally:
        _reset(tokens)
    assert capture_dispatch["agent"] == "browser"
    payload = capture_dispatch["payload"]
    assert payload["allow_private_network"] is is_admin
    assert payload["session_scope"] == ("" if is_admin else "user:tenant-user")


# --- Shared task feeds are scoped per user -------------------------------------------------


@pytest.fixture
def task_store(monkeypatch, tmp_path):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(
        '[{"id": "plan-mine", "title": "plan+execute run", "owner_id": "tenant-user", "details": {}},'
        ' {"id": "plan-other", "title": "plan+execute run", "owner_id": "other-user", "details": {}},'
        ' {"id": "legacy", "title": "legacy task", "details": {}}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(api_server, "TASKS_FILE", tasks_file)
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [{"message": "secret"}])
    monkeypatch.setattr(api_server, "_load_approvals", lambda: [{"code": "secret"}])
    monkeypatch.setattr(api_server, "_load_snapshots", lambda: [{"path": "secret"}])
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: {})
    return tasks_file


@pytest.mark.parametrize("is_admin", [False, True])
def test_observability_runs_scoped(task_store, monkeypatch, is_admin):
    tokens = _as_user(monkeypatch, is_admin=is_admin)
    try:
        result = asyncio.run(api_server.get_observability_runs())
    finally:
        _reset(tokens)
    run_ids = {run["run_id"] for run in result["runs"]}
    if is_admin:
        assert run_ids == {"plan-mine", "plan-other", "legacy"}
        assert result["activities"] and result["approvals"] and result["snapshots"]
    else:
        assert run_ids == {"plan-mine"}
        assert result["activities"] == [] and result["approvals"] == [] and result["snapshots"] == []


def test_autonomous_runs_scoped_for_non_admin(task_store, monkeypatch):
    tokens = _as_user(monkeypatch, is_admin=False)
    try:
        visible = api_server._visible_tasks()
    finally:
        _reset(tokens)
    assert [task["id"] for task in visible] == ["plan-mine"]


def test_upsert_task_stamps_and_preserves_owner(task_store, monkeypatch):
    tokens = _as_user(monkeypatch, is_admin=True)
    try:
        created = api_server._upsert_task("new-task", "New")
        updated = api_server._upsert_task("plan-other", "Renamed")
    finally:
        _reset(tokens)
    assert created["owner_id"] == "tenant-user"
    assert updated["owner_id"] == "other-user"


@pytest.mark.parametrize("is_admin", [False, True])
def test_task_inbox_lists_only_own_tasks(task_store, monkeypatch, is_admin):
    tokens = _as_user(monkeypatch, is_admin=is_admin)
    try:
        result = asyncio.run(api_server.get_tasks())
    finally:
        _reset(tokens)
    ids = {task["id"] for task in result}
    assert ids == ({"plan-mine", "plan-other", "legacy"} if is_admin else {"plan-mine"})


def test_task_inbox_cannot_edit_foreign_task(task_store, monkeypatch):
    tokens = _as_user(monkeypatch, is_admin=False)
    try:
        foreign = asyncio.run(api_server.upsert_task({"id": "plan-other", "title": "hijack", "status": "complete"}))
        legacy = asyncio.run(api_server.upsert_task({"id": "legacy", "title": "hijack"}))
        own = asyncio.run(api_server.upsert_task({"id": "plan-mine", "title": "mine", "status": "complete"}))
    finally:
        _reset(tokens)
    assert foreign.status_code == 404 and legacy.status_code == 404
    assert own["status"] == "complete" and own["owner_id"] == "tenant-user"
    stored = {task["id"]: task for task in api_server._load_tasks()}
    assert stored["plan-other"]["title"] == "plan+execute run"


def test_task_inbox_rejects_anonymous(task_store, monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    tokens = api_server._REQUEST_USER_ID.set("anonymous"), api_server._REQUEST_IS_ADMIN.set(False)
    try:
        result = asyncio.run(api_server.get_tasks())
    finally:
        _reset(tokens)
    assert result.status_code == 401


# --- Generated research documents are owner-scoped -----------------------------------------


@pytest.fixture
def doc_store(monkeypatch, tmp_path):
    docs = tmp_path / "generated_docs"
    docs.mkdir()
    for name in ("mine.docx", "theirs.docx", "legacy.docx"):
        (docs / name).write_bytes(b"PK")
    monkeypatch.setattr(api_server, "GENERATED_DOCS_DIR", docs)
    monkeypatch.setattr(api_server, "GENERATED_DOC_OWNERS_FILE", tmp_path / "owners.json")
    return docs


def _download_as(monkeypatch, filename, *, is_admin, user="tenant-user"):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    tokens = api_server._REQUEST_USER_ID.set(user), api_server._REQUEST_IS_ADMIN.set(is_admin)
    try:
        return api_server.download_docx_file(filename)
    finally:
        _reset(tokens)


def test_docx_download_is_owner_scoped(doc_store, monkeypatch):
    for owner, name in (("tenant-user", "mine.docx"), ("other-user", "theirs.docx")):
        tokens = api_server._REQUEST_USER_ID.set(owner), api_server._REQUEST_IS_ADMIN.set(False)
        try:
            api_server._record_generated_doc_owner(name)
        finally:
            _reset(tokens)

    assert _download_as(monkeypatch, "mine.docx", is_admin=False).status_code == 200
    assert _download_as(monkeypatch, "theirs.docx", is_admin=False).status_code == 404
    assert _download_as(monkeypatch, "legacy.docx", is_admin=False).status_code == 404
    assert _download_as(monkeypatch, "missing.docx", is_admin=False).status_code == 404
    assert _download_as(monkeypatch, "legacy.docx", is_admin=True).status_code == 200
    assert _download_as(monkeypatch, "mine.docx", is_admin=False, user="anonymous").status_code == 401


@pytest.mark.parametrize("name", ["../secret.docx", "sub/mine.docx", "mine.txt"])
def test_docx_download_rejects_bad_names(doc_store, monkeypatch, name):
    assert _download_as(monkeypatch, name, is_admin=True).status_code == 400
