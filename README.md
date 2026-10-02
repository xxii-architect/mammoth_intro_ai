# MammothOS — Quick Operations Guide

This repo contains the ATLAS CLI, FastAPI backend, and the Mad Architecht Command Center UI.

## Current upgrade wave (SDK optimization + Mammoth Mind)

| Phase | What shipped |
|---|---|
| 0–1 | Repo lockdown: no repo selected → no repo context; platform repo owner-only; users connect their own repos (tenant repo sources) |
| 2 | Design tokens, trace vocabulary, public user guide docs |
| 3 | Mammoth Mind agent loop (`mammoth.run.v1`): plan, MCP-style tools, approvals, reasoning/run traces; header pill replaces the floating FAB |
| 4 | Mammoth Paths workspace SDK (Python `MammothPaths`, JS `@mammothos/paths`), server-side tier gates, per-user build log; tutor SDK renamed Mammoth Mind |
| 5 | Tutor delivery: lesson manifests, stall telemetry, comprehension gate with override, retrieval dedupe |
| 6 | Research hygiene: reasoning stripped to traces, relevance/disambiguation filtering, dedupe, truncation repair |

Details for each are in the sections below and in `ATLAS_MANUAL.md`.

## Phase 3/4 productization highlights

- UI story surfaces are now workflow-first:
  - Artifact Library for saved generated reports
  - Task Inbox for queued workflow cards
  - Structured Coding Artifact panel in Agent Console (overview/code/tests/docs/diff)
- Observability surfaces are now tighter:
  - Run History replay keeps task metadata (`task_id`, `trace_id`) and runtime adapter/model context
  - Coding patch apply status is reflected in both artifact detail and run history markers
  - Internet command runs (`/research`, `/web`) are persisted as structured chat events with evidence metadata
  - Chat trust surfaces now consume dynamic backend metadata (`confidence`, `trust_metadata`, `evidence_items`) rather than static UI defaults.
- UX consistency updates now live:
  - Theme options are simplified to **Dark** and **Aurora** with legacy `darker` / `midnight` values auto-normalized to **Dark**
  - Mammoth Mind reply depth adapts to the ask: brief, conversational replies for simple questions and useful structure for complex work
  - Runtime health is a color-coded header pill beside Mammoth Mind; press it to expand provider and fallback details without taking space from page content
  - The chat feed flows directly into the composer without a separating rule


## Repo access model (Mammoth Mind, ATLAS, Workspace)

Enforced server-side in `src/mammoth_os/repo_access.py` (not by UI hiding):

- **No repo selected → no repo context.** There is no implicit default repository.
- **Platform repo is owner/admin-only.** `platform`, `xxii-architect/mammoth_intro_ai`, the backend's own path, and forks of it are rejected for everyone else. Add more private slugs with `MAMMOTH_PLATFORM_REPOS=owner/repo,...`.
- **Users bring their own repos.** `POST /api/mammoth/repo-sources {"repo": "owner/repo"}` clones a public GitHub repo into a per-user sandbox (`MAMMOTH_TENANT_REPO_DIR`, default `.mammoth/tenant_repos/`). Users address it by source id or slug, never by filesystem path. Limit: 5 per user.
- **Writes are proposal-only.** `POST /api/mammoth/repo-sources/{id}/propose` writes on a fresh local branch and returns a git patch. Nothing is pushed. Private repos need the MammothOS GitHub App (not yet registered).
- **Guide uses published docs.** `/guide` answers from `docs/public/` + product guides, not live source.
- **Host-executing agents are admin-only** (shell, filesystem, deploy, build, executor, ui_builder, database, custodial), including the `/agent/*` HTTP routes.
- Production must run with `MAMMOTH_REQUIRE_AUTH=1`; with auth off every request is treated as the local owner.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/mammoth/repo-sources` | List your sources + picker options (platform option only for admin) |
| `POST /api/mammoth/repo-sources` | Connect `owner/repo` |
| `POST /api/mammoth/repo-sources/{id}/sync` | Re-clone latest default branch |
| `DELETE /api/mammoth/repo-sources/{id}` | Remove source and sandbox clone |
| `POST /api/mammoth/repo-sources/{id}/propose` | Branch + patch proposal (never pushed) |
| `POST /api/mammoth/repo-context` | Snapshot for a selected source (403 when denied) |

## Design tokens + trace vocabulary

- Tokens live in `ui/mad-architecht-command-center/src/design/tokens.json` (W3C DTCG format) and compile to `tokens.css` via `npm run tokens` (runs automatically before `npm run build`).
- One agent accent (copper `--mm-color-agent-default`) for agent activity and pending approvals; blue for system state; red only for failures/irreversible actions. Motion tokens drop to 0ms under `prefers-reduced-motion`.
- Trace glyphs (`src/design/traceVocabulary.js`, `TraceGlyph.jsx`): read, searched, fetched, planned, reasoning, ran, tool, delegated, wrote, proposed, awaiting approval, applied, reverted, failed. Every glyph carries a text label; meaning never depends on colour alone.

## Mammoth Mind agent runs (`mammoth.run.v1`)

Mammoth Mind's **Agent** mode (default; toggle to **Classic** in the chat header) runs a plan → tool → observe loop in `src/mammoth_os/agent_loop/` and streams every step as Server-Sent Events. The UI renders them as a collapsible timeline: plan checklist, one-line reasoning summaries, tool rows, proposed diffs, and inline approval cards. Slash commands and attachments still use the classic chat path.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/mammoth/tools?repo=` | Tool catalog visible to *you* for that repo selection |
| `POST /api/mammoth/runs` | Start a run (SSE). Body: `message`, `agent_id`, `repo_context.root`, `approval_mode` (`tools`\|`always`), `thread_id` |
| `GET /api/mammoth/runs` / `GET /api/mammoth/runs/{id}?after=` | Your recent runs / replay events after a sequence number |
| `POST /api/mammoth/runs/{id}/approval` | `{approval_id, decision: approve\|reject, note}` → resumes the stream (audited) |
| `POST /api/mammoth/runs/{id}/cancel` | Stop a run |

