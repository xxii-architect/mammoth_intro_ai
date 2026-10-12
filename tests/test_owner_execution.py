import asyncio
import os
import subprocess
import threading

import pytest
from fastapi.testclient import TestClient

from mammoth_os.agent_loop import (
    AgentRun,
    AgentRunner,
    RunStore,
    ToolContext,
    ToolRegistry,
)
from mammoth_os.owner_execution import (
    ContainerExecutor,
    ExecutionError,
    OwnerExecution,
    git,
    head_sha,
    snapshot,
    validate_changes,
)
from mammoth_os.owner_execution_tools import register_owner_execution_tools

IMAGE = "python@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93"


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    (root / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text(
        "import unittest\nfrom app import add\nclass TestAdd(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=must-not-leave-host", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.test",
                    "commit", "-m", "Fixture"], check=True, capture_output=True)
    return root


class FakeExecutor:
    image = IMAGE
    timeout = 60
    def __init__(self):
        self.calls = []
    def readiness(self):
        return {"ready": True}
    def run(self, files, profile, cancelled, **kwargs):
        self.calls.append(files)
        return {"passed": b"return a + b" in files["app.py"], "log": "fixture evidence", "duration_ms": 1}


def prepared(service, root):
    return service.prepare(root, "explicit/repo", "owner", [{"path": "app.py", "content": "def add(a, b):\n    return a + b\n"}],
                           base_sha=head_sha(root), profile="python_unittest")


def test_disposable_worktree_does_not_modify_owner_checkout(repository, tmp_path):
    executor = FakeExecutor()
    service = OwnerExecution(tmp_path / "jobs", executor, enabled=True)
    job = prepared(service, repository)
    result = service.execute(job["id"], "owner", repository, job["approval_digest"])
    assert result["status"] == "validated"
    assert result["baseline"]["passed"] is False and result["candidate"]["passed"] is True
    assert (repository / "app.py").read_text().endswith("return a - b\n")
    assert ".env" not in executor.calls[0] and ".git" not in executor.calls[0]
    assert b"must-not-leave-host" not in b"".join(executor.calls[0].values())
    assert "root" not in result and "changes" not in result
    trees = subprocess.run(["git", "-C", str(repository), "worktree", "list", "--porcelain"], capture_output=True, text=True, check=True)
    assert trees.stdout.count("worktree ") == 1
    with pytest.raises(ExecutionError, match="already used"):
        service.execute(job["id"], "owner", repository, job["approval_digest"])


@pytest.mark.parametrize("path", ["../escape.py", ".git/config", ".env", "dir/.env.local", "id_rsa", "/tmp/out", "C:\\out", "node_modules/x", "a/../app.py"])
def test_unsafe_changes_are_rejected(repository, path):
    with pytest.raises(ExecutionError):
        validate_changes([{"path": path, "content": "x"}], repository)


