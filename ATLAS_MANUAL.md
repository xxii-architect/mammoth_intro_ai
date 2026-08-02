# 🐘 ATLAS Manual — MammothOS CLI Reference

> **Quick rule:** every command starts with `python -m cli.main atlas …`
> Run this from the repo root after setting the env vars below.

---

## 1 — One-time setup

### 1a. Set PYTHONPATH (required every new terminal)
```powershell
$env:PYTHONPATH = "src"
```

### 1b. Set Supabase credentials (required for DB commands)
```powershell
$env:SUPABASE_URL              = "https://mkstgbegjkonmwmjqkpz.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "<your service_role JWT from Supabase dashboard>"
```

> **Tip — never set the JWT without quotes in PowerShell.** The dots in the token confuse
> the parser. Always wrap in double-quotes:
> ```powershell
> $env:SUPABASE_SERVICE_ROLE_KEY = "eyJhbG..."
> ```

### 1c. (Optional) Pre-set your Supabase user UUID so ATLAS tracks you
```powershell
$env:ATLAS_USER_ID = "<your UUID from auth.users>"
```
If you skip this, ATLAS will auto-resolve it from `public.profiles` using
`SUPABASE_ANON_KEY` (if set), or fall back to `cli_user`.

---

## 2 — All wired CLI commands

### Start a lesson
```powershell
python -m cli.main atlas lesson "Python for loops"
python -m cli.main atlas lesson "Python lists" --difficulty intermediate
python -m cli.main atlas lesson "Recursion" --module 2 --lesson 1
python -m cli.main atlas lesson "Functions" --llm          # uses LLM if OPENAI_API_KEY set
```

### Check your current session
```powershell
python -m cli.main atlas status           # shows active lesson + exercise prompt
python -m cli.main atlas status --db      # also fetches the latest mammoth.ai_sessions row from Supabase
```

### Submit a solution
```powershell
# Submit a file
python -m cli.main atlas submit solution.py

# Submit inline code (great for quick tests)
python -m cli.main atlas submit --inline "def solution(*args, **kwargs): return 42"
```
On pass you get ✅ PASSED; on fail you see the error and a hint from TutorAgent.

### Advance to the next lesson
```powershell
python -m cli.main atlas next
```

### Reset your session (wipe local state)
```powershell
python -m cli.main atlas reset
```

### CodingAgent — generate code
```powershell
python -m cli.main atlas code generate "a function that sums a list"
python -m cli.main atlas code generate "binary search implementation"
```
Generates code, runs tests in the sandbox, and logs the session to
`mammoth.ai_sessions` in Supabase.

### CodingAgent — refactor a file
```powershell
python -m cli.main atlas code refactor my_script.py              # writes to my_script.refactored.py
python -m cli.main atlas code refactor my_script.py --inplace    # overwrites original
python -m cli.main atlas code refactor my_script.py --output out.py
```

### CodingAgent — explain a file
```powershell
python -m cli.main atlas code explain my_script.py
```

---

## 3 — Verify Supabase connectivity

### Check all tables are reachable
```powershell
python .mammoth\check_supabase.py
```
Expected output when everything is working:
```
OK  mammoth.users accessible
OK  mammoth.progress accessible
OK  mammoth.activity_log accessible
OK  atlas.atlas_progress accessible
OK  atlas.adaptive_metrics accessible
OK  atlas.community_stats accessible
OK  atlas.sessions accessible
```

### Show the latest AI session row logged to Supabase
```powershell
python -m cli.main atlas status --db
```
Expected output (after running `atlas code generate` at least once):
```
🗄️  Latest mammoth.ai_sessions row
────────────────────────────────────────────────────────────
  id          : <uuid>
  created_at  : 2026-08-02T19:06:21+00:00
  tokens_used : 312
  prompt      : a function that sums a list
  metadata    : {"source": "atlas.code.generate", "ok": true}
```

---

## 4 — Where things live

| What | Path |
|---|---|
| CLI commands | `cli/atlas.py` |
| CLI entry point | `cli/main.py` |
| Session state (local JSON) | `.mammoth/atlas_cli_session.json` |
| Supabase schema | `.mammoth/supabase_schema.sql` |
| Supabase connectivity check | `.mammoth/check_supabase.py` |
| TutorAgent | `src/mammoth_os/agents/tutor_agent.py` |
| CurriculumAgent | `src/mammoth_os/agents/curriculum_agent.py` |
| CodingAgent | `src/mammoth_os/agents/coding_agent.py` |
| Sandbox runner | `src/mammoth_os/sandbox_runner.py` |
| Unit tests | `src/mammoth_os/test_*.py` |

---

## 5 — Project status (as of August 2026)

### ✅ Done and working
- Full ATLAS lesson → submit → pass/fail loop wired to Supabase
- `adaptive_metrics` and `atlas_progress` rows written on each submission
- `mammoth.ai_sessions` rows logged on every `atlas code generate` call
- CurriculumAgent reads real lessons from `mammoth.modules` / `mammoth.lessons`
  before falling back to built-in templates
- CLI auto-resolves your UUID from `public.profiles` (no manual `ATLAS_USER_ID` needed)
- `atlas status --db` shows latest DB row for quick verification

### 🔜 Next up (Priority order)
1. **Wire `atlas.sessions` rows** — write one row per CLI lesson session so you can
   track start/end time per topic (file: `cli/atlas.py` → `cmd_atlas_lesson`)
2. **Add `atlas progress` command** — show XP, lessons_completed, and streak from
   `atlas.community_stats`
3. **Adaptive hints from ReasoningAgent** — when a submission fails, TutorAgent
   calls ReasoningAgent to generate a chain-of-thought hint
4. **Dashboard / analytics** — aggregate `atlas.adaptive_metrics` into a weekly report

### 🧊 Parked (waiting on credentials/infrastructure)
- Docker sandbox seccomp tuning (CI artifacts needed)
- Full LLM-powered lesson generation at scale (needs OpenAI credits or local model)

---

## 6 — Quick troubleshooting

| Symptom | Fix |
|---|---|
| `SKIP: SUPABASE_URL not set` | Set both `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` env vars |
| `Invalid API key` | Wrap the JWT in double-quotes when setting env var |
| `permission denied for table sessions` | Run the `GRANT SELECT ON atlas.sessions TO service_role;` line in Supabase SQL Editor |
| `check constraint adaptive_metrics_difficulty_level_check` | Already fixed — difficulty now maps to `easy`/`medium`/`hard` |
| `[CodingAgent:WARN] initialized without sub-engines` | Informational only — means OpenAI key not set, using local fallback. Safe to ignore. |
| `No active exercise` | Run `atlas lesson <topic>` first |

---

## 7 — Run the full test suite

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

> Tests that hit Supabase are skipped when credentials are not set — safe to run offline.
