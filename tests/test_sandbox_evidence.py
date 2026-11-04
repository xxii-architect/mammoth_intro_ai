import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mammoth_os.sandbox_runner import SandboxRunner


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sandbox_ci_probe", ROOT / ".github" / "scripts" / "run_sandbox_test.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.fixture
def runner(monkeypatch):
    instance = SandboxRunner()
    monkeypatch.setattr(instance, "_emit_telemetry", lambda *_args: None)
    monkeypatch.setattr(instance, "_run_in_subprocess", lambda *_args: pytest.fail("Docker-required mode executed on host"))
    monkeypatch.setenv("SANDBOX_RUNNER_REQUIRE_DOCKER", "1")
    return instance


@pytest.mark.parametrize("override", [None, "FORCE_SUBPROCESS_FALLBACK", "SANDBOX_RUNNER_MODE"])
def test_required_docker_never_falls_back_when_unavailable(runner, monkeypatch, override):
    monkeypatch.setattr("mammoth_os.sandbox_runner.shutil.which", lambda _name: None)
    if override:
        monkeypatch.setenv(override, "1" if override.startswith("FORCE") else "subprocess")
    result = runner.run_code("", "print('not executed')")
    assert result["passed"] is False
    assert result["method"] == "docker-unavailable"
    assert result["failure_code"] == "docker_unavailable"


def test_required_docker_overrides_development_fallback(runner, monkeypatch):
    monkeypatch.setenv("FORCE_SUBPROCESS_FALLBACK", "1")
    monkeypatch.setattr("mammoth_os.sandbox_runner.shutil.which", lambda _name: "docker")
    assert runner._docker_available() is True


@pytest.mark.parametrize("error", ["operation not permitted", "bind-mount /proc: no such file or directory"])
def test_required_docker_preserves_runtime_failure_without_host_execution(runner, monkeypatch, error):
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr("mammoth_os.sandbox_runner.subprocess.run", lambda *_args, **_kwargs:
                        SimpleNamespace(returncode=125, stdout="", stderr=error))
    result = runner.run_code("", "assert True")
    assert result["method"] == "docker"
    assert result["passed"] is False and result["returncode"] == 125
    assert result["stderr"] == error


@pytest.mark.parametrize("docker_available", [False, True])
def test_legacy_development_fallback_is_preserved(runner, monkeypatch, docker_available):
    monkeypatch.delenv("SANDBOX_RUNNER_REQUIRE_DOCKER")
    monkeypatch.setattr(runner, "_docker_available", lambda: docker_available)
    monkeypatch.setattr(runner, "_run_in_subprocess", lambda *_args:
                        {"passed": True, "stdout": "trusted local test", "stderr": "", "returncode": 0})
    monkeypatch.setattr("mammoth_os.sandbox_runner.subprocess.run", lambda *_args, **_kwargs:
                        SimpleNamespace(returncode=125, stdout="", stderr="operation not permitted"))
    result = runner.run_code("", "assert True")
    assert result["passed"] is True
    assert result["method"] == ("subprocess-fallback-after-docker" if docker_available else "subprocess")
    if docker_available:
        assert result["docker_stderr"] == "operation not permitted"


def receipt(**updates):
    result = {"method": "docker", "passed": True, "returncode": 0, "stderr": "",
              "stdout": "---RUNTIME-INFO-START---\nSeccomp:\t2\nCapEff:\t0000000000000000\nNoNewPrivs:\t1\n"
                        "---RUNTIME-INFO-END---\nTEST_OK\n"}
    return {**result, **updates}


