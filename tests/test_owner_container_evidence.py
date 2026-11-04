import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mammoth_os.owner_execution import ExecutionError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("owner_container_probe", ROOT / "scripts" / "quality" / "check_owner_container.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
IMAGE = "python@sha256:" + "a" * 64


def runtime():
    return {"uid": 65534, "gid": 65534, "seccomp": 2, "effective_capabilities": 0,
            "no_new_privileges": True, "network_interfaces": ["lo"], "root_read_only": True,
            "input_read_only": True, "bounded_tmpfs_writable": True, "tmp_noexec": True,
            "memory_limit_bytes": 268435456, "pids_limit": 64, "cpu_quota": 100000, "cpu_period": 100000,
            "docker_socket_absent": True, "rlimits_checked": True}


@pytest.fixture
def executor(monkeypatch):
    class Fake:
        ready = True
        result_override = {}
        calls = []

        def __init__(self, image, timeout):
            self.image, self.timeout = image, timeout

        def readiness(self):
            return {"ready": self.ready, "reason": "fixture readiness", "profiles": {"python_unittest": self.ready}}

        def run(self, files, profile, cancelled, *, container_name):
            phase = len(self.calls)
            self.calls.append((files, profile, container_name))
            log = [probe.MARKER + json.dumps(runtime()), "EXPECTED_ACCEPTANCE_FAILURE", "MAMMOTH_TIMEOUT_STARTED"][phase]
            return {**{"passed": phase == 0, "tests_detected": phase != 2, "log": log,
                       "returncode": [0, 1, -9][phase], "failure_code": ["", "checks_failed", "timeout"][phase],
                       "isolation": "docker", "image": IMAGE, "log_truncated": False},
                    **self.result_override.get(phase, {})}

    monkeypatch.setattr(probe, "ContainerExecutor", Fake)
    monkeypatch.setattr(probe, "_cleanup_observed", lambda name: True)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="fixture-provenance", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", run)
    Fake.commands = commands
    return Fake


def test_acceptance_exercises_real_profile_with_trusted_fixtures_and_bounded_receipt(executor):
    evidence = probe.collect(IMAGE)
    assert evidence["status"] == "verified" and len(executor.calls) == 3
    assert evidence["runtime"] == runtime()
    assert evidence["contract"] == "mammoth.owner-container-evidence.v1"
    assert len(evidence["probe_sha256"]) == len(evidence["executor_sha256"]) == 64
    assert set(evidence["fixture_sha256"]) == {"runtime", "negative", "timeout"}
    assert all(profile == "python_unittest" for _, profile, _ in executor.calls)
    assert all(list(files) == ["tests/test_acceptance.py"] for files, _, _ in executor.calls)
    assert len({name for _, _, name in executor.calls}) == 3
    assert not any("pull" in command for command in executor.commands)
    assert "not hostile-code" in evidence["scope"]


@pytest.mark.parametrize("prefix", [
    "",
    "test_runtime_contract (test_acceptance.RuntimeChecks.test_runtime_contract) ... ",
])
def test_unittest_progress_prefix_does_not_hide_complete_runtime_marker(executor, prefix):
    executor.result_override = {0: {"log": prefix + probe.MARKER + json.dumps(runtime()) + "\nok\n"}}
    evidence = probe.collect(IMAGE)
    assert evidence["status"] == "verified" and evidence["runtime"] == runtime()


def test_duplicate_markers_remain_ambiguous_even_with_unittest_prefix(executor):
    marker = probe.MARKER + json.dumps(runtime())
    executor.result_override = {0: {"log": "test ... " + marker + "\n" + marker}}
    assert probe.collect(IMAGE)["status"] == "failed"


@pytest.mark.parametrize("image", ["python:latest", "-e", "python@sha256:abc", ""])
def test_unpinned_input_never_reaches_docker(executor, image):
    assert probe.collect(image)["status"] == "not_verified"
    assert not executor.calls and not executor.commands


def test_missing_runtime_readiness_never_runs_fixtures(executor):
    executor.ready = False
    assert probe.collect(IMAGE)["status"] == "not_verified"
    assert not executor.calls


@pytest.mark.parametrize("phase,updates,status", [
    (0, {"log": "", "passed": False, "tests_detected": False}, "not_verified"),
    (0, {"log": "AssertionError", "passed": False, "tests_detected": True}, "failed"),
    (0, {"isolation": "subprocess"}, "failed"),
    (0, {"image": "wrong"}, "failed"),
    (0, {"tests_detected": False}, "failed"),
    (0, {"returncode": False}, "failed"),
    (0, {"returncode": 1}, "failed"),
    (0, {"log_truncated": True}, "failed"),
    (0, {"failure_code": "timeout"}, "failed"),
    (0, {"log": probe.MARKER + "{}"}, "failed"),
    (0, {"log": probe.MARKER + "invalid-json"}, "failed"),
    (1, {"passed": True}, "failed"),
    (1, {"tests_detected": False}, "failed"),
    (1, {"returncode": 0}, "failed"),
    (1, {"returncode": True}, "failed"),
    (2, {"failure_code": ""}, "failed"),
    (2, {"log": ""}, "failed"),
])
def test_incomplete_or_failed_evidence_never_passes(executor, phase, updates, status):
    executor.result_override = {phase: updates}
    evidence = probe.collect(IMAGE)
    assert evidence["status"] == status
    assert len(executor.calls) == phase + 1


@pytest.mark.parametrize("key,value", [
    ("uid", 0), ("seccomp", 0), ("no_new_privileges", 1), ("effective_capabilities", True),
    ("root_read_only", False), ("network_interfaces", ["lo", "eth0"]),
    ("memory_limit_bytes", -1), ("memory_limit_bytes", 536870912), ("pids_limit", "64"),
    ("cpu_quota", 200000), ("cpu_period", True), ("docker_socket_absent", False),
])
def test_runtime_shape_and_thresholds_are_strict(executor, key, value):
    observed = {**runtime(), key: value}
    executor.result_override = {0: {"log": probe.MARKER + json.dumps(observed)}}
    assert probe.collect(IMAGE)["status"] == "failed"


def test_unconfirmed_cleanup_is_a_hard_failure_not_infrastructure_success(executor, monkeypatch):
    monkeypatch.setattr(probe, "_cleanup_observed", lambda name: False)
    evidence = probe.collect(IMAGE)
    assert evidence["status"] == "failed" and len(executor.calls) == 1


def test_probe_cleanup_exception_is_not_hidden(executor, monkeypatch):
    def unavailable(self):
        raise ExecutionError("Cleanup refused", "cleanup_failed", 503)

    monkeypatch.setattr(executor, "readiness", unavailable)
    assert probe.collect(IMAGE)["status"] == "failed"


def test_cleanup_inspection_only_accepts_named_container_absence(monkeypatch):
    for returncode, error, expected in [(1, "Error: No such container: named", True),
                                        (0, "", False), (1, "Cannot connect to daemon", False)]:
        monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                            SimpleNamespace(returncode=returncode, stderr=error))
        assert probe._cleanup_observed("mammoth-owner-exec-" + "a" * 24 + "-candidate") is expected


@pytest.mark.parametrize("status", ["verified", "failed", "not_verified"])
def test_cli_persists_receipt_and_is_strict_for_every_unverified_result(tmp_path, monkeypatch, status):
    evidence = {"status": status, "reason": "fixture", "contract": probe.CONTRACT}
    monkeypatch.setattr(probe, "collect", lambda image: evidence)
    assert probe.main(["--image", IMAGE, "--output-dir", str(tmp_path)]) == (0 if status == "verified" else 1)
    assert json.loads((tmp_path / "owner_container_evidence.json").read_text()) == evidence


def test_manual_workflow_is_operator_selected_strict_and_never_weakens_runtime():
    workflow = (ROOT / ".github" / "workflows" / "owner-container-acceptance.yml").read_text()
    assert "workflow_dispatch:" in workflow and "pull_request:" not in workflow
    assert "contents: read" in workflow and "persist-credentials: false" in workflow
    assert 'docker pull -- "$REVIEWED_IMAGE"' in workflow
    assert "check_owner_container.py" in workflow and "if: always()" in workflow
    assert "continue-on-error" not in workflow and "|| true" not in workflow
    assert "--privileged" not in workflow and "--security-opt=seccomp=unconfined" not in workflow
