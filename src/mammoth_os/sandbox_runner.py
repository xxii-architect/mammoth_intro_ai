"""Sandbox runner for safely executing generated code/tests.

API (simple):
- run_code(code: str, test_script: str, timeout: int = 30, memory_limit_mb: int = 256) -> dict

Behavior:
- If Docker is available, run inside a python:3.11-slim container with network disabled and memory limit.
- Otherwise, fallback to running the test script with the system Python in a temporary directory (best-effort).

This is a pragmatic, testable implementation suitable for local dev and unit testing.
"""
import os
import shutil
import subprocess
import tempfile
import time
from typing import Dict, Any


class SandboxRunner:
    def __init__(self, docker_image: str = "python:3.11-slim"):
        self.docker_image = docker_image

    def _docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def run_code(
        self,
        code: str,
        test_script: str,
        timeout: int = 30,
        memory_limit_mb: int = 256,
    ) -> Dict[str, Any]:
        """Run `code` and `test_script` in an isolated environment.

        Returns a dict with keys: passed (bool), stdout, stderr, returncode, duration_ms, method
        """
        start = time.time()
        if self._docker_available():
            result = self._run_in_docker(code, test_script, timeout, memory_limit_mb)
            result["method"] = "docker"
            result["duration_ms"] = int((time.time() - start) * 1000)
            return result
        else:
            result = self._run_in_subprocess(code, test_script, timeout)
            result["method"] = "subprocess"
            result["duration_ms"] = int((time.time() - start) * 1000)
            return result

    def _run_in_subprocess(self, code: str, test_script: str, timeout: int) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            code_path = os.path.join(tmp, "code.py")
            test_path = os.path.join(tmp, "test_runner.py")
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_script)

            # Run test runner using system python
            try:
                proc = subprocess.run(
                    [shutil.which("python") or "python", test_path],
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                return {
                    "passed": proc.returncode == 0,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": proc.returncode,
                }
            except subprocess.TimeoutExpired as te:
                return {"passed": False, "stdout": "", "stderr": f"timeout: {te}", "returncode": -1}
            except Exception as exc:
                return {"passed": False, "stdout": "", "stderr": str(exc), "returncode": -2}

    def _run_in_docker(self, code: str, test_script: str, timeout: int, memory_limit_mb: int) -> Dict[str, Any]:
        # Create a temp dir and write files
        with tempfile.TemporaryDirectory() as tmp:
            code_path = os.path.join(tmp, "code.py")
            test_path = os.path.join(tmp, "test_runner.py")
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_script)

            # Build docker run command
            mem_limit = f"{memory_limit_mb}m"
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                f"{tmp}:/workspace",
                "-w",
                "/workspace",
                "--memory",
                mem_limit,
                self.docker_image,
                "bash",
                "-lc",
                # Ensure pytest is available only if requested; here run test script directly
                f"{shutil.which('python') or 'python'} test_runner.py",
            ]

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                return {
                    "passed": proc.returncode == 0,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "returncode": proc.returncode,
                }
            except subprocess.TimeoutExpired as te:
                return {"passed": False, "stdout": "", "stderr": f"timeout: {te}", "returncode": -1}
            except Exception as exc:
                return {"passed": False, "stdout": "", "stderr": str(exc), "returncode": -2}


# Convenience function
def run_code(code: str, test_script: str, timeout: int = 30, memory_limit_mb: int = 256) -> Dict[str, Any]:
    runner = SandboxRunner()
    return runner.run_code(code, test_script, timeout=timeout, memory_limit_mb=memory_limit_mb)