@pytest.mark.parametrize("result,status", [
    (receipt(), "verified"),
    (receipt(passed=False, returncode=1, stderr="AssertionError"), "failed"),
    (receipt(method="subprocess"), "not_verified"),
    (receipt(method="subprocess-fallback-after-docker"), "not_verified"),
    (receipt(passed=False, returncode=125, stdout="", stderr="namespace unavailable"), "not_verified"),
    (receipt(stdout="TEST_OK\nSeccomp: 2\nCapEff: 0\nNoNewPrivs: 1"), "not_verified"),
    (receipt(stdout=receipt()["stdout"].replace("Seccomp:\t2", "Seccomp:\t0")), "failed"),
    (receipt(stdout=receipt()["stdout"].replace("CapEff:\t0000000000000000", "CapEff:\t0000000000000001")), "failed"),
    (receipt(stdout=receipt()["stdout"].replace("NoNewPrivs:\t1", "NoNewPrivs:\t0")), "failed"),
    (receipt(stdout=receipt()["stdout"].replace("TEST_OK", "test did not run")), "failed"),
    (receipt(passed="true"), "failed"),
    (receipt(returncode=False), "failed"),
    (receipt(stdout=receipt()["stdout"].replace("Seccomp:\t2\n", "")), "not_verified"),
])
def test_evidence_requires_docker_success_and_observed_runtime_fields(result, status):
    assert probe.classify(result)["status"] == status


@pytest.mark.parametrize("diagnostic", [False, True])
@pytest.mark.parametrize("status", ["verified", "failed", "not_verified", "exception"])
def test_probe_exit_artifacts_and_diagnostic_boundary(tmp_path, monkeypatch, diagnostic, status):
    results = {
        "verified": receipt(),
        "failed": receipt(passed=False, returncode=1, stderr="AssertionError"),
        "not_verified": receipt(method="subprocess-fallback-after-docker", docker_stderr="namespace unavailable"),
    }

    def run(**_kwargs):
        assert probe.os.environ["SANDBOX_RUNNER_REQUIRE_DOCKER"] == "1"
        if status == "exception":
            raise OSError("daemon unavailable")
        return results[status]

    monkeypatch.setattr(probe, "run_code", run)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.txt"))
    monkeypatch.delenv("SANDBOX_RUNNER_REQUIRE_DOCKER", raising=False)
    args = ["--output-dir", str(tmp_path)]
    if diagnostic:
        args.append("--diagnostic")
    code = probe.main(args)
    expected = "not_verified" if status == "exception" else status
    assert code == (0 if expected == "verified" or (diagnostic and expected == "not_verified") else 1)
    evidence = json.loads((tmp_path / "runtime_evidence.json").read_text())
    assert evidence["status"] == expected
    assert evidence["contract"] == "mammoth.sandbox-evidence.v1"
    assert f"Sandbox execution: {expected}" in (tmp_path / "summary.txt").read_text()
    assert (tmp_path / "runtime_info.txt").exists()
    assert (tmp_path / "runtime_error.txt").exists()
    if status == "not_verified":
        assert "namespace unavailable" in (tmp_path / "runtime_error.txt").read_text()
    assert "SANDBOX_RUNNER_REQUIRE_DOCKER" not in probe.os.environ


