"""Docker-only smoke evidence; diagnostics may be unavailable, never falsely verified."""

import argparse
import json
import os
import re
from pathlib import Path

from mammoth_os.sandbox_runner import run_code


def startup_diagnosis(result):
    """Classify missing runtime evidence without guessing a seccomp policy fix."""
    error = str(result.get("stderr", "")).lower()
    if result.get("method") == "docker-unavailable":
        code, action = "docker_unavailable", "Install/configure the operator's Docker executable and daemon."
    elif any(marker in error for marker in ("bind-mount /proc", "reopen exec fifo", "fsmount:fscontext:proc")):
        code, action = "container_namespace_startup", (
            "Inspect the runner's nested-container/kernel namespace and mount support. "
            "The test process was not observed; do not loosen application seccomp or use host fallback."
        )
    elif any(marker in error for marker in ("cannot connect to the docker daemon", "daemon unavailable", "error during connect")):
        code, action = "docker_daemon_unavailable", "Inspect daemon availability and operator permissions; do not bypass isolation."
    elif any(marker in error for marker in ("pull access denied", "manifest unknown", "failed to resolve reference")):
        code, action = "image_unavailable", "Review the requested image and registry availability; do not substitute an unreviewed image."
    elif result.get("returncode") == -1:
        code, action = "timeout_without_runtime", "Inspect startup timing and container cleanup before retrying."
    else:
        code, action = "runtime_evidence_absent", "Inspect Docker stderr and runtime startup; no syscall denial is established."
    return {"failure_code": code, "next_action": action, "seccomp_change_supported": False}


def classify(result):
    evidence = {"contract": "mammoth.sandbox-evidence.v1", "status": "not_verified", "result": result}
    if result.get("method") != "docker":
        return {**evidence, **startup_diagnosis(result),
                "reason": "Docker execution was not observed. Host fallback cannot verify isolation."}
    stdout = result.get("stdout", "")
    match = re.search(r"---RUNTIME-INFO-START---\r?\n(.*?)---RUNTIME-INFO-END---", stdout, re.DOTALL)
    if not match:
        return {**evidence, **startup_diagnosis(result),
                "reason": "Container runtime evidence is absent; infrastructure/startup needs operator review."}
    runtime = match.group(1)
    fields = {
        "seccomp": re.search(r"^Seccomp:\s*([0-9]+)\s*$", runtime, re.MULTILINE),
        "capabilities": re.search(r"^CapEff:\s*([0-9a-fA-F]+)\s*$", runtime, re.MULTILINE),
        "no_new_privileges": re.search(r"^NoNewPrivs:\s*([0-9]+)\s*$", runtime, re.MULTILINE),
    }
    if not all(fields.values()):
        return {**evidence, "reason": "Container runtime fields are incomplete; isolation is not verified."}
    if (fields["seccomp"].group(1) != "2" or int(fields["capabilities"].group(1), 16) != 0
            or fields["no_new_privileges"].group(1) != "1"):
        return {**evidence, "status": "failed", "reason": "Observed container hardening differs from the required smoke profile."}
    if (result.get("passed") is not True or type(result.get("returncode")) is not int
            or result["returncode"] != 0 or "TEST_OK" not in stdout.splitlines()):
        return {**evidence, "status": "failed", "reason": "Container smoke assertion failed or did not complete."}
    return {**evidence, "status": "verified",
            "reason": "Docker smoke passed with observed seccomp, dropped capabilities and no-new-privileges. "
                      "This is not owner-execution, non-root test-process or production isolation acceptance."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic", action="store_true",
                        help="Allow not_verified infrastructure evidence without failing; actual smoke/hardening failures still fail.")
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    previous = os.environ.get("SANDBOX_RUNNER_REQUIRE_DOCKER")
    os.environ["SANDBOX_RUNNER_REQUIRE_DOCKER"] = "1"
    try:
        try:
            result = run_code(code="", test_script="import check_math; assert check_math.VALUE == 2; print('TEST_OK')",
                              timeout=120, memory_limit_mb=256, project_files={"check_math.py": "VALUE = 2\n"})
        except (OSError, RuntimeError) as exc:
            result = {"passed": False, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}",
                      "returncode": -3, "method": "docker-error"}
    finally:
        if previous is None:
            os.environ.pop("SANDBOX_RUNNER_REQUIRE_DOCKER", None)
        else:
            os.environ["SANDBOX_RUNNER_REQUIRE_DOCKER"] = previous
    for key in ("stdout", "stderr", "docker_stdout", "docker_stderr"):
        if isinstance(result.get(key), bytes):
            result[key] = result[key].decode("utf-8", errors="replace")
    evidence = classify(result)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "runtime_info.txt").write_text(result.get("stdout", ""), encoding="utf-8")
    errors = "\n".join(filter(None, [result.get("stderr", ""), result.get("docker_stderr", "")]))
    (args.output_dir / "runtime_error.txt").write_text(errors, encoding="utf-8")
    (args.output_dir / "runtime_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    summary = f"### Sandbox execution: {evidence['status']}\n\n{evidence['reason']}\n"
    if evidence.get("next_action"):
        summary += f"\nClassification: `{evidence['failure_code']}`\n\n{evidence['next_action']}\n"
    print(summary)
    print(json.dumps(evidence))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(summary)
    return 0 if evidence["status"] == "verified" or (args.diagnostic and evidence["status"] == "not_verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
