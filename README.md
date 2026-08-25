# MammothOS — Quick Operations Guide

This repo contains the ATLAS CLI, FastAPI backend, and the Mad Architecht Command Center UI.

## Phase 3/4 productization highlights

- UI story surfaces are now workflow-first:
  - Artifact Library for saved generated reports
  - Task Inbox for queued workflow cards
  - Structured Coding Artifact panel in Agent Console (overview/code/tests/docs/diff)
- Observability surfaces are now tighter:
  - Run History replay keeps task metadata (`task_id`, `trace_id`) and runtime adapter/model context
  - Coding patch apply status is reflected in both artifact detail and run history markers
  - Internet command runs (`/research`, `/web`) are persisted as structured chat events with evidence metadata
- UX consistency updates now live:
  - Theme options are simplified to **Dark** and **Aurora** with legacy `darker` / `midnight` values auto-normalized to **Dark**
  - Runtime status in the top shell is compact by default and can be expanded on demand; the expand/collapse preference persists in browser storage


## MCP Browser Bridge + Repo Access

MammothOS now ships three MCP server configs in `mcp/` that give Mammoth Mind real browser automation, repo read/write access, and git awareness.

### Quick start

```bash
# Install Playwright Chromium (once)
npx playwright install chromium

# Start the browser bridge (headed mode for first auth)
bash scripts/start-browser-mcp.sh        # Linux/macOS
.\scripts\start-browser-mcp.ps1          # Windows
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

## Product docs

- `docs\atlas_fab_product_guide.md` - ATLAS FAB positioning, workflow diagram, and pricing skeleton
- `docs\mammoth_os_package_offering.md` - package offering, install tiers, and commercialization framing
- `ATLAS_MANUAL.md` - operator/CLI playbook and phased upgrade notes
- `ui\mad-architecht-command-center\src\pages\ManualPage.jsx` - in-app UI manual

## Deploy to DigitalOcean droplet (live site)

This repo now includes `.github/workflows/deploy-digitalocean.yml` for push-to-`main` and manual deploys.
Every push to `main` auto-deploys to the live server at `165.227.80.86`.

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

## Standalone ATLAS FAB SDK

MammothOS now exposes an embeddable Python SDK surface for ATLAS so it can be positioned as a standalone product inside another app, workflow, or developer tool.

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
from mammoth_os import AtlasFAB, AtlasFABConfig, ATLASSession
```

Example embedding flow:

```python
from mammoth_os import AtlasFAB, AtlasFABConfig

fab = AtlasFAB(
    AtlasFABConfig(
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
- clear SDK entry point (`AtlasFAB`)
- workspace-scoped learner identity support
- structured runtime-state surface for provider health/fallback visibility
- lesson, submit, next-lesson, and code-gen loops exposed programmatically

## Packaging posture for monetization

The Python package is now closer to a sellable SDK than a repo-only prototype:
- package metadata is declared in `pyproject.toml`
- runtime dependencies are explicit
- server-only dependencies live in the `server` extra
- CLI version is sourced from the package version
- public imports are centralized in `src\mammoth_os\__init__.py`

Highest-value next commercial upgrades after this:
1. hosted API keys / tenant auth
2. usage metering endpoint (`/api/billing/usage` or equivalent)
3. Stripe or billing-provider integration
4. plan enforcement and entitlement middleware
5. SDK docs site + integration recipes for React, FastAPI, and internal tools

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

This build is materially stronger than the original prototype. The highest-value workstreams are now in place: native chat orchestration, runtime guardrails, structured agent contracts, source-aware research outputs, diagnostics/export surfaces, and broader operator health/entitlement visibility.

### Overall scorecard

- System overall: 8.2 / 10
- Most production-ready lanes:
  - CodingAgent: 8.7 (upgraded: asyncio safety, structured logging, exception handling)
  - TutorAgent: 8.2
  - ShellAgent: 8.0
  - Operator Health / Finance Backend: 8.0
  - MammothOS Chat: 8.4
- Most important remaining gaps:
  - LLM Runtime / Provider Chain: 5.5
  - UI / Command Center: 7.5
  - API Server / Orchestration Layer: 7.8

### What is already solid

- Native chat page with operator workflow surfaces and right-rail context panels
- Provider fallback guidance with graceful degradation instead of dead-end failures
- Source-aware outputs for research/market/reflection flows
- Approval gates and rollback-friendly workflow posture
- Health, diagnostics, and export paths for operator validation
- Lessons page now supports an expanded multi-domain track catalog plus an adaptive exercise UI toggle for future non-code lesson surfaces

### What still needs attention before “production grade”

- Runtime/provider UX still leaks raw exceptions when cloud providers are unavailable or keys are missing
- Chat/agent progress surfaces still need more consistent streaming and thought-step visibility across all lanes
- Some UI surfaces are still functionally strong but not yet fully polished for a broad non-technical operator experience

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

## Audit export

- Backend audit API: `GET /api/audit`
- CSV export: `GET /api/audit/export`
- UI path: Diagnostics page → **Export CSV**

## Safety-first agent workflow

- In Agent Console, keep **Preview first** enabled for coding edits.
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
