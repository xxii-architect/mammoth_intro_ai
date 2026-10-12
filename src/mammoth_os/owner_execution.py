"""Approval-bound owner proposals validated in disposable, network-free containers.

Containers share the host kernel. This opt-in pilot is not a hostile-code VM,
and never merges, commits or pushes a proposal into the selected repository.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mammoth_os.agent_loop.builtin_tools import SKIP_DIRS, safe_repo_path

CONTRACT = "mammoth.owner-execution.v1"
PROFILES = {
    "python_unittest": ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
    "python_pytest": ["python", "-m", "pytest", "tests", "-q"],
    "node_test": ["node", "--test"],
}
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 3000
MAX_CHANGE_BYTES = 500_000
MAX_PATCH_BYTES = 1_000_000
LOG_BYTES = 16_000
APPROVAL_TTL = 900
JOB_RE = re.compile(r"^exec-[a-f0-9]{24}$")
IMAGE_RE = re.compile(r"^[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}$")


class ExecutionError(Exception):
    def __init__(self, message: str, code: str = "execution_failed", status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


class ExecutionLease:
    """OS-released exclusive lease; parallel API workers cannot reuse an approval."""
    def __init__(self, storage: Path, *, name: str = "worker.lock", blocking: bool = False):
        self.stream = (storage / name).open("a+b")
        self.stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError as exc:
            self.stream.close()
            raise ExecutionError("Another owner validation is running.", "execution_busy", 409) from exc

    def close(self) -> None:
        if sys.platform == "win32":
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        self.stream.close()


class ExecutionCancellation(threading.Event):
    def __init__(self, check):
        super().__init__()
        self.check = check

    def is_set(self) -> bool:
        return super().is_set() or self.check()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    # Do not inherit git credentials, alternate object directories, or injected config.
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "HOME") if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "--no-pager", "-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false",
         "-c", "core.autocrlf=false", *args], cwd=root, env=env, capture_output=True, timeout=30, input=input_bytes, check=False,
    )
    if result.returncode:
        raise ExecutionError("Git snapshot operation failed: " + result.stderr.decode(errors="replace")[:400])
    return result.stdout


def head_sha(root: Path) -> str:
    value = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40,64}", value):
        raise ExecutionError("Selected repository has no valid HEAD.", "invalid_repository")
    return value


def validate_changes(changes: Any, root: Path) -> list[dict[str, str]]:
    if not isinstance(changes, list) or not 1 <= len(changes) <= 20:
        raise ExecutionError("Supply 1-20 explicit file changes.", "invalid_changes")
    normalized = []
    seen = set()
    size = 0
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"path", "content"}:
            raise ExecutionError("Each change requires exactly path and content.", "invalid_changes")
        rel, content = change["path"], change["content"]
        if not isinstance(rel, str) or not isinstance(content, str) or "\x00" in rel or "\x00" in content:
            raise ExecutionError("Changes must contain text paths and text content.", "invalid_changes")
        rel = rel.replace("\\", "/")
        parts = rel.split("/")
        if (safe_repo_path(root, rel) is None or any(part in SKIP_DIRS for part in parts)
                or any(part in {"", ".", ".."} for part in parts)
                or any(ord(char) < 32 for char in rel)):
            raise ExecutionError(f"Path is not permitted: {rel}", "invalid_path")
        if rel.casefold() in seen:
            raise ExecutionError("Duplicate change paths are not permitted.", "invalid_changes")
        seen.add(rel.casefold())
        size += len(content.encode())
        normalized.append({"path": rel, "content": content})
    if size > MAX_CHANGE_BYTES:
        raise ExecutionError("Proposal exceeds the 500 KB change limit.", "too_large")
    return normalized


def snapshot(root: Path, sha: str) -> dict[str, bytes]:
    # Read objects, not the working tree. No checkout hooks, filters or submodules run.
    listing = git(root, "ls-tree", "-r", "-l", "-z", sha)
    entries = listing.split(b"\0")
    paths: list[tuple[str, str, int]] = []
    total = 0
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid, size = metadata.decode().split()
        rel = path.decode("utf-8", errors="strict")
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ExecutionError("Symlinks and submodules are not supported by isolated execution.", "unsupported_snapshot")
        if safe_repo_path(root, rel) is None or any(part in SKIP_DIRS for part in rel.split("/")):
            continue
        length = int(size)
        total += length
        if total > MAX_BYTES or len(paths) >= MAX_FILES:
            raise ExecutionError("Repository snapshot exceeds 32 MB or 3000 files.", "too_large")
        paths.append((rel, oid, length))
    if not paths:
        raise ExecutionError("Selected revision has no permitted source files.", "empty_snapshot")
    data = io.BytesIO(git(root, "cat-file", "--batch", input_bytes="".join(oid + "\n" for _, oid, _ in paths).encode()))
    files = {}
    for rel, oid, length in paths:
        if data.readline().decode().split() != [oid, "blob", str(length)]:
            raise ExecutionError("Git object batch did not match the approved tree.", "invalid_snapshot")
        content = data.read(length)
        if len(content) != length or data.read(1) != b"\n":
            raise ExecutionError("Git snapshot was incomplete.", "invalid_snapshot")
        files[rel] = content
    return files


def patch_text(before: dict[str, bytes], changes: list[dict[str, str]]) -> str:
    chunks: list[str] = []
    for change in changes:
        rel = change["path"]
        try:
            original = before.get(rel, b"").decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExecutionError("Binary files cannot be changed by this text proposal.", "invalid_changes") from exc
        lines = difflib.unified_diff(
            original.splitlines(keepends=True), change["content"].splitlines(keepends=True),
            fromfile=f"a/{rel}" if rel in before else "/dev/null", tofile=f"b/{rel}",
        )
        chunks.extend(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)
    return "".join(chunks)


class ContainerExecutor:
    def __init__(self, image: str, *, timeout: int = 60):
        self.image, self.timeout = image, timeout

    def readiness(self) -> dict[str, Any]:
        if not IMAGE_RE.fullmatch(self.image):
            return {"ready": False, "reason": "Set MAMMOTH_OWNER_EXEC_IMAGE to an operator-reviewed image@sha256:digest."}
        try:
            server = subprocess.run(["docker", "info", "--format", "{{.OSType}}"], capture_output=True, text=True, timeout=10, check=False)
            image = subprocess.run(["docker", "image", "inspect", self.image], capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {"ready": False, "reason": "Docker daemon unavailable. Host fallback is forbidden."}
        if server.returncode or server.stdout.strip() != "linux" or image.returncode:
            return {"ready": False, "reason": "A Linux Docker daemon and the pinned local image are required; automatic image pulls are disabled."}
        return {"ready": True, "reason": "Pinned Linux image available.", "image": self.image}

    def run(self, files: dict[str, bytes], profile: str, cancelled: threading.Event, *, container_name: str) -> dict[str, Any]:
        readiness = self.readiness()
        if not readiness["ready"]:
            raise ExecutionError(readiness["reason"], "isolation_unavailable", 503)
        if not re.fullmatch(r"mammoth-owner-exec-[a-f0-9]{24}-(baseline|candidate)", container_name):
            raise ExecutionError("Invalid isolated container identity.", "invalid_execution")
        name = container_name
        started = time.monotonic()
        # The only host mount is read-only. Test code writes exclusively to bounded tmpfs.
        with tempfile.TemporaryDirectory(prefix="mammoth-exec-input-") as folder:
            directory = Path(folder)
            archive = directory / "source.tar"
            with tarfile.open(archive, "w") as stream:
                for rel, data in files.items():
                    info = tarfile.TarInfo(rel)
                    info.size, info.mode = len(data), 0o644
                    stream.addfile(info, io.BytesIO(data))
            archive.chmod(0o644)
            # Image entrypoint is ignored; this trusted launcher copies our vetted archive.
            launcher = (
                "import os,tarfile;"
                "tarfile.open('/input/source.tar').extractall('/work',filter='data');"
                "os.chdir('/work');os.execvp(" + repr(PROFILES[profile][0]) + "," + repr(PROFILES[profile]) + ")"
            )
            command = [
                "docker", "run", "--rm", "--init", "--pull=never", "--name", name, "--network=none",
                "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--user=65534:65534", "--pids-limit=64", "--memory=256m", "--memory-swap=256m",
                "--cpus=1", "--ulimit=nofile=256:256", "--ulimit=fsize=16777216:16777216",
                "--log-driver=none", "--tmpfs=/work:rw,nosuid,nodev,size=64m,mode=1777",
                "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
                "--mount", f"type=bind,source={archive},target=/input/source.tar,readonly",
                "--workdir=/work", "--env=HOME=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1",
                "--entrypoint=python", self.image, "-I", "-c", launcher,
            ]
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = bytearray()
            truncated = threading.Event()

            def drain() -> None:
                stdout = proc.stdout
                if stdout is None:
                    return
                for chunk in iter(lambda: stdout.read(4096), b""):
                    room = max(0, LOG_BYTES - len(output))
                    output.extend(chunk[:room])
                    if len(chunk) > room:
                        truncated.set()

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            reason = ""
            cleanup_error = ""
            try:
                while proc.poll() is None:
                    if cancelled.is_set():
                        reason = "cancelled"
                        break
                    if time.monotonic() - started >= self.timeout:
                        reason = "timeout"
                        break
                    time.sleep(0.05)
            finally:
                # Always stop exactly this container, never by broad process/container name.
                try:
                    removed = subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=15, check=False)
                    if removed.returncode and "No such container" not in removed.stderr:
                        cleanup_error = "Container cleanup failed; operator intervention required."
                except (OSError, subprocess.SubprocessError) as exc:
                    cleanup_error = f"Container cleanup failed; operator intervention required: {exc}"
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait(timeout=10)
                    reader.join(timeout=5)
                    if proc.stdout:
                        proc.stdout.close()
            log = output.decode(errors="replace")
            # unittest returns zero when it discovers no tests: that is not verification.
            collected = profile != "python_unittest" or bool(re.search(r"Ran [1-9][0-9]* tests?", log))
            if profile == "node_test":
                collected = bool(re.search(r"(?:# tests |ℹ tests )[1-9][0-9]*", log))
            if profile == "python_pytest":
                collected = bool(re.search(r"[1-9][0-9]* passed", log))
            passed = proc.returncode == 0 and collected and not reason and not cleanup_error
            test_results = dict(re.findall(r"^test\S+ \(([^)\r\n]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\r\n]*)$", log, re.MULTILINE))
            return {"passed": passed, "returncode": proc.returncode, "log": log,
                    "test_results": test_results,
                    "log_truncated": truncated.is_set(), "tests_detected": collected,
                    "failure_code": reason or ("cleanup_failed" if cleanup_error else "" if passed else "checks_failed"),
                    "error": cleanup_error, "duration_ms": round((time.monotonic() - started) * 1000),
                    "profile": profile, "command": PROFILES[profile], "image": self.image, "isolation": "docker"}


class OwnerExecution:
    def __init__(self, storage: Path, executor: ContainerExecutor, *, enabled: bool = False):
        self.storage, self.executor, self.enabled = storage, executor, enabled
        self.lock = threading.RLock()
        self.active: dict[str, threading.Event] = {}
        self.recovery_error = ""
        self.storage.mkdir(parents=True, exist_ok=True)
        # Never resume processes or reuse an approval after a worker restart.
        try:
            lease = ExecutionLease(storage)
        except ExecutionError:
            lease = None  # A live worker owns the records; do not recover its jobs.
        if lease:
            try:
                self._recover()
            finally:
                lease.close()

    def _recover(self) -> None:
        for path in self.storage.glob("exec-*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.recovery_error = "An execution record is unreadable; owner execution is blocked until operator repair."
                continue
            if (not isinstance(record, dict) or record.get("id") != path.stem
                    or not JOB_RE.fullmatch(path.stem) or not isinstance(record.get("owner_id"), str)
                    or not isinstance(record.get("root"), str)
                    or not isinstance(record.get("status"), str)
                    or record.get("status") not in {"pending_approval", "running", "validated", "failed", "cancelled"}):
                self.recovery_error = "An execution record has invalid metadata; owner execution is blocked until operator repair."
                continue
            if record.get("status") != "running" and record.get("failure_code") != "cleanup_failed":
                continue
            for phase in ("baseline", "candidate"):
                try:
                    removed = subprocess.run(["docker", "rm", "-f", f"mammoth-owner-{record['id']}-{phase}"],
                                             capture_output=True, text=True, timeout=15, check=False)
                    if removed.returncode and "No such container" not in removed.stderr:
                        self.recovery_error = "Restart recovery could not stop an isolated container; owner execution is blocked."
                except (OSError, subprocess.TimeoutExpired):
                    self.recovery_error = "Restart recovery requires Docker to stop interrupted containers; owner execution is blocked."
            record.update(status="failed", error=self.recovery_error or "Worker restarted; inspect execution evidence before retrying.",
                          failure_code="cleanup_failed" if self.recovery_error else "worker_restart")
            try:
                self._cleanup_worktree(record)
            except (ExecutionError, OSError) as exc:
                self.recovery_error = f"Restart worktree cleanup failed; owner execution is blocked: {exc}"
                record.update(error=self.recovery_error, failure_code="cleanup_failed")
            self._save(record)

    def _cleanup_worktree(self, record: dict[str, Any]) -> None:
        if not record.get("worktree"):
            return
        expected = self.storage.resolve() / "worktrees" / record["id"] / "proposal"
        if Path(record["worktree"]) != expected:
            raise ExecutionError("Unexpected worktree recovery path.", "cleanup_failed")
        entries = git(Path(record["root"]), "worktree", "list", "--porcelain", "-z").split(b"\0")
        registered = any(Path(entry[9:].decode()) == expected for entry in entries if entry.startswith(b"worktree "))
        if registered:
            git(Path(record["root"]), "worktree", "remove", "--force", str(expected))
        elif expected.exists():
            expected.rmdir()
        if expected.parent.exists():
            expected.parent.rmdir()

    def _path(self, job_id: str) -> Path:
        if not JOB_RE.fullmatch(job_id):
            raise ExecutionError("Execution not found.", "not_found", 404)
        return self.storage / f"{job_id}.json"

    def _save(self, record: dict[str, Any]) -> None:
        path = self._path(record["id"])
        lease = ExecutionLease(self.storage, name="state.lock", blocking=True)
        try:
            if path.exists():
                previous = json.loads(path.read_text(encoding="utf-8"))
                if previous["status"] == "cancelled" and record.get("failure_code") != "cleanup_failed":
                    record["status"] = "cancelled"
                elif record["status"] == "cancelled" and previous["status"] not in {"pending_approval", "running"}:
                    record.clear()
                    record.update(previous)
            record["updated_at"] = stamp()
            temporary = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
            temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            lease.close()

    def _load(self, job_id: str, user_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.exists():
            raise ExecutionError("Execution not found.", "not_found", 404)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExecutionError("Execution record is unreadable; operator repair is required.", "storage_failed", 503) from exc
        if (not isinstance(record, dict) or record.get("id") != job_id or not isinstance(record.get("owner_id"), str)
                or not isinstance(record.get("status"), str)
                or record["status"] not in {"pending_approval", "running", "validated", "failed", "cancelled"}):
            raise ExecutionError("Execution record has invalid metadata; operator repair is required.", "storage_failed", 503)
        if record["owner_id"] != user_id:
            raise ExecutionError("Execution not found.", "not_found", 404)
        return record

    @staticmethod
    def public(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key not in {"root", "changes", "snapshot_digest", "worktree"}}

    def capabilities(self) -> dict[str, Any]:
        return {"contract": CONTRACT, "enabled": self.enabled,
                "profiles": list(PROFILES), "limits": {"timeout_s": self.executor.timeout, "memory_mb": 256,
                    "snapshot_bytes": MAX_BYTES, "files": MAX_FILES, "change_bytes": MAX_CHANGE_BYTES, "patch_bytes": MAX_PATCH_BYTES},
                "isolation": {"ready": False, "reason": self.recovery_error} if self.recovery_error else
                    self.executor.readiness() if self.enabled else {"ready": False, "reason": "Owner execution pilot is disabled."},
                "automatic_merge": False, "automatic_push": False, "benchmark_gated_autonomy": False}

    def prepare(self, root: Path, repo_ref: str, user_id: str, changes: Any, *, base_sha: str, profile: str) -> dict[str, Any]:
        if not self.enabled:
            raise ExecutionError("Owner execution pilot is disabled.", "execution_disabled", 503)
        if self.recovery_error:
            raise ExecutionError(self.recovery_error, "cleanup_failed", 503)
        if not isinstance(profile, str) or profile not in PROFILES:
            raise ExecutionError("Unknown approved test profile.", "invalid_profile")
        if head_sha(root) != base_sha:
            raise ExecutionError("Repository HEAD changed. Prepare a new proposal.", "stale_base", 409)
        normalized = validate_changes(changes, root)
        files = snapshot(root, base_sha)
        patch = patch_text(files, normalized)
        if not patch:
            raise ExecutionError("Proposal makes no changes.", "empty_patch")
        if len(patch.encode()) > MAX_PATCH_BYTES:
            raise ExecutionError("Rendered patch exceeds the 1 MB evidence limit.", "too_large")
        record = {
            "contract": CONTRACT, "id": "exec-" + uuid.uuid4().hex[:24], "owner_id": user_id,
            "root": str(root), "repo": repo_ref, "base_sha": base_sha, "profile": profile,
            "changes": normalized, "patch": patch, "snapshot_digest": fingerprint({k: hashlib.sha256(v).hexdigest() for k, v in files.items()}),
            "image": self.executor.image, "status": "pending_approval", "created_at": stamp(),
            "expires_at": time.time() + APPROVAL_TTL,
        }
        record["approval_digest"] = fingerprint({key: record[key] for key in ("repo", "base_sha", "profile", "changes", "image", "snapshot_digest")})
        with self.lock:
            self._save(record)
        return self.public(record)

    def get(self, job_id: str, user_id: str) -> dict[str, Any]:
        with self.lock:
            return self.public(self._load(job_id, user_id))

    def cancel(self, job_id: str, user_id: str) -> dict[str, Any]:
        with self.lock:
            record = self._load(job_id, user_id)
            if record["status"] in {"pending_approval", "running"}:
                record["status"] = "cancelled"
                self._save(record)
                if job_id in self.active:
                    self.active[job_id].set()
            return self.public(record)

    def execute(self, job_id: str, user_id: str, root: Path, approval_digest: str, *,
                on_started: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise ExecutionError("Owner execution pilot is disabled.", "execution_disabled", 503)
        if self.recovery_error:
            raise ExecutionError(self.recovery_error, "cleanup_failed", 503)
        with self.lock:
            record = self._load(job_id, user_id)
            if (record["status"] != "pending_approval" or record["approval_digest"] != approval_digest
                    or record["root"] != str(root) or record["image"] != self.executor.image
                    or time.time() > record["expires_at"]):
                raise ExecutionError("Approval is expired, mismatched, or already used.", "stale_approval", 409)
            if self.active:
                raise ExecutionError("Another owner validation is running; retry after it finishes.", "execution_busy", 409)
            if head_sha(root) != record["base_sha"]:
                raise ExecutionError("Repository HEAD changed. Prepare and approve a new proposal.", "stale_base", 409)
            readiness = self.executor.readiness()
            if not readiness["ready"]:
                raise ExecutionError(readiness["reason"], "isolation_unavailable", 503)
            lease = ExecutionLease(self.storage)
            try:
                self._recover()
                if self.recovery_error:
                    raise ExecutionError(self.recovery_error, "cleanup_failed", 503)
                # Another worker may have completed this approval while we probed Docker.
                record = self._load(job_id, user_id)
                if (record["status"] != "pending_approval" or record["approval_digest"] != approval_digest
                        or record["root"] != str(root) or record["image"] != self.executor.image
                        or time.time() > record["expires_at"]):
                    raise ExecutionError("Approval is expired, mismatched, or already used.", "stale_approval", 409)
                record.update(status="running", approved_at=stamp())
                cancelled = ExecutionCancellation(lambda: self._load(job_id, user_id)["status"] == "cancelled")
                self.active[job_id] = cancelled
                self._save(record)
            except (ExecutionError, OSError, json.JSONDecodeError):
                self.active.pop(job_id, None)
                lease.close()
                raise
        worktree = None
        started = time.monotonic()
        try:
            if on_started:
                on_started(self.public(record))
            # Worktrees hold proposals only; no repository code executes on the host.
            worktree = self.storage.resolve() / "worktrees" / job_id / "proposal"
            record["worktree"] = str(worktree)
            self._save(record)
            worktree.parent.mkdir(parents=True)
            git(root, "worktree", "add", "--detach", "--no-checkout", str(worktree), record["base_sha"])
            files = snapshot(root, record["base_sha"])
            if fingerprint({k: hashlib.sha256(v).hexdigest() for k, v in files.items()}) != record["snapshot_digest"]:
                raise ExecutionError("Snapshot changed since approval.", "stale_approval", 409)
            # Populate manually, bypassing Git checkout filters and hooks.
            for rel, data in files.items():
                target = safe_repo_path(worktree, rel)
                if target is None:
                    raise ExecutionError("Unsafe worktree path.", "invalid_path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            candidate = dict(files)
            for change in record["changes"]:
                target = safe_repo_path(worktree, change["path"])
                if target is None:
                    raise ExecutionError("Unsafe proposal path.", "invalid_path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change["content"], encoding="utf-8", newline="")
                candidate[change["path"]] = change["content"].encode()
            if sum(map(len, candidate.values())) > MAX_BYTES or len(candidate) > MAX_FILES:
                raise ExecutionError("Candidate exceeds snapshot limits.", "too_large")
            record["baseline"] = self.executor.run(files, record["profile"], cancelled, container_name=f"mammoth-owner-{job_id}-baseline")
            if record["baseline"].get("failure_code") == "cleanup_failed":
                raise ExecutionError(record["baseline"]["error"], "cleanup_failed")
            if cancelled.is_set():
                record["status"] = "cancelled"
            else:
                record["candidate"] = self.executor.run(candidate, record["profile"], cancelled, container_name=f"mammoth-owner-{job_id}-candidate")
                if record["candidate"].get("failure_code") == "cleanup_failed":
                    raise ExecutionError(record["candidate"]["error"], "cleanup_failed")
                record["status"] = "cancelled" if cancelled.is_set() else "validated" if record["candidate"]["passed"] else "failed"
                baseline_tests = record["baseline"].get("test_results", {})
                candidate_tests = record["candidate"].get("test_results", {})
                record["regression"] = (record["baseline"]["passed"] and not record["candidate"]["passed"]) or any(
                    outcome == "ok" and candidate_tests.get(name) != "ok" for name, outcome in baseline_tests.items())
            if head_sha(root) != record["base_sha"]:
                record.update(status="failed", failure_code="stale_base", error="Repository changed while validation ran; results cannot approve applying this patch.")
        except (ExecutionError, OSError, subprocess.SubprocessError) as exc:
            record.update(status="failed", error=str(exc)[:500], failure_code=getattr(exc, "code", "execution_failed"))
        finally:
            if worktree is not None:
                try:
                    self._cleanup_worktree(record)
                except (ExecutionError, OSError) as exc:
                    record.update(status="failed", failure_code="cleanup_failed", error=f"Worktree cleanup failed: {exc}")
            record["duration_ms"] = round((time.monotonic() - started) * 1000)
            try:
                with self.lock:
                    if record.get("failure_code") == "cleanup_failed":
                        self.recovery_error = record["error"]
                    elif self._load(job_id, user_id)["status"] == "cancelled":
                        record["status"] = "cancelled"
                    self._save(record)
            finally:
                self.active.pop(job_id, None)
                lease.close()
        return self.public(record)
