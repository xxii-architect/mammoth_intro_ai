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

from mammoth_os.learner_model import build_learner_context, build_lesson_plan, load_learner_model, save_learner_model, set_onboarding_profile, update_learner_model

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
SNAPSHOTS_FILE = MAMMOTH_DIR / "snapshots.json"
UI_DIR        = ROOT / "ui" / "mad-architecht-command-center"
VENV_PYTHON   = ROOT / ".venv" / "Scripts" / "python.exe"
VENV_UVICORN  = ROOT / ".venv" / "Scripts" / "uvicorn.exe"
AGENT_ACTIVITY_FILE = MAMMOTH_DIR / "agent_activity.json"
TASKS_FILE = MAMMOTH_DIR / "tasks.json"

for _f in [NOTES_FILE, BUILDLOG_FILE, SALES_FILE, AGENT_ACTIVITY_FILE, TASKS_FILE, SNAPSHOTS_FILE]:
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


def _load_activity_events() -> List[Dict[str, Any]]:
    return _read_json(AGENT_ACTIVITY_FILE)


def _save_activity_events(entries: List[Dict[str, Any]]):
    _write_json(AGENT_ACTIVITY_FILE, entries)


def _append_activity(message: str, *, agent_id: str = "", task_id: str = "", kind: str = "event", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entries = _load_activity_events()
    entry = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "message": message,
        "agent_id": agent_id,
        "task_id": task_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    if len(entries) > 250:
        entries = entries[-250:]
    _save_activity_events(entries)
    return entry


def _create_approval_record(task_id: str, *, agent_id: str, operation: str, target: str, preview: Dict[str, Any], payload: Optional[Dict[str, Any]] = None, requested_by: str = "user") -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "agent_id": agent_id,
        "operation": operation,
        "target": target,
        "payload": payload or {},
        "preview": preview,
        "requested_by": requested_by,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    approvals = _read_json(MAMMOTH_DIR / "approvals.json", default=[])
    approvals.append(record)
    _write_json(MAMMOTH_DIR / "approvals.json", approvals)
    return record


def _build_operation_preview(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    file_path = str(payload.get("file_path", "") or "").strip()
    if operation == "create_file":
        return {
            "summary": "Create file",
            "file_path": file_path,
            "content_preview": str(payload.get("content", "") or "")[:400],
        }
    if operation == "write_file":
        return {
            "summary": "Overwrite file",
            "file_path": file_path,
            "content_preview": str(payload.get("content", "") or "")[:400],
        }
    if operation == "apply_patch":
        return {
            "summary": "Replace file contents",
            "file_path": file_path,
            "content_preview": str(payload.get("new_content", "") or "")[:400],
        }
    if operation == "insert_after":
        return {
            "summary": "Insert after anchor",
            "file_path": file_path,
            "anchor": str(payload.get("anchor", "") or "")[:120],
            "content_preview": str(payload.get("content", "") or "")[:200],
        }
    return {"summary": "File operation", "file_path": file_path}


def _resolve_target_path(file_path: str) -> Path:
    target = Path(file_path)
    if not target.is_absolute():
        target = ROOT / file_path
    return target


def _load_snapshots() -> List[Dict[str, Any]]:
    return _read_json(SNAPSHOTS_FILE, default=[])


def _save_snapshots(entries: List[Dict[str, Any]]) -> None:
    _write_json(SNAPSHOTS_FILE, entries)


def _create_snapshot(*, approval_id: str, agent_id: str, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    target = _resolve_target_path(str(payload.get("file_path", "") or "").strip())
    existed_before = target.exists()
    snapshot = {
        "id": str(uuid.uuid4()),
        "approval_id": approval_id,
        "agent_id": agent_id,
        "operation": operation,
        "file_path": str(target),
        "existed_before": existed_before,
        "previous_content": target.read_text(encoding="utf-8") if existed_before else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries = _load_snapshots()
    entries.append(snapshot)
    _save_snapshots(entries)
    return snapshot


def _restore_snapshot(snapshot_id: str) -> Dict[str, Any]:
    snapshots = _load_snapshots()
    snapshot = next((item for item in snapshots if item.get("id") == snapshot_id), None)
    if snapshot is None:
        return {"status": "error", "message": "snapshot not found"}

    target = Path(str(snapshot.get("file_path", "") or ""))
    existed_before = bool(snapshot.get("existed_before"))
    previous_content = snapshot.get("previous_content")

    if existed_before:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(previous_content or ""), encoding="utf-8")
    elif target.exists():
        target.unlink()

    snapshot["restored_at"] = datetime.now(timezone.utc).isoformat()
    _save_snapshots(snapshots)
    return {"status": "ok", "snapshot": snapshot}


def _execute_approval_record(record: Dict[str, Any]) -> Dict[str, Any]:
    operation = str(record.get("operation", "")).strip()
    payload = record.get("payload") or {}
    if operation in {"create_file", "write_file", "apply_patch", "insert_after"}:
        snapshot = _create_snapshot(
            approval_id=str(record.get("id", "") or ""),
            agent_id=str(record.get("agent_id", "") or ""),
            operation=operation,
            payload=payload,
        )
        result = _run_file_operation(operation, payload)
        if isinstance(result, dict):
            result["snapshot_id"] = snapshot["id"]
        return result
    return {"status": "error", "message": f"Unsupported approval operation {operation!r}"}


def _approve_record(record_id: str) -> Dict[str, Any]:
    approvals = _read_json(MAMMOTH_DIR / "approvals.json", default=[])
    updated = None
    for item in approvals:
        if item.get("id") == record_id:
            if item.get("status") == "approved":
                return {"status": "ok", "approval": item, "result": item.get("last_result")}
            item["status"] = "approved"
            item["approved_at"] = datetime.now(timezone.utc).isoformat()
            updated = item
            break
    if updated is None:
        return {"status": "error", "message": "approval not found"}
    result = _execute_approval_record(updated)
    updated["last_result"] = result
    updated["completed_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(MAMMOTH_DIR / "approvals.json", approvals)
    return {"status": "ok", "approval": updated, "result": result}


def _load_approvals() -> List[Dict[str, Any]]:
    return _read_json(MAMMOTH_DIR / "approvals.json", default=[])


def _load_tasks() -> List[Dict[str, Any]]:
    return _read_json(TASKS_FILE)


def _save_tasks(tasks: List[Dict[str, Any]]):
    _write_json(TASKS_FILE, tasks)


def _upsert_task(task_id: str, title: str, *, status: str = "queued", agent_id: str = "", description: str = "", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tasks = _load_tasks()
    now = datetime.now(timezone.utc).isoformat()
    existing = next((t for t in tasks if t.get("id") == task_id), None)
    task = {
        "id": task_id,
        "title": title,
        "status": status,
        "agent_id": agent_id,
        "description": description,
        "details": details or {},
        "updated_at": now,
        "created_at": existing.get("created_at") if existing else now,
    }
    if existing:
        task["created_at"] = existing.get("created_at") or now
        tasks = [t for t in tasks if t.get("id") != task_id]
    tasks.append(task)
    _save_tasks(tasks)
    return task


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
    from mammoth_os.agent_registry import agent_registry, AgentStatus, AGENTS
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
# /api/activity + /api/tasks
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/activity")
async def get_activity():
    return _load_activity_events()


@app.post("/api/activity")
async def add_activity(body: Dict[str, Any]):
    return _append_activity(
        str(body.get("message", "")),
        agent_id=str(body.get("agent_id", "") or ""),
        task_id=str(body.get("task_id", "") or ""),
        kind=str(body.get("kind", "event") or "event"),
        details=body.get("details") or {},
    )


@app.get("/api/tasks")
async def get_tasks():
    return _load_tasks()


@app.post("/api/tasks")
async def upsert_task(body: Dict[str, Any]):
    task_id = str(body.get("id") or "").strip() or f"task-{uuid.uuid4().hex[:8]}"
    return _upsert_task(
        task_id,
        str(body.get("title", "Untitled task")),
        status=str(body.get("status", "queued") or "queued"),
        agent_id=str(body.get("agent_id", "") or ""),
        description=str(body.get("description", "") or ""),
        details=body.get("details") or {},
    )


_INTENT_TO_AGENT_ID = {
    "plant_seed": "plant_the_seed_agent",
    "field_ops": "field_ops_agent",
    "market_intel": "market_intel_agent",
    "reflection": "reflection_agent",
    "brand_voice": "brand_voice_agent",
    "research_curriculum": "research_agent",
    "research_survival": "research_agent",
    "research_plants": "research_agent",
    "compare_gear": "research_agent",
    "summarize": "research_agent",
}

_AGENT_ID_TO_RUNTIME = {
    "plant_the_seed_agent": "plant_the_seed",
    "field_ops_agent": "field_ops",
    "market_intel_agent": "market_intel",
    "reflection_agent": "reflection",
    "brand_voice_agent": "brand_voice",
    "research_agent": "research",
    "coding_agent": "coding",
    "community_engine_agent": "community_engine",
    "custodial_agent": "custodial",
}


def _agent_id_from_intent(intent: str) -> str:
    return _INTENT_TO_AGENT_ID.get(str(intent or "").strip(), "")


def _runtime_agent_name(intent: str, selected_agent_id: str) -> str:
    if selected_agent_id and selected_agent_id in _AGENT_ID_TO_RUNTIME:
        return _AGENT_ID_TO_RUNTIME[selected_agent_id]
    inferred = _agent_id_from_intent(intent)
    if inferred:
        return _AGENT_ID_TO_RUNTIME.get(inferred, "")
    return ""


def _parse_coding_operation(payload: Dict[str, Any], prompt_text: str) -> tuple[str, Dict[str, Any]]:
    if isinstance(payload, dict):
        op = str(payload.get("operation", "")).strip().lower()
        file_path = str(payload.get("file_path", "")).strip()
        if op in {"create_file", "write_file", "apply_patch"} and file_path:
            if op == "apply_patch":
                content = str(payload.get("new_content", ""))
                return op, {"file_path": file_path, "new_content": content}
            content = str(payload.get("content", ""))
            return op, {"file_path": file_path, "content": content}
        if op == "insert_after" and file_path:
            anchor = str(payload.get("anchor", ""))
            content = str(payload.get("content", ""))
            if anchor and content:
                return op, {"file_path": file_path, "anchor": anchor, "content": content}

    first, sep, rest = prompt_text.partition("\n")
    first = first.strip()
    if first.startswith("/create "):
        fp = first[len("/create "):].strip()
        return "create_file", {"file_path": fp, "content": rest if sep else ""}
    if first.startswith("/write "):
        fp = first[len("/write "):].strip()
        return "write_file", {"file_path": fp, "content": rest if sep else ""}
    if first.startswith("/patch "):
        fp = first[len("/patch "):].strip()
        return "apply_patch", {"file_path": fp, "new_content": rest if sep else ""}
    if first.startswith("/insert "):
        fp = first[len("/insert "):].strip()
        marker = "\n---\n"
        if marker in rest:
            anchor, content = rest.split(marker, 1)
            if fp and anchor.strip() and content:
                return "insert_after", {"file_path": fp, "anchor": anchor.strip(), "content": content}

    return "", {}


def _insert_after_content(file_path: str, anchor: str, content: str) -> Dict[str, Any]:
    target = _resolve_target_path(file_path)
    if not target.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}
    current = target.read_text(encoding="utf-8")
    idx = current.find(anchor)
    if idx < 0:
        return {"status": "error", "message": "Anchor text not found", "path": str(target)}
    insert_at = idx + len(anchor)
    # Always insert on its own line
    safe_content = content if content.startswith("\n") else "\n" + content
    if not safe_content.endswith("\n"):
        safe_content = safe_content + "\n"
    updated = current[:insert_at] + safe_content + current[insert_at:]
    target.write_text(updated, encoding="utf-8")
    return {"status": "success", "action": "insert_after", "path": str(target)}


_SAFE_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".env", ".sh", ".bat", ".ps1", ".toml", ".cfg", ".ini", ".csv", ".jsx", ".tsx", ".ts", ".js", ".css"}


def _run_file_operation(operation: str, op_payload: Dict[str, Any]) -> Dict[str, Any]:
    file_path = str(op_payload.get("file_path", "")).strip()
    if file_path:
        ext = Path(file_path).suffix.lower()
        if ext not in _SAFE_EXTENSIONS:
            return {"status": "error", "message": f"Extension {ext!r} not in safe-write list. Add it to _SAFE_EXTENSIONS if intentional."}
    if operation == "insert_after":
        return _insert_after_content(
            file_path,
            str(op_payload.get("anchor", "")),
            str(op_payload.get("content", "")),
        )
    from mammoth_os.agents.autonomous_engine import AutonomousEngine
    engine = AutonomousEngine()
    return engine.run_task(operation, op_payload)


# ─────────────────────────────────────────────────────────────────────────────
# /api/run
# ─────────────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_plan_profile(raw_profile: Any) -> str:
    profile = str(raw_profile or "balanced").strip().lower()
    if profile not in {"atlas", "coding", "balanced"}:
        return "balanced"
    return profile


def _build_plan_steps(objective: str, plan_profile: str = "balanced") -> List[Dict[str, str]]:
    objective = (objective or "").strip()
    lower = objective.lower()
    profile = _normalize_plan_profile(plan_profile)
    include_coding = profile == "coding" or any(tok in lower for tok in ["build", "implement", "code", "patch", "create", "ui", "feature"])
    include_market = profile == "atlas" or any(tok in lower for tok in ["market", "audience", "position", "messaging"])
    include_field_ops = profile == "atlas" or any(tok in lower for tok in ["ops", "operational", "runbook", "checklist", "launch"])

    steps: List[Dict[str, str]] = [
        {
            "id": "seed-direction",
            "title": "Plant ATLAS strategic direction",
            "agent_id": "plant_the_seed_agent",
            "intent": "plant_seed",
            "prompt": f"Plant the strategic seed for this objective in 4 concise bullets: {objective}",
        },
        {
            "id": "research-brief",
            "title": "Research objective and constraints",
            "agent_id": "research_agent",
            "intent": "research_curriculum",
            "prompt": f"Analyze this objective and list key constraints in 4 bullets: {objective}",
        },
        {
            "id": "reflection-risks",
            "title": "Identify risks and acceptance criteria",
            "agent_id": "reflection_agent",
            "intent": "reflection",
            "prompt": f"Given this objective, list top risks and acceptance criteria: {objective}",
        },
    ]

    if include_market:
        steps.append(
            {
                "id": "market-angle",
                "title": "Add market and user framing",
                "agent_id": "market_intel_agent",
                "intent": "market_intel",
                "prompt": f"Provide a short market and user framing for: {objective}",
            }
        )

    if include_field_ops:
        steps.append(
            {
                "id": "field-ops-check",
                "title": "Outline operational execution checks",
                "agent_id": "field_ops_agent",
                "intent": "field_ops",
                "prompt": f"Provide an operational execution checklist for this objective: {objective}",
            }
        )

    if include_coding:
        steps.append(
            {
                "id": "coding-plan",
                "title": "Draft implementation approach",
                "agent_id": "coding_agent",
                "intent": "summarize",
                "prompt": f"Provide a concise implementation plan and verification checklist for: {objective}",
            }
        )

    steps.append(
        {
            "id": "brand-summary",
            "title": "Produce stakeholder-ready summary",
            "agent_id": "brand_voice_agent",
            "intent": "brand_voice",
            "prompt": f"Summarize the plan in confident brand voice for stakeholders: {objective}",
        }
    )

    return steps


@app.post("/api/plan-execute")
async def plan_execute(body: Dict[str, Any]):
    objective = str(body.get("objective", "") or body.get("prompt", "")).strip()
    temperature = body.get("temperature", 0.4)
    approval_mode = bool(body.get("approval_mode"))
    stop_on_failure = bool(body.get("stop_on_failure", True))
    plan_profile = _normalize_plan_profile(body.get("plan_profile"))

    if not objective:
        return {"status": "error", "error": "objective is required"}

    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    steps = _build_plan_steps(objective, plan_profile)

    _upsert_task(
        plan_id,
        "plan+execute run",
        status="active",
        agent_id="orchestrator",
        description=objective,
        details={"objective": objective, "step_count": len(steps), "approval_mode": approval_mode, "plan_profile": plan_profile},
    )
    _append_activity(
        "Started plan+execute run",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_started",
        details={"objective": objective, "step_count": len(steps), "plan_profile": plan_profile},
    )

    step_results: List[Dict[str, Any]] = []

    for idx, step in enumerate(steps, start=1):
        started_at = _ts()
        _append_activity(
            f"Plan step {idx}/{len(steps)}: {step['title']}",
            agent_id=step["agent_id"],
            task_id=plan_id,
            kind="plan_step_started",
            details={"step": step},
        )

        run_body = {
            "intent": step["intent"],
            "payload": {"prompt": step["prompt"]},
            "temperature": temperature,
            "agent_id": step["agent_id"],
            "approval_mode": approval_mode if step["agent_id"] == "coding_agent" else False,
        }

        response = await run_agent(run_body)
        result_obj = response.get("result") if isinstance(response, dict) else {}
        inner_status = str((result_obj or {}).get("status", ""))

        if response.get("status") != "ok" or inner_status == "error":
            step_status = "failed"
        elif inner_status == "pending_approval":
            step_status = "pending_approval"
        else:
            step_status = "completed"

        finished_at = _ts()
        duration_ms = max(0, int((datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000))
        step_result = {
            "id": step["id"],
            "title": step["title"],
            "agent_id": step["agent_id"],
            "intent": step["intent"],
            "prompt": step["prompt"],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "status": step_status,
            "response": response,
        }
        step_results.append(step_result)

        _append_activity(
            f"Plan step {idx}/{len(steps)} {step_status}",
            agent_id=step["agent_id"],
            task_id=plan_id,
            kind="plan_step_completed" if step_status != "failed" else "plan_step_failed",
            details={"step_id": step["id"], "status": step_status, "duration_ms": duration_ms},
        )

        if step_status == "failed" and stop_on_failure:
            break

    failed_count = sum(1 for s in step_results if s["status"] == "failed")
    pending_count = sum(1 for s in step_results if s["status"] == "pending_approval")
    completed_count = sum(1 for s in step_results if s["status"] == "completed")
    executed_count = len(step_results)
    total_count = len(steps)

    if failed_count > 0:
        plan_status = "failed"
    elif pending_count > 0:
        plan_status = "pending_approval"
    else:
        plan_status = "completed"

    _upsert_task(
        plan_id,
        "plan+execute run",
        status=plan_status,
        agent_id="orchestrator",
        description=objective,
        details={
            "objective": objective,
            "plan_profile": plan_profile,
            "total": total_count,
            "executed": executed_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
    )

    _append_activity(
        f"Plan+execute run {plan_status}",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_completed" if plan_status != "failed" else "plan_failed",
        details={"objective": objective, "plan_profile": plan_profile, "executed": executed_count, "failed": failed_count},
    )

    return {
        "status": "ok",
        "plan_id": plan_id,
        "objective": objective,
        "plan_profile": plan_profile,
        "plan_status": plan_status,
        "progress": {
            "total": total_count,
            "executed": executed_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
        "plan_steps": step_results,
    }


@app.post("/api/run")
async def run_agent(body: Dict[str, Any]):
    intent = str(body.get("intent", "")).strip()
    payload = body.get("payload", {})
    temperature = body.get("temperature", 0.7)
    requested_agent_id = str(body.get("agent_id", "")).strip()
    tracked_agent_id = requested_agent_id or _agent_id_from_intent(intent)
    prompt_text = str(payload.get("prompt", "") or "").strip()
    approval_mode = bool(body.get("approval_mode") or payload.get("approval_mode") or payload.get("preview_only"))

    thought_steps: List[Dict[str, Any]] = []
    def _think(label: str, detail: str = "", status: str = "info") -> None:
        thought_steps.append({"ts": _ts(), "label": label, "detail": detail, "status": status})

    _think("Received request", f"intent={intent!r}  agent={requested_agent_id!r}  approval_mode={approval_mode}")

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    task = _upsert_task(
        task_id,
        f"{intent or 'agent'} run",
        status="active",
        agent_id=tracked_agent_id,
        description=prompt_text or "Agent execution started",
        details={"intent": intent, "temperature": temperature, "approval_mode": approval_mode},
    )
    _append_activity(
        f"Started task for {intent or 'agent'}",
        agent_id=tracked_agent_id,
        task_id=task_id,
        kind="task_started",
        details={"prompt": prompt_text[:220], "temperature": temperature, "approval_mode": approval_mode},
    )

    manifest = None
    if _agent_registry_ok and tracked_agent_id:
        try:
            manifest = await agent_registry.get_agent(tracked_agent_id)
            if manifest:
                manifest.status = AgentStatus.ACTIVE
                manifest.last_heartbeat = datetime.now(timezone.utc)
                _think("Agent resolved", f"name={manifest.name!r}  type={getattr(manifest, 'agent_type', 'unknown')!r}", "success")
            else:
                _think("Agent not in registry", f"id={tracked_agent_id!r} — will fall back to intent routing", "warning")
        except Exception:
            manifest = None

    try:
        runtime_agent = _runtime_agent_name(intent, tracked_agent_id)
        _think("Routing decision", f"runtime_agent={runtime_agent!r}  agent_id={tracked_agent_id!r}")
        coding_op, coding_payload = _parse_coding_operation(payload if isinstance(payload, dict) else {}, prompt_text)
        if runtime_agent == "coding" and coding_op:
            _think("Operation parsed", f"op={coding_op!r}  target={coding_payload.get('file_path','?')!r}")
            if approval_mode:
                preview = _build_operation_preview(coding_op, coding_payload)
                approval = _create_approval_record(
                    task_id,
                    agent_id=tracked_agent_id or "coding_agent",
                    operation=coding_op,
                    target=str(coding_payload.get("file_path", "")) or "unknown",
                    preview=preview,
                    payload=coding_payload,
                    requested_by="user",
                )
                _upsert_task(
                    task_id,
                    task["title"],
                    status="pending_approval",
                    agent_id=tracked_agent_id,
                    description=prompt_text or "Approval required for file change",
                    details={"intent": intent, "temperature": temperature, "approval_id": approval["id"]},
                )
                _append_activity(
                    f"Requested approval for {coding_op}",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="approval_requested",
                    details={"approval_id": approval["id"], "target": approval["target"]},
                )
                _think("Queued for approval", f"approval_id={approval['id']}  op={coding_op!r}  target={approval['target']!r}", "warning")
                result = {
                    "status": "pending_approval",
                    "runtime_agent": runtime_agent,
                    "operation": coding_op,
                    "approval": approval,
                    "preview": preview,
                }
            else:
                _think("Executing file operation", f"op={coding_op!r}  direct=True")
                raw_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _run_file_operation(coding_op, coding_payload)
                )
                _think("File operation done", f"status={raw_result.get('status','?')!r}  path={raw_result.get('path','?')!r}", "success")
                result = {
                    "status": "ok",
                    "runtime_agent": runtime_agent,
                    "operation": coding_op,
                    "output": raw_result,
                }
        elif runtime_agent and _agent_registry_ok and runtime_agent in AGENTS:
            payload_agents = {"plant_the_seed", "market_intel", "reflection", "brand_voice", "community_engine"}
            if runtime_agent in payload_agents:
                payload_for_agent = dict(payload) if isinstance(payload, dict) else {}
                if prompt_text and not payload_for_agent.get("topic"):
                    payload_for_agent["topic"] = prompt_text
            else:
                payload_for_agent = prompt_text or json.dumps(payload)

            _think("Dispatching to agent", f"runtime_agent={runtime_agent!r}")
            raw_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: AGENTS[runtime_agent](payload_for_agent)
            )
            _think("Agent returned", f"type={type(raw_result).__name__}  preview={str(raw_result)[:120]!r}", "success")
            result = {
                "status": "ok",
                "runtime_agent": runtime_agent,
                "output": raw_result,
            }
        else:
            _think("Falling back to CortexRouter", f"intent={intent!r}  no matching AGENTS key", "warning")
            from mammoth_os.cortex.router import CortexRouter
            router = CortexRouter()
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: router.route(intent, payload)
            )
            _think("CortexRouter returned", f"status={result.get('status','?')!r}  preview={str(result)[:120]!r}", "success")

        if manifest:
            await asyncio.sleep(1.2)
            manifest.status = AgentStatus.IDLE
            manifest.last_heartbeat = datetime.now(timezone.utc)
            manifest.metadata["last_intent"] = intent
            manifest.metadata["last_run_at"] = datetime.now(timezone.utc).isoformat()

        task_status = "completed" if result.get("status") != "pending_approval" else "pending_approval"
        _upsert_task(
            task_id,
            task["title"],
            status=task_status,
            agent_id=tracked_agent_id,
            description=prompt_text or "Agent execution completed",
            details={"intent": intent, "temperature": temperature, "result": str(result)[:1000]},
        )
        if task_status == "completed":
            _append_activity(
                f"Completed task for {intent or 'agent'}",
                agent_id=tracked_agent_id,
                task_id=task_id,
                kind="task_completed",
                details={"result": str(result)[:1000]},
            )

        _think("Run complete", f"task_status={task_status!r}", "success")
        return {
            "status": "ok",
            "result": result,
            "intent": intent,
            "agent_id": tracked_agent_id,
            "temperature": temperature,
            "task_id": task_id,
            "thought_steps": thought_steps,
        }
    except Exception as e:
        if manifest:
            manifest.status = AgentStatus.ERROR
            manifest.last_heartbeat = datetime.now(timezone.utc)
            manifest.metadata["last_error"] = str(e)

        _upsert_task(
            task_id,
            task["title"],
            status="failed",
            agent_id=tracked_agent_id,
            description=prompt_text or "Agent execution failed",
            details={"intent": intent, "temperature": temperature, "error": str(e)[:1000]},
        )
        _append_activity(
            f"Failed task for {intent or 'agent'}",
            agent_id=tracked_agent_id,
            task_id=task_id,
            kind="task_failed",
            details={"error": str(e)[:1000]},
        )

        _think("Run failed", str(e)[:200], "error")
        return {
            "status": "error",
            "error": str(e),
            "intent": intent,
            "agent_id": tracked_agent_id,
            "task_id": task_id,
            "thought_steps": thought_steps,
        }


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


def _hydrate_learner_state(state: Dict[str, Any], *, user_id: str = "default_user", lesson: Optional[Dict[str, Any]] = None, exercise: Optional[Dict[str, Any]] = None, result: Optional[Dict[str, Any]] = None, topic: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    learner_state = load_learner_model(user_id)
    if result is not None:
        learner_state = update_learner_model(
            user_id,
            lesson=lesson,
            exercise=exercise,
            result=result,
            topic=topic,
            metadata=metadata,
        )
    learner_context = build_learner_context(learner_state)
    state["learner_model"] = learner_state
    state["learner_context"] = learner_context
    state["learner_profile"] = {
        "streak": learner_context.get("streak", 0),
        "attempts": learner_context.get("attempts", 0),
        "recommended_difficulty": learner_context.get("recommended_difficulty", "beginner"),
        "preferred_pacing": learner_context.get("preferred_pacing", "gentle"),
    }
    return learner_state


def _append_lesson_history(state: Dict[str, Any], lesson: Dict[str, Any], exercise: Dict[str, Any]):
    history = state.get("lesson_history") or []
    if not isinstance(history, list):
        history = []
    entry = {
        "lesson_id": lesson.get("lesson_id"),
        "lesson": lesson,
        "exercise": exercise,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if not history or history[-1].get("lesson_id") != entry["lesson_id"]:
        history.append(entry)
    state["lesson_history"] = history[-80:]


def _build_lesson_recap(state: Dict[str, Any]) -> str:
    lesson = state.get("current_lesson") or {}
    exercise = state.get("current_exercise") or {}
    submission = state.get("last_submission") or {}
    objectives = lesson.get("objectives") or []
    title = lesson.get("title") or "Current lesson"
    prompt = exercise.get("prompt") or ""
    status = "passed" if submission.get("passed") else "in progress"
    return (
        f"Lesson recap: {title}.\n"
        f"Objectives: {objectives}.\n"
        f"Current exercise: {prompt}\n"
        f"Latest submission status: {status}."
    )


def _build_lesson_quiz(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    lesson = state.get("current_lesson") or {}
    objectives = lesson.get("objectives") or []
    prompt = (state.get("current_exercise") or {}).get("prompt") or ""
    questions: List[Dict[str, Any]] = []
    for idx, obj in enumerate(objectives[:3], start=1):
        questions.append({
            "id": f"q{idx}",
            "question": f"Explain this objective in your own words: {obj}",
            "type": "short_answer",
        })
    if len(questions) < 3:
        questions.append({
            "id": f"q{len(questions)+1}",
            "question": f"What would be your plan to solve this exercise: {prompt}",
            "type": "short_answer",
        })
    return questions[:3]


def _build_lesson_review(state: Dict[str, Any]) -> Dict[str, Any]:
    submission = state.get("last_submission") or {}
    passed = bool(submission.get("passed"))
    hint = submission.get("hint") or "No submission feedback yet."
    return {
        "strengths": ["Consistent lesson activity"] if passed else ["You are actively iterating"],
        "focus_next": [
            "Tighten function return values against test expectations",
            "Run one quick self-check before submitting",
        ] if not passed else ["Increase challenge difficulty", "Try refactoring the passing solution"],
        "coach_note": hint,
    }


def _append_study_aid(state: Dict[str, Any], aid_type: str, data: Any):
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        aids = []
    lesson = state.get("current_lesson") or {}
    aids.append({
        "id": str(uuid.uuid4()),
        "type": str(aid_type or "unknown"),
        "lesson_id": state.get("lesson_id") or lesson.get("lesson_id"),
        "lesson_title": lesson.get("title") or lesson.get("lesson_title"),
        "data": data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    state["study_aids"] = aids[-120:]


def _build_lesson_flashcards(state: Dict[str, Any]) -> List[Dict[str, str]]:
    lesson = state.get("current_lesson") or {}
    exercise = state.get("current_exercise") or {}
    objectives = [str(item).strip() for item in (lesson.get("objectives") or []) if str(item).strip()]
    lesson_title = lesson.get("title") or lesson.get("lesson_title") or "Current lesson"
    cards: List[Dict[str, str]] = []

    for idx, objective in enumerate(objectives[:4], start=1):
        cards.append({
            "id": f"obj-{idx}",
            "front": f"{lesson_title}: What does this objective mean? ({objective})",
            "back": f"Explain {objective} in your own words, then write one tiny example that demonstrates it.",
        })

    prompt = str(exercise.get("prompt") or "").strip()
    if prompt:
        cards.append({
            "id": "exercise-plan",
            "front": "What is your plan before coding this exercise?",
            "back": f"Summarize the input/output, then list 2-3 steps to solve this prompt: {prompt[:220]}",
        })

    return cards[:6]


def _matching_notes_for_lesson(state: Dict[str, Any], lesson_id: Optional[str]) -> List[Dict[str, Any]]:
    notes = _read_json(NOTES_FILE, default=[])
    if not isinstance(notes, list):
        return []

    lesson = state.get("current_lesson") or {}
    keywords = [
        str(lesson_id or "").strip().lower(),
        str(lesson.get("title") or lesson.get("lesson_title") or "").strip().lower(),
        str(state.get("topic") or "").strip().lower(),
    ]
    keywords = [k for k in keywords if k]

    matches: List[Dict[str, Any]] = []
    for raw in reversed(notes):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "") or "")
        body = str(raw.get("body", "") or "")
        haystack = f"{title}\n{body}".lower()
        if keywords and not any(k in haystack for k in keywords):
            continue
        matches.append({
            "id": str(raw.get("id", "")),
            "title": title or "Untitled",
            "preview": body[:220],
            "updated_at": raw.get("updated_at"),
        })
        if len(matches) >= 5:
            break

    if matches:
        return matches

    fallback: List[Dict[str, Any]] = []
    for raw in reversed(notes[-3:]):
        if not isinstance(raw, dict):
            continue
        fallback.append({
            "id": str(raw.get("id", "")),
            "title": str(raw.get("title", "") or "Untitled"),
            "preview": str(raw.get("body", "") or "")[:220],
            "updated_at": raw.get("updated_at"),
        })
    return fallback


def _flashcards_for_lesson(state: Dict[str, Any], lesson_id: Optional[str]) -> List[Dict[str, str]]:
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        aids = []

    cards: List[Dict[str, str]] = []
    for item in reversed(aids):
        if not isinstance(item, dict):
            continue
        if str(item.get("lesson_id") or "") != str(lesson_id or ""):
            continue
        aid_type = str(item.get("type") or "")
        data = item.get("data")
        if aid_type == "flashcards" and isinstance(data, list):
            for card in data:
                if not isinstance(card, dict):
                    continue
                front = str(card.get("front") or "").strip()
                back = str(card.get("back") or "").strip()
                if front and back:
                    cards.append({"front": front, "back": back})
        elif aid_type == "quiz" and isinstance(data, list):
            for q in data:
                question = str((q or {}).get("question") if isinstance(q, dict) else q).strip()
                if question:
                    cards.append({
                        "front": question,
                        "back": "Answer from memory, then verify against the lesson objective and your code.",
                    })
        if len(cards) >= 10:
            break

    deduped: List[Dict[str, str]] = []
    seen = set()
    for card in cards:
        key = card["front"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
        if len(deduped) >= 8:
            break
    return deduped


def _build_resume_packet(state: Dict[str, Any], lesson_id: Optional[str]) -> Dict[str, Any]:
    lesson = state.get("current_lesson") or {}
    submission = state.get("last_submission") or {}
    objectives = [str(item) for item in (lesson.get("objectives") or []) if str(item).strip()]
    notes = _matching_notes_for_lesson(state, lesson_id)
    flashcards = _flashcards_for_lesson(state, lesson_id)
    passed = bool(submission.get("passed"))
    status_line = "Latest submission passed." if passed else "Latest submission still needs work."
    hint = str(submission.get("hint") or submission.get("error") or "").strip()
    summary = (
        f"Welcome back to {lesson.get('title') or lesson.get('lesson_title') or (lesson_id or 'this lesson')}. "
        f"You previously worked on {max(1, len(objectives))} objective(s). "
        f"{status_line} "
        f"{('Last feedback: ' + hint[:180]) if hint else ''}".strip()
    )
    return {
        "lesson_id": lesson_id,
        "lesson_title": lesson.get("title") or lesson.get("lesson_title") or lesson_id,
        "summary": summary,
        "objectives": objectives[:4],
        "notes": notes[:5],
        "flashcards": flashcards[:8],
        "has_resources": bool(notes or flashcards),
    }


@app.get("/api/atlas/status")
async def atlas_status():
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id="default_user")
    lesson_id = state.get("lesson_id")
    if lesson_id:
        state["resume_packet"] = _build_resume_packet(state, lesson_id)
    return state


@app.get("/api/atlas/learner")
async def atlas_learner():
    state = _load_atlas_state()
    learner_state = _hydrate_learner_state(state, user_id="default_user")
    return {"status": "ok", "learner_model": learner_state, "learner_context": state.get("learner_context")}


@app.post("/api/atlas/onboard")
async def atlas_onboard(body: Dict[str, Any]):
    state = _load_atlas_state()
    learner_state = set_onboarding_profile(state, user_id="default_user", onboarding=body)
    _save_atlas_state(state)
    return {
        "status": "ok",
        "learner_model": learner_state,
        "learner_context": state.get("learner_context"),
        "learner_profile": state.get("learner_profile"),
    }


@app.post("/api/atlas/learner/reset")
async def atlas_learner_reset():
    learner_state = load_learner_model("default_user")
    learner_state.update({
        "mastery": {},
        "confidence": {},
        "streak": 0,
        "attempts": 0,
        "error_patterns": {},
        "recent_outcomes": [],
        "memory_graph": {"nodes": [], "edges": [], "last_updated": None},
    })
    learner_state = save_learner_model(learner_state)
    state = _load_atlas_state()
    state["learner_model"] = learner_state
    state["learner_context"] = build_learner_context(learner_state)
    state["learner_profile"] = {
        "streak": 0,
        "attempts": 0,
        "recommended_difficulty": "beginner",
        "preferred_pacing": "gentle",
    }
    _save_atlas_state(state)
    return {"status": "ok", "learner_model": learner_state, "learner_context": state["learner_context"]}


@app.post("/api/atlas/lesson")
async def atlas_lesson(body: Dict[str, Any]):
    topic = body.get("topic", "Python basics")
    try:
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession(user_id="default_user")
        state = _load_atlas_state()
        learner_context = state.get("learner_context") or {}
        if not learner_context:
            _hydrate_learner_state(state, user_id="default_user")
            learner_context = state.get("learner_context") or {}
        lesson_plan = build_lesson_plan(state, topic)
        learner_context = {**learner_context, "lesson_plan": lesson_plan}
        difficulty = str(lesson_plan.get("difficulty") or learner_context.get("recommended_difficulty") or "beginner").strip().lower() or "beginner"
        exercise = await asyncio.get_event_loop().run_in_executor(
            None, lambda: session.start_lesson(topic, difficulty=difficulty, learner_context=learner_context)
        )
        state.update({
            "status":           "active",
            "topic":            topic,
            "current_exercise": exercise,
            "curriculum":       session.curriculum,
            "current_lesson":   session.current_lesson,
            "curriculum_id":    session._curriculum_id,
            "lesson_id":        session._lesson_id,
            "lesson_plan":      lesson_plan,
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        })
        _hydrate_learner_state(state, user_id="default_user")
        _append_lesson_history(state, session.current_lesson or {}, exercise or {})
        state["resume_packet"] = _build_resume_packet(state, state.get("lesson_id"))
        _save_atlas_state(state)
        return {"status": "ok", "exercise": exercise, "learner_context": state.get("learner_context")}
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
        _hydrate_learner_state(
            state,
            user_id="default_user",
            lesson=state.get("current_lesson") or {},
            exercise=state.get("current_exercise") or {},
            result=result,
            topic=state.get("topic"),
            metadata={"error_fingerprint": None},
        )
        state["resume_packet"] = _build_resume_packet(state, state.get("lesson_id"))
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        return {"status": "ok", "result": result, "learner_context": state.get("learner_context")}
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
                    _append_lesson_history(state, next_lesson, state.get("current_exercise") or {})
                    state["resume_packet"] = _build_resume_packet(state, state.get("lesson_id"))
                    _save_atlas_state(state)
                    return {"status": "ok", "lesson": mod["lessons"][next_i]}
                break
        if found:
            break

    return {"status": "ok", "message": "No more lessons in current module"}


@app.post("/api/atlas/back")
async def atlas_back():
    state = _load_atlas_state()
    history = state.get("lesson_history") or []
    if not isinstance(history, list) or len(history) < 2:
        return {"status": "ok", "message": "No previous lesson to return to."}
    history.pop()
    previous = history[-1]
    state["lesson_history"] = history
    state["current_lesson"] = previous.get("lesson") or {}
    state["lesson_id"] = previous.get("lesson_id")
    state["current_exercise"] = previous.get("exercise") or {}
    state["resume_packet"] = _build_resume_packet(state, state.get("lesson_id"))
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {
        "status": "ok",
        "lesson": state.get("current_lesson"),
        "exercise": state.get("current_exercise"),
        "resume_packet": state.get("resume_packet"),
    }


@app.get("/api/atlas/recap")
async def atlas_recap():
    state = _load_atlas_state()
    recap = _build_lesson_recap(state)
    _append_study_aid(state, "recap", recap)
    _save_atlas_state(state)
    return {"status": "ok", "recap": recap}


@app.get("/api/atlas/quiz")
async def atlas_quiz():
    state = _load_atlas_state()
    quiz = _build_lesson_quiz(state)
    _append_study_aid(state, "quiz", quiz)
    _save_atlas_state(state)
    return {"status": "ok", "quiz": quiz}


@app.get("/api/atlas/review")
async def atlas_review():
    state = _load_atlas_state()
    review = _build_lesson_review(state)
    _append_study_aid(state, "review", review)
    _save_atlas_state(state)
    return {"status": "ok", "review": review}


@app.get("/api/atlas/flashcards")
async def atlas_flashcards():
    state = _load_atlas_state()
    flashcards = _build_lesson_flashcards(state)
    _append_study_aid(state, "flashcards", flashcards)
    _save_atlas_state(state)
    return {"status": "ok", "flashcards": flashcards}


@app.get("/api/approvals")
async def get_approvals():
    return _load_approvals()


@app.post("/api/approvals/{record_id}/approve")
async def approve_record_route(record_id: str):
    return _approve_record(record_id)


@app.get("/api/snapshots")
async def get_snapshots():
    return _load_snapshots()


@app.post("/api/snapshots/{snapshot_id}/restore")
async def restore_snapshot_route(snapshot_id: str):
    return _restore_snapshot(snapshot_id)


@app.post("/api/atlas/apply")
async def atlas_apply(body: Dict[str, Any]):
    operation = str(body.get("operation", "")).strip().lower()
    file_path = str(body.get("file_path", "")).strip()
    if operation not in {"create_file", "write_file", "apply_patch", "insert_after"}:
        return {"status": "error", "error": "Unsupported operation"}
    if not file_path:
        return {"status": "error", "error": "file_path is required"}

    payload: Dict[str, Any] = {"file_path": file_path}
    if operation == "apply_patch":
        payload["new_content"] = str(body.get("new_content", ""))
    elif operation == "insert_after":
        payload["anchor"] = str(body.get("anchor", ""))
        payload["content"] = str(body.get("content", ""))
    else:
        payload["content"] = str(body.get("content", ""))

    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        preview = _build_operation_preview(operation, payload)
        approval = _create_approval_record(
            f"atlas-{uuid.uuid4().hex[:8]}",
            agent_id="tutor_agent",
            operation=operation,
            target=file_path,
            preview=preview,
            payload=payload,
            requested_by="user",
        )
        _append_activity(
            f"ATLAS approval requested: {operation}",
            agent_id="tutor_agent",
            kind="atlas_apply",
            details={"file_path": file_path, "approval_id": approval["id"]},
        )
        return {"status": "ok", "operation": operation, "approval": approval, "preview": preview}

    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_file_operation(operation, payload)
    )
    _append_activity(
        f"ATLAS apply operation: {operation}",
        agent_id="tutor_agent",
        kind="atlas_apply",
        details={"file_path": file_path, "result": result},
    )
    return {"status": "ok", "operation": operation, "result": result}


@app.post("/api/atlas/reset")
async def atlas_reset():
    learner_state = load_learner_model("default_user")
    learner_state.update({
        "mastery": {},
        "confidence": {},
        "streak": 0,
        "attempts": 0,
        "error_patterns": {},
        "recent_outcomes": [],
        "memory_graph": {"nodes": [], "edges": [], "last_updated": None},
    })
    learner_state = save_learner_model(learner_state)
    _save_atlas_state({
        "status": "reset",
        "user_id": "default_user",
        "learner_model": learner_state,
        "learner_context": build_learner_context(learner_state),
        "learner_profile": {
            "streak": 0,
            "attempts": 0,
            "recommended_difficulty": "beginner",
            "preferred_pacing": "gentle",
        },
    })
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
    learner_context = state.get("learner_context") or {}
    _hydrate_learner_state(state, user_id="default_user")
    lesson_plan = state.get("lesson_plan") or build_lesson_plan(state, state.get("topic"))
    resume_packet = state.get("resume_packet") or _build_resume_packet(state, state.get("lesson_id"))
    learner_context = {**(state.get("learner_context") or learner_context), "lesson_plan": lesson_plan}

    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.2))

    tutor_prompt = (
        "You are ATLAS Tutor, a practical coding mentor. "
        "Give clear, concise help. Never provide harmful content.\n\n"
        f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
        f"Lesson objectives: {current_lesson.get('objectives', [])}\n"
        f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
        f"Recent submission result: {last_submission}\n"
        f"Adaptive learner context: {json.dumps(learner_context, default=str)[:2500]}\n"
        f"Adaptive lesson plan: {json.dumps(lesson_plan, default=str)[:1500]}\n\n"
        f"Resume packet: {json.dumps(resume_packet, default=str)[:1800]}\n\n"
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
