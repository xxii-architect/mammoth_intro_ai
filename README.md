# MammothOS — Quick Operations Guide

This repo contains the ATLAS CLI, FastAPI backend, and the Mad Architecht Command Center UI.

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
- Review changes in **Pending Approvals**.
- Approve only what you want applied.
- If needed, undo with **Rollback Snapshots** (Restore button).
- Non-coding state mutations now support preview/approval too:
  - `POST /api/atlas/onboard` with `approval_mode: true`
  - `POST /api/atlas/learner/reset` with `approval_mode: true`
  - `POST /api/atlas/reset` with `approval_mode: true`

## Additive agent bridge (Copilot Tasks optional)

MammothOS supports the existing registry-backed runtime and an optional external HTTP bridge.
This is an upgrade-only path: it adds an explicit task runner surface without replacing the native agent runtime.

- `POST /agent/atlas/run` → routes to the runtime `tutor` agent
- `POST /agent/coding/run` → routes to the runtime `coding` agent
- `POST /agent/shell/run` → executes a shell command in the repo worktree with a safe subprocess wrapper

These routes are intentionally additive and can coexist with `GET /api/agents`, `GET /api/modules`, and the plan/execute APIs.

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

## Local AI vs OpenAI routing

Local model support is still active.

Current selection order in `src/mammoth_os/llm_client.py`:
1. `MAMMOTH_LLM_ADAPTER=local` → deterministic local adapter
2. `MAMMOTH_LLM_ADAPTER=ollama|hermes|deepseek|codellama|...` → local Ollama
3. `MAMMOTH_LLM_ADAPTER=openai` → OpenAI
4. `OPENAI_API_KEY` present → OpenAI
5. Ollama running locally → Ollama auto-detect
6. fallback → local deterministic adapter

If you want to prefer local models even when OpenAI key exists, set:
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

