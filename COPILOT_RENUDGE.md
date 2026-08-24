# MammothOS Project Briefing — for Copilot Chat

> **READ THIS FIRST before suggesting anything.**
> This is a briefing document to keep Copilot aligned with the real project.
> Do NOT invent modules, components, or files. Everything below is the authoritative source of truth.

---

## WHO IS THIS PROJECT FOR

**Vernon** — a solo developer building MammothOS: an AI-powered learning OS and personal command center.
His username is `xxii-architect`. Repo: `https://github.com/xxii-architect/mammoth_intro_ai`

---

## WHAT THE PROJECT IS

**MammothOS** is a Python-backed AI system with a React UI called **Mad Architecht Command Center**.

It has two main layers:
1. **Python backend** — CLI tools, AI agents, ATLAS learning system, Supabase integration
2. **React frontend** — 11-page SPA (Vite + React) wired to a FastAPI bridge server

The project is NOT a template, NOT a scaffold demo, NOT a concept — it is **a working, running system**.

---

## WHAT IS BUILT AND WORKING RIGHT NOW

### Python Backend (`src/mammoth_os/`)
- `llm_client.py` — auto-selects adapter: OpenAI → Ollama → local echo fallback
- `openai_adapter.py` — OpenAI v2 SDK, gpt-4o-mini default
- `ollama_adapter.py` — 11 local models wired (hermes3, deepseek-coder, codellama, llama3.1, mistral, qwen2.5, qwen2.5-coder, phi3, nous-hermes, etc.)
- `atlas_session.py` — ATLASSession: `start_lesson()`, `submit()`, `_generate_hint()`
- `agents/tutor_agent.py` — TutorAgent: grades submissions, writes hints, logs to Supabase
- `agents/curriculum_agent.py` — CurriculumAgent: reads lessons from Supabase DB, template fallback
- `agents/coding_agent.py` — CodingAgent: generates/refactors/explains code, runs in sandbox, logs to Supabase
- `agents/cortex_router.py` — CortexRouter: routes intents (plant_seed, field_ops, market_intel, research_*, brand_voice, etc.)
- `sandbox_runner.py` — Runs generated code safely
- `.env` auto-loaded on every CLI run (no manual env var export needed)

### CLI (`cli/`)
- `cli/main.py` — entry point, loads `.env`
- `cli/atlas.py` — all `python -m cli.main atlas *` commands
- Working commands: `atlas lesson`, `atlas submit`, `atlas next`, `atlas reset`, `atlas status`, `atlas status --db`, `atlas code generate/refactor/explain`, `atlas ui scaffold`

### FastAPI Bridge (`api_server.py` — repo root)
All 17+ endpoints bridging the React UI to the Python agents:
- `/api/status`, `/api/health`, `/api/agents`, `/api/run`
- `/api/atlas/status|lesson|submit|next|reset|chat`
- `/api/notes` (CRUD), `/api/buildlog`, `/api/logsale`, `/api/modules`, `/api/models`
- `/api/terminal/exec` (HTTP fallback)
- `WS /ws/terminal` (WebSocket streaming terminal)

### React UI (`ui/mad-architecht-command-center/src/`)
**11 Pages — all fully wired to real API:**
1. **Home** — live status dots, agent count, build log feed, sales total, quick-copy commands
2. **Agent** — run CortexRouter intents with live thought stream
3. **Terminal** — WebSocket terminal + HTTP fallback mode when offline
4. **Notes** — full CRUD, auto-saved
5. **Modules** — live scan of agents directory
6. **Health** — real service checks (Ollama, Supabase, OpenAI)
7. **Log Sale** — sales tracker with running total
8. **Lessons** — quick ATLAS lesson start + embedded chat
9. **ATLAS Tutor** — full 3-column: curriculum tree | exercise + code editor | tutor chat + model picker
10. **Build Log** — tagged build entry log
11. **Settings** — system info, env keys, ATLAS reset, theme toggle, AI runtime status

**Global features:**
- Floating ATLAS FAB chat widget (🧠 violet button, fixed bottom-right, ALL pages)
- Theme toggle: Dark / Aurora — writes CSS custom properties live, persists to localStorage, and normalizes legacy darker/midnight values to Dark
- Design system: `--shell #050608`, `--photon #4da6ff`, `--cyan #00f5d4`, `--violet #b47cff`, glass cards, CRT scanlines, JetBrains Mono

### Supabase
- Schema: `mammoth.*` and `atlas.*` tables
- Writes: `atlas.atlas_progress`, `atlas.adaptive_metrics`, `mammoth.ai_sessions` on submissions/code gen
- Reads: `mammoth.users`, `mammoth.progress`, `atlas.sessions`, `atlas.community_stats`

