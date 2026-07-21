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
import json
from datetime import datetime, timezone
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
        project_files: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        """Run code and emit telemetry for each sandbox run."""

        """Run `code` and `test_script` in an isolated environment.

        project_files: optional mapping of relative_path -> file_content to write into the workspace.

        Returns a dict with keys: passed (bool), stdout, stderr, returncode, duration_ms, method
        """
        start = time.time()
        if self._docker_available():
            result = self._run_in_docker(code, test_script, timeout, memory_limit_mb, project_files)
            result["method"] = "docker"
            result["duration_ms"] = int((time.time() - start) * 1000)
        else:
            result = self._run_in_subprocess(code, test_script, timeout, project_files)
            result["method"] = "subprocess"
            result["duration_ms"] = int((time.time() - start) * 1000)

        # Emit telemetry asynchronously best-effort (do not raise on failure)
        try:
            self._emit_telemetry(result, memory_limit_mb, project_files)
        except Exception:
            pass

        return result

    def _run_in_subprocess(self, code: str, test_script: str, timeout: int, project_files: Dict[str, str] | None = None) -> Dict[str, Any]:
        tmp = tempfile.mkdtemp()
        try:
            # write project files if provided
            if project_files:
                for rel, content in project_files.items():
                    dest = os.path.join(tmp, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(content)

            code_path = os.path.join(tmp, "code.py")
            test_path = os.path.join(tmp, "test_runner.py")
            # Only write code.py if non-empty to avoid shadowing stdlib modules like 'code'
            if code and code.strip():
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write(code)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_script)

            # Run test runner using system python
            try:
                import sys
                python_exec = sys.executable or (shutil.which("python") or "python")
                proc = subprocess.run(
                    [python_exec, "-c", test_script],
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                # Small sleep to allow subprocesses to release handles on Windows
                time.sleep(0.1)
                return {
                    "passed": proc.returncode == 0,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": proc.returncode,
                }
            except subprocess.TimeoutExpired as te:
                # include partial output for debugging
                out = getattr(te, 'output', '') or getattr(te, 'stdout', '') or ''
                err = getattr(te, 'stderr', '') or ''
                return {"passed": False, "stdout": out, "stderr": f"timeout: {te}; stdout={out!r}; stderr={err!r}", "returncode": -1}
            except Exception as exc:
                return {"passed": False, "stdout": "", "stderr": str(exc), "returncode": -2}
        finally:
            # Best-effort cleanup with retries for Windows file-handle races
            for _ in range(8):
                try:
                    shutil.rmtree(tmp)
                    break
                except Exception:
                    time.sleep(0.1)
                    continue

    def _run_in_docker(self, code: str, test_script: str, timeout: int, memory_limit_mb: int, project_files: Dict[str, str] | None = None) -> Dict[str, Any]:
        # Create a temp dir and write files
        tmp = tempfile.mkdtemp()
        try:
            # write project files if provided
            if project_files:
                for rel, content in project_files.items():
                    dest = os.path.join(tmp, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(content)

            code_path = os.path.join(tmp, "code.py")
            test_path = os.path.join(tmp, "test_runner.py")
            # Only write code.py if non-empty to avoid shadowing stdlib modules like 'code'
            if code and code.strip():
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write(code)
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_script)

            # Build docker run command with security hardening
            mem_limit = f"{memory_limit_mb}m"
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                "1000:1000",
                "--security-opt",
                "no-new-privileges",
                "--cap-drop",
                "ALL",
                "--read-only",
                "-v",
                # Mount workspace as writable volume despite read-only root
                f"{tmp}:/workspace:rw",
                "-w",
                "/workspace",
                "--memory",
                mem_limit,
                self.docker_image,
                "bash",
                "-lc",
                # Run the test runner using the container's python
                "python" + " test_runner.py",
            ]

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                time.sleep(0.1)
                return {
                    "passed": proc.returncode == 0,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "returncode": proc.returncode,
                }
            except subprocess.TimeoutExpired as te:
                out = getattr(te, 'output', '') or getattr(te, 'stdout', '') or ''
                err = getattr(te, 'stderr', '') or ''
                return {"passed": False, "stdout": out, "stderr": f"timeout: {te}; stdout={out!r}; stderr={err!r}", "returncode": -1}
            except Exception as exc:
                return {"passed": False, "stdout": "", "stderr": str(exc), "returncode": -2}
        finally:
            for _ in range(8):
                try:
                    shutil.rmtree(tmp)
                    break
                except Exception:
                    time.sleep(0.1)
                    continue

    def _emit_telemetry(self, result: Dict[str, Any], memory_limit_mb: int, project_files: Dict[str, str] | None):
        """Append telemetry about the sandbox run to .mammoth/sandbox_runs.jsonl in the repo root.
        This is best-effort and should never raise to callers.
        """
        try:
            # Determine repo root relative to this file: ../../
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            mammoth_dir = os.path.join(repo_root, ".mammoth")
            os.makedirs(mammoth_dir, exist_ok=True)
            out_path = os.path.join(mammoth_dir, "sandbox_runs.jsonl")

            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": result.get("method"),
                "duration_ms": int(result.get("duration_ms", 0)),
                "returncode": int(result.get("returncode", -1)),
                "memory_limit_mb": int(memory_limit_mb or 0),
                "passed": bool(result.get("passed")),
                "stdout_len": len(result.get("stdout", "") or ""),
                "stderr_len": len(result.get("stderr", "") or ""),
                "file_count": len(project_files) if project_files else 0,
            }
            with open(out_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            # swallow any telemetry errors
            return


# Convenience function
def run_code(code: str, test_script: str, timeout: int = 30, memory_limit_mb: int = 256, project_files: Dict[str, str] | None = None) -> Dict[str, Any]:
    runner = SandboxRunner()
    return runner.run_code(code, test_script, timeout=timeout, memory_limit_mb=memory_limit_mb, project_files=project_files)
