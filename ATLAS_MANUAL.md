# 🐘 ATLAS Manual — MammothOS CLI Reference

> **Quick rule:** every command starts with `python -m cli.main atlas …`
> Run this from the repo root. **Your `.env` file is now loaded automatically** —
> no more setting env vars by hand in every terminal.

## Production-readiness snapshot

This repo is now in a strong “operator-grade prototype” position rather than a bare demo. The native chat surface, runtime orchestration, and production-guardrail work have all moved the stack much closer to real deployment readiness.

### Current rating summary

| Area | Score | Notes |
|---|---:|---|
| System overall | 8.2 / 10 | Strong workflow surface and core runtime, but still not fully hardened for cloud outage UX |
| MammothOS Chat | 8.4 / 10 | Native chat, multi-agent routing, task cards, approvals, and source-aware evidence cards are in place |
| CodingAgent | 8.5 / 10 | Best-validated lane; structured and predictable |
| TutorAgent | 8.2 / 10 | Adaptive tutoring and review flow are strong |
| ShellAgent | 8.0 / 10 | Safety controls are solid and approval-aware |
| API Server / Orchestration | 7.8 / 10 | Good runtime contract, needs smoother error UX and more explicit runtime-state surfaces |
| UI / Command Center | 7.5 / 10 | Operationally useful and polished, but still needs a finishing pass for broad operator usability |
| LLM Runtime / Provider Chain | 5.5 / 10 | The fallback chain exists but still produces rough edges when keys or credits are unavailable |

### What is “ready enough” now

- Developer/operator testing flows are working and validated
- Approval gating, diagnostics export, and health pages are operational
- Core agent lanes are normalized around structured outputs
- Native chat can route to agent work and keep operational context visible

### What still needs a final pass

- Provide more graceful messaging when provider keys or credit pools are exhausted
- Tighten raw runtime exception handling in the chat and provider chain
- Continue polishing the comfort layer for broad adoption: clearer status, thought trails, and less “internal debugging” language in user-facing responses

---

## 1 — One-time setup

### 1a. `.env` file (set once, loads automatically)
The CLI reads `.env` from the repo root on every run. You do not need to
`$env:...` anything manually anymore — just keep the file up to date.

> **Update:** the CLI now hard-pins itself to the active worktree `src\` path on
> startup, so legacy parent-repo installs or stale boot scripts are much less
> likely to hijack imports.

Required keys in `.env`:
```
SUPABASE_URL              = https://mkstgbegjkonmwmjqkpz.supabase.co
SUPABASE_SERVICE_ROLE_KEY = <your service_role JWT>
OPENAI_API_KEY            = <your OpenAI key>          # optional if using Ollama
```

> **PowerShell JWT tip:** always wrap the value in double-quotes in the `.env` file:
> `SUPABASE_SERVICE_ROLE_KEY="eyJhbG..."`

---

## 0 — Scope, suggestions, and operator notes

### Scope right now
- Keep ATLAS as the top-level adaptive tutor and MammothOS as the execution shell.
- Strengthen reliability, continuity, diagnostics, and lesson quality before monetization wiring.
- Maintain enterprise-safe posture: accurate claims, auditable operations, no legal overstatements.

### Suggested next build order (lowest credits first)
1. **Lessons domain architecture** (UI-first track templates, starter pathways, progress shells).
2. **Health dual-mode expansion** (personal readiness + system telemetry in one page).
3. **Finance dual-mode expansion** (personal + business lanes, rollups, and notes).
4. **Payments and checkout** only after the above surfaces are stable and policy-ready.

### Keep in mind
- Use `Preview first` for coding agent edits and approve intentionally.
- Keep startup deterministic (`start-mammothos.bat`) before debugging UI connectivity.
- Record major runs in Build Log and Diagnostics export so work remains portfolio-verifiable.
- Avoid mixing legal claims with roadmap intent; document "current posture" vs "planned posture."

### Source-aware output contracts and prompt shaping

The runtime now keeps structured payloads intact for coding and brand-voice work instead of flattening everything into a raw string, which was the root cause of low-grade generic outputs.

**Core rules:**
- `coding` tasks should always carry a clear `prompt`, `target`, and optional `context.files` or `context.source`.
- Documentation-only requests without a real file path or source snippet return a `needs_context` response rather than fake “generated docs.”
- `brand_voice` tasks should specify `mode`, `audience`, `tone`, and optional `constraints` so the rewrite stays on-message.
- The UI prompt box works best when the user enters: objective + scope + constraints + expected output.

### Additive agent bridge

MammothOS keeps the native runtime-first flow and adds an optional HTTP bridge for external orchestrators such as Copilot Tasks.
The bridge is deliberately additive and does not replace the existing registry + workflow APIs.

```http
POST /agent/atlas/run
POST /agent/coding/run
POST /agent/shell/run
```

Use these endpoints as an optional integration layer when you want an external conductor to delegate to ATLAS or CodingAgent without forcing Copilot itself to do all edits.

### Copilot Tasks integration appendix

This is the recommended integration model when an external orchestrator such as GitHub Copilot / Copilot Tasks needs to talk to MammothOS without bypassing the native runtime.

**Goal:**
- Keep MammothOS as the source of truth for agents, workflows, and state.
- Use Copilot as a conductor, not as the direct file editor.
- Route work through the runtime agents rather than editing files directly from the external tool.
- Preserve safety rails: preview-first, approvals, rollback, observability.

**Connection surface:**
```http
POST /agent/atlas/run
POST /agent/coding/run
POST /agent/shell/run
```

**Contract:**
- `/agent/atlas/run` → routes to the runtime tutor agent for lesson planning, coaching, adaptive feedback, and ATLAS-first orchestration.
- `/agent/coding/run` → routes to the runtime coding agent for code generation, refactor, explain, and UI scaffolding tasks.
- `/agent/shell/run` → executes a safe shell command in the repo worktree using the safe subprocess wrapper.

These routes are additive and coexist with:
- `GET /api/agents`
- `GET /api/modules`
- `POST /api/plan-execute`
- `GET /api/autonomous/runs`

**Copilot Task → MammothOS mapping example:**
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

MammothOS then:
1. Uses the runtime `coding` agent to propose a patch preview.
2. Uses the `tutor` agent if the plan profile is `atlas_first` for strategy and safeguard checks.
3. Surfaces the preview in the approval workflow.
4. Applies changes only after approval, with rollback support enabled.

**Recommended profiles:**
- `atlas_first` — ATLAS strategy layer first, coding subordinate.
- `tutor_coding` — balanced tutoring + implementation.
- `coding_only` — tightly scoped, low-risk code work.
- `autonomous_prep` — larger multi-agent execution with ops and safety steps.

**Safety and authorship rules:**
- Preview-first is mandatory for any Copilot-driven task (`approval_mode: true`).
- No direct file writes from Copilot; all code edits should come through the runtime agent bridge or the plan/execute API.
- Use MammothOS agents as the actual implementation layer; Copilot acts as orchestrator, not direct editor.
- Log and show progress via `GET /api/autonomous/runs` and the build log / diagnostics trail.

**Minimal wiring checklist:**
1. Point the external orchestrator at `http://localhost:8000`.
2. Enable discovery with `GET /api/agents` and `GET /api/modules`.
3. Use the bridge for execution: `POST /agent/atlas/run`, `POST /agent/coding/run`, `POST /agent/shell/run`.
4. Use `POST /api/plan-execute` with `plan_profile` and `approval_mode` for multi-step work.
5. Respect approvals and rollback before any mutable action.
6. Display run history via `GET /api/autonomous/runs`.