Event types: `run.started`, `plan.updated`, `reasoning.summary`, `tool.call`, `tool.result`, `approval.requested`, `approval.resolved`, `diff.proposed`, `message.delta`, `message.completed`, `run.awaiting_approval`, `run.completed`, `run.failed`, `run.cancelled`. Each event carries `contract`, `run_id`, `seq`, `ts`.

Rules the loop enforces:

- **Tool tiers:** `read`, `network`, `write` (proposal-only, never touches the checkout), `exec` (always needs approval). MCP tools whose names look mutating also need approval; `git_push` is never exposed.
- **Repo tools follow the repo access model.** No repo selected → no repo tools. Paths are repo-relative; `..`, absolute paths, `.git`, symlinks, and secret files are refused.
- **Patches are edit-first.** `repo_propose_patch` takes either full `content` (new or small files) or `edits` (exact `old` → `new` snippets, each matching once) per file, so the model never has to re-send a large file. A missed edit reports the line(s) where its first line appears. The connected repo is named in every prompt.
- **Large files:** `repo_read_file` can reach any line of files up to 5 MB (400 lines / 20 KB per call, with `total_lines` and `next_start_line`). The newest three tool results are shown to the model in full (24K chars) as raw text, and older ones are condensed. Clipped excerpts always state the last line shown, so the model never edits text it hasn't seen. DeepSeek's native tool-call markup is parsed as a real tool call.
- **MCP access:** each `mcp/*.json` declares `access: admin|tenant`. Admin repo servers (filesystem, git) are only offered to the owner with the platform repo selected; tenant servers run with the user's sandbox clone as cwd.
- **Honest output:** reasoning lines are short model-written summaries (no hidden chain-of-thought). Repeated identical tool calls and exhausted step budgets go straight to a final answer. A cut-off or malformed decision is never shown to the user: the model is told and retries once, then the run ends with a plain message. With no cloud or Ollama provider the run says it is offline instead of echoing.
- Runs are stored per user under `.mammoth/agent_runs/` (last 50); other users get 404.
- `/api/internet/*` fetches refuse private, loopback, and link-local targets, including on redirects (SSRF guard).

## MCP Browser Bridge + Repo Access

MammothOS now ships three MCP server configs in `mcp/` that give Mammoth Mind real browser automation, repo read/write access, and git awareness.

## Repo-context quick prompting (Mammoth Mind + ATLAS)

If you want the chat assistant to read file contents (not just repo names), include at least one of:

- a filename (`api_server.py`, `DiagnosticsPage.jsx`)
- a relative path (`src/mammoth_os/atlas_session.py`)

A repository must be selected in the Repo Context panel first (see the repo access model above).

What now happens automatically:

- filename/path hints in natural language are resolved to real tracked files when possible
- repo context falls back to token-based search when full-query grep returns no hits
- chat evidence now includes repo snippet/search signals so trust badges can reflect real context use
- the chat response reports `repo_scope` (`none`, `tenant`, `platform`, `public_docs`) and a `repo_access_notice` when a request was denied

### Quick start

```bash
# Start the browser bridge (headed mode for first auth)
bash scripts/start-browser-mcp.sh        # Linux/macOS
.\scripts\start-browser-mcp.ps1          # Windows
```

Linux fallback for non-interactive audits:

```bash
MCP_BROWSER_MODE=system-headless bash scripts/start-browser-mcp.sh
```

If needed, point at a specific browser:

