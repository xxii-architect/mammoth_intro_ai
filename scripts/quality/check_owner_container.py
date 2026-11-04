"""Operator-only acceptance of a local reviewed image through the real owner executor.

Runs only bundled trusted fixtures, never repository/user code. No image pulls,
host fallback, Docker configuration changes or production enablement.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mammoth_os.owner_execution import ContainerExecutor, ExecutionError, IMAGE_RE

CONTRACT = "mammoth.owner-container-evidence.v1"
MARKER = "MAMMOTH_OWNER_RUNTIME:"
RUNTIME_TEST = r'''
import errno
import json
import os
import resource
import unittest
from pathlib import Path

class RuntimeChecks(unittest.TestCase):
    def test_runtime_contract(self):
        status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
        self.assertEqual(os.getuid(), 65534)
        self.assertEqual(os.getgid(), 65534)
        self.assertEqual(status["Seccomp"].strip(), "2")
        self.assertEqual(int(status["CapEff"].strip(), 16), 0)
        self.assertEqual(status["NoNewPrivs"].strip(), "1")
        self.assertEqual(set(os.listdir("/sys/class/net")), {"lo"})
        self.assertFalse(Path("/var/run/docker.sock").exists())
        self.assertEqual(os.environ.get("HOME"), "/tmp")
        mounts = {}
        for line in Path("/proc/mounts").read_text().splitlines():
            fields = line.split()
            mounts[fields[1]] = (fields[2], fields[3].split(","))
        self.assertIn("ro", mounts["/"][1])
        self.assertIn("ro", mounts["/input/source.tar"][1])
        for path in ("/work", "/tmp"):
            self.assertEqual(mounts[path][0], "tmpfs")
            self.assertTrue({"rw", "nosuid", "nodev"}.issubset(mounts[path][1]))
        self.assertIn("noexec", mounts["/tmp"][1])
        for path in ("/work/acceptance-write", "/tmp/acceptance-write"):
            Path(path).write_text("bounded trusted fixture")
        with self.assertRaises(OSError) as root_error:
            Path("/acceptance-root-write").write_text("must fail")
        self.assertIn(root_error.exception.errno, (errno.EROFS, errno.EACCES))
        with self.assertRaises(OSError):
            with open("/input/source.tar", "ab") as stream:
                stream.write(b"must fail")
        self.assertEqual(resource.getrlimit(resource.RLIMIT_NOFILE), (256, 256))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_FSIZE), (16777216, 16777216))
        # Both cgroup layouts are supported; missing controls fail, never default.
        def control(v2, v1):
            path = Path("/sys/fs/cgroup") / v2
            return (path if path.exists() else Path("/sys/fs/cgroup") / v1).read_text().strip()
        memory = int(control("memory.max", "memory/memory.limit_in_bytes"))
        pids = int(control("pids.max", "pids/pids.max"))
        self.assertGreater(memory, 0)
        self.assertLessEqual(memory, 256 * 1024 * 1024)
        self.assertGreater(pids, 0)
        self.assertLessEqual(pids, 64)
        cpu = Path("/sys/fs/cgroup/cpu.max")
        if cpu.exists():
            quota, period = map(int, cpu.read_text().split())
        else:
            quota = int(control("cpu/cpu.cfs_quota_us", "cpu/cpu.cfs_quota_us"))
            period = int(control("cpu/cpu.cfs_period_us", "cpu/cpu.cfs_period_us"))
        self.assertGreater(quota, 0)
        self.assertLessEqual(quota, period)
        print("MAMMOTH_OWNER_RUNTIME:" + json.dumps({
            "uid": os.getuid(), "gid": os.getgid(), "seccomp": 2, "effective_capabilities": 0,
            "no_new_privileges": True, "network_interfaces": ["lo"], "root_read_only": True,
            "input_read_only": True, "bounded_tmpfs_writable": True, "tmp_noexec": True,
            "memory_limit_bytes": memory, "pids_limit": pids, "cpu_quota": quota, "cpu_period": period,
            "docker_socket_absent": True, "rlimits_checked": True,
        }), flush=True)
'''
FAILURE_TEST = "import unittest\nclass Failure(unittest.TestCase):\n def test_failure(self):\n  self.fail('EXPECTED_ACCEPTANCE_FAILURE')\n"
TIMEOUT_TEST = "import time,unittest\nclass Timeout(unittest.TestCase):\n def test_timeout(self):\n  print('MAMMOTH_TIMEOUT_STARTED',flush=True)\n  time.sleep(120)\n"


def _cleanup_observed(name):
    try:
        result = subprocess.run(["docker", "container", "inspect", name], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode and "No such container" in result.stderr:
        return True
    return False


def _valid_runtime(runtime):
    expected = {"uid": 65534, "gid": 65534, "seccomp": 2, "effective_capabilities": 0,
                "no_new_privileges": True, "network_interfaces": ["lo"], "root_read_only": True,
                "input_read_only": True, "bounded_tmpfs_writable": True, "tmp_noexec": True,
                "docker_socket_absent": True, "rlimits_checked": True}
    if not isinstance(runtime, dict) or any(
        type(runtime.get(key)) is not type(value) or runtime.get(key) != value for key, value in expected.items()
    ):
        return False
    for key, maximum in (("memory_limit_bytes", 256 * 1024 * 1024), ("pids_limit", 64)):
        if type(runtime.get(key)) is not int or not 0 < runtime[key] <= maximum:
            return False
    return (type(runtime.get("cpu_quota")) is int and type(runtime.get("cpu_period")) is int
            and 0 < runtime["cpu_quota"] <= runtime["cpu_period"])


def collect(image, *, timeout=10):
    evidence = {
        "contract": CONTRACT, "status": "not_verified", "observed_at": datetime.now(timezone.utc).isoformat(),
        "image": image, "profile": "python_unittest", "checks": {}, "runtime": None,
        "scope": "Bundled trusted Python fixtures through ContainerExecutor; not hostile-code, frontend or production certification.",
    }
    if not IMAGE_RE.fullmatch(image):
        evidence["reason"] = "A reviewed digest-pinned local image is required."
        return evidence
    executor = ContainerExecutor(image, timeout=timeout)
    try:
        evidence["probe_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        evidence["executor_sha256"] = hashlib.sha256(Path(inspect.getfile(ContainerExecutor)).read_bytes()).hexdigest()
        evidence["fixture_sha256"] = {name: hashlib.sha256(script.encode()).hexdigest()
                                      for name, script in (("runtime", RUNTIME_TEST), ("negative", FAILURE_TEST),
                                                           ("timeout", TIMEOUT_TEST))}
        readiness = executor.readiness()
        evidence["readiness"] = readiness
        if not readiness["ready"]:
            evidence["reason"] = readiness["reason"]
            return evidence
        # No daemon ID, host paths, environment or registry credentials enter the receipt.
        version = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                                 capture_output=True, text=True, timeout=10, check=True)
        inspected = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                                   capture_output=True, text=True, timeout=10, check=True)
        evidence["docker_server_version"] = version.stdout.strip()
        evidence["image_id"] = inspected.stdout.strip()
        for phase, script in (("runtime", RUNTIME_TEST), ("negative", FAILURE_TEST), ("timeout", TIMEOUT_TEST)):
            name = f"mammoth-owner-exec-{uuid.uuid4().hex[:24]}-candidate"
            executor.timeout = 3 if phase == "timeout" else timeout
            result = executor.run({"tests/test_acceptance.py": script.encode()}, "python_unittest",
                                  threading.Event(), container_name=name)
            cleanup = _cleanup_observed(name)
            evidence["checks"][phase] = {**result, "container_removed": cleanup}
            if not cleanup or result.get("failure_code") == "cleanup_failed":
                evidence.update(status="failed", reason="Named container cleanup was not confirmed; stop and inspect the runtime.")
                return evidence
            if result.get("isolation") != "docker" or result.get("image") != image or result.get("log_truncated") is not False:
                evidence.update(status="failed", reason="Fixture evidence has wrong runtime identity or incomplete logs.")
                return evidence
            if phase == "runtime":
                markers = [line[len(MARKER):] for line in result["log"].splitlines() if line.startswith(MARKER)]
                if not markers:
                    evidence["reason"] = "The trusted test process produced no complete runtime evidence."
                    # A discovered test that fails is observed failure, not unavailable infrastructure.
                    if result.get("tests_detected"):
                        evidence["status"] = "failed"
                    return evidence
                if (len(markers) != 1 or result["passed"] is not True or result.get("tests_detected") is not True
                        or type(result.get("returncode")) is not int or result["returncode"] != 0
                        or result.get("failure_code") != ""):
                    evidence.update(status="failed", reason="Trusted runtime checks failed or produced ambiguous evidence.")
                    return evidence
                try:
                    evidence["runtime"] = json.loads(markers[0])
                except json.JSONDecodeError:
                    evidence.update(status="failed", reason="Trusted runtime marker contains malformed evidence.")
                    return evidence
                if not _valid_runtime(evidence["runtime"]):
                    evidence.update(status="failed", reason="Observed runtime evidence does not satisfy the acceptance profile.")
                    return evidence
            elif phase == "negative":
                if (result["passed"] is not False or result.get("tests_detected") is not True
                        or "EXPECTED_ACCEPTANCE_FAILURE" not in result["log"]
                        or type(result.get("returncode")) is not int or result["returncode"] != 1):
                    evidence.update(status="failed", reason="An intentionally failing test was not correctly rejected.")
                    return evidence
            elif (result["passed"] is not False or result.get("failure_code") != "timeout"
                  or "MAMMOTH_TIMEOUT_STARTED" not in result["log"]):
                evidence.update(status="failed", reason="Started timeout fixture did not produce bounded failure evidence.")
                return evidence
        evidence.update(status="verified", reason="Trusted runtime, negative-result and timeout/cleanup checks passed for this image and host.")
    except ExecutionError as exc:
        evidence.update(status="failed" if exc.code == "cleanup_failed" else "not_verified",
                        reason=f"Owner executor refused acceptance: {exc.code}: {exc}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        evidence.update(reason=f"Acceptance evidence could not be collected: {type(exc).__name__}: {exc}")
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Operator-reviewed local image@sha256:digest; never pulled here.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = collect(args.image)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "owner_container_evidence.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Owner container acceptance: {evidence['status']}\n{evidence['reason']}\nReceipt: {path}")
    return 0 if evidence["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
