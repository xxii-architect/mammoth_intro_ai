CI Seccomp Tuner

This folder contains a helper script used by CI to analyze the captured
runtime information from the sandbox container and produce a suggestion
for seccomp tweaks when the container fails to run Python under the
currently mounted seccomp profile.

Files
- ci_seccomp_tuner.py: script that reads runtime_info.txt and optional runtime_error.txt and produces:
  - diagnostics/suggestion.json: suggested syscall names to consider adding
  - diagnostics/diagnostics.txt: full snapshot of runtime and stderr plus notes

How it is used in CI
- The sandbox-diagnostics job runs sandbox_runner in Docker-required mode and writes runtime_info.txt
  (this file contains the container stdout, including /proc/self/status between markers).
- The job then runs: python .github/scripts/ci_seccomp_tuner.py --runtime runtime_info.txt --stderr runtime_error.txt --out diagnostics
- The diagnostics directory is uploaded as a CI artifact for review.
- runtime_error.txt and runtime_evidence.json are uploaded alongside stdout.
  The structured receipt distinguishes verified, failed and not_verified.
  Docker absence/startup failures never execute the smoke on the host. The
  diagnostic job permits not_verified but fails observed smoke/hardening failures.
  Run `run_sandbox_test.py` without `--diagnostic` to require verified evidence.
  Successful diagnostic collection is not owner-execution isolation acceptance.

Security & workflow notes
- The tuner does NOT modify the repository. It makes non-destructive suggestions and a human should review the suggested syscalls before applying them to .mammoth/seccomp.json.
- Common workflow:
  1. Run CI. If sandbox-diagnostics reports failed or not_verified, download sandbox-runtime-info and seccomp-diagnostics artifacts.
  2. Inspect diagnostics/suggestion.json for recommended syscalls.
  3. If acceptable, open a small PR that adds the minimal syscall names to .mammoth/seccomp.json and re-run CI.

The workflow has read-only repository permissions. It never applies a suggestion
or opens a patch PR automatically. These heuristic suggestions are not evidence
that a syscall change is necessary or safe; namespace/mount startup failures may
instead require infrastructure repair. Never weaken isolation to obtain a pass.
The observation describes the runtime shell, not the test process's user
identity. No production, hostile-code or reviewed owner-image acceptance is claimed.