```bash
MCP_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium MCP_BROWSER_MODE=system-headless bash scripts/start-browser-mcp.sh
```

### MCP servers

| Server | Config | What it does |
|---|---|---|
| **Browser (Playwright)** | `mcp/playwright.json` | Headed Chromium automation — navigate, click, fill, screenshot, Lighthouse audit |
| **Filesystem** | `mcp/filesystem.json` | Read/write repo files (secrets denied) |
| **Git** | `mcp/git.json` | status, diff, log, branch; commit/push require approval |

### Site audit intent

In Agent Console, use intent `site_audit` to run a full browser + Lighthouse audit against any URL. Results include heading structure, nav/CTA extraction, performance score, SEO score, accessibility score, and top 10 fix opportunities.

### MCP status in UI

The **Modules page** shows a **MCP Tool Bridges** panel with live ready/needs_setup/disabled status for each bridge.

## 8 → 9 upgrade phases (completed)

All four phases of the 8 → 9 pass are now done:

1. **Execution quality loop ✓** — plan → act → verify → retry with explicit success checks; structured agent responses in place.
2. **Browser automation layer ✓** — stateful navigation, form filling, and replayable browser actions.
3. **Agent memory + evals ✓** — durable `MemoryEngine` records ATLAS lesson outcomes; `/api/memory` and `/api/atlas/evals` expose history; eval observability is wired.
4. **UI / manual / docs refresh ✓** — `ATLAS_MANUAL.md`, the in-app Manual page, `LandingPage` doc links, and this README are now in sync.

## 9.5 hardening pass (completed)

- Runtime reliability is now fail-closed for fallback conditions so degraded provider states are explicit.
- `/api/health` now emits a `health_gate` snapshot that combines runtime, env, venv, and repo readiness.
- `/api/release-readiness` now emits both `release_gate` and `eval_gate` snapshots and blocks release readiness when eval history is absent or below threshold.
- ATLAS learner context now includes `outcome_summary`, `learning_signal`, and `progress_score` for measurable tutoring outcomes.
- `AtlasFAB.snapshot()` now includes explicit `contract_version`, `product_surface`, tenant binding state, and usage policy metadata.
- Billing warning behavior is available through `GET /api/billing/usage/current` with preview-safe metering labels and warning levels.

## Product docs

- `docs\atlas_fab_product_guide.md` - Mammoth Mind tutor SDK (formerly ATLAS FAB) positioning, workflow diagram, and pricing skeleton
- `docs\public\mammoth_mind_user_guide.md` - end-user guide for Mammoth Mind (agent mode, traces, repo context, tutor)
- `docs\public\mammoth_paths_sdk_guide.md` - Mammoth Paths workspace SDK guide (Python + JS)
- `packages\mammoth-paths\README.md` - JS client package reference
- `docs\mammoth_os_package_offering.md` - package offering, install tiers, and commercialization framing
- `ATLAS_MANUAL.md` - operator/CLI playbook and phased upgrade notes
- `ui\mad-architecht-command-center\src\pages\ManualPage.jsx` - in-app UI manual

## Deploy to DigitalOcean droplet (live site)

This repo now includes `.github/workflows/deploy-digitalocean.yml` for push-to-`main` and manual deploys.
Every push to `main` auto-deploys to the live server at `165.227.80.86`.
The deploy workflow now runs release guardrail tests first and only deploys when they pass.

### Mandatory release gate workflow

`.github/workflows/release-guardrails.yml` enforces the reliability/eval/tutor/SDK gate suite on:
- pull requests targeting `main`
- pushes to `main`
- manual workflow dispatch

Recommended branch protection policy:
- require `Release Guardrails / guardrails` to pass before merge
- require `CI / tests` to pass before merge

### GitHub repository secrets (set once under Settings → Environments → production)

Required:

| Secret | Value |
|---|---|
| `DO_SSH_PRIVATE_KEY_B64` | **base64-encoded** deploy private key (preferred — avoids multiline secret corruption) |
| `DO_HOST` | `165.227.80.86` |
| `DO_USER` | `root` |
| `DO_APP_PATH` | `/opt/mammothos/mammoth_intro_ai` |
| `DO_DEPLOY_COMMAND` | `bash /opt/mammothos/mammoth_intro_ai/scripts/deploy-droplet.sh` |

Optional:

| Secret | Default |
|---|---|
| `DO_SSH_PRIVATE_KEY` | Fallback plain-text key (use B64 instead whenever possible) |
| `DO_PORT` | `22` |
| `DO_BRANCH` | `main` |
| `DO_KNOWN_HOSTS` | Auto-scanned via `ssh-keyscan` if omitted |

### Generating the base64 deploy key (one-time setup)

```bash
# On your local machine — encode the existing deploy key
base64 -w 0 ~/.ssh/mammoth_deploy_ed25519
# Paste the output as DO_SSH_PRIVATE_KEY_B64 in GitHub secrets
```

