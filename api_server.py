"""
MammothOS Command Center — FastAPI Server
Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── ensure src/ is on path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MammothOS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── startup time ─────────────────────────────────────────────────────────────
_START_TIME = time.time()

# ── .mammoth storage ─────────────────────────────────────────────────────────
MAMMOTH_DIR = ROOT / ".mammoth"
MAMMOTH_DIR.mkdir(exist_ok=True)

NOTES_FILE    = MAMMOTH_DIR / "notes.json"
BUILDLOG_FILE = MAMMOTH_DIR / "buildlog.json"
SALES_FILE    = MAMMOTH_DIR / "sales_log.json"
ATLAS_FILE    = MAMMOTH_DIR / "atlas_cli_session.json"
UI_DIR        = ROOT / "ui" / "mad-architecht-command-center"
VENV_PYTHON   = ROOT / ".venv" / "Scripts" / "python.exe"
VENV_UVICORN  = ROOT / ".venv" / "Scripts" / "uvicorn.exe"

for _f in [NOTES_FILE, BUILDLOG_FILE, SALES_FILE]:
    if not _f.exists():
        _f.write_text("[]")


def _read_json(path: Path, default=None):
    if default is None:
        default = []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _read_env_vars() -> Dict[str, str]:
    env_file = ROOT / ".env"
    env_vars: Dict[str, str] = {}
    if not env_file.exists():
        return env_vars
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        return {}
    return env_vars


def _ollama_running(base_url: str) -> bool:
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _ollama_installed_models(base_url: str) -> List[str]:
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=4) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = payload.get("models") or []
        names: List[str] = []
        for m in models:
            if isinstance(m, dict):
                names.append(str(m.get("name") or "").strip())
        return [m for m in names if m]
    except Exception:
        return []


def _models_snapshot() -> Dict[str, Any]:
    env = _read_env_vars()
    llm_adapter = (os.environ.get("MAMMOTH_LLM_ADAPTER") or env.get("MAMMOTH_LLM_ADAPTER") or "").strip().lower()
    openai_model = (os.environ.get("OPENAI_MODEL") or env.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
    ollama_model = (os.environ.get("OLLAMA_MODEL") or env.get("OLLAMA_MODEL") or "hermes3:8b").strip()
    ollama_base = (os.environ.get("OLLAMA_BASE_URL") or env.get("OLLAMA_BASE_URL") or "http://localhost:11434").strip()
    openai_key_present = bool((os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY") or "").strip())
    ollama_up = _ollama_running(ollama_base)
    installed_local = _ollama_installed_models(ollama_base) if ollama_up else []

    if llm_adapter:
        active_adapter = llm_adapter
    elif openai_key_present:
        active_adapter = "openai"
    elif ollama_up:
        active_adapter = "ollama"
    else:
        active_adapter = "local"

    if active_adapter == "openai":
        active_model = openai_model
    elif active_adapter == "ollama":
        active_model = ollama_model
    else:
        active_model = "local-adapter"

    configured_locals = [
        "hermes3:8b",
        "deepseek-coder:latest",
        "qwen2.5-coder:latest",
        "codellama:latest",
        "llama3.1:8b",
        "mistral:latest",
        "qwen2.5:latest",
        "phi3:latest",
        "nous-hermes:7b",
    ]
    local_model_items = []
    for m in configured_locals:
        local_model_items.append({
            "id": m,
            "provider": "ollama",
            "installed": m in installed_local,
        })

    cloud_model_items = [{
        "id": openai_model,
        "provider": "openai",
        "installed": openai_key_present,
    }]

    return {
        "active_adapter": active_adapter,
        "active_model": active_model,
        "ollama_base_url": ollama_base,
        "ollama_running": ollama_up,
        "openai_key_present": openai_key_present,
        "local_models_installed": installed_local,
        "models": local_model_items + cloud_model_items,
    }


# ── lazy registry imports ─────────────────────────────────────────────────────
try:
    from mammoth_os.engine_registry import EngineRegistry
    _engine_registry_ok = True
except Exception as _e:
    _engine_registry_ok = False
    _engine_registry_err = str(_e)

try:
    from mammoth_os.agent_registry import agent_registry
    _agent_registry_ok = True
except Exception as _e:
    _agent_registry_ok = False
    _agent_registry_err = str(_e)

# ─────────────────────────────────────────────────────────────────────────────
# /api/status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    uptime_s = int(time.time() - _START_TIME)
    h, rem = divmod(uptime_s, 3600)
    m, s   = divmod(rem, 60)
    uptime_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    engines = {}
    if _engine_registry_ok:
        try:
            engines = EngineRegistry.list_engines()
        except Exception:
            pass

    agents = []
    if _agent_registry_ok:
        try:
            agents = await agent_registry.list_agents()
        except Exception:
            pass

    buildlog = _read_json(BUILDLOG_FILE)

    models = _models_snapshot()

    return {
        "status": "ok",
        "python_version": sys.version,
        "uptime": uptime_str,
        "uptime_seconds": uptime_s,
        "engine_count": len(engines),
        "agent_count": len(agents),
        "cli_commands_run": len(buildlog),
        "active_models": max(1, len(models.get("local_models_installed", []))),
        "active_adapter": models.get("active_adapter"),
        "active_model": models.get("active_model"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# /api/agents
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/agents")
async def get_agents():
    if _agent_registry_ok:
        try:
            manifests = await agent_registry.list_agents()
            return [
                {
                    "id":           m.agent_id,
                    "name":         m.name,
                    "version":      m.version,
                    "status":       m.status.value if hasattr(m.status, "value") else str(m.status),
                    "capabilities": m.capabilities,
                    "level":        m.level,
                    "endpoint":     m.endpoint,
                }
                for m in manifests
            ]
        except Exception:
            pass

    # fallback — scan agents/ directory
    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    results = []
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            name = f.stem.replace("_", " ").title().replace(" ", "")
            results.append({
                "id":           f.stem,
                "name":         name,
                "version":      "v1.0.0",
                "status":       "IDLE",
                "capabilities": [],
                "level":        1,
                "endpoint":     f"http://localhost:8000/agents/{f.stem}",
            })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# /api/health
# ─────────────────────────────────────────────────────────────────────────────

def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


@app.get("/api/health")
async def get_health():
    env_file = ROOT / ".env"
    env_exists = env_file.exists()
    env_values = _read_env_vars()
    env_vars: Dict[str, bool] = {}
    openai_ok = False
    supabase_ok = False
    for k, v in env_values.items():
        env_vars[k] = bool(v)
    openai_ok = bool(env_values.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    supabase_ok = bool(env_values.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL"))
    models = _models_snapshot()

    # check git
    git_ok = (ROOT / ".git").exists()

    # check venv
    venv_ok = (ROOT / ".venv").exists()

    services = [
        {
            "label":  "Backend API",
            "detail": ":8000 FastAPI",
            "status": "green" if _port_open(8000) else "red",
            "up":     _port_open(8000),
        },
        {
            "label":  "React Dev Server (5173)",
            "detail": ":5173 Vite",
            "status": "green" if _port_open(5173) else "red",
            "up":     _port_open(5173),
        },
        {
            "label":  "React Dev Server (5174)",
            "detail": ":5174 Vite",
            "status": "green" if _port_open(5174) else "yellow",
            "up":     _port_open(5174),
        },
        {
            "label":  ".env Config",
            "detail": str(env_file),
            "status": "green" if env_exists else "red",
            "up":     env_exists,
        },
        {
            "label":  "Git Repository",
            "detail": str(ROOT),
            "status": "green" if git_ok else "red",
            "up":     git_ok,
        },
        {
            "label":  "Python venv",
            "detail": str(ROOT / ".venv"),
            "status": "green" if venv_ok else "yellow",
            "up":     venv_ok,
        },
        {
            "label":  "OpenAI Key",
            "detail": "OPENAI_API_KEY in .env",
            "status": "green" if openai_ok else "yellow",
            "up":     openai_ok,
        },
        {
            "label":  "Supabase URL",
            "detail": "SUPABASE_URL in .env",
            "status": "green" if supabase_ok else "yellow",
            "up":     supabase_ok,
        },
        {
            "label":  "Ollama Runtime",
            "detail": models.get("ollama_base_url", "http://localhost:11434"),
            "status": "green" if models.get("ollama_running") else "yellow",
            "up":     bool(models.get("ollama_running")),
        },
    ]

    return {
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "env_keys": list(env_vars.keys()),
    }


@app.get("/api/models")
async def get_models():
    return _models_snapshot()


# ─────────────────────────────────────────────────────────────────────────────
# /api/run
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/run")
async def run_agent(body: Dict[str, Any]):
    intent      = body.get("intent", "")
    payload     = body.get("payload", {})
    temperature = body.get("temperature", 0.7)

    try:
        from mammoth_os.cortex.router import CortexRouter
        router = CortexRouter()
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: router.route(intent, payload)
        )
        return {"status": "ok", "result": result, "intent": intent}
    except Exception as e:
        return {"status": "error", "error": str(e), "intent": intent}


# ─────────────────────────────────────────────────────────────────────────────
# /api/atlas/*
# ─────────────────────────────────────────────────────────────────────────────

def _load_atlas_state() -> Dict[str, Any]:
    if ATLAS_FILE.exists():
        try:
            return json.loads(ATLAS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "no_session", "user_id": "default_user"}


def _save_atlas_state(state: Dict[str, Any]):
    ATLAS_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


@app.get("/api/atlas/status")
async def atlas_status():
    return _load_atlas_state()


@app.post("/api/atlas/lesson")
async def atlas_lesson(body: Dict[str, Any]):
    topic = body.get("topic", "Python basics")
    try:
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession(user_id="default_user")
        exercise = await asyncio.get_event_loop().run_in_executor(
            None, lambda: session.start_lesson(topic)
        )
        state = _load_atlas_state()
        state.update({
            "status":           "active",
            "topic":            topic,
            "current_exercise": exercise,
            "curriculum":       session.curriculum,
            "current_lesson":   session.current_lesson,
            "curriculum_id":    session._curriculum_id,
            "lesson_id":        session._lesson_id,
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        })
        _save_atlas_state(state)
        return {"status": "ok", "exercise": exercise}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/atlas/submit")
async def atlas_submit(body: Dict[str, Any]):
    code = body.get("code", "")
    try:
        state = _load_atlas_state()
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession(user_id="default_user")
        session.curriculum       = state.get("curriculum")
        session.current_lesson   = state.get("current_lesson")
        session.current_exercise = state.get("current_exercise")
        session._curriculum_id   = state.get("curriculum_id")
        session._lesson_id       = state.get("lesson_id")

        files = {"solution.py": code}
        result = await session.submit(files)

        state["last_submission"] = result
        state["updated_at"]      = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/atlas/next")
async def atlas_next():
    state = _load_atlas_state()
    curriculum = state.get("curriculum", {})
    modules    = curriculum.get("modules", []) if curriculum else []

    lesson_id = state.get("lesson_id", "")
    # find next lesson index
    found = False
    for mod in modules:
        for i, lesson in enumerate(mod.get("lessons", [])):
            if lesson.get("lesson_id") == lesson_id:
                found = True
                next_i = i + 1
                if next_i < len(mod["lessons"]):
                    next_lesson = mod["lessons"][next_i]
                    state["current_lesson"] = next_lesson
                    state["lesson_id"]      = next_lesson["lesson_id"]
                    try:
                        from mammoth_os.exercise_generator import generate_exercises_for_lesson
                        generated = generate_exercises_for_lesson(next_lesson, count=1)
                        if generated:
                            state["current_exercise"] = generated[0]
                    except Exception:
                        # Keep session moving even if exercise generation fails.
                        pass
                    state["updated_at"]     = datetime.now(timezone.utc).isoformat()
                    _save_atlas_state(state)
                    return {"status": "ok", "lesson": mod["lessons"][next_i]}
                break
        if found:
            break

    return {"status": "ok", "message": "No more lessons in current module"}


@app.post("/api/atlas/reset")
async def atlas_reset():
    _save_atlas_state({"status": "reset", "user_id": "default_user"})
    return {"status": "ok", "message": "Session reset"}


@app.post("/api/atlas/chat")
async def atlas_chat(body: Dict[str, Any]):
    message = str(body.get("message", "")).strip()
    if not message:
        return {"status": "error", "error": "message is required"}

    state = _load_atlas_state()
    current_lesson = state.get("current_lesson") or {}
    current_exercise = state.get("current_exercise") or {}
    last_submission = state.get("last_submission") or {}

    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.2))

    tutor_prompt = (
        "You are ATLAS Tutor, a practical coding mentor. "
        "Give clear, concise help. Never provide harmful content.\n\n"
        f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
        f"Lesson objectives: {current_lesson.get('objectives', [])}\n"
        f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
        f"Recent submission result: {last_submission}\n\n"
        f"Student message: {message}\n\n"
        "Respond as a tutor with: 1) diagnosis, 2) next concrete step, 3) short example when useful."
    )

    llm_reply = ""
    active_model = ""
    active_adapter = ""
    try:
        from mammoth_os.llm_client import get_llm_client
        cfg: Dict[str, Any] = {}
        if adapter:
            cfg["adapter"] = adapter
        if model:
            cfg["model"] = model
            # If a local model/tag is requested, force Ollama adapter explicitly.
            model_l = model.lower()
            try:
                from mammoth_os.ollama_adapter import MODEL_ALIASES
                if model_l in MODEL_ALIASES or model_l in MODEL_ALIASES.values() or ":" in model_l:
                    cfg["adapter"] = "ollama"
            except Exception:
                if ":" in model_l:
                    cfg["adapter"] = "ollama"
        client = get_llm_client(config=cfg)
        active_model = str(getattr(client, "model", model or "unknown"))
        active_adapter = str((cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER") or "").strip() or "auto")
        llm_reply = await client.generate(tutor_prompt, temperature=temperature)
    except Exception as e:
        llm_reply = (
            "I could not reach the configured LLM runtime. "
            f"Here is a local fallback tip:\n{str(e)}\n\n"
            "Try: check your function signature, return value, and failing assertion line."
        )
        if not active_model:
            active_model = "fallback-local"
        if not active_adapter:
            active_adapter = "fallback-local"

    history = state.get("chat_history") or []
    if not isinstance(history, list):
        history = []
    history.append({
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    history.append({
        "role": "assistant",
        "message": llm_reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter": active_adapter,
        "model": active_model,
    })
    state["chat_history"] = history[-60:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)

    return {
        "status": "ok",
        "reply": llm_reply,
        "adapter": active_adapter,
        "model": active_model,
        "chat_history": state["chat_history"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# /api/notes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/notes")
async def get_notes():
    return _read_json(NOTES_FILE)


@app.post("/api/notes")
async def upsert_note(body: Dict[str, Any]):
    notes = _read_json(NOTES_FILE)
    note_id = body.get("id")
    now = datetime.now(timezone.utc).isoformat()
    if note_id:
        for i, n in enumerate(notes):
            if n.get("id") == note_id:
                notes[i] = {**n, **body, "updated_at": now}
                _write_json(NOTES_FILE, notes)
                return notes[i]
    # create new
    new_note = {
        "id":         str(uuid.uuid4()),
        "title":      body.get("title", "Untitled"),
        "body":       body.get("body", ""),
        "updated_at": now,
    }
    notes.append(new_note)
    _write_json(NOTES_FILE, notes)
    return new_note


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str):
    notes = _read_json(NOTES_FILE)
    notes = [n for n in notes if n.get("id") != note_id]
    _write_json(NOTES_FILE, notes)
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# /api/buildlog
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/buildlog")
async def get_buildlog():
    return _read_json(BUILDLOG_FILE)


@app.post("/api/buildlog")
async def append_buildlog(body: Dict[str, Any]):
    entries = _read_json(BUILDLOG_FILE)
    entry = {
        "id":          str(uuid.uuid4()),
        "title":       body.get("title", ""),
        "description": body.get("description", ""),
        "tags":        body.get("tags", []),
        "command":     body.get("command", ""),
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _write_json(BUILDLOG_FILE, entries)
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# /api/logsale
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/logsale")
async def get_sales():
    return _read_json(SALES_FILE)


@app.post("/api/logsale")
async def log_sale(body: Dict[str, Any]):
    sales = _read_json(SALES_FILE)
    entry = {
        "id":         str(uuid.uuid4()),
        "item":       body.get("item", ""),
        "amount":     body.get("amount", 0),
        "notes":      body.get("notes", ""),
        "date":       body.get("date", datetime.now(timezone.utc).date().isoformat()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sales.append(entry)
    _write_json(SALES_FILE, sales)
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# /api/modules
# ─────────────────────────────────────────────────────────────────────────────

_STATIC_MODULES = [
    {"id": "coding_agent",      "name": "CodingAgent",      "version": "v1.2.0", "status": "active",   "description": "Code generation, refactor, review"},
    {"id": "field_ops_agent",   "name": "FieldOpsAgent",    "version": "v0.9.1", "status": "active",   "description": "Planting, irrigation, field data"},
    {"id": "research_agent",    "name": "ResearchAgent",    "version": "v0.8.3", "status": "active",   "description": "Market intel, curriculum research"},
    {"id": "memory_engine",     "name": "MemoryEngine",     "version": "v0.8.0", "status": "active",   "description": "Long-term context & session memory"},
    {"id": "atlas_session",     "name": "ATLASSession",     "version": "v0.5.0", "status": "idle",     "description": "Progress tracking & subsystem status"},
    {"id": "plant_seed_agent",  "name": "PlantSeedAgent",   "version": "v0.6.2", "status": "idle",     "description": "Seed sourcing, planting schedules"},
    {"id": "market_intel_agent","name": "MarketIntelAgent", "version": "v0.3.0", "status": "idle",     "description": "Price feeds, market analysis"},
    {"id": "cortex_router",     "name": "CortexRouter",     "version": "v1.0.0", "status": "active",   "description": "Intent-based routing layer"},
    {"id": "engine_registry",   "name": "EngineRegistry",   "version": "v1.0.0", "status": "active",   "description": "Discovers and registers engine classes"},
]


@app.get("/api/modules")
async def get_modules():
    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    dynamic_ids = set(m["id"] for m in _STATIC_MODULES)
    extra = []
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            mid = f.stem
            if mid not in dynamic_ids:
                name = "".join(w.title() for w in mid.split("_"))
                extra.append({
                    "id":          mid,
                    "name":        name,
                    "version":     "v1.0.0",
                    "status":      "idle",
                    "description": f"Agent: {mid}",
                })
    return _STATIC_MODULES + extra



# ─────────────────────────────────────────────────────────────────────────────
# /api/terminal/exec  (HTTP fallback — returns full output at once)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/terminal/exec")
async def terminal_exec(body: Dict[str, Any]):
    cmd = str(body.get("cmd", "")).strip()
    if not cmd:
        return {"stdout": "", "stderr": "No command provided.", "exit_code": 1}
    if not _is_allowed(cmd):
        return {
            "stdout": "",
            "stderr": f"Not in allow-list: {cmd}\nAllowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}",
            "exit_code": 1,
        }
    result = await _execute_terminal_command(cmd)
    return {
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket /ws/terminal
# ─────────────────────────────────────────────────────────────────────────────

ALLOW_LIST = {
    "git status",
    "git log --oneline -20",
    "git log --oneline",
    "git diff --stat",
    "git branch",
    "npm run dev",
    "npm run build",
    "npm install",
    "python -m cli.main status",
    "python -m cli.main agent-list",
    "python -m cli.main health",
    "python -m cli.main atlas status",
    "python -m cli.main version",
    "python -m cli.main diagnostics",
    "py -m cli.main status",
    "uvicorn api_server:app --reload",
    "ls",
    "dir",
    "pwd",
}

ALLOW_PREFIXES = (
    "python -m cli.main",
    "py -m cli.main",
    "npm ",
    "uvicorn ",
    "cat ",
    "ls ",
    "dir ",
    "git ",
)


def _is_allowed(cmd: str) -> bool:
    s = cmd.strip()
    if s in ALLOW_LIST:
        return True
    for prefix in ALLOW_PREFIXES:
        if s.startswith(prefix):
            return True
    return False


def _make_env() -> dict:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    if src_path not in existing:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}" if existing else src_path
    return env


def _normalize_terminal_command(cmd: str) -> tuple:
    normalized = cmd.strip()
    run_cwd = ROOT

    # Unix aliases -> PowerShell
    if normalized == "pwd":
        normalized = "Get-Location | Select-Object -ExpandProperty Path"
    elif normalized == "ls":
        normalized = "Get-ChildItem | Format-Table Name,Length,LastWriteTime"
    elif normalized.startswith("cat "):
        normalized = "Get-Content " + normalized[4:]

    # npm -> UI dir
    if normalized.startswith("npm "):
        run_cwd = UI_DIR if UI_DIR.exists() else ROOT

    # Use venv python
    if normalized.startswith("python -m cli.main") and VENV_PYTHON.exists():
        normalized = f'& "{VENV_PYTHON}"' + normalized[len("python"):]
    elif normalized.startswith("py -m cli.main") and VENV_PYTHON.exists():
        normalized = f'& "{VENV_PYTHON}"' + normalized[len("py"):]

    # Use venv uvicorn
    if normalized.startswith("uvicorn ") and VENV_UVICORN.exists():
        normalized = f'& "{VENV_UVICORN}"' + normalized[len("uvicorn"):]

    return normalized, run_cwd


def _run_command_sync(resolved: str, run_cwd: Path, env: dict, timeout: int) -> Dict[str, Any]:
    """Run command synchronously via subprocess.run (Windows ProactorEventLoop-safe)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", resolved],
            capture_output=True,
            cwd=str(run_cwd),
            env=env,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace"),
            "exit_code": int(result.returncode or 0),
            "resolved": resolved,
            "cwd": str(run_cwd),
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out ({timeout}s)",
            "exit_code": 1,
            "resolved": resolved,
            "cwd": str(run_cwd),
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e!r}",
            "exit_code": 1,
            "resolved": resolved,
            "cwd": str(run_cwd),
        }


