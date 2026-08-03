# 🐘 ATLAS Manual — MammothOS CLI Reference

> **Quick rule:** every command starts with `python -m cli.main atlas …`
> Run this from the repo root. **Your `.env` file is now loaded automatically** —
> no more setting env vars by hand in every terminal.

---

## 1 — One-time setup

### 1a. Set PYTHONPATH (required every new terminal)
```powershell
$env:PYTHONPATH = "src"
```

### 1b. `.env` file (set once, loads automatically)
The CLI reads `.env` from the repo root on every run. You do not need to
`$env:...` anything manually anymore — just keep the file up to date.

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

## 5 — Where things live

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
| Unit tests | `src/mammoth_os/test_*.py` |

---

## 6 — Project status (as of August 2026)

### Done and working
- Full ATLAS lesson → submit → pass/fail loop wired to Supabase
- adaptive_metrics and atlas_progress written on each submission
- mammoth.ai_sessions logged on every atlas code generate call
- CurriculumAgent reads real DB lessons with template fallback
- CLI auto-resolves UUID from public.profiles
- atlas status --db shows latest DB row
- .env auto-loaded on every CLI run
- All 11 local Ollama models wired (hermes3, deepseek-coder, codellama, llama3.1, mistral, qwen2.5, qwen2.5-coder, phi3, nous-hermes)
- OpenAI adapter updated to v2 SDK (gpt-4o-mini default)
- LLM auto-detection: Ollama running = use it; OPENAI_API_KEY set = use that
- Code gen always names function solution() so sandbox tests can import it
- UI scaffolding flow now works: `atlas ui scaffold` generates a Vite + React app and the generated app builds successfully

### Next up (priority order)
1. Write atlas.sessions rows on lesson start (track topic history)
2. atlas progress command — show XP, lessons, streak from Supabase
3. ReasoningAgent hints on submission fail (chain-of-thought)
4. Connect generated UI to real Supabase progress data (XP, lessons, streak)
5. UIBuilderAgent — scaffold richer React/Next.js components via LLM
6. OrchestratorAgent CLI — multi-agent pipeline from one command

### Parked
- Docker sandbox seccomp tuning (needs CI artifacts)
- Full LLM lesson generation at scale (ATLAS_EXERCISE_GEN_MODE=llm)

---

## 7 — Quick troubleshooting

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
| No active exercise | Run atlas lesson topic first |

---

## 8 — Run the full test suite

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Tests that hit Supabase or OpenAI are skipped when credentials not set — safe offline.