### Backend restart (on droplet)

Always use systemd — **never** start uvicorn manually on the server:

```bash
sudo systemctl restart mammothos   # restart backend
sudo systemctl status mammothos    # check health
sudo journalctl -u mammothos -n 50 # tail logs
```

The service runs: `python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8000`

### Manual deploy (without GitHub Actions)

```bash
ssh root@165.227.80.86
bash /opt/mammothos/mammoth_intro_ai/scripts/deploy-droplet.sh
```

## SDKs at a glance

| SDK | What it embeds | Python | JavaScript |
| --- | --- | --- | --- |
| **Mammoth Mind** (tutor; formerly ATLAS FAB) | Adaptive lessons, submissions, progress, runtime state | `from mammoth_os import MammothMind` | (UI pill in the app) |
| **Mammoth Paths** (workspace) | Mammoth Mind agent runs + approvals, bring-your-own repos, notes, build log, owner terminal | `from mammoth_os import MammothPaths` | `@mammothos/paths` in `packages/mammoth-paths/` |

The `AtlasFAB*` names are permanent aliases for `MammothMind*` (same classes), and wire values such as `product_surface: "atlas_fab"` are unchanged, so existing integrations keep working.

## Mammoth Paths workspace SDK

Mammoth Paths is a thin, versioned client (`mammoth.paths.v1`) over the backend. Every call is scoped server-side to the caller's token, so an embedder can never read another user's runs, repos, notes, or build log, or the platform repository.

```python
from mammoth_os import MammothPaths

paths = MammothPaths("https://your-backend", token=user_access_token, usage_hook=print)
paths.connect_repo("owner/repo")                       # public GitHub repo -> private sandbox
result = paths.run(
    "Find where auth tokens are validated",
    repo="owner/repo",
    on_event=lambda e: print(e.type),                 # mammoth.run.v1 events
    approve=lambda e: e.data["tool"].startswith("repo_"),  # optional approval policy
)
print(result.status, result.reply, result.diffs)
paths.save_note("Follow up on token expiry", title="Auth")
paths.log_build("Shipped token validation fix")
```

```js
import { createPathsClient, createRunStore } from '@mammothos/paths'

const paths = createPathsClient({ baseUrl: 'https://your-backend', getToken: () => session.access_token })
const store = createRunStore()                   // React: useSyncExternalStore(store.subscribe, store.getSnapshot)
const result = await paths.run('Summarize the README', { repo: 'owner/repo', onEvent: store.dispatch })
```

Surface access:

| Surface | Who |
| --- | --- |
| Agent runs, tools, repo sources | Any signed-in user (own data only) |
| Notes, build log | Pro / Enterprise / developer access, enforced server-side (`tier_required` 403 otherwise); entries are per user, and pre-scoping build-log entries stay owner-only |
| Terminal | Owner/admin only |

`usage_hook` / `usageHook` receives `{surface, method, path, status, duration}` for every call. Use it for client-side metering until server-side tenant metering ships. The JS package is `private: true` until you decide to publish it. The app consumes it from source (Vite alias) so the UI and embedders fold run events identically.

## Mammoth Mind tutor SDK (formerly ATLAS FAB)

MammothOS exposes an embeddable Python SDK surface for the tutor so it can be positioned as a standalone product inside another app, workflow, or developer tool.

### Install

```bash
pip install mammoth-os
```

For the FastAPI backend / UI stack:

```bash
pip install mammoth-os[server]
```

Core public imports:

```python
from mammoth_os import MammothMind, MammothMindConfig, ATLASSession
# Legacy names still work: AtlasFAB, AtlasFABConfig, AtlasFABError
```

Example embedding flow:

```python
from mammoth_os import MammothMind, MammothMindConfig

fab = MammothMind(
    MammothMindConfig(
        user_id="workspace:customer-123",
        adapter="openai",
        audience="developer",
        mode="tutor",
        metadata={
            "learner_context": {
                "goals": ["Ship a safer integration"],
                "preferred_pacing": "steady",
            }
        },
    )
)

lesson = fab.start_lesson("FastAPI authentication basics", difficulty="beginner")
result = fab.submit(solution_code="def solution(token):\n    return bool(token)\n")
runtime = fab.runtime_state()
```

Embeddable monetization strengths now present:
- clear SDK entry point (`MammothMind`, alias `AtlasFAB`)
- workspace-scoped learner identity support
- structured runtime-state surface for provider health/fallback visibility
- lesson, submit, next-lesson, and code-gen loops exposed programmatically
- lesson delivery surfaces: `fab.lesson_manifest()`, `fab.stall_status()`, `fab.next_lesson(require_mastery=True)` (raises `LessonGateError` until the exercise passes), and a `stall` block on every submission report

