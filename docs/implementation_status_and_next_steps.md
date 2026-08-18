MammothOS / ATLAS — Status \& Next Steps

Purpose

* Provide context for where the project currently stands, where we are aiming, and concrete next actions so a regular Copilot instance (or another developer) can continue work while you wait for a credit refresh.

Current state (Where we are)

* Core features implemented and tested locally:

  * LLM adapter factory (OpenAIAdapter + LocalAdapter fallback).
  * SandboxRunner with Docker preferred path and subprocess fallback.
  * CodingAgent.run\_tests integrated with SandboxRunner.
  * Telemetry for sandbox runs appended to .mammoth/sandbox\_runs.jsonl.
  * CI workflow added (.github/workflows/ci.yml) with docker-tests-linux job and seccomp tuner scripts.
  * Conservative .mammoth/seccomp.json present and CI tuning scripts in .github/scripts.
  * ExerciseGenerator (deterministic) and TutorAgent MVP (local persistence + Supabase scaffold) implemented.
  * Unit tests added for major modules (sandbox, coding\_agent, exercise\_generator, tutor\_agent).
  * Native MammothOS chat workflow with agent routing, task cards, and right-rail operator context is shipped and validated.
  * Production guardrails pass completed: runtime health, diagnostics export, provider-aware backend contracts, and developer access/entitlement surfaces.

### Current production-readiness snapshot

| Area | Score | Summary |
|---|---:|---|
| System overall | 8.2 / 10 | Significantly stronger than the original prototype; user-facing workflow is credible |
| CodingAgent | 8.5 | Best-performing lane and most trustworthy implementation path |
| TutorAgent | 8.2 | Strong learning flow with adaptive guidance |
| ShellAgent | 8.0 | Safety controls and approval gating are in place |
| MammothOS Chat | 8.4 | Native UI layer feels like a real operator workspace |
| API Server / Orchestration | 7.8 | Good workflow layer, but still needs smoother provider error UX |
| UI / Command Center | 7.5 | Functional and polished, but not yet complete “broad-operator” polish |
| LLM Runtime / Provider | 5.5 | Fallback chain exists, but outage and quota UX still need tightening |

### Most valuable remaining work

1. Improve cloud-provider outage UX and raw exception surfacing in the chat/runtime layer.
2. Finish the final UI comfort pass for operator readability and state clarity.
3. Continue the release-readiness pass by trimming risk surfaces rather than adding feature breadth.

Current blockers / issues

* CI runs are failing/canceling before pytest and sandbox test steps finish, preventing artifact upload and seccomp tuner diagnostics.
* The workflow previously had YAML heredoc issues; those were moved to a script and fixed.
* Need actionable runtime\_info.txt and diagnostics/suggestion.json from CI to iterate seccomp safely.
* Supabase persistence is scaffolded but not tested/integrated (requires credentials \& schema).

Immediate aim (short-term goal)

* Get CI to reliably produce pytest artifacts and sandbox runtime captures so the seccomp tuner can suggest minimal syscall additions.
* Once CI artifacts are available, review suggestions, iterate seccomp profile, and optionally create a draft PR for review.
* Ensure the sandbox Docker path is exercised in CI and validated for security flags (no-new-privileges, seccomp mount, cap-drop, read-only root where possible).

Planned next steps (ordered, credit-aware)

1. Isolate failing CI variant (already done): temporarily run CI on ubuntu-latest + python 3.11 only to produce deterministic logs/artifacts. (In progress — commit pushed.)
2. If CI produces artifacts: download and review runtime\_info.txt and diagnostics. Apply minimal safe seccomp adjustments in a draft PR for human review.
3. If CI still cancels early: inspect the failing step logs (tests job) and fix the underlying error (commonly: incorrect setup-python versions, environment mismatch, or step timeouts). Use explicit pytest outputs (junitxml + test.log) and upload with always(): true so we can download logs when failures occur.
4. Once CI produces runtime info, iterate seccomp.json conservatively and re-run CI until the docker sandbox tests pass.
5. Finalize TutorAgent persistence (optional): create Supabase progress table schema and add integration tests (mocked). Gate Supabase with config env vars.
6. Add adaptive difficulty improvements and logging in TutorAgent (time-to-pass, error classes), with tests.
7. Add telemetry aggregation and a small diagnostics script to summarize .mammoth/sandbox\_runs.jsonl and CI diagnostics.

Longer-term goals (where we are aiming)

* ATLAS fully integrated: CurriculumAgent -> ExerciseGenerator -> TutorAgent -> CodingAgent.run\_tests -> progress + adaptive heuristics -> ReasoningAgent hints
* Secure \& repeatable sandbox runner in CI with minimal seccomp allow-list and robust telemetry
* Optional Supabase-backed progress persistence (config gated) and dashboard/analytics

How to continue (instructions for Copilot or another developer)

* Work in the branch: agents/mammothos-atlas-agent-system (worktree path: C:\\Users\\runni\\mammoth\_intro\_ai.worktrees\\agents-mammothos-atlas-agent-system)
* To reproduce CI locally:

  * Ensure Docker is available and runs without requiring root in the container. Use the SandboxRunner test script at .github/scripts/run\_sandbox\_test.py.
  * Run unit tests: python -m pytest -q
* When CI artifacts appear, download runtime\_info.txt and diagnostics and look for these markers in runtime\_info:

  * "---RUNTIME-INFO-START---"
  * Seccomp and CapEff entries
* If a seccomp suggestion file appears (diagnostics/suggestion.json), review entries against known minimal syscall list and only accept the smallest-safe additions.

Notes on safety and review

* Never merge seccomp profile changes without human review. The repo includes an optional CI auto-PR flow, but it is gated and should be reviewed before merging.
* Keep Supabase credentials out of the repo. Use environment variables for remote persistence.

Contact points

* Files to inspect when debugging CI: .github/workflows/ci.yml, .github/scripts/run\_sandbox\_test.py, .github/scripts/ci\_seccomp\_tuner.py, .mammoth/seccomp.json, src/mammoth\_os/sandbox\_runner.py

If you want, I can also produce a compact checklist (one-page) to paste into Copilot prompts so it knows exactly which commands and files to run next.

