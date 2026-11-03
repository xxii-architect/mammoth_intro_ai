"""Docker-only smoke evidence; diagnostics may be unavailable, never falsely verified."""

import argparse
import json
import os
import re
from pathlib import Path

from mammoth_os.sandbox_runner import run_code


def classify(result):
    evidence = {"contract": "mammoth.sandbox-evidence.v1", "status": "not_verified", "result": result}
    if result.get("method") != "docker":
        return {**evidence, "reason": "Docker execution was not observed. Host fallback cannot verify isolation."}
    stdout = result.get("stdout", "")
    match = re.search(r"---RUNTIME-INFO-START---\r?\n(.*?)---RUNTIME-INFO-END---", stdout, re.DOTALL)
    if not match:
        return {**evidence, "reason": "Container runtime evidence is absent; infrastructure/startup needs operator review."}
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
    print(summary)
    print(json.dumps(evidence))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(summary)
    return 0 if evidence["status"] == "verified" or (args.diagnostic and evidence["status"] == "not_verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