## Packaging posture for monetization

The Python package is now closer to a sellable SDK than a repo-only prototype:
- package metadata is declared in `pyproject.toml`
- runtime dependencies are explicit
- server-only dependencies live in the `server` extra
- CLI version is sourced from the package version
- public imports are centralized in `src\mammoth_os\__init__.py`

Highest-value next commercial upgrades after this:
1. Stripe or billing-provider integration
2. plan enforcement and entitlement middleware
3. hosted onboarding + tenant self-serve provisioning
4. SDK docs site + integration recipes for React, FastAPI, and internal tools
5. release-gate policy rollout in CI/CD for mandatory pre-merge checks

### What I meant by a billing / usage API

If you later want the product to warn users when they are close to limits, the backend needs some source of truth for usage.

Typical shape:

```json
{
  "plan": "pro",
  "period_start": "2026-08-01T00:00:00Z",
  "period_end": "2026-08-31T23:59:59Z",
  "usage": {
    "requests": 812,
    "request_limit": 1000,
    "tokens": 184200,
    "token_limit": 250000
  },
  "percent_used": 81.2,
  "warning_level": "elevated"
}
```

Then the UI can render a warning banner or usage meter before the limit is hit.

The backend now also exposes a preview-safe tenant usage response at:

- `GET /api/billing/usage/current`

It is intentionally labeled as preview metering until hosted billing tables are wired.

## Production auth + tenant blueprint

The repo now includes a production-oriented Supabase tenant/auth scaffold at:

- `.mammoth\supabase_tenant_auth.sql`

This layer is intended to sit around your existing `atlas` and `mammoth` product tables rather than replacing them.

What it adds:
- tenant ownership (`public.tenants`)
- tenant membership and roles (`public.workspace_memberships`)
- workspace/account containers (`public.workspace_accounts`)
- tenant settings and feature flags (`public.tenant_settings`)
- usage metering and rollups (`public.usage_events`, `public.usage_rollups_daily`)
- policy acceptance and audit trails (`public.policy_versions`, `public.policy_acceptances`, `public.audit_events`)
- owner bootstrap function for your current Supabase user (`public.bootstrap_tenant_for_user(...)`)

Recommended execution order:
1. Run `.mammoth\supabase_schema.sql` if your baseline tables are not already present.
2. Run `.mammoth\supabase_tenant_auth.sql` in the Supabase SQL Editor.
3. Sign in with the account you want to be the admin/owner.
4. Call `select public.bootstrap_tenant_for_user('MammothOS', 'mammothos');`
5. Wire the backend to read tenant membership before exposing admin controls or shared dashboard state.
6. Only then turn on public domain access.

## What you have now

You are no longer at “prototype with cool features only.” You now have:
- a stronger ATLAS SDK / FAB package surface
- safer provider fallback behavior
- auth-guard and tenant-state regression coverage
- a production tenant/auth SQL blueprint
- clearer separation between customer-facing pricing and internal operator/admin controls
- documentation that points toward hosted SaaS + embeddable SDK monetization

That means the product is much closer to a real platform, but it still needs final live-environment wiring before you should treat it as broadly public.

## Biggest launch blockers to watch for

The most likely things that can hinder a clean launch are:

1. **Auth not fully enforced**
   - If route guards are incomplete, a user could see dashboard shells they should not see.
   - Fix: require authenticated tenant context before loading private state.

2. **RLS/policy mismatch in Supabase**
   - If SQL policies and backend assumptions diverge, users may see empty data, permission errors, or cross-tenant leakage risk.
   - Fix: test owner/admin/member flows explicitly after running the migration.

3. **Placeholder metrics shown in production UI**
   - Finance, usage, or health views should not imply real billing if they are still local/demo-only.
   - Fix: gate incomplete metrics behind “demo/local-only/internal” labels until real usage data is wired.

4. **Provider credits / key exhaustion**
   - The runtime now degrades better, but the user experience still needs friendly messaging and warnings at the product layer.
   - Fix: surface usage and provider status through a real backend endpoint.

5. **Public vs admin route confusion**
   - Marketing pages can be public; dashboards and operator tools should require login and tenant membership.
   - Fix: keep a hard route split between public site, customer app, and internal admin screens.

## Recommended next product steps

### Next step inside the product
1. Run the Supabase migration.
2. Bootstrap your current account as owner/admin.
3. Wire real tenant lookup into login/session handling.
4. Add a real `/api/billing/usage/current` response backed by tenant usage tables.
5. Gate the UI so anonymous visitors only see landing/pricing/compliance pages.

### Next step after that
1. Connect billing (Stripe or equivalent).
2. Define plans, limits, and entitlements.
3. Publish terms, privacy, refund, and acceptable-use policies that match actual behavior.
4. Create a hosted onboarding flow for new tenants.
5. Package the SDK with install docs, examples, and a stable versioned API contract.

