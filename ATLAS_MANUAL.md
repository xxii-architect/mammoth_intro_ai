# 🐘 ATLAS Manual — MammothOS CLI Reference

> **Quick rule:** every command starts with `python -m cli.main atlas …`
> Run this from the repo root. **Your `.env` file is now loaded automatically** —
> no more setting env vars by hand in every terminal.

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

## 2 — LLM model selection

MammothOS auto-selects the best available model. Priority order:

| Priority | Condition | Result |
|---|---|---|
| 1 | `MAMMOTH_LLM_ADAPTER=local` in `.env` | Deterministic echo (CI only) |
| 2 | `MAMMOTH_LLM_ADAPTER=hermes` (or deepseek, codellama...) | That Ollama model |
| 3 | `MAMMOTH_LLM_ADAPTER=openai` | OpenAI |
| 4 | `OPENAI_API_KEY` is set | OpenAI (gpt-4o-mini default) |
| 5 | Ollama is running on localhost:11434 | Ollama auto-detected |
| 6 | Nothing available | Local echo fallback |

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
MAMMOTH_LLM_ADAPTER=deepseek    # DeepSeek Coder for code tasks
MAMMOTH_LLM_ADAPTER=hermes      # Hermes3 for ATLAS (recommended default)
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
python -m cli.main atlas code generate "a React component that shows XP"
```
Generates solution() + tests + docs, runs tests in sandbox, logs to Supabase.
Works with both OpenAI and all Ollama models.

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

## 4 — Verify Supabase connectivity

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

## 5 — Where things live (source map)

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
| Runtime data files | `.mammoth/` (notes, buildlog, sales_log, atlas session) |

---

## 6 — Mad Architecht Command Center (Main UI)

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
| **Agent** | Run any CortexRouter intent (plant_seed, field_ops, research_*, etc.) with live thought stream, approval queue, snapshot rollback, and coding shortcuts |
| **Terminal** | WebSocket terminal wired to the backend. HTTP fallback mode when WS is offline. Quick-action buttons for common commands |
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

### ATLAS learning memory
The ATLAS Tutor sidebar now shows:
- current lesson resume state
- saved lesson history
- total lesson count in the loaded curriculum
- latest submission outcome and coaching hint

### Floating ATLAS Chat (FAB)
A violet 🧠 button is fixed to the bottom-right corner on **every page**.  
Click it → glass chat panel slides up → chat directly with ATLAS tutor without leaving your current screen.  
Wired to `POST /api/atlas/chat` with full chat history.

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
| `GET /api/atlas/status` | Current ATLAS session: lesson, exercise, curriculum, chat history |
| `POST /api/atlas/lesson` | Start a lesson (`{topic, difficulty, module, lesson, llm}`) |
| `POST /api/atlas/submit` | Submit code (`{code}`) → graded result |
| `POST /api/atlas/next` | Advance to next lesson |
| `POST /api/atlas/reset` | Reset ATLAS session |
| `POST /api/atlas/chat` | Chat with ATLAS tutor (`{message, model?}`) |
| `GET /api/models` | All available models: active adapter, model, Ollama status, installed models |
| `GET/POST /api/notes` | Note CRUD |
| `GET/POST /api/buildlog` | Build log entries |
| `GET/POST /api/logsale` | Sales log entries |
| `GET /api/modules` | Scans real agents directory |
| `POST /api/terminal/exec` | HTTP terminal fallback: run an allowed command, returns stdout/stderr/exit_code |
| `WS /ws/terminal` | WebSocket terminal with streaming stdout/stderr |

---

## 7 — Project status (as of August 2026)

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

### Next up (priority order)
1. `atlas progress` CLI command — show XP, lessons completed, streak from Supabase
2. Write `atlas.sessions` rows on lesson start (track topic history in DB)
3. ReasoningAgent hints on submission fail (chain-of-thought explanation)
4. Agent page: per-run adapter/model selection dropdown
5. Ascension Metrics page — real learning stats pulled from Supabase `atlas_ascension` table
6. Completion Graph — visual skill tree of completed vs pending lessons
7. Wednesday theme variant — gothic neon styling toggle (planned for future)
8. OrchestratorAgent CLI — multi-agent pipeline from one command

### Parked
- Docker sandbox seccomp tuning (needs CI artifacts)
- Full LLM lesson generation at scale (`ATLAS_EXERCISE_GEN_MODE=llm`)

---

## 8 — Quick troubleshooting

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

---

## 9 — Run the full test suite

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Tests that hit Supabase or OpenAI are skipped when credentials not set — safe offline.