---

## WHERE THE CODE LIVES

```
repo root
├── api_server.py              ← FastAPI server (bridge)
├── cli/
│   ├── main.py                ← CLI entry point
│   └── atlas.py               ← All atlas subcommands
├── src/mammoth_os/
│   ├── llm_client.py
│   ├── openai_adapter.py
│   ├── ollama_adapter.py
│   ├── atlas_session.py
│   ├── sandbox_runner.py
│   └── agents/
│       ├── tutor_agent.py
│       ├── curriculum_agent.py
│       ├── coding_agent.py
│       └── cortex_router.py
├── ui/mad-architecht-command-center/
│   ├── src/
│   │   ├── App.jsx            ← Shell, routing, FAB, theme
│   │   ├── index.css          ← Full design system
│   │   ├── api/client.js      ← Fetch wrapper + WS helper
│   │   ├── hooks/useApi.js    ← useApi(), useInterval()
│   │   └── pages/
│   │       ├── HomePage.jsx
│   │       ├── AgentPage.jsx
│   │       ├── TerminalPage.jsx
│   │       ├── NotesPage.jsx
│   │       ├── ModulesPage.jsx
│   │       ├── HealthPage.jsx
│   │       ├── LogSalePage.jsx
│   │       ├── LessonsPage.jsx
│   │       ├── AtlasTutorPage.jsx
│   │       ├── BuildLogPage.jsx
│   │       └── SettingsPage.jsx
└── .mammoth/
    ├── atlas_cli_session.json  ← Live ATLAS session state
    ├── notes.json
    ├── buildlog.json
    └── sales_log.json
```

---

## HOW TO START THE SYSTEM

**Terminal 1 (Backend):**
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```powershell
cd ui/mad-architecht-command-center
npm run dev
```

Open **http://localhost:5173**

---

## WHAT IS PLANNED NEXT (DO build these)

In priority order:
1. `atlas progress` CLI command — XP, lessons completed, streak from Supabase
2. Write `atlas.sessions` rows on lesson start (track topic history in DB)
3. ReasoningAgent hints on submit fail (chain-of-thought explanation)
4. Agent page per-run model/adapter selector (dropdown from `/api/models`)
5. **Ascension Metrics page** — learning stats graph from Supabase `atlas_ascension` table
6. **Completion Graph** — visual skill tree of completed vs pending lessons
7. **Wednesday gothic theme variant** — optional dark gothic neon styling (Vernon loves this idea, planned for future)
8. OrchestratorAgent CLI — multi-agent pipeline from one command

---

## WHAT DOES NOT EXIST — DO NOT INVENT THESE

These files/modules were **hallucinated by another Copilot session** and do NOT exist in the repo:

❌ `ui/ascension/AscensionEnginePanel.jsx`
❌ `ui/ascension/CompletionSealCard.jsx`
❌ `ui/ascension/UnifiedConsciousnessGraph.jsx`
❌ `ui/ascension/FinalIntegrationPanel.jsx`
❌ `ui/ascension/StabilizationFabricPanel.jsx`
❌ `ui/ascension/CompletionGraph.jsx`
❌ `ui/ascension/WednesdayAscensionPanel.jsx`
❌ `ui/ascension/WednesdayAscensionVerdict.jsx`
❌ `hooks/useAscensionEngine.js`
❌ `hooks/useCompletionSeal.js`
❌ `hooks/useUnifiedConsciousness.js`
❌ `hooks/useFinalIntegration.js`
❌ `hooks/useStabilizationFabric.js`
❌ `hooks/useCompletionGraph.js`

If you see yourself about to reference these, stop and re-read this document.

---

## DESIGN RULES

- **Dark neon cosmic theme.** Charcoal/near-black shell, cyan/violet/photon-blue neons, glass cards, CRT scanlines.
- **No Tailwind.** The project uses plain CSS custom properties and inline styles in JSX. Do NOT suggest converting to Tailwind.
- **Functional first.** Every component must wire to a real API endpoint. No mock data except loading states.
- **React (Vite), not Next.js.** Do not suggest migrating to Next.js.
- **Python 3.11+ on Windows.** Use PowerShell syntax for all shell commands.
- **`.venv` virtualenv** at repo root. Activate with `.\.venv\Scripts\Activate.ps1`

---

## BRANCH INFO

- Active branch: `ui/compliance-legal-shell`
- Pushed to: `origin/ui/compliance-legal-shell`
- Full git history preserved at: `https://github.com/xxii-architect/mammoth_intro_ai`

---

*This briefing was generated by the Copilot CLI agent after completing the full MammothOS UI wiring pass — August 2026.*