## Legal / monetization checklist

Before broadly charging customers, make sure you have:
- real authentication and tenant isolation
- a privacy policy aligned with stored user/session data
- terms of service / acceptable use policy
- billing/refund language that matches your checkout flow
- a support/contact path
- a clear statement of what is beta vs production
- a defined data-retention and admin-access posture

This is the difference between “cool software” and “legitimately monetizable software.”

## Current production-readiness snapshot

This build now includes the completed reliability, eval, tutor-outcome, and SDK contract hardening pass. The core platform has moved from "strong prototype" into "controlled production candidate" status.

### What is now enforced

- Runtime fallback states are explicitly degraded instead of silently treated as ready.
- Health/readiness surfaces fail closed when core dependencies are not healthy.
- Release readiness includes an ATLAS eval gate so weak or missing eval history blocks green release status.
- Tutor outcomes are measurable through explicit learner signals (`learning_signal`, `progress_score`, `outcome_summary`).
- SDK snapshots expose stable contract and tenant/usage metadata for embedders.

### Remaining gap is execution polish, not core wiring

- CI enforcement for release-gate policy should be mandatory on every merge path.
- UI polish on lower-traffic pages still needs one final visual pass.
- Hosted billing provider integration is still pending (current usage endpoint is intentionally preview-safe).

## Start the stack

One-click (Windows):
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\start-mammothos.bat
```

This opens two terminal windows automatically:
- Backend (FastAPI on port 8000)
- Frontend (Vite on port 5173)

If you see `WinError 10013`, port 8000 is usually already occupied. Stop the listener and retry:
```powershell
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -First 1
Stop-Process -Id $conn.OwningProcess
.\start-mammothos.bat
```

Backend:
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\.venv\Scripts\Activate.ps1
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system\ui\mad-architecht-command-center
npm run dev
```

UI: http://localhost:5173

System health only checks the Vite dev server when auth is off (local dev), using `MAMMOTH_DEV_SERVER_PORT` (default 5173). A stopped dev server shows as a warning and never blocks the runtime health gate; production does not report it at all.

## Audit export

- Backend audit API: `GET /api/audit`
- CSV export: `GET /api/audit/export`
- UI path: Diagnostics page → **Export CSV**

## Agent Workspace

The Agent page opens on a calm workspace instead of a console:

- **Roster**: agents in plain language (what each one is for), with a live Ready / Working / Offline status from `/api/agents`. System agents are hidden behind **Show system agents**.
- **Agent chats**: each agent keeps its own thread (stored locally, last 30 messages). Follow-ups send the last 8 turns as `payload.history`, so the agent remembers the conversation. Start a message with `@reflection`, `@coding`, `@research`, etc. to send that message, with the thread's context, to another agent.
- **Team run**: describe an objective, preview the plan (`POST /api/plan-execute` with `dry_run: true`), untick steps you don't want, then run the selected `step_ids`. Each step sees earlier results, and a final synthesis step returns one answer (`summary`). Every step expands to show its full output.
- **Advanced**: creativity (temperature), "Preview file changes before applying", and **Classic console** (the original intent/payload console, unchanged).
- The right-hand panel (runs, approvals, autonomous runs) stays as it was.

Conversation history and earlier step results reach the model through a scoped **background channel** (`mammoth_os.llm_client.conversation_context`), never by rewriting the agent's prompt. Template-based agents (reflection, tutor flows) treat the prompt as a topic, so stuffing transcripts into it would leak them into the output.

## Safety-first agent workflow

- In the Agent page (Advanced → Preview file changes before applying, or Preview first in the classic console), keep previews enabled for coding edits.
- The Agent Console prompt box accepts short one-line prompts, but best results come from: objective + scope + constraints.
- The Command Center now includes an in-app **Manual** page with terminal examples and prompt patterns for new users.
- Review changes in **Pending Approvals**.
- Approve only what you want applied.
- If needed, undo with **Rollback Snapshots** (Restore button).
- Non-coding state mutations now support preview/approval too:
  - `POST /api/atlas/onboard` with `approval_mode: true`
  - `POST /api/atlas/learner/reset` with `approval_mode: true`
  - `POST /api/atlas/reset` with `approval_mode: true`

## CodingAgent hardening pass (v1.2)

Latest improvements to CodingAgent stability and error handling:
- **Asyncio safety**: Replaced unsafe `asyncio.run()` calls with a robust `_run_async()` bridge that detects and handles already-running event loops gracefully.
- **Structured logging**: Wired `log()` method to the standard Python `logging` module for consistent log levels and operator visibility.
- **Exception safety**: Added proper exception handling in async task execution and commit operations with detailed logging for debugging.
- **Type hints**: Fixed Python <3.10 compatibility by using `Union` instead of `|` type syntax.
- **Input validation**: Added guards for empty file lists in `commit_changes()` to prevent silent git errors.