def test_stale_approval_wrong_owner_and_cancellation(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    with pytest.raises(ExecutionError, match="not found"):
        service.get(job["id"], "someone-else")
    with pytest.raises(ExecutionError, match="mismatched"):
        service.execute(job["id"], "owner", repository, "wrong")
    assert service.cancel(job["id"], "owner")["status"] == "cancelled"
    with pytest.raises(ExecutionError):
        service.execute(job["id"], "owner", repository, job["approval_digest"])
    job = prepared(service, repository)
    subprocess.run(["git", "-C", str(repository), "-c", "user.name=Test", "-c", "user.email=test@example.test",
                    "commit", "--allow-empty", "-m", "Head moved"], capture_output=True, check=True)
    with pytest.raises(ExecutionError, match="HEAD changed"):
        service.execute(job["id"], "owner", repository, job["approval_digest"])


def test_disabled_and_missing_isolation_never_use_host_fallback(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", ContainerExecutor(""), enabled=False)
    with pytest.raises(ExecutionError, match="disabled"):
        prepared(service, repository)
    service.enabled = True
    job = prepared(service, repository)
    with pytest.raises(ExecutionError, match="operator-reviewed"):
        service.execute(job["id"], "owner", repository, job["approval_digest"])
    assert service.get(job["id"], "owner")["status"] == "pending_approval"


def test_working_tree_changes_are_not_implicitly_included(repository, tmp_path):
    (repository / "app.py").write_text("UNCOMMITTED OWNER WORK", encoding="utf-8")
    assert b"return a - b" in snapshot(repository, head_sha(repository))["app.py"]
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    assert "UNCOMMITTED OWNER WORK" not in job["patch"]
    result = service.execute(job["id"], "owner", repository, job["approval_digest"])
    assert result["status"] == "validated"
    assert (repository / "app.py").read_text() == "UNCOMMITTED OWNER WORK"


def test_symlink_git_objects_and_snapshot_limits_are_rejected(repository, monkeypatch):
    import mammoth_os.owner_execution as execution
    sha = head_sha(repository)
    monkeypatch.setattr(execution, "MAX_FILES", 1)
    with pytest.raises(ExecutionError, match="3000 files"):
        snapshot(repository, sha)
    monkeypatch.setattr(execution, "MAX_FILES", 3000)
    monkeypatch.setattr(execution, "MAX_BYTES", 1)
    with pytest.raises(ExecutionError, match="32 MB"):
        snapshot(repository, sha)
    monkeypatch.setattr(execution, "MAX_BYTES", 32 * 1024 * 1024)
    oid = git(repository, "hash-object", "-w", "--stdin", input_bytes=b"app.py").decode().strip()
    git(repository, "update-index", "--add", "--cacheinfo", f"120000,{oid},link")
    git(repository, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "Symlink fixture")
    with pytest.raises(ExecutionError, match="Symlinks"):
        snapshot(repository, head_sha(repository))


def test_corrupt_records_block_owner_execution_without_crashing_platform(tmp_path):
    storage = tmp_path / "jobs"
    storage.mkdir()
    job_id = "exec-" + "a" * 24
    (storage / f"{job_id}.json").write_text("{broken", encoding="utf-8")
    service = OwnerExecution(storage, FakeExecutor(), enabled=True)
    assert service.capabilities()["isolation"]["ready"] is False
    with pytest.raises(ExecutionError, match="unreadable"):
        service.get(job_id, "owner")


def test_running_job_cancels_and_cannot_be_reapproved(repository, tmp_path):
    entered = threading.Event()
    class Waiting(FakeExecutor):
        def run(self, files, profile, cancelled, **kwargs):
            entered.set()
            assert cancelled.wait(5)
            return {"passed": False, "failure_code": "cancelled"}
    service = OwnerExecution(tmp_path / "jobs", Waiting(), enabled=True)
    job = prepared(service, repository)
    results = []
    thread = threading.Thread(target=lambda: results.append(service.execute(job["id"], "owner", repository, job["approval_digest"])))
    thread.start()
    assert entered.wait(5)
    service.cancel(job["id"], "owner")
    thread.join(10)
    assert results[0]["status"] == "cancelled"


def test_restart_marks_interrupted_work_failed_without_resuming(repository, tmp_path, monkeypatch):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    record = service._load(job["id"], "owner")
    record["status"] = "running"
    service._save(record)
    cleanup = []
    def fake_run(command, **kwargs):
        cleanup.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    restarted = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    assert restarted.get(job["id"], "owner")["failure_code"] == "worker_restart"
    assert len(cleanup) == 2 and all(command[:3] == ["docker", "rm", "-f"] for command in cleanup)


def test_restart_without_docker_blocks_execution_not_platform_startup(repository, tmp_path, monkeypatch):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    record = service._load(job["id"], "owner")
    record["status"] = "running"
    service._save(record)
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("Docker missing")
    monkeypatch.setattr(subprocess, "run", unavailable)
    restarted = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    assert restarted.get(job["id"], "owner")["failure_code"] == "cleanup_failed"
    assert restarted.capabilities()["isolation"]["ready"] is False
    with pytest.raises(ExecutionError, match="blocked"):
        restarted.prepare(repository, "explicit/repo", "owner", [{"path": "app.py", "content": "x"}],
                          base_sha=job["base_sha"], profile="python_unittest")


def test_expired_root_and_image_bound_approval(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    with pytest.raises(ExecutionError, match="mismatched"):
        service.execute(job["id"], "owner", tmp_path, job["approval_digest"])
    service.executor.image = "other@sha256:" + "0" * 64
    with pytest.raises(ExecutionError, match="mismatched"):
        service.execute(job["id"], "owner", repository, job["approval_digest"])
    service.executor.image = IMAGE
    record = service._load(job["id"], "owner")
    record["expires_at"] = 0
    service._save(record)
    with pytest.raises(ExecutionError, match="expired"):
        service.execute(job["id"], "owner", repository, job["approval_digest"])


def test_second_worker_never_recovers_live_job_and_can_cancel_it(repository, tmp_path):
    entered = threading.Event()
    class Waiting(FakeExecutor):
        def run(self, files, profile, cancelled, **kwargs):
            import time
            entered.set()
            deadline = time.monotonic() + 5
            while not cancelled.is_set() and time.monotonic() < deadline:
                time.sleep(.05)
            assert cancelled.is_set()
            return {"passed": False, "failure_code": "cancelled"}
    service = OwnerExecution(tmp_path / "jobs", Waiting(), enabled=True)
    job = prepared(service, repository)
    results = []
    thread = threading.Thread(target=lambda: results.append(service.execute(job["id"], "owner", repository, job["approval_digest"])))
    thread.start()
    assert entered.wait(5)
    other = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    assert other.get(job["id"], "owner")["status"] == "running"
    another = prepared(other, repository)
    with pytest.raises(ExecutionError, match="Another owner"):
        other.execute(another["id"], "owner", repository, another["approval_digest"])
    other.cancel(job["id"], "owner")
    thread.join(10)
    assert results[0]["status"] == "cancelled"


def test_api_requires_owner_and_explicit_repo(repository, tmp_path, monkeypatch):
    import api_server
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    monkeypatch.setattr(api_server, "_OWNER_EXECUTION", service)
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": token, "is_admin": token == "owner", "email": ""
    } if token in {"owner", "tenant"} else None)
    client = TestClient(api_server.app)
    for path in ["/api/owner-executions/capabilities", "/api/owner-executions/exec-" + "0" * 24]:
        assert client.get(path, headers={"Authorization": "Bearer tenant"}).status_code == 403
        assert client.get(path).status_code == 401
    assert client.post("/api/owner-executions", headers={"Authorization": "Bearer owner"}, json={}).status_code == 403
    for suffix in ("approve", "cancel"):
        assert client.post("/api/owner-executions/exec-" + "0" * 24 + "/" + suffix,
                           headers={"Authorization": "Bearer tenant"}, json={}).status_code == 403


def test_api_accepted_execution_saves_task_patch_and_truthful_approval(repository, tmp_path, monkeypatch):
    import api_server
    from mammoth_os.repo_access import RepoAccessPolicy
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    monkeypatch.setattr(api_server, "_OWNER_EXECUTION", service)
    monkeypatch.setattr(api_server, "_REPO_POLICY", RepoAccessPolicy(
        platform_root=repository, tenant_base=tmp_path / "tenants", registry_dir=tmp_path / "registry",
        platform_slugs={"owner/repo"},
    ))
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {"id": "owner", "is_admin": True, "email": ""} if token == "owner" else None)
    state, tasks, activity = {}, [], []
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda value: None)
    monkeypatch.setattr(api_server, "_load_tasks", lambda: tasks.copy())
    monkeypatch.setattr(api_server, "_save_tasks", lambda value: tasks.__setitem__(slice(None), value))
    monkeypatch.setattr(api_server, "_append_activity", lambda title, **kwargs: activity.append((title, kwargs)))
    client = TestClient(api_server.app)
    headers = {"Authorization": "Bearer owner"}
    capability = client.get("/api/owner-executions/capabilities?repo=owner/repo", headers=headers).json()
    assert capability["base_sha"] == head_sha(repository)
    response = client.post("/api/owner-executions", headers=headers, json={
        "repo_context": {"root": "owner/repo"}, "base_sha": capability["base_sha"], "profile": "python_unittest",
        "changes": [{"path": "app.py", "content": "def add(a, b):\n    return a + b\n"}],
    })
    assert response.status_code == 200, response.text
    job = response.json()["execution"]
    rejected = client.post(f"/api/owner-executions/{job['id']}/approve", headers=headers,
                           json={"repo_context": {"root": "owner/repo"}, "approval_digest": "wrong"})
    assert rejected.status_code == 409
    assert not any(item[1]["kind"] == "approval_resolved" for item in activity)
    result = client.post(f"/api/owner-executions/{job['id']}/approve", headers=headers,
                         json={"repo_context": {"root": "owner/repo"}, "approval_digest": job["approval_digest"]})
    assert result.status_code == 200 and result.json()["execution"]["status"] == "validated", result.text
    assert tasks[0]["details"]["source"] == "owner_execution"
    assert api_server._task_status_editable(tasks[0]) is False
    artifact = state["workspace_artifacts"][0]
    assert artifact["artifact_status"] == "draft" and artifact["category"] == "code"
    assert artifact["lineage"]["base_sha"] == capability["base_sha"]
    assert artifact["verification"]["candidate"]["passed"] is True
    assert artifact["quality"]["tests_are_independent"] is False
    assert artifact["body"] == result.json()["execution"]["patch"]
    git(repository, "apply", "--cached", "--check", "--whitespace=nowarn", "-", input_bytes=artifact["body"].encode())
    assert any(item[1]["kind"] == "approval_resolved" for item in activity)
    record = service._load(job["id"], "owner")
    record.update(status="failed", failure_code="worker_restart", error="Worker restarted.")
    service._save(record)
    recorded_task = api_server._decorate_task(tasks[0])
    assert recorded_task["status"] == "failed"  # Durable execution wins over stale task-file state.
    assert recorded_task["details"]["failure_code"] == "worker_restart"


