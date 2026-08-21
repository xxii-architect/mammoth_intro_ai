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
- The docker-tests-linux job runs the sandbox_runner and writes runtime_info.txt
  (this file contains the container stdout, including /proc/self/status between markers).
- The job then runs: python .github/scripts/ci_seccomp_tuner.py --runtime runtime_info.txt --stderr runtime_error.txt --out diagnostics
- The diagnostics directory is uploaded as a CI artifact for review.

Security & workflow notes
- The tuner does NOT modify the repository. It makes non-destructive suggestions and a human should review the suggested syscalls before applying them to .mammoth/seccomp.json.
- Common workflow:
  1. Run CI. If docker-tests-linux fails with seccomp errors, download sandbox-runtime-info and diagnostics artifacts.
  2. Inspect diagnostics/suggestion.json for recommended syscalls.
  3. If acceptable, open a small PR that adds the minimal syscall names to .mammoth/seccomp.json and re-run CI.