---

## 2 — LLM model selection

MammothOS now supports a safe dual-provider runtime: DeepSeek for reasoning-heavy work and OpenAI for coding tasks, with automatic fallback if a provider is out of credits or a key is invalid.

| Priority | Condition | Result |
|---|---|---|
| 1 | `MAMMOTH_LLM_ADAPTER=local` in `.env` | Deterministic echo (CI only) |
| 2 | `MAMMOTH_LLM_ADAPTER=ollama|hermes|codellama|...` | That Ollama model |
| 3 | `MAMMOTH_LLM_ADAPTER=deepseek|deepseek-api|deepseek-cloud` | DeepSeek cloud reasoning path |
| 4 | `MAMMOTH_LLM_ADAPTER=openai` | OpenAI |
| 5 | `OPENAI_API_KEY` is set | OpenAI (`gpt-4o-mini` default) |
| 6 | `DEEPSEEK_API_KEY` is set | DeepSeek cloud fallback |
| 7 | Ollama is running on localhost:11434 | Ollama auto-detected |
| 8 | Nothing available | Local echo fallback |

### Recommended provider split

- Use DeepSeek for reasoning, long-context tutoring, and ATLAS coaching.
- Use OpenAI `gpt-4o-mini` for coding generation, repair, and code review.
- If the current provider is out of quota / billing blocked / key invalid, MammothOS retries through the next provider instead of dead-ending the workflow.