These changes reduce the risk of runtime `RuntimeError` exceptions when CodingAgent is called from async contexts or when handling large workloads.

## Source-aware output contracts

The runtime now treats output quality as a real contract instead of a loose text blob.

- `coding` responses preserve structured payloads instead of flattening everything to raw strings.
- Documentation requests require a real path or source snippet; placeholder values like `unknown` now fail with a `needs_context` result instead of fake docs.
- `brand_voice` accepts explicit modes such as `stakeholder_summary`, `tutorial_copy`, and `rewrite_with_constraints` so the tone and audience stay consistent.
- UI prompts should specify: objective, target file or scope, audience, and guardrails.

This keeps the output source-aware, easier to validate, and far less likely to devolve into generic product copy.

### Research output hygiene (`src/mammoth_os/research_quality.py`)

- **Reasoning never leaks into deliverables.** `<think>`/`<thinking>`/`<reasoning>` blocks (closed, dangling, or cut off mid-way) and task meta-lines ("Okay, let me…", "Here's the section:", "Let me know if…") are stripped from research JSON, long-form sections, and conclusions. Stripped reasoning is returned separately as `reasoning_trace` (research) or per-section `trace` (long-form).
- **Relevance filter.** Disambiguation pages are always dropped. Sources sharing no keywords with the query (light stemming, so "learners" matches "learning") are dropped when at least two on-topic sources exist; otherwise they are kept last with `relevance: "weak"`. Provided sources are never filtered. Dropped sources are listed in `sources_filtered`.
- **Entity disambiguation.** When the query names an entity (quoted phrase or multi-word proper noun), sources that don't mention it in full are ranked below those that do. They are never dropped, because the entity may just be a qualifier.
- **Dedupe.** Near-duplicate findings, key facts, key points, next steps, and concepts are collapsed. Long-form documents drop paragraphs that repeat an earlier section.
- **Completeness.** Long-form sections retry once when the model fails or returns nothing but reasoning. Text cut off mid-sentence is trimmed back to the last complete sentence. A section that still fails is marked `status: "failed"` with empty content instead of embedding an error string in the document. The `quality` block reports failed, retried, and trimmed sections, duplicates removed, and sources filtered.
- **Prompt contracts.** Summarize and curriculum modes ask for their own schema fields (`key_points[]`, `core_concepts[]`, `learning_path[]`) instead of the research-only `findings[]`. Outline fallbacks use topic-specific headings instead of market boilerplate.

## Additive agent bridge (Copilot Tasks optional)

MammothOS supports the existing registry-backed runtime and an optional external HTTP bridge.
This is an upgrade-only path: it adds an explicit task runner surface without replacing the native agent runtime.

- `POST /agent/atlas/run` → routes to the runtime `tutor` agent
- `POST /agent/coding/run` → routes to the runtime `coding` agent
- `POST /agent/shell/run` → executes a shell command in the repo worktree with a safe subprocess wrapper

These routes are intentionally additive and can coexist with `GET /api/agents`, `GET /api/modules`, and the plan/execute APIs.

## Copilot Tasks integration appendix

This is the recommended integration model when an external orchestrator such as GitHub Copilot / Copilot Tasks needs to call into MammothOS without bypassing the native runtime.

- Keep MammothOS as the source of truth for agents, workflows, and state.
- Use Copilot as a conductor, never as the direct file editor.
- Route work through `tutor`, `coding`, and `shell` agent endpoints rather than editing the repo directly.
- Preserve preview-first approval, rollback, and observability.

Example mapping:
```json
POST /agent/coding/run
{
  "objective": "Apply MammothOS Command Center theme to NotesPanel.",
  "context": {
    "files": [
      "ui/mad-architecht-command-center/src/notes/NotesPanel.tsx",
      "ui/mad-architecht-command-center/src/index.css"
    ],
    "plan_profile": "atlas_first",
    "approval_mode": true
  }
}
```

This aligns with the actual runtime contract in `api_server.py`: the external bridge is additive and the real work remains in the runtime-backed agent system.

## Autonomous run contract (Phase 5 prep)

- `GET /api/autonomous/runs` returns a unified run feed from:
  - orchestrator plan/execute tasks
  - ATLAS plan history
- Response includes:
  - `contract_version`
  - `profiles` (`atlas`, `coding`, `balanced`, `autonomous`)
  - aggregate `summary`
  - recent `runs` with status/progress/source
- Agent Console now renders an **Autonomous Runs** panel using this endpoint.

## Local AI vs cloud routing

MammothOS supports a safe multi-provider workflow without failing hard when an account is empty or a key is invalid.

