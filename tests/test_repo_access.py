import asyncio
import subprocess
from pathlib import Path

import pytest

import api_server
from mammoth_os.repo_access import RepoAccessPolicy, normalize_slug, user_storage_key


@pytest.fixture()
def policy(tmp_path):
    platform = tmp_path / "platform"
    platform.mkdir()
    return RepoAccessPolicy(
        platform_root=platform,
        tenant_base=tmp_path / "tenants",
        registry_dir=tmp_path / "registry",
        platform_slugs={"xxii-architect/mammoth_intro_ai"},
    )


def _git_init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    (path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"], check=True)


def _register(policy: RepoAccessPolicy, user_id: str, slug: str = "alice/app") -> dict:
    source = {"id": "src-0123456789", "slug": slug, "provider": "github", "default_branch": "main", "status": "ready", "added_at": "", "last_synced_at": "", "error": ""}
    policy._save_sources(user_id, [source])
    _git_init(policy.user_sandbox_dir(user_id) / source["id"])
    return source


def test_normalize_slug_accepts_urls_and_rejects_garbage():
    assert normalize_slug("https://github.com/alice/app.git") == "alice/app"
    assert normalize_slug("alice/app") == "alice/app"
    assert normalize_slug("../etc/passwd") == ""
    assert normalize_slug("alice/..") == ""
    assert normalize_slug("C:/Users/x") == ""


def test_empty_request_means_no_context(policy):
    for is_admin in (True, False):
        res = policy.resolve("", user_id="u1", is_admin=is_admin)
        assert res.scope == "none" and res.root == ""


def test_platform_repo_is_owner_only(policy):
    for ref in ("platform", "mammothos", "xxii-architect/mammoth_intro_ai", "https://github.com/xxii-architect/mammoth_intro_ai"):
        denied = policy.resolve(ref, user_id="u1", is_admin=False)
        assert denied.scope == "denied" and denied.root == ""
        allowed = policy.resolve(ref, user_id="owner", is_admin=True)
        assert allowed.scope == "platform" and allowed.root == str(policy.platform_root)


def test_non_admin_cannot_use_filesystem_paths(policy, tmp_path):
    res = policy.resolve(str(policy.platform_root), user_id="u1", is_admin=False)
    assert res.scope == "denied" and res.root == ""
    res = policy.resolve(str(tmp_path), user_id="u1", is_admin=False)
    assert res.scope == "denied"


def test_admin_unknown_path_is_denied_not_defaulted(policy):
    res = policy.resolve("C:/definitely/missing", user_id="owner", is_admin=True)
    assert res.scope == "denied" and res.root == ""


def test_user_reaches_only_their_own_connected_repo(policy):
    source = _register(policy, "alice")
    mine = policy.resolve("alice/app", user_id="alice", is_admin=False)
    assert mine.scope == "tenant" and mine.root.endswith(source["id"])
    by_id = policy.resolve(source["id"], user_id="alice", is_admin=False)
    assert by_id.root == mine.root
    theirs = policy.resolve(source["id"], user_id="mallory", is_admin=False)
    assert theirs.scope == "denied" and theirs.root == ""


def test_connect_refuses_platform_repo_for_non_admin(policy):
    result = policy.connect("u1", "xxii-architect/mammoth_intro_ai", is_admin=False)
    assert result["status"] == "error" and result["code"] == "platform_repo_private"


def test_connect_refuses_platform_fork(policy, monkeypatch):
    monkeypatch.setattr(policy, "_github_repo_meta", lambda slug: {"full_name": slug, "fork": True, "parent": {"full_name": "xxii-architect/mammoth_intro_ai"}})
    result = policy.connect("u1", "mallory/mammoth-fork", is_admin=False)
    assert result["code"] == "platform_repo_private"


def test_registry_paths_do_not_leak_raw_user_ids(policy):
    _register(policy, "user@example.com")
    files = [p.name for p in policy.registry_dir.iterdir()]
    assert files == [f"{user_storage_key('user@example.com')}.json"]
    public = policy.public_source(policy.list_sources("user@example.com")[0])
    assert "path" not in public and "clone_path" not in public


def test_propose_patch_creates_branch_patch_and_never_pushes(policy):
    source = _register(policy, "alice")
    result = policy.propose_patch("alice", source["id"], [{"path": "app.py", "content": "print('bye')\n"}], title="Say bye")
    assert result["status"] == "ok"
    assert result["pushed"] is False
    assert "print('bye')" in result["patch"]
    repo = policy.user_sandbox_dir("alice") / source["id"]
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert head == "main"
    assert (repo / "app.py").read_text(encoding="utf-8") == "print('hi')\n"


def test_propose_patch_rejects_traversal(policy):
    source = _register(policy, "alice")
    for bad in ("../escape.py", ".git/config", "a/../../escape.py", "..\\escape.py"):
        result = policy.propose_patch("alice", source["id"], [{"path": bad, "content": "x"}])
        assert result["status"] == "error", bad


# ── API-level enforcement ───────────────────────────────────────────────────

@pytest.fixture()
def non_admin(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    token_user = api_server._REQUEST_USER_ID.set("tenant-user")
    token_admin = api_server._REQUEST_IS_ADMIN.set(False)
    yield
    api_server._REQUEST_USER_ID.reset(token_user)
    api_server._REQUEST_IS_ADMIN.reset(token_admin)


def test_api_non_admin_platform_request_yields_no_context(non_admin):
    assert api_server._normalize_repo_context_request({"root": "platform", "query": "sdk"}) == {}
    assert api_server._normalize_repo_context_request({"root": str(api_server.ROOT), "query": "sdk"}) == {}
    assert api_server._normalize_repo_context_request({"query": "sdk"}) == {}


def test_api_repo_context_endpoint_denies_platform_for_non_admin(non_admin):
    response = asyncio.run(api_server.mammoth_repo_context({"repo_context": {"root": "platform", "query": "atlas"}}))
    assert response.status_code == 403


def test_api_runtime_snapshot_repo_context_empty_for_non_admin(non_admin):
    assert api_server._build_repo_context_snapshot() == {}


def test_api_repo_sources_hide_platform_option_for_non_admin(non_admin):
    payload = api_server._repo_sources_payload("tenant-user")
    assert all(opt.get("scope") != "platform" for opt in payload["options"])


def test_api_privileged_agent_denied_for_non_admin(non_admin, monkeypatch):
    monkeypatch.setattr(api_server, "_upsert_task", lambda *a, **k: {"title": "t"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *a, **k: None)
    response = asyncio.run(api_server.run_agent({"agent_id": "shell_agent", "intent": "shell", "payload": {"prompt": "ls"}}))
    assert response["status"] == "error"
    assert response["result"]["code"] == "owner_required"


def test_public_docs_context_contains_no_source_code():
    snapshot = api_server._collect_public_docs_context("how do I embed atlas")
    for snippet in snapshot.get("snippets", []):
        assert snippet["path"].endswith(".md")
    assert snapshot.get("scope") in {None, "public_docs"}