async def _execute_terminal_command(cmd: str, timeout: int = 60) -> Dict[str, Any]:
    resolved, run_cwd = _normalize_terminal_command(cmd)
    env = _make_env()
    return await asyncio.to_thread(_run_command_sync, resolved, run_cwd, env, timeout)


@app.websocket("/ws/terminal")
async def terminal_ws(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"line": "MammothOS Terminal ready. Type a command.", "type": "stdout"})
    try:
        while True:
            data = await ws.receive_json()
            cmd = data.get("cmd", "").strip()
            if not cmd:
                continue

            if not _is_allowed(cmd):
                await ws.send_json({"line": f"Not in allow-list: {cmd}", "type": "stderr"})
                await ws.send_json({"line": f"  Allowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}", "type": "stderr"})
                await ws.send_json({"line": f"[exit 1]", "type": "exit", "code": 1})
                continue

            await ws.send_json({"line": f"$ {cmd}", "type": "cmd"})
            result = await _execute_terminal_command(cmd)
            await ws.send_json({"line": f"[cwd] {result['cwd']}", "type": "stdout"})
            if result.get("stdout"):
                for line in result["stdout"].splitlines():
                    if line.strip():
                        await ws.send_json({"line": line, "type": "stdout"})
            if result.get("stderr"):
                for line in result["stderr"].splitlines():
                    if line.strip():
                        await ws.send_json({"line": line, "type": "stderr"})
            await ws.send_json({"line": f"[exit {result['exit_code']}]", "type": "exit", "code": result["exit_code"]})

    except WebSocketDisconnect:
        pass