Current selection order in `src/mammoth_os/llm_client.py`:
1. `MAMMOTH_LLM_ADAPTER=local` → deterministic local adapter
2. `MAMMOTH_LLM_ADAPTER=ollama|hermes|deepseek|codellama|...` → local Ollama model path
3. `MAMMOTH_LLM_ADAPTER=deepseek|deepseek-api|deepseek-cloud` → DeepSeek cloud reasoning path
4. `MAMMOTH_LLM_ADAPTER=openai` → OpenAI coding path
5. `OPENAI_API_KEY` present → OpenAI (`gpt-4o-mini` by default)
6. `DEEPSEEK_API_KEY` present → DeepSeek cloud fallback
7. Ollama running locally → Ollama auto-detect
8. fallback → local deterministic adapter

Graceful-fallback behavior:
- If DeepSeek or OpenAI rejects the request for quota/billing/auth reasons, the runtime falls back to the next viable provider.
- This is the safe path when a provider runs out of credits or a key has expired.
- The app remains usable rather than crashing with a terminal failure.

Recommended split:
- DeepSeek reasoning / ATLAS tutor / long-context coaching
- OpenAI `gpt-4o-mini` for coding generation and code-review work
- Ollama or local echo only when cloud providers are unavailable

If you want to prefer local models even when cloud keys exist, set:
```powershell
$env:MAMMOTH_LLM_ADAPTER = "hermes"
# or
$env:MAMMOTH_LLM_ADAPTER = "ollama"
```

## Sandbox fallback (until kernel update)

If Docker sandboxing is unavailable, force subprocess mode:

```powershell
$env:FORCE_SUBPROCESS_FALLBACK = "1"
# or
$env:SANDBOX_RUNNER_MODE = "subprocess"
```

This keeps development moving but is less isolated than Docker sandboxing.

## Detailed manuals

- `ATLAS_MANUAL.md` — full CLI + UI operating guide
- `ui\mad-architecht-command-center\README.md` — UI-specific workflows

## UI terminal note

- The Command Center terminal supports safe `python -m cli.main ...` flows, including `atlas code` and `atlas ui` commands.
- Long-running ATLAS coding/UI commands now receive extended backend timeouts so they behave more like a real operator terminal session.

## Lessons + curriculum note

- **Lesson manifest** (`mammoth.lesson_manifest.v1`): `/api/atlas/status`, `/lesson`, `/next`, and `/back` return `lesson_manifest` with prerequisites, sample input, expected output, and "done when" criteria. All of it comes from the real lesson/exercise (asserts in the test scaffold, rubric lines, earlier lesson titles). Missing data stays empty instead of being invented.
- **Stall telemetry** (`mammoth.lesson_telemetry.v1`): every submission records per-lesson attempts, consecutive failures, and a normalized error fingerprint in `lesson_telemetry`. `/api/atlas/submit` returns `stall` (`stalled`, `reasons`, one `suggestion`); the status payload carries `lesson_stall`. The thresholds are 3 failures in a row, the same error twice, or 20 minutes without progress.
- **Comprehension gate**: `POST /api/atlas/next` returns `{"status": "gated", "gate": {...}}` when the current exercise has not passed. Send `{"override": true}` to move on anyway; overrides are written to the audit log. Lessons without a gradable exercise are never gated.
- **Retrieval hygiene**: lesson chunk retrieval drops empty and duplicate/near-duplicate chunks before taking the top-k, and labels each chunk with `source_label`.

- `GET /api/atlas/modules` now exposes a broader module catalog across outdoors, emergency, business, health, technology, creative, and life-skills tracks.
- The Lessons page includes an **Adaptive UI** toggle that morphs the exercise surface by lesson type (`code`, `knowledge`, `writing`, `checklist`, `scenario`).
- Until deeper non-code submission contracts land, non-coding lessons still use a Python-backed helper exercise under the hood, but the prompt/test scaffolding is now topic-aware instead of a one-size-fits-all generic coding task.

## Scope + suggestions (credit-efficient path)

### Current scope
- Keep ATLAS + MammothOS stable as a tutor-first system with diagnostics, audit history, and operator logging.
- Prioritize quality and continuity over adding paid features too early.
- Keep product language compliance-safe (no overclaims, no patent claims unless filed).

### Suggestions (in order)
1. Expand **lessons domain architecture** (lowest credit cost, mostly UI/state wiring).
2. Expand **health page** into personal + system health (medium cost).
3. Expand **finances page** into personal + business tracking (medium-high cost).
4. Defer payment wiring until core learning loops and trust surfaces are locked.

### Keep in mind
- Always start from `.\start-mammothos.bat` first to avoid false "disconnected" states.
- Port 8000 conflicts can mimic backend failures; clear listeners before retrying.
- Track meaningful work in Build Log + Diagnostics so progress is provable and reviewable.