def test_tool_visibility_approval_and_bounded_approval_identity(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    registry = ToolRegistry()
    register_owner_execution_tools(registry, service)
    assert registry.available(ToolContext(user_id="tenant", repo_root=repository)) == []
    assert registry.available(ToolContext(user_id="owner", is_admin=True)) == []
    ctx = ToolContext(user_id="owner", is_admin=True, repo_root=repository)
    result = asyncio.run(registry.invoke("owner_execution_prepare", {
        "base_sha": head_sha(repository), "profile": "python_unittest",
        "changes": [{"path": "app.py", "content": "x = 1\n" * 10000}],
    }, ctx))
    assert result["status"] == "ok" and result.get("truncated") is not True
    assert result["execution"]["approval_digest"]
    assert result["execution"]["patch_truncated"] is True
    runner = AgentRunner(registry, lambda: None, RunStore(tmp_path / "runs"))
    run = AgentRun(id="run-" + "a" * 16, user_id="owner", message="Validate", request={"approval_mode": "never"})
    assert runner._needs_approval(registry.get("owner_execution_run"), run) is True


def test_run_stop_cancels_owner_tool_and_records_evidence(repository, tmp_path):
    entered = threading.Event()
    class Waiting(FakeExecutor):
        def run(self, files, profile, cancelled, **kwargs):
            entered.set()
            assert cancelled.wait(5)
            return {"passed": False, "failure_code": "cancelled"}
    service = OwnerExecution(tmp_path / "jobs", Waiting(), enabled=True)
    job = prepared(service, repository)
    evidence = []
    async def record(result, run_id):
        evidence.append((result["status"], run_id))
    registry = ToolRegistry()
    register_owner_execution_tools(registry, service, record_execution=record)
    runner = AgentRunner(registry, lambda: None, RunStore(tmp_path / "runs"))
    run = AgentRun(id="run-" + "a" * 16, user_id="owner", message="Validate")
    async def exercise():
        async def consume():
            return [event async for event in runner._execute_tool(run, ToolContext(user_id="owner", is_admin=True, repo_root=repository),
                "owner_execution_run", {"execution_id": job["id"], "approval_digest": job["approval_digest"]})]
        worker = asyncio.create_task(consume())
        assert await asyncio.to_thread(entered.wait, 5)
        runner.cancel(run)
        events = await worker
        assert events[-1].data["result"]["execution"]["status"] == "cancelled"
    asyncio.run(exercise())
    assert evidence == [("cancelled", run.id)]
    assert service.get(job["id"], "owner")["status"] == "cancelled"


@pytest.mark.parametrize("missing_checkout", [False, True])
def test_restart_cleans_recorded_disposable_worktree(repository, tmp_path, monkeypatch, missing_checkout):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    record = service._load(job["id"], "owner")
    worktree = service.storage.resolve() / "worktrees" / job["id"] / "proposal"
    worktree.parent.mkdir(parents=True)
    git(repository, "worktree", "add", "--detach", "--no-checkout", str(worktree), record["base_sha"])
    if missing_checkout:
        (worktree / ".git").unlink()
        worktree.rmdir()
    record.update(status="running", worktree=str(worktree))
    service._save(record)
    original = subprocess.run
    def stop_containers(command, **kwargs):
        if command[0] == "docker":
            return subprocess.CompletedProcess(command, 0, "", "")
        return original(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", stop_containers)
    restarted = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    assert restarted.get(job["id"], "owner")["failure_code"] == "worker_restart"
    assert not worktree.parent.exists()
    assert git(repository, "worktree", "list", "--porcelain").count(b"worktree ") == 1


@pytest.mark.skipif(os.environ.get("MAMMOTH_TEST_OWNER_DOCKER") != "1", reason="Explicit Docker integration opt-in")
def test_real_docker_timeout_no_tests_and_bounded_output():
    import uuid
    executor = ContainerExecutor(os.environ.get("MAMMOTH_OWNER_EXEC_IMAGE", IMAGE), timeout=3)
    def check(files):
        return executor.run(files, "python_unittest", threading.Event(),
                            container_name="mammoth-owner-exec-" + uuid.uuid4().hex[:24] + "-candidate")
    empty = check({"tests/readme.txt": b"No tests"})
    assert empty["passed"] is False and empty["tests_detected"] is False
    timed = check({"tests/test_wait.py": b"import unittest,time\nclass Check(unittest.TestCase):\n def test_wait(self): time.sleep(20)\n"})
    assert timed["passed"] is False and timed["failure_code"] == "timeout"
    output = check({"tests/test_output.py": b"import unittest\nclass Check(unittest.TestCase):\n def test_output(self): print('x'*64000,flush=True)\n"})
    assert output["log_truncated"] is True and len(output["log"].encode()) <= 16000


@pytest.mark.skipif(os.environ.get("MAMMOTH_TEST_OWNER_DOCKER") != "1", reason="Explicit Docker integration opt-in")
def test_real_docker_baseline_candidate_and_isolation(repository, tmp_path):
    executor = ContainerExecutor(os.environ.get("MAMMOTH_OWNER_EXEC_IMAGE", IMAGE), timeout=20)
    assert executor.readiness()["ready"]
    service = OwnerExecution(tmp_path / "jobs", executor, enabled=True)
    job = prepared(service, repository)
    result = service.execute(job["id"], "owner", repository, job["approval_digest"])
    assert result["status"] == "validated", result
    assert result["baseline"]["passed"] is False
    assert result["candidate"]["passed"] is True
    assert result["candidate"]["isolation"] == "docker"
    files = {"tests/test_isolation.py": (
        b"import os,socket,unittest\n"
        b"class TestIsolation(unittest.TestCase):\n"
        b" def test_boundary(self):"
        b"\n  self.assertFalse(os.path.exists('/work/.git'))"
        b"\n  self.assertFalse(os.path.exists('/work/.env'))"
        b"\n  self.assertFalse(os.path.exists('/var/run/docker.sock'))"
        b"\n  self.assertEqual(os.getuid(),65534)"
        b"\n  with self.assertRaises(OSError): open('/input/mutate','w')"
        b"\n  with self.assertRaises(OSError): socket.create_connection(('1.1.1.1',443),timeout=1)\n"
    )}
    boundary = executor.run(files, "python_unittest", threading.Event(),
                            container_name="mammoth-owner-exec-" + "0" * 24 + "-candidate")
    assert boundary["passed"], boundary