### Cloud keys in `.env`

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
MAMMOTH_LLM_ADAPTER=deepseek
```

### Installed local models (Ollama)

All of these are ready to use — set `MAMMOTH_LLM_ADAPTER` in `.env`:

| Alias | Actual model | Best for |
|---|---|---|
| `hermes` | hermes3:8b | ATLAS tutor, hints, general (default) |
| `deepseek` | deepseek-coder:latest | Code generation |
| `qwen-coder` | qwen2.5-coder:latest | Code generation (alt) |
| `codellama` | codellama:latest | Code generation (fallback) |
| `llama` | llama3.1:8b | General purpose |
| `mistral` | mistral:latest | General purpose |
| `qwen` | qwen2.5:latest | General purpose |
| `phi` | phi3:latest | Fast/lightweight tasks |
| `nous-hermes` | nous-hermes:7b | Instruction following |

**Switch models by changing one line in `.env`:**
```
MAMMOTH_LLM_ADAPTER=deepseek    # DeepSeek reasoning path (cloud)
MAMMOTH_LLM_ADAPTER=hermes      # Hermes3 for ATLAS (local)
MAMMOTH_LLM_ADAPTER=openai      # force OpenAI even if Ollama is running
```

**Ollama must be running** for local models:
```powershell
ollama serve    # start in a separate terminal (or it auto-starts on Windows)
```

---

## 3 — All wired CLI commands

### Start a lesson
```powershell
python -m cli.main atlas lesson "Python for loops"
python -m cli.main atlas lesson "Python lists" --difficulty intermediate
python -m cli.main atlas lesson "Recursion" --module 2 --lesson 1
python -m cli.main atlas lesson "Functions" --llm   # LLM-generated exercise
```

### Check your current session
```powershell
python -m cli.main atlas status           # shows active lesson + exercise prompt
python -m cli.main atlas status --db      # also fetches the latest mammoth.ai_sessions row
```

### Submit a solution
```powershell
python -m cli.main atlas submit solution.py
python -m cli.main atlas submit --inline "def solution(a, b): return a + b"
```
On pass: XP recorded in Supabase. On fail: error + TutorAgent hint.

### Advance to the next lesson
```powershell
python -m cli.main atlas next
```

### Reset your session
```powershell
python -m cli.main atlas reset
```

### CodingAgent — generate code
```powershell
python -m cli.main atlas code generate "a function that sums a list"
python -m cli.main atlas code generate "binary search implementation"
python -m cli.main atlas code generate "a parser that reads a build log into JSON"
```
Generates solution() + tests + docs, runs tests in sandbox, logs to Supabase.
Works with both OpenAI and all Ollama models.

Use this command for Python/problem-solving work. If the prompt is UI-first (for example `notes panel`, `dashboard`, `component`, `theme`, or `styling`), the CLI now redirects you to the UIBuilder path instead of generating misleading Python:

```powershell
python -m cli.main atlas ui component "upgrade my notes panel"
python -m cli.main atlas ui palette "apply MammothOS command center styling to NotesPanel"
```

### CodingAgent — refactor a file
```powershell
python -m cli.main atlas code refactor my_script.py             # writes my_script.refactored.py
python -m cli.main atlas code refactor my_script.py --inplace   # overwrites original
python -m cli.main atlas code refactor my_script.py --output out.py
```

### CodingAgent — explain a file
```powershell
python -m cli.main atlas code explain my_script.py
```

### UI scaffolding — generate a starter app
```powershell
python -m cli.main atlas ui scaffold "ATLAS progress dashboard"
```
Creates a Vite + React starter app in `ui/atlas-progress-dashboard`.

Run it locally:
```powershell
cd ui/atlas-progress-dashboard
npm install
python server.py
```
In a second terminal:
```powershell
cd ui/atlas-progress-dashboard
npm run dev
```
Open http://localhost:3000. The Vite frontend proxies `/api/*` to the Python API server on port `8765`, which reads live Supabase metrics from your repo `.env` file.

This is a lightweight first-pass UI workflow: prompt → scaffold app → preview locally → show real ATLAS progress data.

### UI generator baseline verification
From the active worktree root, this PowerShell-native sequence verifies the UI
generator path and the current scaffold target:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m cli.main atlas ui scaffold "mad architecht command center"
& $py -m cli.main atlas ui component "Create status card component"
& $py -m cli.main atlas ui style "Apply enterprise dark neon style tokens"
& $py -m cli.main atlas ui backend "Generate API hooks for /api/status and /api/agents"
& $py -m cli.main atlas ui graph "Generate simple activity graph module"
& $py -m cli.main atlas ui palette "Generate command palette actions"
& $py -c "import json,pathlib; s=json.loads(pathlib.Path('.mammoth/atlas_ui_state.json').read_text('utf-8')); assert 'mammoth_intro_ai.worktrees' in s.get('active_ui_project',''); print('State check: OK')"
Set-Location ui\mad-architecht-command-center; npm run build; Set-Location ..\..
```

---

## 4 — Adaptive learner model

ATLAS now keeps a lightweight learner profile in `.mammoth/atlas_learner_model.json` and surfaces it in the tutor UI. The model tracks concept mastery, confidence, streaks, error patterns, and recent outcomes so future lessons and hints can be tuned to the student’s current state.

The tutor UI reads this profile through `/api/atlas/status` and shows the recommended difficulty, pacing, and the weakest concepts to focus on next.

---

## 5 — ATLAS plan + execute

ATLAS can now turn the current lesson or exercise into a visible tutor plan. The plan is generated from the active lesson context, executed step-by-step through the agent runtime, and surfaced in the ATLAS tutor page with real progress and step status.

- Use the new **Build Plan** action in the ATLAS lesson page to generate a plan from the active exercise.
- Choose a tutor plan profile directly in the lesson page:
  - **Tutor + Coding** for implementation-heavy work
  - **Balanced** for mixed coaching/execution
  - **ATLAS-first** for more strategic tutoring and safeguards
  - **Autonomous Prep** to include community and custodial readiness steps
- Each plan step is executed by the relevant sub-agent (seed/research/coding/reflection/ops) and reported back to the tutor UI.
- The plan is persisted in the atlas session state so returning to the lesson preserves the most recent plan view.
- Every completed plan now includes an **ATLAS synthesis** block with:
  - learner-facing summary
  - coding brief
  - safe next action
  - checkpoint list distilled from the sub-agent outputs

---

## 6 — ATLAS evals + observability

ATLAS now has a lightweight tutor observability layer in the lesson UI.

- Use **Run Evals** in the tutor page to execute the current smoke checks:
  - onboarding profile persistence
  - adaptive feedback generation
  - resume continuity reconstruction
- Recent eval runs are stored in `.mammoth/atlas_evals.json` and surfaced back into the tutor UI.
- The tutor sidebar now shows compact observability metrics:
  - learner pass rate
  - eval pass rate
  - plan/eval run counts
  - guard trigger rate
  - sandbox success rate
- The tutor page also shows recent plan history so you can track ATLAS orchestration over time.

---

## 7 — Verify Supabase connectivity

```powershell
python .mammoth\check_supabase.py
```
Expected output:
```
OK  mammoth.users accessible
OK  mammoth.progress accessible
OK  mammoth.activity_log accessible
OK  atlas.atlas_progress accessible
OK  atlas.adaptive_metrics accessible
OK  atlas.community_stats accessible
OK  atlas.sessions accessible
```

Show the latest AI session row:
```powershell
python -m cli.main atlas status --db
```

> **If `ai_sessions` shows 404:** Run `.mammoth/supabase_schema.sql` in Supabase
> SQL Editor to create the `mammoth.ai_sessions` table.

---

## 8 — Where things live (source map)

| What | Path |
|---|---|
| CLI commands | `cli/atlas.py` |
| CLI entry point (loads .env) | `cli/main.py` |
| LLM routing factory | `src/mammoth_os/llm_client.py` |
| OpenAI adapter (v2 SDK) | `src/mammoth_os/openai_adapter.py` |
| Ollama adapter | `src/mammoth_os/ollama_adapter.py` |
| Session state (local JSON) | `.mammoth/atlas_cli_session.json` |
| Supabase schema | `.mammoth/supabase_schema.sql` |
| Supabase connectivity check | `.mammoth/check_supabase.py` |
| TutorAgent | `src/mammoth_os/agents/tutor_agent.py` |
| CurriculumAgent | `src/mammoth_os/agents/curriculum_agent.py` |
| CodingAgent | `src/mammoth_os/agents/coding_agent.py` |
| Sandbox runner | `src/mammoth_os/sandbox_runner.py` |
| UI shell + routing + FAB | `ui/mad-architecht-command-center/src/App.jsx` |
| All UI pages | `ui/mad-architecht-command-center/src/pages/` |
| API fetch wrapper + WS helper | `ui/mad-architecht-command-center/src/api/client.js` |
| React polling hooks | `ui/mad-architecht-command-center/src/hooks/useApi.js` |
| Design tokens + CSS | `ui/mad-architecht-command-center/src/index.css` |
| FastAPI backend | `api_server.py` (repo root) |
| Runtime data files | `.mammoth/` (notes, buildlog, sales_log, atlas session, eval history) |

---

## 9 — Mad Architecht Command Center (Main UI)

The primary user interface is a full React SPA located at:
```
ui/mad-architecht-command-center/
```

### Start the full stack

**Terminal 1 — FastAPI backend:**
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\.venv\Scripts\Activate.ps1
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — React frontend (Vite):**
```powershell
cd ui/mad-architecht-command-center
npm run dev
```
Open **http://localhost:5173**

### Pages in the UI

| Page | What it does |
|---|---|
| **Home** | Live dashboard: agent status, health dots, build log feed, sales total, quick-copy commands |
| **Agent** | Run any CortexRouter intent (plant_seed, field_ops, research_*, etc.) with live thought stream, approval queue, snapshot rollback, coding shortcuts, and prompt playbook examples |
| **Terminal** | WebSocket terminal wired to the backend. HTTP fallback mode when WS is offline. Quick-action buttons plus ATLAS CLI examples for safe `python -m cli.main ...` runs |
| **Manual** | In-app operator guide for terminal usage, prompt patterns, and recommended workflow habits |
| **Notes** | Full CRUD note-taking, auto-saved to `.mammoth/notes.json` |
| **Modules** | Live scan of all agents in `src/mammoth_os/agents/` |
| **Health** | Real-time service health: Ollama, Supabase, OpenAI, API server — polls every 10s |
| **Log Sale** | Sales tracker: log items + amounts, running total, persisted to `.mammoth/sales_log.json` |
| **Lessons** | Quick-access ATLAS lesson start + embedded tutor chat |
| **ATLAS Tutor** | Full 3-column ATLAS experience: curriculum tree | exercise + code editor | live chat with model selector, lesson memory, and latest submission summary |
| **Build Log** | Log + browse project build entries with tags, persisted to `.mammoth/buildlog.json` |
| **Settings** | System info, env key inspector, ATLAS reset, **theme toggle** (Darker/Dark/Midnight), AI runtime status |

### Agent Console safety flow
- Turn on **Preview first** before using the coding agent for file edits.
- Switch to **Plan + Execute** mode to run multi-agent orchestration from one objective.
- Use **Plan Profile = ATLAS-First** to keep seed/strategy framing at the front of the run.
- Use **ATLAS + Coding Assistant** when you want coding depth without making coding the top-level driver.
- Approved edits are queued in **Pending Approvals**.
- Once approved, the backend applies the change and creates a rollback entry in
  **Rollback Snapshots**.
- Use **Restore** on a snapshot to reverse the approved change.

### Coding shortcuts
When **coding_agent** is selected in the Agent Console, quick templates are
available for:
- `/create`
- `/write`
- `/patch`
- `/insert`

These are the safest way to teach yourself the command shapes while keeping
approval mode on.

### Prompting guidance
- A short sentence is valid in the Agent Console.
- Better prompts usually include:
  1. the outcome you want
  2. the files, module, or page in scope
  3. any constraints like "keep preview first on" or "preserve existing navigation"
- Use **Plan + Execute** for multi-step objectives, tutorials, onboarding, or cross-surface changes.

### Terminal CLI guidance
- The UI terminal is meant to support the same safe MammothOS commands you would run in PowerShell.
- Supported examples now include:
  - `python -m cli.main atlas status`
  - `python -m cli.main atlas code generate "build a MammothOS notes panel"`
  - `python -m cli.main atlas ui component "create a neon command-center status card"`
- For safety, chained shell expressions and metacharacter-heavy commands are blocked in the UI terminal.
- Long-running `atlas code` and `atlas ui` commands get longer backend timeouts than simple status/health calls.

### ATLAS learning memory
The ATLAS Tutor sidebar now shows:
- current lesson resume state
- saved lesson history
- total lesson count in the loaded curriculum
- latest submission outcome and coaching hint
- welcome-back lesson summary when returning to a prior lesson
- deterministic prior-work summary recovered from lesson history, even for legacy state shapes
- quick pull-up actions for related notes and saved flashcards
- onboarding profile controls for experience, pacing, style, goals, and focus areas
- learner memory map summary with recent lesson/concept nodes

### Floating ATLAS Chat (FAB)
A violet 🐘 button is fixed to the bottom-right corner on **every page**.  
Click it → glass chat panel slides up → chat directly with ATLAS tutor without leaving your current screen.  
Wired to `POST /api/atlas/chat` with full chat history.

Phase 2 upgrades now wired in the FAB:
- **Tutor mode** + **Plan + Build mode** toggle
- **No-cheat guard** toggle (blocks direct answer dumping for active exercises)
- automatic **fresh exercise regeneration** when guard is triggered (if enabled)
- page-aware context payload (current page, selection, lesson snapshot) so ATLAS can observe what you're working on
- usage telemetry events (`fab_usage_events`) recorded for future monetization analytics

### Theme Toggle
Settings → Theme section. Three options:
- **Darker** `#050608` — near-black (default)
- **Dark** `#0d1117` — GitHub dark
- **Midnight** `#080c14` — deep blue-black

Applies instantly via CSS custom properties. Persists across sessions via `localStorage`.

### Design System
- Colors: `--shell`, `--photon: #4da6ff`, `--cyan: #00f5d4`, `--violet: #b47cff`
- Glass cards: `backdrop-filter: blur(16px)`, `rgba(13,17,23,0.7)`
- CRT scanline overlay on entire app
- Fonts: Inter (UI), JetBrains Mono (code/terminal)

### API endpoints (api_server.py)

| Endpoint | Purpose |
|---|---|
| `GET /api/status` | Python version, uptime, agent count, engine count |
| `GET /api/health` | Service connectivity: Ollama, Supabase, OpenAI, env keys |
| `GET /api/agents` | List all agent files from `src/mammoth_os/agents/` |
| `POST /api/run` | Run a CortexRouter intent (`{intent, context}`) |
| `POST /api/plan-execute` | Run orchestrated multi-agent plan (`{objective, plan_profile, approval_mode}`) |
| `GET /api/autonomous/runs` | Unified autonomous run feed (`plan_execute` + `atlas_plan`) with status/progress summary |
| `GET /api/atlas/status` | Current ATLAS session: lesson, exercise, curriculum, chat history |
| `POST /api/atlas/lesson` | Start a lesson (`{topic, difficulty, module, lesson, llm}`) |
| `POST /api/atlas/submit` | Submit code (`{code}`) → graded result + adaptive feedback payload |
| `POST /api/atlas/onboard` | Save learner onboarding profile (`approval_mode` supported for preview-first) |
| `POST /api/atlas/next` | Advance to next lesson |
| `POST /api/atlas/back` | Return to previous lesson with resume packet |
| `GET /api/atlas/flashcards` | Generate + save lesson flashcards for recall |
| `POST /api/atlas/regenerate` | Generate a new exercise variant for the current lesson |
| `POST /api/atlas/learner/reset` | Reset learner model (`approval_mode` supported for preview-first) |
| `POST /api/atlas/reset` | Reset ATLAS session (`approval_mode` supported for preview-first) |
| `POST /api/atlas/chat` | Chat with ATLAS tutor (`{message, model?, mode, strict_guard, regenerate_on_guard, page_context}`) |
| `GET /api/models` | All available models: active adapter, model, Ollama status, installed models |
| `GET/POST /api/notes` | Note CRUD |
| `GET/POST /api/buildlog` | Build log entries |
| `GET/POST /api/logsale` | Sales log entries |
| `GET /api/modules` | Scans real agents directory |
| `POST /api/terminal/exec` | HTTP terminal fallback: run an allowed command, returns stdout/stderr/exit_code |
| `WS /ws/terminal` | WebSocket terminal with streaming stdout/stderr |

---

## 8 — Project status (as of August 2026)

### Done and working ✅
- Full ATLAS lesson → submit → pass/fail loop wired to Supabase
- adaptive_metrics and atlas_progress written on each submission
- mammoth.ai_sessions logged on every atlas code generate call
- CurriculumAgent reads real DB lessons with template fallback
- CLI auto-resolves UUID from public.profiles
- `.env` auto-loaded on every CLI run
- All 11 local Ollama models wired (hermes3, deepseek-coder, codellama, llama3.1, mistral, qwen2.5, qwen2.5-coder, phi3, nous-hermes)
- OpenAI adapter updated to v2 SDK (gpt-4o-mini default)
- LLM auto-detection: Ollama running → use it; OPENAI_API_KEY set → use that
- Mad Architecht Command Center: 11-page React UI fully wired to FastAPI backend
- Floating ATLAS FAB chat widget on all pages
- Dedicated ATLAS Tutor page (3-column: curriculum | editor | chat)
- Working theme toggle (Darker/Dark/Midnight) with CSS variable mutation + localStorage
- Terminal WebSocket + HTTP fallback
- All data files auto-initialized in `.mammoth/`
- Branch pushed to origin: `ui/compliance-legal-shell`
- Agent Console run history (browser-local, replay/clear, up to 20 entries)
- Plan + Execute multi-agent orchestration mode in Agent Console
- ATLAS-First plan profile (seed/strategy framing before code)
- Agent smoke test workflow with baseline health validation
- **Phase 1 complete:** learner onboarding profile, memory graph, `POST /api/atlas/onboard`,  
  `POST /api/atlas/back` (resume packet), `GET /api/atlas/flashcards` (recall),  
  welcome-back lesson summary in ATLAS Tutor UI

### Next up (priority order)
1. **Phase 2** — Adaptive lesson delivery (see roadmap below)
2. `atlas progress` CLI command — show XP, lessons completed, streak from Supabase
3. Write `atlas.sessions` rows on lesson start (track topic history in DB)
4. ReasoningAgent hints on submission fail (chain-of-thought explanation)
5. Ascension Metrics page — real learning stats pulled from Supabase `atlas_ascension` table
6. Completion Graph — visual skill tree of completed vs pending lessons

### Parked
- Docker sandbox seccomp tuning (needs CI artifacts)
- Full LLM lesson generation at scale (`ATLAS_EXERCISE_GEN_MODE=llm`)
- Wednesday gothic neon theme variant

---

## 9 — ATLAS Upgrade Roadmap

> **ATLAS is the top-level system.** The CodingAgent is ATLAS's teaching assistant —  
> it generates, explains, and refactors code *in service of ATLAS's adaptive learning goals.*  
> The original idea: a recursive, self-improving, individualized cognitive tutor OS.  
> This roadmap is the execution plan for that vision.

---

### Phase 1 — Onboarding + Learner Memory Foundation ✅ COMPLETE

**Goal:** Know the student before the first lesson starts.

| Feature | Status |
|---|---|
| Learner model file (`learner_model.py`) | ✅ Done |
| Onboarding profile (experience, pacing, style, goals, focus areas) | ✅ Done |
| Memory graph (concept nodes + lesson edges) | ✅ Done |
| `POST /api/atlas/onboard` endpoint | ✅ Done |
| Onboarding UI in ATLAS Tutor sidebar | ✅ Done |
| Learner memory map display in UI | ✅ Done |
| Welcome-back lesson summary on return | ✅ Done |
| Flashcard recall (`GET /api/atlas/flashcards`) | ✅ Done |
| `POST /api/atlas/back` resume packet | ✅ Done |

---

### Phase 2 — Adaptive Lesson Delivery 🚧 IN PROGRESS

**Goal:** ATLAS selects the *right lesson* at the *right difficulty* based on the learner model.

| Feature | Plan |
|---|---|
| Learner-model-informed lesson selection | Pull weakest concepts from mastery map and weight curriculum accordingly |
| Dynamic difficulty scaling | Adjust difficulty based on streak + recent outcome history from learner model |
| Hint depth calibration | Measure confidence score → calibrate hint verbosity (less hand-holding for high confidence). **Baseline shipped** via `adaptive_coaching.hint_depth` |
| Pacing adapter | Honor onboarding `preferred_pacing` field to space exercises / explanations |
| Post-lesson mastery update | Write concept mastery scores back to learner model after every submission. **Shipped** with mastery/confidence deltas in `recent_outcomes` |
| Remediation branching | Trigger support mode for repeated failures, with optional automatic exercise regeneration |
| Anti-cheat continuity | If direct-answer request is detected on active exercises, ATLAS refuses and can auto-generate a parallel variant |
| Supabase session rows on lesson start | Write `atlas.sessions` entries for full lesson-history tracking |
| `atlas progress` CLI command | Display XP, lessons completed, streak, weakest concepts from DB + learner model |

---

### Phase 3 — ReasoningAgent Chain-of-Thought Hints

**Goal:** When a student fails, ATLAS explains *why* step-by-step, not just "wrong."

| Feature | Plan |
|---|---|
| ReasoningAgent integration on fail | CodingAgent fails → ReasoningAgent generates chain-of-thought walkthrough |
| Socratic probe mode | ATLAS asks follow-up questions instead of immediately revealing the fix |
| Error pattern tracking | Repeated errors update `error_patterns` in learner model → ATLAS flags known sticking points. **Foundation shipped** in learner model + adaptive coaching |
| Contextual micro-lessons | When a concept is repeatedly failed, inject a targeted micro-lesson before the next attempt |
| Return continuity hardening | **Shipped** — deterministic resume packets on status reads/transitions, historical submission recovery, legacy study-aid normalization, note/flashcard pull-up fallback |

---

### Phase 4 — Ascension Metrics + Skill Tree

**Goal:** Make the student's growth visible and motivating.

| Feature | Plan |
|---|---|
| Ascension Metrics page | Real learning stats from Supabase `atlas_ascension` table |
| Completion Graph | Visual skill tree: completed vs pending lessons, mastery color-coded |
| Streak + XP leaderboard (personal) | Self-comparison over time, not competitive |
| Weekly focus report | ATLAS generates a "here's what you learned this week" summary |
| Concept dependency graph | Show which concepts unlock which advanced topics |

---

### Phase 5 — Multi-Agent Cognitive Loop (Recursive Self-Improvement)

**Goal:** ATLAS + CodingAgent teach each other. The system improves its own curriculum.

| Feature | Plan |
|---|---|
| ATLAS evaluates CodingAgent output | ATLAS scores code quality against learner goals, not just correctness |
| CodingAgent proposes curriculum additions | When generating code solutions, agent flags concepts student hasn't seen yet |
| Curriculum self-amendment | OrchestratorAgent can add new lessons to the curriculum based on learner model gaps |
| Agent role hierarchy enforced in UI | Plan Profile = ATLAS-First locks ATLAS as strategy layer; CodingAgent always subordinate |
| Recursive improvement loop | Each lesson cycle produces learner model updates → curriculum updates → better next lesson |

---

### CodingAgent Upgrade Plan (parallel track, subordinate to ATLAS)

The CodingAgent is ATLAS's teaching assistant. These upgrades make it a better one:

| Upgrade | Purpose |
|---|---|
| Per-run model selection in Agent Console | Let ATLAS choose the best model for each coding task |
| Reasoning trace display | Show CodingAgent's thought steps live in the UI |
| Context-aware code generation | CodingAgent reads learner model before generating — calibrates complexity to student level |
| File approval + rollback | Already wired; ensure rollback snapshots preserve ATLAS lesson state too |
| Smoke test on every code write | Run sandbox tests automatically after every CodingAgent file write |

---

## 10 — Quick troubleshooting

| Symptom | Fix |
|---|---|
| SKIP: SUPABASE_URL not set | Check .env file exists at repo root with correct keys |
| Invalid API key (Supabase) | Wrap JWT in double-quotes in .env |
| permission denied for table | Run GRANT SELECT ON table TO service_role; in Supabase SQL Editor |
| ai_sessions write failed 404 | Run .mammoth/supabase_schema.sql in Supabase SQL Editor |
| [LOCAL_ADAPTER] in output | Ollama not running (ollama serve) and no OPENAI_API_KEY set |
| Ollama not reachable | Start Ollama: ollama serve |
| [CodingAgent:WARN] no sub-engines | Informational only — safe to ignore |
| check constraint adaptive_metrics | Already fixed — difficulty maps to easy/medium/hard |
| UI shows blank / no data | Start the FastAPI backend first: `uvicorn api_server:app --reload` on port 8000 |
| Terminal says DISCONNECTED | Backend not running. UI auto-switches to HTTP fallback mode — commands still work via POST /api/terminal/exec |
| `atlas code` feels unsupported in the UI terminal | Use the full CLI form like `python -m cli.main atlas code generate "..."`. The terminal now supports safe ATLAS CLI command trees and gives code/UI flows longer timeouts |

---

## 11 — Run the full test suite

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Tests that hit Supabase or OpenAI are skipped when credentials not set — safe offline.


---

## 9 — Compliance, Legal & Monetization

### 9a. Product pages (in-app)

Three public-facing product pages are now wired into the MammothOS sidebar under the **Product** section:

| Page | Route key | Description |
|---|---|---|
| Landing Page | `landing` | Hero, feature grid, free/pro tiers, legal footer |
| Pricing | `pricing` | 3-tier grid (Explorer / Pro / Enterprise) + FAQ |
| Legal & Compliance | `compliance` | 4-tab legal: Terms, Privacy, Acceptable Use, Disclaimer |

All pages use `setPage` prop for navigation — no separate router needed. A compliance footer strip (Terms · Privacy · About) also appears at the bottom of the sidebar.

---

### 9b. Terms of Use (summary)

- MammothOS is an AI-assisted educational platform for personal and educational use.
- ATLAS is a learning aid — not professional instruction, therapy, or certified education.
- Do not use MammothOS to cheat on exams or circumvent academic integrity policies.
- Users retain ownership of their submitted code and notes. MammothOS makes no claim.
- By using the platform you agree to these terms. Full text available in-app under **Legal & Compliance**.

---

### 9c. Privacy Policy (summary)

- Data collected: lesson history, onboarding profile, learner model state, submitted code.
- Storage: local browser session + your local Supabase instance. No third-party analytics.
- AI providers (OpenAI, Ollama) process prompts per their own terms.
- We do not sell, rent, or share personal data.
- Delete your data anytime: Settings → Reset Session.

---

### 9d. Acceptable Use Policy

- ATLAS is a coach, not a solution generator. Do not use it to produce work you submit as your own.
- Do not attempt to bypass the no-cheat guard via prompt engineering.
- Do not use MammothOS for harmful, abusive, or illegal content generation.
- Violations may restrict access to advanced features.

---

### 9e. Monetization tiers

| Tier | Price | Status |
|---|---|---|
| **Explorer** | Free, forever | ✅ Active |
| **Pro** | ~$12/mo (est.) | 🔜 Coming soon |
| **Enterprise / Team** | Contact us | 📅 Future |

**Explorer** includes: ATLAS tutor chat, adaptive pacing, lesson resume, flashcards/quiz, basic evals, local storage.

**Pro** adds: multi-agent plan orchestration, all plan profiles, Supabase sync, eval history dashboard, audit export, coding agent with approval workflow, priority model routing.

**Enterprise** adds: team dashboards, cohort analytics, custom curriculum authoring, LMS integration, white-label ATLAS, fine-tuned models, SLA.

> **Monetization note:** No formal patents have been filed. "Patents pending on adaptive tutor and memory graph methodologies" is forward-looking product positioning language. All monetization scaffolding is designed to be wired to Stripe + Supabase entitlement sync when billing is ready.

---

### 9f. Entitlement API

Two routes control feature gating:

**`GET /api/entitlements`** — returns current tier and feature flags:
```json
{
  "status": "ok",
  "tier": "explorer",
  "features": {
    "atlas_tutor": true,
    "adaptive_pacing": true,
    "multi_agent_orchestration": false,
    "supabase_sync": false,
    ...
  },
  "upgrade_cta": "pricing"
}
```

**`POST /api/entitlements/tier`** — set tier (admin/testing):
```bash
curl -X POST http://localhost:8000/api/entitlements/tier \
  -H "Content-Type: application/json" \
  -d '{"tier": "pro"}'
```

Valid tiers: `explorer`, `pro`, `enterprise`. Tier is persisted to `.mammoth/atlas_state.json`.

---

### 9g. Compliance and monetization scaling plan

| Phase | Feature | Status |
|---|---|---|
| ✅ Phase 6a | Product pages (Landing, Pricing, Compliance) | Done |
| ✅ Phase 6b | Entitlement API with tier persistence | Done |
| 🔜 Phase 7 | Stripe integration for Pro subscriptions | Planned |
| 🔜 Phase 8 | Supabase user accounts + tier sync | Planned |
| 🔜 Phase 9 | Team dashboards and cohort reporting | Planned |
| 🔜 Phase 10 | White-label ATLAS for schools/bootcamps | Future |

---

### 9h. Legal positioning

MammothOS is positioned as an **educational AI assistant**:
- Not a covered educational institution (not FERPA-regulated as a software vendor)
- Not intended for users under 13 (COPPA safe harbor requires collecting no data from minors)
- Not providing certified instruction or professional advice
- All AI outputs carry an implicit "verify before use" disclaimer surfaced in the Disclaimer tab

When seeking investment, partnerships, or enterprise contracts: lead with the adaptive tutor story, the memory graph, and the no-cheat guard — these are your key differentiators.
