MammothOS — Sandbox Runner / Fallback Usage

Quick note: if your environment's WSL2 kernel or Docker setup is incompatible with the sandbox Docker runner, you can force the subprocess fallback to continue development locally.

Force subprocess fallback (temporary)
- Bash / Linux / macOS:
  export FORCE_SUBPROCESS_FALLBACK=1
  # or
  export SANDBOX_RUNNER_MODE=subprocess

- PowerShell (Windows):
  $env:FORCE_SUBPROCESS_FALLBACK = '1'
  # or
  $env:SANDBOX_RUNNER_MODE = 'subprocess'

- CMD (Windows):
  set FORCE_SUBPROCESS_FALLBACK=1

Behavior
- With the override set, the SandboxRunner.run_code(...) API will use a best-effort subprocess-based execution (writes files to a temp dir and runs them with the local Python interpreter) instead of Docker.
- The run_code return shape is preserved (passed, stdout, stderr, returncode, method, duration_ms), so CodingAgent and TutorAgent callers will continue to work without changes.

When to revert
- Remove the override once your environment supports Docker sandboxing again (e.g., after kernel update or switching Docker backend). The runner will automatically prefer Docker when available and no override is set.

Notes
- This fallback is intended to keep development moving while kernel/Docker issues are resolved. It is less isolated than the Docker sandbox and should not be used as a long-term replacement for production testing.

See docs/implementation_status_and_next_steps.md for the project status and prioritized next actions for getting ATLAS/TutorAgent to production-grade readiness.
