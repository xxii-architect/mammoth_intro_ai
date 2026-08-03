# MammothOS — Quick Operations Guide

This repo contains the ATLAS CLI, FastAPI backend, and the Mad Architecht Command Center UI.

## Start the stack

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

## Safety-first agent workflow

- In Agent Console, keep **Preview first** enabled for coding edits.
- Review changes in **Pending Approvals**.
- Approve only what you want applied.
- If needed, undo with **Rollback Snapshots** (Restore button).

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
