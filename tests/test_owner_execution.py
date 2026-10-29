import asyncio
import os
import subprocess
import threading
from pathlib import Path

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
    PROFILES,
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
        return {"ready": True, "profiles": {name: name == "python_unittest" for name in PROFILES}}
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


@pytest.mark.parametrize("mode", ["120000", "160000"])
@pytest.mark.parametrize("excluded", [True, False])
def test_snapshot_excludes_environment_entries_but_rejects_source_links(repository, mode, excluded):
    rel = "venv/lib64" if excluded else "source-link"
    oid = (git(repository, "hash-object", "-w", "--stdin", input_bytes=b"/outside-the-repo\n").decode().strip()
           if mode == "120000" else head_sha(repository))
    git(repository, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{rel}")
    git(repository, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "Add link fixture")
    if excluded:
        files = snapshot(repository, head_sha(repository))
        assert rel not in files and "app.py" in files
        assert b"/outside-the-repo" not in b"".join(files.values())
    else:
        with pytest.raises(ExecutionError, match=f"Unsupported source entry '{rel}'") as error:
            snapshot(repository, head_sha(repository))
        assert error.value.code == "unsupported_snapshot"


def test_prepare_rejects_unavailable_profile_without_freezing(repository, tmp_path):
    executor = FakeExecutor()
    service = OwnerExecution(tmp_path / "jobs", executor, enabled=True)
    assert service.capabilities()["isolation"]["profiles"]["node_test"] is False
    with pytest.raises(ExecutionError, match="unavailable in the pinned image") as error:
        service.prepare(repository, "owner/repo", "owner", [{"path": "app.py", "content": "x"}],
                        base_sha=head_sha(repository), profile="node_test")
    assert error.value.code == "profile_unavailable"
    assert not list(service.storage.glob("exec-*.json")) and not executor.calls


@pytest.mark.parametrize("probe_result", ["available", "invalid", "failure", "timeout"])
def test_image_probe_reports_actual_tools_and_cleans_up(monkeypatch, probe_result):
    import json
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "info":
            return subprocess.CompletedProcess(command, 0, stdout="linux\n", stderr="")
        if command[1] == "run":
            assert "--network=none" in command and "--read-only" in command and "--pull=never" in command
            assert "--user=65534:65534" in command and "--memory=256m" in command
            assert not any("mount" in arg for arg in command)
            if probe_result == "timeout":
                raise subprocess.TimeoutExpired(command, 15)
            return subprocess.CompletedProcess(command, 1 if probe_result == "failure" else 0,
                stdout="{}" if probe_result == "invalid" else json.dumps(
                    {name: name == "python_unittest" for name in PROFILES}), stderr="probe error")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    readiness = ContainerExecutor(IMAGE).readiness()
    assert readiness["ready"] is (probe_result == "available")
    if readiness["ready"]:
        assert readiness["profiles"] == {name: name == "python_unittest" for name in PROFILES}
    else:
        assert readiness["reason"]
    assert calls[-1][:3] == ["docker", "rm", "-f"]
    assert calls[-1][-1] == calls[2][calls[2].index("--name") + 1]


def test_exact_edits_use_committed_base_preserving_dirty_checkout_and_large_files(repository, tmp_path):
    source = "header\n" + ("unchanged line\n" * 10000) + "return a - b\n"
    (repository / "large.txt").write_bytes(source.encode())
    git(repository, "add", "large.txt")
    git(repository, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "Large file")
    (repository / "large.txt").write_text("dirty owner work\n", encoding="utf-8")
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = service.prepare(repository, "owner/repo", "owner",
                          [{"path": "large.txt", "edits": [{"old": "return a - b", "new": "return a + b"}]}],
                          base_sha=head_sha(repository), profile="python_unittest")
    record = service._load(job["id"], "owner")
    assert record["changes"][0]["content"] == source.replace("return a - b", "return a + b")
    assert (repository / "large.txt").read_text() == "dirty owner work\n"
    assert len(job["patch"]) < 500
    with pytest.raises(ExecutionError, match="was not found"):
        service.prepare(repository, "owner/repo", "owner",
                        [{"path": "large.txt", "edits": [{"old": "dirty owner work", "new": "oops"}]}],
                        base_sha=head_sha(repository), profile="python_unittest")


@pytest.mark.parametrize("change", [
    {"path": "app.py", "content": "x", "edits": [{"old": "a", "new": "b"}]},
    {"path": "app.py", "edits": []},
    {"path": "app.py", "edits": [{"old": "", "new": "x"}]},
    {"path": "app.py", "edits": [{"old": "a", "new": "x"}]},
    {"path": "missing.py", "edits": [{"old": "x", "new": "y"}]},
    {"path": ".env", "edits": [{"old": "SECRET", "new": "x"}]},
])
def test_invalid_exact_edits_never_freeze_a_proposal(repository, tmp_path, change):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    with pytest.raises(ExecutionError):
        service.prepare(repository, "owner/repo", "owner", [change],
                        base_sha=head_sha(repository), profile="python_unittest")
    assert not list(service.storage.glob("exec-*.json"))


@pytest.mark.parametrize("standard_ready", [True, False])
def test_frontend_profile_uses_separate_pinned_executor(repository, tmp_path, standard_ready):
    class Standard(FakeExecutor):
        def readiness(self):
            return super().readiness() if standard_ready else {"ready": False, "reason": "Standard image missing."}
    class Frontend(FakeExecutor):
        image = "sha256:" + "1" * 64
        def readiness(self):
            return {"ready": True, "profiles": {name: name in {"ui_build", "ui_component"} for name in PROFILES}}
    executor = Frontend()
    service = OwnerExecution(tmp_path / "jobs", Standard(), enabled=True, frontend_executor=executor)
    capabilities = service.capabilities()
    assert capabilities["isolation"]["ready"] is True
    assert capabilities["isolation"]["profiles"]["python_unittest"] is standard_ready
    assert capabilities["isolation"]["profiles"]["ui_build"] is True
    job = service.prepare(repository, "owner/repo", "owner",
                          [{"path": "app.py", "edits": [{"old": "return a - b", "new": "return a + b"}]}],
                          base_sha=head_sha(repository), profile="ui_build")
    assert job["image"] == executor.image
    checked = service.execute(job["id"], "owner", repository, job["approval_digest"])
    assert checked["status"] == "validated" and len(executor.calls) == 2
    assert not service.executor.calls
    executor.image = "sha256:" + "2" * 64
    with pytest.raises(ExecutionError):
        service.apply(job["id"], "owner", repository, checked["application"]["approval_digest"])


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
    with pytest.raises(ExecutionError, match="operator-reviewed"):
        prepared(service, repository)
    assert not list(service.storage.glob("exec-*.json"))


def validated(service, repository):
    job = prepared(service, repository)
    return service.execute(job["id"], "owner", repository, job["approval_digest"])


def test_approved_application_creates_exact_branch_without_touching_checkout_or_index(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = validated(service, repository)
    before_head = head_sha(repository)
    (repository / "app.py").write_text("UNCOMMITTED OWNER WORK\n", encoding="utf-8")
    (repository / "staged.txt").write_text("staged work", encoding="utf-8")
    git(repository, "add", "staged.txt")
    index_before = git(repository, "write-tree")
    result = service.apply(job["id"], "owner", repository, job["application"]["approval_digest"])
    application = result["application"]
    assert application["status"] == "applied"
    assert head_sha(repository) == before_head
    assert (repository / "app.py").read_text() == "UNCOMMITTED OWNER WORK\n"
    assert git(repository, "write-tree") == index_before
    commit = application["commit_sha"]
    assert git(repository, "show", f"{commit}:app.py") == b"def add(a, b):\n    return a + b\n"
    assert git(repository, "show", f"{commit}:.env") == git(repository, "show", f"{before_head}:.env")
    assert git(repository, "rev-parse", f"{commit}^").decode().strip() == before_head
    assert git(repository, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).decode().splitlines() == ["app.py"]
    assert git(repository, "rev-parse", f"refs/heads/{application['branch']}").decode().strip() == commit
    with pytest.raises(ExecutionError, match="already used"):
        service.apply(job["id"], "owner", repository, job["application"]["approval_digest"])


@pytest.mark.parametrize("reason", ["wrong_digest", "validation_digest", "expired", "wrong_root", "wrong_owner",
                                  "changed_head", "changed_image", "regression", "tampered_changes", "disabled"])
def test_branch_application_fails_closed(repository, tmp_path, reason):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = validated(service, repository)
    digest, owner, root = job["application"]["approval_digest"], "owner", repository
    record = service._load(job["id"], "owner")
    if reason == "wrong_digest":
        digest = "0" * 64
    elif reason == "validation_digest":
        digest = job["approval_digest"]
    elif reason == "expired":
        record["application"]["expires_at"] = 0
    elif reason == "wrong_root":
        root = tmp_path
    elif reason == "wrong_owner":
        owner = "tenant"
    elif reason == "changed_head":
        git(repository, "-c", "user.name=Test", "-c", "user.email=t@example.test", "commit", "--allow-empty", "-m", "New head")
    elif reason == "changed_image":
        service.executor.image = "different@sha256:" + "0" * 64
    elif reason == "regression":
        record["regression"] = True
    elif reason == "tampered_changes":
        record["changes"][0]["content"] = "pass\n"
    elif reason == "disabled":
        service.enabled = False
    service._save(record)
    with pytest.raises(ExecutionError):
        service.apply(job["id"], owner, root, digest)
    assert not git(repository, "for-each-ref", "--format=%(refname)", "refs/heads/mammoth/owner")


def test_unvalidated_proposal_cannot_be_applied(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = prepared(service, repository)
    with pytest.raises(ExecutionError, match="unavailable"):
        service.apply(job["id"], "owner", repository, job["approval_digest"])


@pytest.mark.parametrize("ref_created", [False, True])
def test_application_restart_reconciles_intent_without_reapplying(repository, tmp_path, monkeypatch, ref_created):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = validated(service, repository)
    original_git = git
    def interrupt(root, *args, **kwargs):
        if args[0] == "update-ref":
            if ref_created:
                original_git(root, *args, **kwargs)
            raise OSError("Simulated worker interruption")
        return original_git(root, *args, **kwargs)
    monkeypatch.setattr("mammoth_os.owner_execution.git", interrupt)
    with pytest.raises(ExecutionError, match="did not finish cleanly"):
        service.apply(job["id"], "owner", repository, job["application"]["approval_digest"])
    monkeypatch.setattr("mammoth_os.owner_execution.git", original_git)
    restarted = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    recovered = restarted.get(job["id"], "owner")["application"]
    assert recovered["status"] == ("applied" if ref_created else "failed")
    with pytest.raises(ExecutionError, match="already used"):
        restarted.apply(job["id"], "owner", repository, job["application"]["approval_digest"])


def test_existing_owner_branch_is_never_overwritten(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = validated(service, repository)
    original = head_sha(repository)
    git(repository, "update-ref", f"refs/heads/{job['application']['branch']}", original)
    with pytest.raises(ExecutionError, match="did not finish cleanly"):
        service.apply(job["id"], "owner", repository, job["application"]["approval_digest"])
    assert git(repository, "rev-parse", f"refs/heads/{job['application']['branch']}").decode().strip() == original


def test_application_preserves_exact_multifile_content_and_empty_new_files(repository, tmp_path):
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    changes = [{"path": "app.py", "content": "def add(a, b):\n    return a + b"},
               {"path": "new module.txt", "content": "no final newline"},
               {"path": "empty file.txt", "content": ""}]
    job = service.prepare(repository, "explicit/repo", "owner", changes,
                          base_sha=head_sha(repository), profile="python_unittest")
    checked = service.execute(job["id"], "owner", repository, job["approval_digest"])
    applied = service.apply(job["id"], "owner", repository, checked["application"]["approval_digest"])
    for change in changes:
        assert git(repository, "show", f"{applied['application']['branch']}:{change['path']}") == change["content"].encode()
    assert "new file mode 100644" in job["patch"]


@pytest.mark.parametrize("approved", [False, True])
def test_mind_application_pauses_for_user_decision_even_in_never_approval_mode(repository, tmp_path, approved):
    import json
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = validated(service, repository)
    class Model:
        model = "scripted"
        def __init__(self):
            self.called = False
        async def generate(self, prompt, **kwargs):
            if not self.called:
                self.called = True
                return json.dumps({"reasoning": "Validation passed; request the separate branch approval.",
                                   "tool": "owner_execution_apply", "args": {
                                       "execution_id": job["id"], "approval_digest": job["application"]["approval_digest"]}})
            return json.dumps({"final": "Reviewed the recorded branch application result."})
    model = Model()
    registry = ToolRegistry()
    register_owner_execution_tools(registry, service)
    runner = AgentRunner(registry, lambda: model, RunStore(tmp_path / "runs"))
    run = AgentRun(id=AgentRun.new_id(), user_id="owner", message="Apply the validated changes",
                   request={"approval_mode": "never"})
    ctx = ToolContext(user_id="owner", is_admin=True, repo_root=repository)
    async def exercise():
        initial = [event async for event in runner.start(run, ctx)]
        assert run.status == "awaiting_approval"
        assert initial[-1].type == "run.awaiting_approval"
        assert not git(repository, "for-each-ref", "--format=%(refname)", "refs/heads/mammoth/owner")
        decision = run.pending_approval["id"]
        return [event async for event in runner.resume(run, ctx, approval_id=decision, approved=approved)]
    asyncio.run(exercise())
    refs = git(repository, "for-each-ref", "--format=%(refname)", "refs/heads/mammoth/owner")
    assert bool(refs) == approved
    assert service.get(job["id"], "owner")["application"]["status"] == ("applied" if approved else "ready")
    assert run.status == ("completed" if approved else "partial")
    assert run.progress()["goal"] == "applied"
    assert run.progress()["goal_met"] is approved
    if approved:
        assert run.progress()["executions"][0]["application"]["commit_sha"]
    else:
        assert run.progress()["blocker"] == "User rejected this action."
    assert "separate approval" in runner._final_prompt(run, ctx)


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
    for suffix in ("approve", "cancel", "apply"):
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
    application = result.json()["execution"]["application"]
    applied = client.post(f"/api/owner-executions/{job['id']}/apply", headers=headers,
                         json={"repo_context": {"root": "owner/repo"}, "approval_digest": application["approval_digest"]})
    assert applied.status_code == 200, applied.text
    assert applied.json()["execution"]["application"]["status"] == "applied"
    assert state["workspace_artifacts"][0]["verification"]["application"]["status"] == "applied"
    assert state["workspace_artifacts"][0]["lineage"]["branch"] == application["branch"]
    assert any(item[1]["kind"] == "patch_applied" for item in activity)
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
    assert runner._needs_approval(registry.get("owner_execution_apply"), run) is True


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
    oid = git(repository, "hash-object", "-w", "--stdin", input_bytes=b"/outside-the-repo\n").decode().strip()
    git(repository, "update-index", "--add", "--cacheinfo", f"120000,{oid},venv/lib64")
    git(repository, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "Excluded environment link")
    executor = ContainerExecutor(os.environ.get("MAMMOTH_OWNER_EXEC_IMAGE", IMAGE), timeout=20)
    readiness = executor.readiness()
    assert readiness["ready"] and readiness["profiles"]["python_unittest"]
    service = OwnerExecution(tmp_path / "jobs", executor, enabled=True)
    job = prepared(service, repository)
    result = service.execute(job["id"], "owner", repository, job["approval_digest"])
    assert result["status"] == "validated", result
    assert result["baseline"]["passed"] is False
    assert result["candidate"]["passed"] is True
    assert result["candidate"]["isolation"] == "docker"
    applied = service.apply(job["id"], "owner", repository, result["application"]["approval_digest"])
    assert applied["application"]["status"] == "applied"
    assert git(repository, "show", f"{applied['application']['branch']}:venv/lib64") == b"/outside-the-repo\n"
    assert git(repository, "show", f"{applied['application']['branch']}:app.py").decode() == "def add(a, b):\n    return a + b\n"
    assert head_sha(repository) == job["base_sha"]
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


@pytest.mark.skipif(not os.environ.get("MAMMOTH_TEST_OWNER_UI_IMAGE"), reason="Reviewed frontend image integration opt-in")
def test_real_frontend_build_rendering_regressions_and_approved_branch(tmp_path):
    import json
    import uuid
    source = Path(__file__).parents[1]
    files = snapshot(source, head_sha(source))
    for rel in files:
        if rel.startswith(("ui/mad-architecht-command-center/", "packages/mammoth-paths/")):
            files[rel] = (source / rel).read_bytes()
    executor = ContainerExecutor(os.environ["MAMMOTH_TEST_OWNER_UI_IMAGE"], timeout=120)

    def check(content, profile):
        return executor.run(content, profile, threading.Event(),
                            container_name="mammoth-owner-exec-" + uuid.uuid4().hex[:24] + "-candidate")

    assert check(files, "ui_build")["passed"]
    assert check(files, "ui_component")["passed"]
    rel = "ui/mad-architecht-command-center/src/components/TrustSurfaces.jsx"
    broken = {**files, rel: files[rel] + b"\nconst = invalid syntax;\n"}
    assert check(broken, "ui_build")["passed"] is False
    old = b"const percentage = Math.round(score * 100)"
    assert files[rel].count(old) == 1
    wrong = {**files, rel: files[rel].replace(old, b"const percentage = 91")}
    assert check(wrong, "ui_component")["passed"] is False
    manifest_path = "ui/mad-architecht-command-center/package.json"
    manifest = json.loads(files[manifest_path])
    manifest["version"] = "0.0.0-unreviewed"
    mismatch = check({**files, manifest_path: json.dumps(manifest).encode()}, "ui_build")
    assert mismatch["passed"] is False and "Dependency manifest changed" in mismatch["log"]

    root = tmp_path / "frontend-repo"
    root.mkdir()
    git(root, "init")
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "Frontend fixture")
    base = head_sha(root)
    dirty = files[rel] + b"\n// local uncommitted content\n"
    (root / rel).write_bytes(dirty)
    index = git(root, "ls-files", "--stage")
    service = OwnerExecution(tmp_path / "frontend-jobs", FakeExecutor(), enabled=True, frontend_executor=executor)
    job = service.prepare(root, "owner/frontend", "owner", [{"path": rel, "edits": [{
        "old": old.decode(), "new": "const percentage = Math.round(100 * score)",
    }]}], base_sha=base, profile="ui_component")
    checked = service.execute(job["id"], "owner", root, job["approval_digest"])
    assert checked["status"] == "validated", checked
    assert checked["baseline"]["passed"] and checked["candidate"]["passed"]
    applied = service.apply(job["id"], "owner", root, checked["application"]["approval_digest"])
    assert applied["application"]["status"] == "applied"
    assert b"Math.round(100 * score)" in git(root, "show", f"{applied['application']['branch']}:{rel}")
    assert head_sha(root) == base and (root / rel).read_bytes() == dirty
    assert git(root, "ls-files", "--stage") == index