def test_probe_cli_fails_in_strict_mode_without_docker(tmp_path):
    import os
    import sys

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PATH": ""}
    env.pop("GITHUB_STEP_SUMMARY", None)
    result = subprocess.run(
        [sys.executable, str(ROOT / ".github" / "scripts" / "run_sandbox_test.py"), "--output-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, timeout=20,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    evidence = json.loads((tmp_path / "runtime_evidence.json").read_text())
    assert evidence["status"] == "not_verified"
    assert evidence["result"]["method"] == "docker-unavailable"


def test_timeout_bytes_remain_explicit_unverified_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "run_code", lambda **_kwargs:
                        receipt(passed=False, returncode=-1, stdout=b"partial \xff", stderr=b"timeout"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert probe.main(["--output-dir", str(tmp_path)]) == 1
    evidence = json.loads((tmp_path / "runtime_evidence.json").read_text())
    assert evidence["status"] == "not_verified"
    assert evidence["result"]["stderr"] == "timeout"
    assert "partial" in (tmp_path / "runtime_info.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("diagnostic", [False, True])
@pytest.mark.parametrize("status", ["verified", "failed", "not_verified"])
def test_actual_cli_exit_codes_cannot_hide_smoke_failures(tmp_path, diagnostic, status):
    import os
    import sys

    package = tmp_path / "mammoth_os"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    result = {
        "verified": receipt(),
        "failed": receipt(passed=False, returncode=1, stderr="AssertionError"),
        "not_verified": receipt(method="docker-unavailable", passed=False, returncode=-3),
    }[status]
    (package / "sandbox_runner.py").write_text(
        "import os\n"
        "def run_code(**kwargs):\n"
        "    assert os.environ['SANDBOX_RUNNER_REQUIRE_DOCKER'] == '1'\n"
        f"    return {result!r}\n", encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    env.pop("GITHUB_STEP_SUMMARY", None)
    args = [sys.executable, str(ROOT / ".github" / "scripts" / "run_sandbox_test.py"),
            "--output-dir", str(tmp_path)]
    if diagnostic:
        args.append("--diagnostic")
    completed = subprocess.run(args, capture_output=True, text=True, env=env, timeout=20)
    assert completed.returncode == (0 if status == "verified" or (diagnostic and status == "not_verified") else 1)
    assert json.loads((tmp_path / "runtime_evidence.json").read_text())["status"] == status


def test_workflow_labels_diagnostics_and_does_not_ignore_smoke_failures():
    import re

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "\n  docker-tests-linux:" not in workflow
    job = re.search(r"(?ms)^  sandbox-diagnostics:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow).group(1)
    assert "permissions:\n      contents: read" in job
    assert "run_sandbox_test.py --diagnostic" in job
    assert "|| true" not in job and "continue-on-error" not in job
    assert "apply_suggestion" not in job
    assert "runtime_evidence.json" in job and "runtime_error.txt" in job


@pytest.mark.parametrize("error,code", [
    ("reopen exec fifo: get safe /proc/thread-self/fd handle: operation not permitted", "container_namespace_startup"),
    ("bind-mount /proc/123/ns/net: no such file or directory", "container_namespace_startup"),
    ("Cannot connect to the Docker daemon", "docker_daemon_unavailable"),
    ("pull access denied", "image_unavailable"),
    ("unrecognized failure", "runtime_evidence_absent"),
])
def test_missing_runtime_receipt_explains_startup_without_suggesting_seccomp_changes(error, code):
    evidence = probe.classify(receipt(stdout="", stderr=error, passed=False, returncode=127))
    assert evidence["status"] == "not_verified"
    assert evidence["failure_code"] == code
    assert evidence["seccomp_change_supported"] is False
    assert evidence["next_action"]


def load_tuner():
    spec = importlib.util.spec_from_file_location("seccomp_diagnostics", ROOT / ".github" / "scripts" / "ci_seccomp_tuner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("runtime,error", [
    ("", "operation not permitted; bind-mount /proc"),
    ("TEST_OK", "seccomp denied syscall=mprotect"),
    ("Seccomp: 2", "denied syscall=mprotect"),
    (receipt()["stdout"], "operation not permitted"),
    (receipt()["stdout"], "denied syscall=unreviewed_syscall"),
    (receipt()["stdout"], "denied arbitrary words mprotect syscall other"),
    (receipt()["stdout"].replace("Seccomp:\t2", "Seccomp:\t0"), "denied syscall=mprotect"),
])
def test_tuner_never_guesses_relaxations_from_startup_or_unnamed_permission_errors(runtime, error):
    suggestions, notes = load_tuner().suggest_from_runtime(runtime, error)
    assert suggestions == []
    assert notes


def test_tuner_only_retains_named_allowlisted_denials_as_review_candidates():
    suggestions, notes = load_tuner().suggest_from_runtime(
        receipt()["stdout"], "denied syscall=mprotect\nblocked syscall: statx\ndenied syscall=mprotect")
    assert suggestions == ["mprotect", "statx"]
    assert any("operator review" in note for note in notes)
