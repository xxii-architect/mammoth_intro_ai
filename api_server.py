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

    return {
        "status": "ok",
        "python_version": sys.version,
        "uptime": uptime_str,
        "uptime_seconds": uptime_s,
        "engine_count": len(engines),
        "agent_count": len(agents),
        "cli_commands_run": len(buildlog),
        "active_models": 3,
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
    env_vars: Dict[str, bool] = {}
    openai_ok = False
    supabase_ok = False
    if env_exists:
        try:
            text = env_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    env_vars[k] = bool(v)
            openai_ok  = bool(env_vars.get("OPENAI_API_KEY"))
            supabase_ok = bool(env_vars.get("SUPABASE_URL"))
        except Exception:
            pass

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
    ]

    return {
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "env_keys": list(env_vars.keys()),
    }


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
                    state["current_lesson"] = mod["lessons"][next_i]
                    state["lesson_id"]      = mod["lessons"][next_i]["lesson_id"]
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
# WebSocket /ws/terminal
# ─────────────────────────────────────────────────────────────────────────────

ALLOW_LIST = {
    "git status",
    "git log --oneline -20",
    "git diff --stat",
    "git branch",
    "git log --oneline",
    "npm run dev",
    "npm run build",
    "npm install",
    "python -m cli.main status",
    "python -m cli.main agent-list",
    "python -m cli.main health",
    "python -m cli.main atlas status",
    "uvicorn api_server:app --reload",
    "ls",
    "dir",
    "pwd",
}

ALLOW_PREFIXES = (
    "python -m cli.main",
    "cat ",
    "ls ",
    "dir ",
    "git log",
    "git diff",
)


def _is_allowed(cmd: str) -> bool:
    cmd_stripped = cmd.strip()
    if cmd_stripped in ALLOW_LIST:
        return True
    for prefix in ALLOW_PREFIXES:
        if cmd_stripped.startswith(prefix):
            return True
    return False


@app.websocket("/ws/terminal")
async def terminal_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            cmd  = data.get("cmd", "").strip()
            if not cmd:
                continue

            if not _is_allowed(cmd):
                await ws.send_json({"line": f"⛔ Command not in allow-list: {cmd}", "type": "stderr"})
                await ws.send_json({"line": "", "type": "exit", "code": 1})
                continue

            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(ROOT),
                )

                async def stream(stream_obj, stype):
                    async for raw in stream_obj:
                        line = raw.decode(errors="replace").rstrip("\n")
                        await ws.send_json({"line": line, "type": stype})

                await asyncio.gather(
                    stream(proc.stdout, "stdout"),
                    stream(proc.stderr, "stderr"),
                )
                code = await proc.wait()
                await ws.send_json({"line": f"[exit {code}]", "type": "exit", "code": code})
            except Exception as e:
                await ws.send_json({"line": f"Error: {e}", "type": "stderr"})
                await ws.send_json({"line": "", "type": "exit", "code": 1})

    except WebSocketDisconnect:
        pass
