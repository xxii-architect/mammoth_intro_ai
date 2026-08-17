"""
MammothOS Command Center — FastAPI Server
Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import ast
import asyncio
import csv
import io
import json
import os
import re
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
from fastapi.responses import PlainTextResponse

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
ATLAS_EVALS_FILE = MAMMOTH_DIR / "atlas_evals.json"
AUDIT_LOG_FILE = MAMMOTH_DIR / "audit_log.json"
UI_DIR        = ROOT / "ui" / "mad-architecht-command-center"
VENV_PYTHON   = ROOT / ".venv" / "Scripts" / "python.exe"
VENV_UVICORN  = ROOT / ".venv" / "Scripts" / "uvicorn.exe"
AGENT_ACTIVITY_FILE = MAMMOTH_DIR / "agent_activity.json"
TASKS_FILE = MAMMOTH_DIR / "tasks.json"

for _f in [NOTES_FILE, BUILDLOG_FILE, SALES_FILE, AGENT_ACTIVITY_FILE, TASKS_FILE, SNAPSHOTS_FILE, ATLAS_EVALS_FILE, AUDIT_LOG_FILE]:
    if not _f.exists():
        _f.write_text("[]")

ATLAS_MODULE_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "wilderness-survival",
        "label": "Wilderness Navigation + Survival",
        "topic": "Wilderness navigation survival and safety fundamentals",
        "summary": "Field-ready navigation, shelter, water, and risk management fundamentals.",
        "outcomes": [
            "Map-and-compass orientation with terrain awareness",
            "Shelter, water, and fire decision-making under pressure",
            "Safety-first route planning and emergency signaling basics",
        ],
        "operator_note": "Keep examples practical, safety-first, and grounded in conservative field decisions.",
    },
    {
        "id": "hunting-fishing",
        "label": "Hunting + Fishing",
        "topic": "Hunting and fishing safety ethics and field basics",
        "summary": "Ethical harvest, gear discipline, and field-readiness basics for outdoor food systems.",
        "outcomes": [
            "Safe tool handling and site awareness",
            "Ethical harvest principles and conservation framing",
            "Basic field prep, legal mindset, and risk reduction habits",
        ],
        "operator_note": "Emphasize lawful, ethical, and humane practice over optimization or tactics.",
    },
    {
        "id": "ham-radio",
        "label": "Ham Radio",
        "topic": "Ham radio fundamentals call signs and emergency comms basics",
        "summary": "Introductory radio literacy for disciplined communication and emergency readiness.",
        "outcomes": [
            "Call-sign etiquette and net discipline basics",
            "Frequency, repeater, and simplex communication fundamentals",
            "Emergency message structure and communication logging habits",
        ],
        "operator_note": "Use novice-friendly comms scenarios with disciplined operating habits.",
    },
    {
        "id": "emt-emergency-management",
        "label": "EMT + Emergency Mgmt",
        "topic": "EMT and emergency management triage and incident fundamentals",
        "summary": "Structured emergency response thinking with triage, ICS awareness, and scene safety.",
        "outcomes": [
            "Scene safety, triage priorities, and patient communication basics",
            "Incident command awareness and escalation habits",
            "Documentation-minded response flow under stress",
        ],
        "operator_note": "Stay educational and procedural; do not present as professional medical direction.",
    },
    {
        "id": "horticulture-weather",
        "label": "Horticulture + Weather",
        "topic": "Horticulture botany and weather pattern literacy basics",
        "summary": "Plant care, growth cycles, and weather-aware decision-making for practical stewardship.",
        "outcomes": [
            "Plant structure, soil, and watering fundamentals",
            "Seasonal planning informed by basic weather pattern reading",
            "Observation logs that connect weather signals to plant decisions",
        ],
        "operator_note": "Favor observation, stewardship, and repeatable habits over overconfident predictions.",
    },
]


def _read_json(path: Path, default=None):
    if default is None:
        default = []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _normalize_module_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _serialize_module_track(track: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(track, dict):
        return None
    return {
        "id": str(track.get("id") or "").strip(),
        "label": str(track.get("label") or "").strip(),
        "topic": str(track.get("topic") or "").strip(),
        "summary": str(track.get("summary") or "").strip(),
        "outcomes": [str(item).strip() for item in (track.get("outcomes") or []) if str(item).strip()],
        "operator_note": str(track.get("operator_note") or "").strip(),
    }


def _atlas_module_catalog() -> List[Dict[str, Any]]:
    return [track for track in (_serialize_module_track(item) for item in ATLAS_MODULE_TRACKS) if track]


def _resolve_module_track(module_id: Any = None, topic: Any = None) -> Optional[Dict[str, Any]]:
    normalized_module_id = _normalize_module_key(module_id)
    normalized_topic = _normalize_module_key(topic)

    if normalized_module_id:
        for track in ATLAS_MODULE_TRACKS:
            if track["id"] == normalized_module_id:
                return track

    if normalized_topic:
        for track in ATLAS_MODULE_TRACKS:
            candidates = {
                _normalize_module_key(track.get("id")),
                _normalize_module_key(track.get("label")),
                _normalize_module_key(track.get("topic")),
            }
            if normalized_topic in candidates:
                return track
    return None


def _compose_module_curriculum_topic(requested_topic: str, track: Optional[Dict[str, Any]]) -> str:
    base_topic = str(requested_topic or "").strip()
    if not track:
        return base_topic or "Python basics"
    if not base_topic:
        base_topic = str(track.get("topic") or track.get("label") or "Python basics").strip()
    outcomes = [str(item).strip() for item in (track.get("outcomes") or []) if str(item).strip()]
    emphasis = "; ".join(outcomes[:3])
    return (
        f"{base_topic}. Build a practical beginner-friendly lesson track for {track['label']} "
        f"with safety-aware, real-world scenarios and emphasis on: {emphasis}."
    )


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
    if operation == "atlas_onboard_update":
        onboarding = payload.get("onboarding") if isinstance(payload.get("onboarding"), dict) else {}
        return {
            "summary": "Update ATLAS onboarding profile",
            "target": "atlas/onboarding",
            "experience_level": str(onboarding.get("experience_level") or "unknown"),
            "preferred_pacing": str(onboarding.get("preferred_pacing") or "gentle"),
            "learning_style": str(onboarding.get("learning_style") or "guided"),
        }
    if operation == "atlas_learner_reset":
        return {
            "summary": "Reset ATLAS learner state",
            "target": "atlas/learner",
        }
    if operation == "atlas_session_reset":
        return {
            "summary": "Reset full ATLAS session",
            "target": "atlas/session",
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
    if operation == "atlas_onboard_update":
        onboarding = payload.get("onboarding") if isinstance(payload.get("onboarding"), dict) else {}
        return _apply_atlas_onboarding_update(onboarding)
    if operation == "atlas_learner_reset":
        return _apply_atlas_learner_reset()
    if operation == "atlas_session_reset":
        return _apply_atlas_session_reset()
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
    task_id = str(updated.get("task_id") or "").strip()
    if task_id:
        operation = str(updated.get("operation") or "approval")
        title = f"approval:{operation}"
        result_status = str(result.get("status", "error"))
        _upsert_task(
            task_id,
            title,
            status="completed" if result_status in {"ok", "success"} else "failed",
            agent_id=str(updated.get("agent_id") or ""),
            description=str(updated.get("target") or operation),
            details={"approval_id": record_id, "result_status": result_status},
        )
    _append_activity(
        f"Approval executed: {updated.get('operation', 'unknown')}",
        agent_id=str(updated.get("agent_id") or ""),
        task_id=task_id,
        kind="approval_executed",
        details={"approval_id": record_id, "status": result.get("status", "unknown")},
    )
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
    from mammoth_os.agent_registry import agent_registry, AgentStatus, AGENTS, run_agent as registry_run_agent
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


def _coerce_http_agent_prompt(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("prompt", "message", "query", "task", "goal", "instruction"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""
    if payload is None:
        return ""
    return str(payload).strip()


async def _dispatch_http_agent(agent_label: str, payload: Any) -> Dict[str, Any]:
    prompt = _coerce_http_agent_prompt(payload)
    if not prompt:
        return {"status": "error", "error": "prompt is required"}
    mapping = {"atlas": "tutor", "coding": "coding"}
    runtime_agent = mapping.get(agent_label)
    if runtime_agent is None:
        return {"status": "error", "error": f"unsupported agent label: {agent_label}"}
    if not _agent_registry_ok:
        return {"status": "error", "error": "agent registry unavailable"}

    def _invoke() -> Any:
        return registry_run_agent(runtime_agent, prompt)

    result = await asyncio.get_event_loop().run_in_executor(None, _invoke)
    return {
        "status": "ok",
        "agent": agent_label,
        "runtime_agent": runtime_agent,
        "result": result,
    }


@app.post("/agent/atlas/run")
async def run_atlas_agent_endpoint(payload: Any):
    return await _dispatch_http_agent("atlas", payload)


@app.post("/agent/coding/run")
async def run_coding_agent_endpoint(payload: Any):
    return await _dispatch_http_agent("coding", payload)


@app.post("/agent/shell/run")
async def run_shell_agent_endpoint(payload: Any):
    prompt = _coerce_http_agent_prompt(payload)
    if not prompt:
        return {"status": "error", "error": "command is required"}
    try:
        completed = subprocess.run(prompt, shell=True, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        return {
            "status": "ok",
            "agent": "shell",
            "result": {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "agent": "shell"}


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
    "lesson_curriculum": "curriculum_agent",
    "grade_submission": "tutor_agent",
    "lesson_coaching": "tutor_agent",
    "reasoning_help": "reasoning_agent",
    "debug_failure": "reasoning_agent",
}

_AGENT_ID_TO_RUNTIME = {
    "plant_the_seed_agent": "plant_the_seed",
    "field_ops_agent": "field_ops",
    "market_intel_agent": "market_intel",
    "reflection_agent": "reflection",
    "brand_voice_agent": "brand_voice",
    "research_agent": "research",
    "curriculum_agent": "curriculum",
    "tutor_agent": "tutor",
    "reasoning_agent": "reasoning",
    "coding_agent": "coding",
    "community_engine_agent": "community_engine",
    "custodial_agent": "custodial",
}

_ATLAS_WORKFLOW_AGENT_IDS = {
    "plant_the_seed_agent",
    "research_agent",
    "curriculum_agent",
    "coding_agent",
    "reflection_agent",
    "field_ops_agent",
    "tutor_agent",
    "reasoning_agent",
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
    if profile not in {"atlas", "coding", "balanced", "autonomous"}:
        return "balanced"
    return profile


def _build_plan_steps(objective: str, plan_profile: str = "balanced") -> List[Dict[str, str]]:
    objective = (objective or "").strip()
    lower = objective.lower()
    profile = _normalize_plan_profile(plan_profile)
    include_coding = profile == "coding" or any(tok in lower for tok in ["build", "implement", "code", "patch", "create", "ui", "feature"])
    include_market = profile == "atlas" or any(tok in lower for tok in ["market", "audience", "position", "messaging"])
    include_field_ops = profile == "atlas" or any(tok in lower for tok in ["ops", "operational", "runbook", "checklist", "launch"])
    include_community = profile == "autonomous"
    include_custodial = profile == "autonomous"

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

    if include_community:
        steps.append(
            {
                "id": "community-check",
                "title": "Prepare community-facing update",
                "agent_id": "community_engine_agent",
                "intent": "summarize",
                "prompt": f"Create a short community update and expectation-setting note for: {objective}",
            }
        )

    if include_custodial:
        steps.append(
            {
                "id": "custodial-check",
                "title": "Run maintenance and safety checklist",
                "agent_id": "custodial_agent",
                "intent": "summarize",
                "prompt": f"Provide a maintenance checklist and rollback guard notes before executing: {objective}",
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


def _read_jsonl_records(path: Path, *, limit: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
    except Exception:
        return []
    return records[-limit:]


def _response_preview(response: Any, *, max_len: int = 240) -> str:
    if not isinstance(response, dict):
        return ""
    candidates = []
    result = response.get("result")
    if isinstance(result, dict):
        candidates.append(result)
    candidates.append(response)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in ("output", "preview", "message", "error"):
            value = candidate.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                text = value.strip()
            else:
                text = json.dumps(value, default=str)
            if text:
                return text[:max_len]
    return ""


def _plan_step_artifacts(step_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for step in step_results:
        preview = _response_preview(step.get("response"))
        artifacts.append({
            "id": step.get("id"),
            "title": step.get("title"),
            "agent_id": step.get("agent_id"),
            "status": step.get("status"),
            "preview": preview,
        })
    return artifacts


def _build_plan_synthesis(step_results: List[Dict[str, Any]], *, objective: str, lesson_title: str = "") -> Dict[str, Any]:
    artifacts = _plan_step_artifacts(step_results)
    completed = [step for step in step_results if step.get("status") == "completed"]
    pending = [step for step in step_results if step.get("status") == "pending_approval"]
    failed = [step for step in step_results if step.get("status") == "failed"]
    coding_preview = next((item["preview"] for item in artifacts if item.get("agent_id") == "coding_agent" and item.get("preview")), "")
    coach_preview = next((item["preview"] for item in artifacts if item.get("agent_id") == "reflection_agent" and item.get("preview")), "")
    completed_titles = [str(step.get("title") or "") for step in completed if str(step.get("title") or "").strip()]
    learner_summary_parts = []
    if lesson_title:
        learner_summary_parts.append(f"ATLAS organized a plan for {lesson_title}.")
    else:
        learner_summary_parts.append("ATLAS organized a plan for the current objective.")
    if completed_titles:
        learner_summary_parts.append(f"Completed focus areas: {', '.join(completed_titles[:3])}.")
    if failed:
        learner_summary_parts.append("One or more steps still need intervention before the plan is learner-ready.")
    elif pending:
        learner_summary_parts.append("A coding step is waiting for approval before ATLAS can finish execution.")
    else:
        learner_summary_parts.append("The plan completed successfully and is ready to coach the learner forward.")

    if failed:
        next_action = f"Review the failed step: {failed[0].get('title') or 'unnamed step'}."
    elif pending:
        next_action = f"Approve and run {pending[0].get('title') or 'the pending step'} to continue."
    elif coach_preview:
        next_action = coach_preview[:180]
    elif coding_preview:
        next_action = f"Use the coding brief to implement or validate the exercise: {coding_preview[:160]}"
    else:
        next_action = f"Start with the first checkpoint for: {objective[:160]}"

    checkpoints = [item["preview"] for item in artifacts if item.get("preview")][:4]
    return {
        "learner_summary": " ".join(learner_summary_parts),
        "coding_brief": coding_preview,
        "coach_note": coach_preview,
        "next_action": next_action,
        "checkpoints": checkpoints,
        "artifacts": artifacts,
    }


def _append_plan_history(state: Dict[str, Any], plan: Dict[str, Any]) -> None:
    history = state.get("plan_history") or []
    if not isinstance(history, list):
        history = []
    history.append({
        "plan_id": plan.get("plan_id"),
        "objective": plan.get("objective"),
        "plan_status": plan.get("plan_status"),
        "plan_profile": plan.get("plan_profile"),
        "progress": plan.get("progress"),
        "created_at": plan.get("created_at") or _ts(),
        "summary": ((plan.get("synthesis") or {}).get("learner_summary") or "")[:300],
        "next_action": ((plan.get("synthesis") or {}).get("next_action") or "")[:220],
    })
    state["plan_history"] = history[-12:]


def _load_eval_history() -> List[Dict[str, Any]]:
    history = _read_json(ATLAS_EVALS_FILE, default=[])
    return history if isinstance(history, list) else []


def _load_audit_log() -> List[Dict[str, Any]]:
    history = _read_json(AUDIT_LOG_FILE, default=[])
    return history if isinstance(history, list) else []


def _append_audit_event(*, kind: str, message: str, details: Optional[Dict[str, Any]] = None, source: str = "system", actor: str = "system", tier: Optional[str] = None) -> Dict[str, Any]:
    entries = _load_audit_log()
    entry = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "message": message,
        "source": source,
        "actor": actor,
        "tier": tier or "explorer",
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    if len(entries) > 250:
        entries = entries[-250:]
    _write_json(AUDIT_LOG_FILE, entries)
    return entry


def _audit_entries_to_csv(entries: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "kind", "message", "source", "actor", "tier", "details_json"])
    for entry in entries:
        writer.writerow([
            str(entry.get("id") or ""),
            str(entry.get("created_at") or ""),
            str(entry.get("kind") or ""),
            str(entry.get("message") or ""),
            str(entry.get("source") or ""),
            str(entry.get("actor") or ""),
            str(entry.get("tier") or ""),
            json.dumps(entry.get("details") or {}, ensure_ascii=False),
        ])
    return output.getvalue()


def _build_atlas_observability(state: Dict[str, Any], *, eval_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    eval_entries = eval_history if isinstance(eval_history, list) else _load_eval_history()
    eval_entries = [entry for entry in eval_entries if isinstance(entry, dict)]
    recent_evals = eval_entries[-8:]
    recent_plans = [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-8:]
    recent_outcomes = [item for item in ((state.get("learner_model") or {}).get("recent_outcomes") or []) if isinstance(item, dict)]
    fab_events = [item for item in (state.get("fab_usage_events") or []) if isinstance(item, dict)]
    sandbox_runs = _read_jsonl_records(MAMMOTH_DIR / "sandbox_runs.jsonl", limit=40)
    recent_activity = [item for item in _load_activity_events() if isinstance(item, dict)][-6:]

    attempts = len(recent_outcomes)
    passed_attempts = sum(1 for item in recent_outcomes if bool(item.get("passed")))
    learner_pass_rate = round((passed_attempts / attempts) * 100) if attempts else 0

    eval_total_checks = sum(len(entry.get("checks") or []) for entry in recent_evals)
    eval_passed_checks = sum(int((entry.get("summary") or {}).get("pass_count") or 0) for entry in recent_evals)
    eval_pass_rate = round((eval_passed_checks / eval_total_checks) * 100) if eval_total_checks else 0

    guard_hits = sum(1 for item in fab_events if bool(item.get("guard_triggered")))
    fab_guard_rate = round((guard_hits / len(fab_events)) * 100) if fab_events else 0

    successful_sandbox_runs = 0
    for run in sandbox_runs:
        if "passed" in run:
            successful_sandbox_runs += 1 if bool(run.get("passed")) else 0
        elif "returncode" in run:
            successful_sandbox_runs += 1 if int(run.get("returncode") or 1) == 0 else 0
    sandbox_success_rate = round((successful_sandbox_runs / len(sandbox_runs)) * 100) if sandbox_runs else 0

    latest_eval = recent_evals[-1] if recent_evals else {}
    latest_plan = recent_plans[-1] if recent_plans else {}

    return {
        "metrics": {
            "learner_pass_rate": learner_pass_rate,
            "recent_attempts": attempts,
            "eval_pass_rate": eval_pass_rate,
            "eval_runs": len(recent_evals),
            "plan_runs": len(recent_plans),
            "fab_guard_rate": fab_guard_rate,
            "sandbox_success_rate": sandbox_success_rate,
        },
        "latest_eval": {
            "generated_at": latest_eval.get("generated_at"),
            "pass_count": int((latest_eval.get("summary") or {}).get("pass_count") or 0),
            "fail_count": int((latest_eval.get("summary") or {}).get("fail_count") or 0),
        },
        "latest_plan": {
            "plan_id": latest_plan.get("plan_id"),
            "status": latest_plan.get("plan_status"),
            "profile": latest_plan.get("plan_profile"),
            "created_at": latest_plan.get("created_at"),
        },
        "recent_evals": [
            {
                "generated_at": entry.get("generated_at"),
                "pass_count": int((entry.get("summary") or {}).get("pass_count") or 0),
                "fail_count": int((entry.get("summary") or {}).get("fail_count") or 0),
            }
            for entry in recent_evals
        ],
        "recent_plans": [
            {
                "plan_id": item.get("plan_id"),
                "objective": item.get("objective"),
                "plan_status": item.get("plan_status"),
                "plan_profile": item.get("plan_profile"),
                "created_at": item.get("created_at"),
            }
            for item in recent_plans
        ],
        "recent_activity": [
            {
                "message": item.get("message"),
                "agent_id": item.get("agent_id"),
                "created_at": item.get("created_at"),
            }
            for item in recent_activity
        ],
    }


def _decorate_atlas_state(state: Dict[str, Any]) -> Dict[str, Any]:
    eval_history = _load_eval_history()
    state["eval_history"] = eval_history[-8:]
    state["observability"] = _build_atlas_observability(state, eval_history=eval_history)
    state["available_modules"] = _atlas_module_catalog()
    active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
    if active_track:
        state["active_module"] = _serialize_module_track(active_track)
    return state


async def _execute_plan_steps(
    *,
    plan_id: str,
    steps: List[Dict[str, Any]],
    objective: str,
    temperature: float,
    approval_mode: bool,
    stop_on_failure: bool,
    activity_agent_id: str,
) -> List[Dict[str, Any]]:
    step_results: List[Dict[str, Any]] = []

    for idx, step in enumerate(steps, start=1):
        started_at = _ts()
        _append_activity(
            f"Plan step {idx}/{len(steps)}: {step['title']}",
            agent_id=step["agent_id"],
            task_id=plan_id,
            kind="plan_step_started",
            details={"step": step, "owner": activity_agent_id},
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
            details={"step_id": step["id"], "status": step_status, "duration_ms": duration_ms, "owner": activity_agent_id},
        )

        if step_status == "failed" and stop_on_failure:
            break

    return step_results


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

    step_results = await _execute_plan_steps(
        plan_id=plan_id,
        steps=steps,
        objective=objective,
        temperature=float(temperature),
        approval_mode=approval_mode,
        stop_on_failure=stop_on_failure,
        activity_agent_id="orchestrator",
    )

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


@app.get("/api/autonomous/runs")
async def get_autonomous_runs():
    state = _load_atlas_state()
    recent_runs: List[Dict[str, Any]] = []

    plan_tasks = [
        task for task in _load_tasks()
        if isinstance(task, dict) and (
            str(task.get("id", "")).startswith("plan-")
            or str(task.get("title", "")).strip() == "plan+execute run"
        )
    ]
    for task in plan_tasks[-12:]:
        details = task.get("details") if isinstance(task.get("details"), dict) else {}
        recent_runs.append({
            "run_id": task.get("id"),
            "source": "plan_execute",
            "objective": details.get("objective") or task.get("description") or "",
            "plan_profile": _normalize_plan_profile(details.get("plan_profile")),
            "plan_status": task.get("status") or "unknown",
            "created_at": task.get("created_at") or task.get("updated_at") or "",
            "updated_at": task.get("updated_at") or task.get("created_at") or "",
            "progress": {
                "total": int(details.get("total") or details.get("step_count") or 0),
                "executed": int(details.get("executed") or 0),
                "completed": int(details.get("completed") or 0),
                "pending_approval": int(details.get("pending_approval") or 0),
                "failed": int(details.get("failed") or 0),
            },
        })

    for plan in [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-12:]:
        progress = plan.get("progress") if isinstance(plan.get("progress"), dict) else {}
        recent_runs.append({
            "run_id": plan.get("plan_id"),
            "source": "atlas_plan",
            "objective": plan.get("objective") or "",
            "plan_profile": _normalize_plan_profile(plan.get("plan_profile")),
            "plan_status": plan.get("plan_status") or "unknown",
            "created_at": plan.get("created_at") or "",
            "updated_at": plan.get("created_at") or "",
            "progress": {
                "total": int(progress.get("total") or 0),
                "executed": int(progress.get("executed") or 0),
                "completed": int(progress.get("completed") or 0),
                "pending_approval": int(progress.get("pending_approval") or 0),
                "failed": int(progress.get("failed") or 0),
            },
        })

    recent_runs.sort(key=lambda run: str(run.get("created_at") or ""), reverse=True)
    recent_runs = recent_runs[:20]

    summary = {
        "total_runs": len(recent_runs),
        "completed": sum(1 for run in recent_runs if run.get("plan_status") == "completed"),
        "pending_approval": sum(1 for run in recent_runs if run.get("plan_status") == "pending_approval"),
        "failed": sum(1 for run in recent_runs if run.get("plan_status") == "failed"),
        "latest_run_at": recent_runs[0].get("created_at") if recent_runs else "",
    }

    return {
        "status": "ok",
        "contract_version": "v1",
        "profiles": ["atlas", "coding", "balanced", "autonomous"],
        "summary": summary,
        "runs": recent_runs,
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

    def _is_failure_payload(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("status") == "error":
                return True
            if value.get("passed") is False:
                return True
            result = value.get("result")
            if isinstance(result, dict) and result.get("passed") is False:
                return True
            return any(_is_failure_payload(child) for child in value.values())
        if isinstance(value, list):
            return any(_is_failure_payload(item) for item in value)
        return False

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
            payload_agents = {"plant_the_seed", "market_intel", "reflection", "brand_voice", "community_engine", "tutor", "reasoning"}
            if runtime_agent in payload_agents:
                payload_for_agent = dict(payload) if isinstance(payload, dict) else {}
                if prompt_text and not payload_for_agent.get("topic") and not payload_for_agent.get("prompt") and not payload_for_agent.get("problem"):
                    payload_for_agent["topic"] = prompt_text
                if runtime_agent == "tutor" and prompt_text and not payload_for_agent.get("prompt"):
                    payload_for_agent["prompt"] = prompt_text
                if runtime_agent == "reasoning" and prompt_text and not payload_for_agent.get("problem"):
                    payload_for_agent["problem"] = prompt_text
            elif runtime_agent in {"curriculum", "research", "field_ops", "coding", "custodial"}:
                payload_for_agent = prompt_text or json.dumps(payload)
            else:
                payload_for_agent = prompt_text or json.dumps(payload)

            _think("Dispatching to agent", f"runtime_agent={runtime_agent!r}")
            raw_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: registry_run_agent(runtime_agent, payload_for_agent)
            )
            _think("Agent returned", f"type={type(raw_result).__name__}  preview={str(raw_result)[:120]!r}", "success")
            result = {
                "status": "ok",
                "runtime_agent": runtime_agent,
                "output": raw_result,
            }
            attach_reasoning = runtime_agent == "tutor" and (
                intent == "lesson_coaching" or (intent == "grade_submission" and _is_failure_payload(raw_result))
            )
            if attach_reasoning:
                if _is_failure_payload(raw_result):
                    _think("Tutor failure detected", "Preparing reasoning guidance for the learner", "warning")
                else:
                    _think("Coaching extension", "Attaching Socratic reasoning guidance", "info")
                reasoning_payload = {
                    "problem": prompt_text or "Explain the tutoring failure and offer a micro-lesson.",
                    "context": {
                        "intent": intent,
                        "prompt": prompt_text,
                        "tutor_result": raw_result,
                        "mode": "coach" if intent == "lesson_coaching" else "tutor_hint",
                    },
                    "mode": "coach" if intent == "lesson_coaching" else "tutor_hint",
                }
                reasoning_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: registry_run_agent("reasoning", reasoning_payload)
                )
                _think("Reasoning guidance attached", f"preview={str(reasoning_result)[:120]!r}", "success")
                result["reasoning"] = reasoning_result
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
            state = json.loads(ATLAS_FILE.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return {"status": "no_session", "user_id": "default_user"}
            normalized_history: List[Dict[str, Any]] = []
            for idx, raw in enumerate(state.get("lesson_history") or []):
                entry = _normalize_lesson_history_entry(raw, idx)
                if entry:
                    normalized_history.append(entry)
            state["lesson_history"] = normalized_history[-80:]
            normalized_aids: List[Dict[str, Any]] = []
            for raw in state.get("study_aids") or []:
                aid = _normalize_study_aid_entry(raw)
                if aid:
                    normalized_aids.append(aid)
            state["study_aids"] = normalized_aids[-120:]
            _sync_resume_packet(state)
            return state
        except Exception:
            pass
    return {"status": "no_session", "user_id": "default_user"}


def _save_atlas_state(state: Dict[str, Any]):
    ATLAS_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _reset_learner_model_state(user_id: str = "default_user") -> Dict[str, Any]:
    learner_state = load_learner_model(user_id)
    learner_state.update({
        "mastery": {},
        "confidence": {},
        "streak": 0,
        "attempts": 0,
        "error_patterns": {},
        "recent_outcomes": [],
        "memory_graph": {"nodes": [], "edges": [], "last_updated": None},
    })
    return save_learner_model(learner_state)


def _apply_atlas_onboarding_update(onboarding: Dict[str, Any]) -> Dict[str, Any]:
    state = _load_atlas_state()
    learner_state = set_onboarding_profile(state, user_id="default_user", onboarding=onboarding)
    _save_atlas_state(state)
    _append_audit_event(
        kind="atlas_onboard",
        message="ATLAS onboarding profile updated",
        details={"profile": onboarding.get("profile") or onboarding.get("goal") or "unknown"},
        source="atlas",
        actor="learner",
    )
    return {
        "status": "ok",
        "learner_model": learner_state,
        "learner_context": state.get("learner_context"),
        "learner_profile": state.get("learner_profile"),
    }


def _apply_atlas_learner_reset() -> Dict[str, Any]:
    learner_state = _reset_learner_model_state("default_user")
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


def _apply_atlas_session_reset() -> Dict[str, Any]:
    learner_state = _reset_learner_model_state("default_user")
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    replaced = False
    normalized_history: List[Dict[str, Any]] = []
    for idx, raw in enumerate(history):
        normalized = _normalize_lesson_history_entry(raw, idx)
        if not normalized:
            continue
        if normalized["lesson_id"] == entry["lesson_id"]:
            normalized = {
                **normalized,
                "lesson": lesson or normalized.get("lesson") or {},
                "exercise": exercise or normalized.get("exercise") or {},
                "updated_at": entry["updated_at"],
            }
            replaced = True
        normalized_history.append(normalized)
    if not replaced:
        normalized_history.append(_normalize_lesson_history_entry(entry, len(normalized_history)) or entry)
    state["lesson_history"] = normalized_history[-80:]


def _record_submission_on_history(state: Dict[str, Any], submission: Dict[str, Any]) -> None:
    lesson_id = str(state.get("lesson_id") or "").strip()
    if not lesson_id:
        return
    summary = _summarize_prior_work(state, lesson_id)
    normalized_history: List[Dict[str, Any]] = []
    for idx, raw in enumerate(state.get("lesson_history") or []):
        entry = _normalize_lesson_history_entry(raw, idx)
        if not entry:
            continue
        if entry["lesson_id"] == lesson_id:
            entry["last_submission"] = submission
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            entry["summary"] = summary
        normalized_history.append(entry)
    state["lesson_history"] = normalized_history[-80:]


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


def _normalize_lesson_history_entry(raw: Any, index: int = 0) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    lesson = raw.get("lesson") if isinstance(raw.get("lesson"), dict) else {}
    exercise = raw.get("exercise") if isinstance(raw.get("exercise"), dict) else {}
    lesson_id = str(
        raw.get("lesson_id")
        or lesson.get("lesson_id")
        or exercise.get("lesson_id")
        or ""
    ).strip()
    if not lesson_id:
        return None
    created_at = raw.get("created_at") or raw.get("updated_at") or datetime.now(timezone.utc).isoformat()
    summary = str(raw.get("summary") or raw.get("resume_summary") or "").strip()
    return {
        "lesson_id": lesson_id,
        "lesson": lesson,
        "exercise": exercise,
        "created_at": created_at,
        "updated_at": raw.get("updated_at") or created_at,
        "summary": summary,
        "last_submission": raw.get("last_submission") if isinstance(raw.get("last_submission"), dict) else None,
        "study_aid_count": int(raw.get("study_aid_count") or 0),
        "resume_packet": raw.get("resume_packet") if isinstance(raw.get("resume_packet"), dict) else None,
        "sequence": int(raw.get("sequence") or index),
    }


def _normalize_study_aid_entry(raw: Any, lesson_id: str = "", lesson_title: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    data = raw.get("data")
    aid_type = str(raw.get("type") or "unknown").strip() or "unknown"
    normalized_lesson_id = str(raw.get("lesson_id") or lesson_id or "").strip()
    if isinstance(data, dict) and aid_type == "flashcards" and "cards" in data and isinstance(data.get("cards"), list):
        data = data.get("cards")
    elif isinstance(data, str) and aid_type in {"flashcards", "quiz"}:
        data = [data]
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "type": aid_type,
        "lesson_id": normalized_lesson_id,
        "lesson_title": str(raw.get("lesson_title") or lesson_title or "").strip(),
        "data": data,
        "created_at": raw.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }


def _find_lesson_snapshot(state: Dict[str, Any], lesson_id: Optional[str]) -> Dict[str, Any]:
    target_id = str(lesson_id or state.get("lesson_id") or "").strip()
    current_lesson = state.get("current_lesson") if isinstance(state.get("current_lesson"), dict) else {}
    if target_id and str(current_lesson.get("lesson_id") or "").strip() == target_id:
        return current_lesson

    history = state.get("lesson_history") or []
    if isinstance(history, list):
        for raw in reversed(history):
            entry = _normalize_lesson_history_entry(raw)
            if entry and entry["lesson_id"] == target_id:
                return entry.get("lesson") or {}

    curriculum = state.get("curriculum") if isinstance(state.get("curriculum"), dict) else {}
    for module in curriculum.get("modules") or []:
        if not isinstance(module, dict):
            continue
        for lesson in module.get("lessons") or []:
            if not isinstance(lesson, dict):
                continue
            if str(lesson.get("lesson_id") or "").strip() == target_id:
                return lesson
    return current_lesson if current_lesson else {}


def _matching_history_entry(state: Dict[str, Any], lesson_id: Optional[str]) -> Optional[Dict[str, Any]]:
    target_id = str(lesson_id or "").strip()
    history = state.get("lesson_history") or []
    if not isinstance(history, list):
        return None
    for raw in reversed(history):
        entry = _normalize_lesson_history_entry(raw)
        if entry and entry["lesson_id"] == target_id:
            return entry
    return None


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

    lesson = _find_lesson_snapshot(state, lesson_id)
    objectives = [str(item).strip().lower() for item in (lesson.get("objectives") or []) if str(item).strip()]
    keywords = [
        str(lesson_id or "").strip().lower(),
        str(lesson.get("title") or lesson.get("lesson_title") or "").strip().lower(),
        str(state.get("topic") or "").strip().lower(),
    ]
    keywords = [k for k in keywords if k] + objectives[:2]

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
    lesson = _find_lesson_snapshot(state, lesson_id)
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        aids = []

    cards: List[Dict[str, str]] = []
    for item in reversed(aids):
        normalized = _normalize_study_aid_entry(
            item,
            str(lesson_id or ""),
            str(lesson.get("title") or lesson.get("lesson_title") or ""),
        )
        if not normalized:
            continue
        if str(normalized.get("lesson_id") or "") != str(lesson_id or ""):
            continue
        aid_type = str(normalized.get("type") or "")
        data = normalized.get("data")
        if aid_type == "flashcards" and isinstance(data, list):
            for card in data:
                if isinstance(card, str) and card.strip():
                    cards.append({
                        "front": card.strip(),
                        "back": "Recall the underlying concept, then verify it against your latest lesson work.",
                    })
                    continue
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
    if deduped:
        return deduped
    fallback_state = {
        **state,
        "current_lesson": lesson,
        "current_exercise": state.get("current_exercise") or {},
    }
    return _build_lesson_flashcards(fallback_state)[:4]
    
    

def _summarize_prior_work(state: Dict[str, Any], lesson_id: Optional[str]) -> str:
    entry = _matching_history_entry(state, lesson_id)
    lesson = _find_lesson_snapshot(state, lesson_id)
    if entry and entry.get("summary"):
        return str(entry["summary"])
    submission = entry.get("last_submission") if entry else None
    if not isinstance(submission, dict):
        submission = state.get("last_submission") if str(state.get("lesson_id") or "") == str(lesson_id or "") else {}
    exercise = (entry or {}).get("exercise") if entry else {}
    objective_count = len([item for item in (lesson.get("objectives") or []) if str(item).strip()])
    prompt = str((exercise or {}).get("prompt") or "").strip()
    hint = str((submission or {}).get("hint") or (submission or {}).get("error") or "").strip()
    if submission:
        status_line = "last attempt passed" if bool(submission.get("passed")) else "last attempt still needed work"
    else:
        status_line = "you explored this lesson earlier"
    detail = f"Prompt focus: {prompt[:140]}" if prompt else ""
    feedback = f"Last feedback: {hint[:160]}" if hint else ""
    title = lesson.get("title") or lesson.get("lesson_title") or (lesson_id or "this lesson")
    pieces = [
        f"Returning to {title}.",
        f"You previously worked on {max(1, objective_count)} objective(s), and {status_line}.",
        detail,
        feedback,
    ]
    return " ".join(piece for piece in pieces if piece).strip()


def _sync_resume_packet(state: Dict[str, Any], lesson_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    target_lesson_id = str(lesson_id or state.get("lesson_id") or "").strip()
    if not target_lesson_id:
        state["resume_packet"] = None
        return None
    packet = _build_resume_packet(state, target_lesson_id)
    state["resume_packet"] = packet
    entry = _matching_history_entry(state, target_lesson_id)
    if entry:
        entry["resume_packet"] = packet
        entry["summary"] = packet.get("prior_work_summary") or packet.get("summary") or ""
        entry["study_aid_count"] = int(packet.get("resource_counts", {}).get("total") or 0)
        normalized_history: List[Dict[str, Any]] = []
        for idx, raw in enumerate(state.get("lesson_history") or []):
            normalized = _normalize_lesson_history_entry(raw, idx)
            if not normalized:
                continue
            if normalized["lesson_id"] == target_lesson_id:
                normalized = {**normalized, **entry}
            normalized_history.append(normalized)
        state["lesson_history"] = normalized_history[-80:]
    return packet


def _build_resume_packet(state: Dict[str, Any], lesson_id: Optional[str]) -> Dict[str, Any]:
    lesson = _find_lesson_snapshot(state, lesson_id)
    history_entry = _matching_history_entry(state, lesson_id)
    submission = history_entry.get("last_submission") if history_entry and isinstance(history_entry.get("last_submission"), dict) else {}
    if not submission and str(state.get("lesson_id") or "") == str(lesson_id or ""):
        submission = state.get("last_submission") or {}
    objectives = [str(item) for item in (lesson.get("objectives") or []) if str(item).strip()]
    notes = _matching_notes_for_lesson(state, lesson_id)
    flashcards = _flashcards_for_lesson(state, lesson_id)
    prior_work_summary = _summarize_prior_work(state, lesson_id)
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
        "prior_work_summary": prior_work_summary,
        "objectives": objectives[:4],
        "notes": notes[:5],
        "flashcards": flashcards[:8],
        "resource_counts": {
            "notes": len(notes[:5]),
            "flashcards": len(flashcards[:8]),
            "total": len(notes[:5]) + len(flashcards[:8]),
        },
        "latest_activity_at": (history_entry or {}).get("updated_at") or (history_entry or {}).get("created_at") or state.get("updated_at"),
        "has_resources": bool(notes or flashcards),
    }


def _build_submit_adaptation(learner_context: Dict[str, Any], submission_result: Dict[str, Any]) -> Dict[str, Any]:
    coaching = learner_context.get("adaptive_coaching") if isinstance(learner_context, dict) else {}
    if not isinstance(coaching, dict):
        coaching = {}
    hint_depth = str(coaching.get("hint_depth") or "guided")
    challenge_level = str(coaching.get("challenge_level") or "balanced")
    remediation_needed = bool(coaching.get("remediation_needed"))
    passed = bool((submission_result or {}).get("passed"))
    mastery_delta = learner_context.get("latest_mastery_delta")
    confidence_delta = learner_context.get("latest_confidence_delta")

    if passed and challenge_level == "stretch":
        next_step = "You passed. Increase challenge: add edge-case tests and refactor for clarity."
    elif passed:
        next_step = "You passed. Lock in understanding by explaining your approach in one paragraph."
    elif hint_depth == "foundational":
        next_step = "Break this into 2-3 tiny steps and validate each with a quick print/assert check."
    elif hint_depth == "guided":
        next_step = "Fix one failing branch first, then re-run tests before adding new logic."
    else:
        next_step = "Try a minimal patch focused only on the failing assertion, then re-test."

    return {
        "hint_depth": hint_depth,
        "challenge_level": challenge_level,
        "coaching_tone": str(coaching.get("coaching_tone") or "step_by_step"),
        "remediation_needed": remediation_needed,
        "passed": passed,
        "mastery_delta": mastery_delta,
        "confidence_delta": confidence_delta,
        "next_step": next_step,
    }


def _is_answer_seeking_request(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    patterns = [
        r"\bjust give (me )?the answer\b",
        r"\bwrite (the )?solution for me\b",
        r"\bsolve (this|it) for me\b",
        r"\bfull answer only\b",
        r"\bno explanation\b",
        r"\bexact answer\b",
        r"\bjust the code\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _regenerate_current_exercise(state: Dict[str, Any], *, reason: str) -> Optional[Dict[str, Any]]:
    lesson = state.get("current_lesson") or {}
    if not isinstance(lesson, dict) or not lesson:
        return None
    from mammoth_os.exercise_generator import generate_exercises_for_lesson
    generated = generate_exercises_for_lesson(lesson, count=1)
    if not generated:
        return None
    previous = state.get("current_exercise") or {}
    next_exercise = generated[0]
    state["current_exercise"] = next_exercise
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["regenerated_exercise"] = {
        "reason": reason,
        "created_at": state["updated_at"],
        "previous_title": previous.get("title"),
        "next_title": next_exercise.get("title"),
    }
    return next_exercise


def _append_fab_usage_event(
    state: Dict[str, Any],
    *,
    mode: str,
    page_context: Dict[str, Any],
    guard_triggered: bool,
) -> None:
    events = state.get("fab_usage_events") or []
    if not isinstance(events, list):
        events = []
    events.append({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
        "guard_triggered": guard_triggered,
        "has_lesson_context": bool(page_context.get("lesson")),
    })
    state["fab_usage_events"] = events[-200:]


def _run_atlas_evals(state: Dict[str, Any]) -> Dict[str, Any]:
    eval_state = {
        **state,
        "current_lesson": dict(state.get("current_lesson") or {}),
        "current_exercise": dict(state.get("current_exercise") or {}),
        "lesson_id": str(state.get("lesson_id") or "lesson-1"),
        "topic": state.get("topic") or "Python basics",
        "lesson_history": [
            {
                "lesson_id": str(state.get("lesson_id") or "lesson-1"),
                "lesson": dict(state.get("current_lesson") or {}),
                "exercise": dict(state.get("current_exercise") or {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    onboarding_payload = {
        "experience_level": "intermediate",
        "preferred_pacing": "steady",
        "learning_style": "guided",
        "goals": "Build reliably",
        "focus_areas": "debugging, planning",
    }
    learner_state = set_onboarding_profile(eval_state, user_id="default_user", onboarding=onboarding_payload)
    onboarding_ok = bool(learner_state.get("onboarding") or {})

    failure_result = {
        "passed": False,
        "hint": "Add a return statement and validate the function signature.",
        "error": "AssertionError: expected 3",
    }
    learner_state = update_learner_model(
        "default_user",
        lesson=eval_state.get("current_lesson") or {},
        exercise=eval_state.get("current_exercise") or {},
        result=failure_result,
        topic=eval_state.get("topic"),
        metadata={"eval_run": True},
    )
    learner_context = build_learner_context(learner_state)
    adaptive_feedback = _build_submit_adaptation(learner_context, failure_result)
    adaptation_ok = bool(adaptive_feedback.get("next_step"))

    resume_packet = _build_resume_packet(eval_state, eval_state.get("lesson_id"))
    continuity_ok = bool(resume_packet.get("summary"))

    checks = [
        {
            "name": "onboarding_profile",
            "status": "pass" if onboarding_ok else "fail",
            "detail": "Onboarding profile persisted and exposed through the learner model.",
        },
        {
            "name": "adaptive_feedback",
            "status": "pass" if adaptation_ok else "fail",
            "detail": adaptive_feedback.get("next_step") or "Adaptive feedback did not produce a coaching step.",
        },
        {
            "name": "resume_continuity",
            "status": "pass" if continuity_ok else "fail",
            "detail": resume_packet.get("summary") or "Resume packet could not be built.",
        },
    ]
    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "summary": {
            "pass_count": sum(1 for item in checks if item["status"] == "pass"),
            "fail_count": sum(1 for item in checks if item["status"] != "pass"),
        },
    }


def _build_atlas_plan_steps(state: Dict[str, Any], plan_profile: str = "coding") -> List[Dict[str, Any]]:
    lesson = state.get("current_lesson") or {}
    exercise = state.get("current_exercise") or {}
    learner_context = state.get("learner_context") or {}
    module_track = state.get("active_module") or _serialize_module_track(_resolve_module_track(state.get("module_id"), state.get("topic"))) or {}
    topic = str(state.get("topic") or lesson.get("title") or lesson.get("lesson_title") or "current lesson").strip()
    prompt = str(exercise.get("prompt") or "").strip()
    objective = prompt or f"Complete the {topic} lesson with a clear plan and safe next steps."
    profile = _normalize_plan_profile(plan_profile)
    difficulty = str(learner_context.get("recommended_difficulty") or "beginner")
    weakest = [str(item.get("concept") or "").replace("-", " ") for item in (learner_context.get("weakest_concepts") or []) if isinstance(item, dict)]
    weakest_summary = ", ".join([item for item in weakest[:3] if item]) or "the current lesson objective"
    steps: List[Dict[str, Any]] = [
        {
            "id": "atlas-curriculum",
            "title": "Align the lesson to the active module",
            "agent_id": "curriculum_agent",
            "intent": "lesson_curriculum",
            "prompt": (
                f"Generate a concise curriculum framing for {topic}. "
                f"Module: {module_track.get('label') or state.get('module_id') or 'current track'}. "
                f"Objective: {objective}"
            ),
        },
        {
            "id": "atlas-clarify",
            "title": "Clarify the lesson objective",
            "agent_id": "plant_the_seed_agent",
            "intent": "plant_seed",
            "prompt": f"Turn this lesson objective into a concise learning plan for a {difficulty} learner: {objective}",
        },
        {
            "id": "atlas-research",
            "title": "Map constraints and pitfalls",
            "agent_id": "research_agent",
            "intent": "research_curriculum",
            "prompt": f"Summarize the likely constraints and pitfalls for this lesson objective, especially around {weakest_summary}: {objective}",
        },
        {
            "id": "atlas-build",
            "title": "Draft a concrete build plan",
            "agent_id": "coding_agent",
            "intent": "summarize",
            "prompt": f"Draft a short implementation plan, lightweight code sketch guidance, and verification checklist for: {objective}",
        },
        {
            "id": "atlas-coach",
            "title": "Translate the plan into coaching checkpoints",
            "agent_id": "tutor_agent",
            "intent": "lesson_coaching",
            "prompt": (
                f"Create learner checkpoints, a reflection question, and a safe next action for this lesson. "
                f"Topic: {topic}. Objective: {objective}"
            ),
        },
    ]

    if profile in {"atlas", "balanced", "autonomous"}:
        steps.append(
            {
                "id": "atlas-operations",
                "title": "Prepare execution safeguards",
                "agent_id": "field_ops_agent",
                "intent": "field_ops",
                "prompt": f"Create a short execution checklist to keep this lesson safe, testable, and non-cheaty: {objective}",
            }
        )

    if profile == "autonomous":
        steps.extend(
            [
                {
                    "id": "atlas-community",
                    "title": "Create stakeholder update",
                    "agent_id": "community_engine_agent",
                    "intent": "summarize",
                    "prompt": f"Draft a short progress update and expectation-setting note for this lesson objective: {objective}",
                },
                {
                    "id": "atlas-custodial",
                    "title": "Add maintenance + rollback checkpoints",
                    "agent_id": "custodial_agent",
                    "intent": "summarize",
                    "prompt": f"Generate maintenance checks and rollback checkpoints before shipping this lesson work: {objective}",
                },
            ]
        )

    return steps


@app.get("/api/atlas/status")
async def atlas_status():
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id="default_user")
    _sync_resume_packet(state)
    return _decorate_atlas_state(state)


@app.get("/api/atlas/modules")
async def atlas_modules():
    state = _load_atlas_state()
    active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
    return {
        "status": "ok",
        "modules": _atlas_module_catalog(),
        "active_module": _serialize_module_track(active_track),
    }


@app.get("/api/atlas/learner")
async def atlas_learner():
    state = _load_atlas_state()
    learner_state = _hydrate_learner_state(state, user_id="default_user")
    return {"status": "ok", "learner_model": learner_state, "learner_context": state.get("learner_context")}


@app.post("/api/atlas/onboard")
async def atlas_onboard(body: Dict[str, Any]):
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-onboard-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_onboard_update", {"onboarding": body})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_onboard_update",
            target="atlas/onboarding",
            preview=preview,
            payload={"onboarding": body},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_onboard_update",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS onboarding profile update pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS onboarding update queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_onboarding_update(body)


@app.post("/api/atlas/learner/reset")
async def atlas_learner_reset(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-learner-reset-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_learner_reset", {})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_learner_reset",
            target="atlas/learner",
            preview=preview,
            payload={},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_learner_reset",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS learner reset pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS learner reset queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_learner_reset()


@app.post("/api/atlas/lesson")
async def atlas_lesson(body: Dict[str, Any]):
    requested_topic = str(body.get("topic") or "").strip()
    module_track = _resolve_module_track(body.get("module_id"), requested_topic)
    topic = requested_topic or str((module_track or {}).get("topic") or "Python basics")
    curriculum_topic = _compose_module_curriculum_topic(topic, module_track)
    try:
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession(user_id="default_user")
        state = _load_atlas_state()
        learner_context = state.get("learner_context") or {}
        if not learner_context:
            _hydrate_learner_state(state, user_id="default_user")
            learner_context = state.get("learner_context") or {}
        lesson_plan = build_lesson_plan(state, topic)
        if module_track:
            lesson_plan["module_track"] = _serialize_module_track(module_track)
            lesson_plan["curriculum_topic"] = curriculum_topic
        learner_context = {**learner_context, "lesson_plan": lesson_plan}
        if module_track:
            learner_context["module_track"] = _serialize_module_track(module_track)
        difficulty = str(lesson_plan.get("difficulty") or learner_context.get("recommended_difficulty") or "beginner").strip().lower() or "beginner"
        exercise = await asyncio.get_event_loop().run_in_executor(
            None, lambda: session.start_lesson(curriculum_topic, difficulty=difficulty, learner_context=learner_context)
        )
        state.update({
            "status":           "active",
            "topic":            topic,
            "curriculum_topic": curriculum_topic,
            "current_exercise": exercise,
            "curriculum":       session.curriculum,
            "current_lesson":   session.current_lesson,
            "curriculum_id":    session._curriculum_id,
            "lesson_id":        session._lesson_id,
            "lesson_plan":      lesson_plan,
            "module_id":        (module_track or {}).get("id"),
            "active_module":    _serialize_module_track(module_track),
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        })
        _hydrate_learner_state(state, user_id="default_user")
        _append_lesson_history(state, session.current_lesson or {}, exercise or {})
        _sync_resume_packet(state, state.get("lesson_id"))
        _save_atlas_state(state)
        _append_audit_event(
            kind="atlas_lesson",
            message="ATLAS lesson started",
            details={"topic": topic, "difficulty": difficulty, "module_id": (module_track or {}).get("id")},
            source="atlas",
            actor="learner",
        )
        return {
            "status": "ok",
            "exercise": exercise,
            "learner_context": state.get("learner_context"),
            "active_module": _serialize_module_track(module_track),
            "curriculum_topic": curriculum_topic,
        }
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
        learner_context = state.get("learner_context") or {}
        adaptive_feedback = _build_submit_adaptation(learner_context, result)
        _record_submission_on_history(state, result)
        regenerated_exercise = None
        if (
            bool(body.get("regenerate_on_fail"))
            and not bool(result.get("passed"))
            and adaptive_feedback.get("remediation_needed")
        ):
            regenerated_exercise = _regenerate_current_exercise(
                state,
                reason="remediation_after_failed_submission",
            )
        _sync_resume_packet(state, state.get("lesson_id"))
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        _append_audit_event(
            kind="atlas_submit",
            message="ATLAS submission evaluated",
            details={"passed": bool(result.get("passed")), "score": result.get("score")},
            source="atlas",
            actor="learner",
        )
        return {
            "status": "ok",
            "result": result,
            "learner_context": state.get("learner_context"),
            "adaptive_feedback": adaptive_feedback,
            "current_exercise": state.get("current_exercise"),
            "regenerated_exercise": regenerated_exercise,
        }
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
                    _sync_resume_packet(state, state.get("lesson_id"))
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
    if isinstance(previous.get("last_submission"), dict):
        state["last_submission"] = previous.get("last_submission")
    _sync_resume_packet(state, state.get("lesson_id"))
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


@app.post("/api/atlas/plan")
async def atlas_plan(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id="default_user")
    body = body or {}
    plan_profile = _normalize_plan_profile(body.get("plan_profile") or "coding")
    approval_mode = bool(body.get("approval_mode", False))
    steps = _build_atlas_plan_steps(state, plan_profile)
    plan_id = f"atlas-plan-{uuid.uuid4().hex[:8]}"
    objective = str((state.get("current_exercise") or {}).get("prompt") or state.get("topic") or "Current lesson")
    step_results = await _execute_plan_steps(
        plan_id=plan_id,
        steps=steps,
        objective=objective,
        temperature=0.3,
        approval_mode=approval_mode,
        stop_on_failure=True,
        activity_agent_id="tutor_agent",
    )

    completed_count = sum(1 for step in step_results if step["status"] == "completed")
    failed_count = sum(1 for step in step_results if step["status"] == "failed")
    pending_count = sum(1 for step in step_results if step["status"] == "pending_approval")
    total_count = len(step_results)
    plan_status = "completed" if failed_count == 0 and pending_count == 0 else "pending_approval" if pending_count > 0 else "failed"
    synthesis = _build_plan_synthesis(
        step_results,
        objective=objective,
        lesson_title=str((state.get("current_lesson") or {}).get("title") or (state.get("current_lesson") or {}).get("lesson_title") or ""),
    )
    plan = {
        "plan_id": plan_id,
        "objective": objective,
        "plan_profile": plan_profile,
        "plan_status": plan_status,
        "progress": {
            "total": total_count,
            "executed": total_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
        "plan_steps": step_results,
        "synthesis": synthesis,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state["active_plan"] = plan
    _append_plan_history(state, plan)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_activity(
        "ATLAS tutor plan generated",
        agent_id="tutor_agent",
        task_id=plan["plan_id"],
        kind="atlas_plan_generated",
        details={"plan_status": plan_status, "step_count": total_count, "plan_profile": plan_profile},
    )
    _append_audit_event(
        kind="atlas_plan",
        message="ATLAS plan generated",
        details={"plan_id": plan_id, "plan_profile": plan_profile, "plan_status": plan_status},
        source="atlas",
        actor="system",
    )
    _save_atlas_state(state)
    return {"status": "ok", "plan": plan, "plan_history": state.get("plan_history", []), "observability": _build_atlas_observability(state)}


@app.post("/api/atlas/evals")
async def atlas_evals(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    evaluation = _run_atlas_evals(state)
    history = _load_eval_history()
    history.append(evaluation)
    if len(history) > 20:
        history = history[-20:]
    _write_json(ATLAS_EVALS_FILE, history)
    _append_audit_event(
        kind="atlas_eval",
        message="ATLAS eval run completed",
        details={"pass_count": int((evaluation.get("summary") or {}).get("pass_count") or 0), "fail_count": int((evaluation.get("summary") or {}).get("fail_count") or 0)},
        source="atlas",
        actor="system",
    )
    return {"status": "ok", "evaluation": evaluation, "history": history, "observability": _build_atlas_observability(state, eval_history=history)}


@app.post("/api/atlas/regenerate")
async def atlas_regenerate(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    reason = "manual_regeneration"
    if isinstance(body, dict):
        reason = str(body.get("reason") or reason)
    exercise = _regenerate_current_exercise(state, reason=reason)
    if not exercise:
        return {"status": "error", "error": "No active lesson available for regeneration."}
    _append_lesson_history(state, state.get("current_lesson") or {}, exercise or {})
    _sync_resume_packet(state, state.get("lesson_id"))
    _save_atlas_state(state)
    return {
        "status": "ok",
        "exercise": exercise,
        "reason": reason,
        "learner_context": state.get("learner_context"),
    }


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
async def atlas_reset(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-reset-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_session_reset", {})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_session_reset",
            target="atlas/session",
            preview=preview,
            payload={},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_session_reset",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS session reset pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS session reset queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_session_reset()


@app.post("/api/atlas/chat")
async def atlas_chat(body: Dict[str, Any]):
    message = str(body.get("message", "")).strip()
    if not message:
        return {"status": "error", "error": "message is required"}

    state = _load_atlas_state()
    mode = str(body.get("mode") or "tutor").strip().lower() or "tutor"
    if mode in {"assistant", "general", "chat"}:
        mode = "assistant"
    elif mode not in {"tutor", "build"}:
        mode = "tutor"
    strict_guard = bool(body.get("strict_guard", True))
    regenerate_on_guard = bool(body.get("regenerate_on_guard"))
    page_context = body.get("page_context") if isinstance(body.get("page_context"), dict) else {}
    current_lesson = state.get("current_lesson") or {}
    current_exercise = state.get("current_exercise") or {}
    last_submission = state.get("last_submission") or {}
    learner_context = state.get("learner_context") or {}
    _hydrate_learner_state(state, user_id="default_user")
    lesson_plan = state.get("lesson_plan") or build_lesson_plan(state, state.get("topic"))
    resume_packet = state.get("resume_packet") or _build_resume_packet(state, state.get("lesson_id"))
    learner_context = {**(state.get("learner_context") or learner_context), "lesson_plan": lesson_plan}
    has_active_exercise = bool(current_exercise and current_exercise.get("prompt"))
    guard_triggered = mode in {"tutor", "build"} and strict_guard and has_active_exercise and _is_answer_seeking_request(message)
    _sync_resume_packet(state, state.get("lesson_id"))

    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.2))

    history_key = "assistant_chat_history" if mode == "assistant" else "chat_history"
    history = state.get(history_key) or []
    if not isinstance(history, list):
        history = []
    history.append({
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
    })

    if guard_triggered:
        regenerated_exercise = None
        if regenerate_on_guard:
            regenerated_exercise = _regenerate_current_exercise(
                state,
                reason="anti_cheat_guard_triggered",
            )
        guard_reply = (
            "I can't provide direct answer dumps for an active exercise. "
            "I can coach you step-by-step or generate a fresh parallel exercise."
        )
        if regenerated_exercise:
            guard_reply += "\n\n✅ I generated a new exercise variant so you can keep learning without answer leakage."
        history.append({
            "role": "assistant",
            "message": guard_reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adapter": "policy-guard",
            "model": "policy-guard",
            "guard_triggered": True,
        })
        state[history_key] = history[-60:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_fab_usage_event(
            state,
            mode=mode,
            page_context=page_context,
            guard_triggered=True,
        )
        _save_atlas_state(state)
        return {
            "status": "ok",
            "reply": guard_reply,
            "adapter": "policy-guard",
            "model": "policy-guard",
            "chat_history": state[history_key],
            "guard_triggered": True,
            "regenerated_exercise": regenerated_exercise,
            "current_exercise": state.get("current_exercise"),
        }

    if mode == "assistant":
        tutor_prompt = (
            "You are MammothOS Assistant, a natural-language AI partner for building, planning, and learning. "
            "Be conversational, practical, and concise. Never provide harmful content.\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1600]}\n\n"
            f"User message: {message}\n\n"
            "If the user asks for lesson-specific coaching, you can optionally use this context:\n"
            f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
            f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
            f"Recent submission result: {last_submission}\n\n"
            "Respond naturally like a normal AI chat assistant. Do not force lesson framing unless the user asks for it."
        )
    else:
        tutor_prompt = (
            "You are ATLAS Tutor, a practical coding mentor. "
            "Give clear, concise help. Never provide harmful content.\n\n"
            f"Interaction mode: {mode}\n"
            f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
            f"Lesson objectives: {current_lesson.get('objectives', [])}\n"
            f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
            f"Recent submission result: {last_submission}\n"
            f"Adaptive learner context: {json.dumps(learner_context, default=str)[:2500]}\n"
            f"Adaptive lesson plan: {json.dumps(lesson_plan, default=str)[:1500]}\n\n"
            f"Resume packet: {json.dumps(resume_packet, default=str)[:1800]}\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1600]}\n\n"
            f"Student message: {message}\n\n"
            "Policy: do not provide direct final answers for active exercises. Use hints and checks.\n"
            "If mode is 'build', include a short implementation plan plus one safe next action.\n"
            "Respond with: 1) diagnosis, 2) next concrete step, 3) short example when useful."
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

    history.append({
        "role": "assistant",
        "message": llm_reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter": active_adapter,
        "model": active_model,
        "mode": mode,
    })
    state[history_key] = history[-60:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_fab_usage_event(
        state,
        mode=mode,
        page_context=page_context,
        guard_triggered=False,
    )
    _save_atlas_state(state)

    return {
        "status": "ok",
        "reply": llm_reply,
        "adapter": active_adapter,
        "model": active_model,
        "chat_history": state[history_key],
        "guard_triggered": False,
        "mode": mode,
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
    fields = body.get("fields", {})
    if not isinstance(fields, dict):
        fields = {}
    entry = {
        "id":          str(uuid.uuid4()),
        "title":       body.get("title", "") or str(fields.get("primary_task") or ""),
        "description": body.get("description", "") or str(fields.get("session_goal") or ""),
        "tags":        body.get("tags", []),
        "command":     body.get("command", ""),
        "project":     body.get("project", "") or str(fields.get("project") or ""),
        "phase":       body.get("phase", "") or str(fields.get("phase") or ""),
        "month":       body.get("month", "") or str(fields.get("month") or ""),
        "status":      body.get("status", "") or str(fields.get("goal_outcome") or ""),
        "fields":      fields,
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

def _normalize_module_status(raw_status: Any) -> str:
    if hasattr(raw_status, "value"):
        raw_status = raw_status.value
    if isinstance(raw_status, str):
        raw_status = raw_status.strip().upper()
    else:
        raw_status = ""
    mapping = {
        "ACTIVE": "active",
        "READY": "ready",
        "IDLE": "ready",
        "LOADING": "loading",
        "ERROR": "error",
        "SHUTDOWN": "disabled",
        "DISABLED": "disabled",
    }
    return mapping.get(str(raw_status), "ready")


def _workflow_state_for_agent(agent_id: str) -> Dict[str, Any]:
    normalized_id = str(agent_id or "").strip()
    agent_runtime_map = globals().get("AGENTS", {})
    routed = normalized_id in _AGENT_ID_TO_RUNTIME or normalized_id in agent_runtime_map
    atlas_routed = normalized_id in _ATLAS_WORKFLOW_AGENT_IDS
    return {
        "workflow_ready": routed or atlas_routed,
        "workflow_stage": "autonomous" if atlas_routed else "routed" if routed else "registered",
        "workflow_path": "atlas_lesson" if atlas_routed else "plan_execute" if routed else "manual",
    }


def _agent_source_path(agent_id: str) -> Path:
    return ROOT / "src" / "mammoth_os" / "agents" / f"{agent_id}.py"


def _parse_iso_datetime(raw_value: Any) -> Optional[datetime]:
    if isinstance(raw_value, datetime):
        if raw_value.tzinfo is None:
            return raw_value.replace(tzinfo=timezone.utc)
        return raw_value.astimezone(timezone.utc)
    if not isinstance(raw_value, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_agent_keys(agent_id: Any) -> List[str]:
    normalized = _normalize_module_key(agent_id)
    if not normalized:
        return []
    keys = {normalized}
    if normalized.endswith("-agent"):
        keys.add(normalized[: -len("-agent")])
    return [item for item in keys if item]


def _build_activity_index() -> Dict[str, Dict[str, Any]]:
    latest_by_key: Dict[str, Dict[str, Any]] = {}
    for entry in _load_activity_events():
        if not isinstance(entry, dict):
            continue
        agent_id = entry.get("agent_id")
        if not agent_id:
            continue
        created_at = _parse_iso_datetime(entry.get("created_at"))
        if created_at is None:
            continue
        event = {
            "created_at": created_at,
            "created_at_iso": created_at.isoformat(),
            "kind": str(entry.get("kind") or "event"),
            "message": str(entry.get("message") or "").strip(),
        }
        for key in _canonical_agent_keys(agent_id):
            previous = latest_by_key.get(key)
            if not previous or created_at > previous["created_at"]:
                latest_by_key[key] = event
    return latest_by_key


def _module_observability_snapshot(module_id: str, status: str, *, manifest: Any = None, activity_index: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    activity_index = activity_index or {}

    latest_activity: Optional[Dict[str, Any]] = None
    for key in _canonical_agent_keys(module_id):
        candidate = activity_index.get(key)
        if candidate and (latest_activity is None or candidate["created_at"] > latest_activity["created_at"]):
            latest_activity = candidate

    heartbeat_dt = _parse_iso_datetime(getattr(manifest, "last_heartbeat", None))
    metadata = getattr(manifest, "metadata", {}) if manifest else {}
    if not isinstance(metadata, dict):
        metadata = {}
    last_run_dt = _parse_iso_datetime(metadata.get("last_run_at"))

    activity_age_seconds = int((now - latest_activity["created_at"]).total_seconds()) if latest_activity else None
    heartbeat_age_seconds = int((now - heartbeat_dt).total_seconds()) if heartbeat_dt else None
    has_recent_activity = activity_age_seconds is not None and activity_age_seconds <= 180
    has_recent_heartbeat = (
        heartbeat_age_seconds is not None
        and heartbeat_age_seconds <= 180
        and (last_run_dt is not None or latest_activity is not None)
    )
    observed_active = has_recent_activity or has_recent_heartbeat

    effective_status = status
    if status == "ready" and observed_active:
        effective_status = "active"

    return {
        "status": effective_status,
        "observed_active": observed_active,
        "last_activity_at": latest_activity["created_at_iso"] if latest_activity else "",
        "last_activity_kind": latest_activity["kind"] if latest_activity else "",
        "last_activity_message": latest_activity["message"] if latest_activity else "",
        "activity_age_seconds": activity_age_seconds,
        "last_heartbeat_at": heartbeat_dt.isoformat() if heartbeat_dt else "",
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "last_run_at": last_run_dt.isoformat() if last_run_dt else "",
    }


def _agent_quality_snapshot(agent_id: str) -> Dict[str, Any]:
    source_path = _agent_source_path(agent_id)
    if not source_path.exists():
        return {}

    try:
        text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "quality_score": 20,
            "quality_tier": "error",
            "quality_findings": [f"Could not read source: {exc}"],
            "interface_mode": "unknown",
        }

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "quality_score": 10,
            "quality_tier": "error",
            "quality_findings": [f"Syntax issue at line {exc.lineno}"],
            "interface_mode": "unknown",
        }

    class_node = next(
        (
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.lower().endswith("agent")
        ),
        None,
    )
    if not class_node:
        return {
            "quality_score": 25,
            "quality_tier": "prototype",
            "quality_findings": ["No agent class was discovered in the file."],
            "interface_mode": "unknown",
        }

    method_nodes = [node for node in class_node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    method_names = {node.name for node in method_nodes}
    run_node = next((node for node in method_nodes if node.name == "run"), None)
    inherits_base_agent = any(
        (isinstance(base, ast.Name) and base.id == "BaseAgent")
        or (isinstance(base, ast.Attribute) and base.attr == "BaseAgent")
        for base in class_node.bases
    )

    score = 92
    findings: List[str] = []
    interface_mode = "async" if isinstance(run_node, ast.AsyncFunctionDef) else "sync" if run_node else "specialized"
    lowered = text.lower()
    placeholder_markers = [
        marker for marker in ("implement later", "placeholder", "todo", "deeper logic later")
        if marker in lowered
    ]

    if not inherits_base_agent:
        score -= 12
        findings.append("Does not inherit BaseAgent.")
    if "run" not in method_names and "accept_submission" not in method_names:
        score -= 20
        findings.append("No standard workflow entrypoint was found.")
    if placeholder_markers:
        score -= min(24, 8 * len(placeholder_markers))
        findings.append("Contains placeholder-oriented logic markers.")
    if len(method_names) <= 2:
        score -= 8
        findings.append("Agent surface area is still narrow.")
    if len(text.splitlines()) < 40:
        score -= 6
        findings.append("Implementation is still lightweight.")
    if "accept_submission" in method_names and run_node:
        interface_mode = "hybrid"

    score = max(10, min(100, score))
    if score >= 88:
        tier = "top-tier"
    elif score >= 75:
        tier = "strong"
    elif score >= 60:
        tier = "developing"
    else:
        tier = "prototype"

    return {
        "quality_score": score,
        "quality_tier": tier,
        "quality_findings": findings[:2],
        "interface_mode": interface_mode,
        "source_file": str(source_path.relative_to(ROOT)),
    }


_STATIC_MODULES = [
    {"id": "coding_agent",      "name": "CodingAgent",      "version": "v1.2.0", "status": "active",   "description": "Code generation, refactor, review"},
    {"id": "field_ops_agent",   "name": "FieldOpsAgent",    "version": "v0.9.1", "status": "active",   "description": "Planting, irrigation, field data"},
    {"id": "research_agent",    "name": "ResearchAgent",    "version": "v0.8.3", "status": "active",   "description": "Market intel, curriculum research"},
    {"id": "memory_engine",     "name": "MemoryEngine",     "version": "v0.8.0", "status": "active",   "description": "Long-term context & session memory"},
    {"id": "atlas_session",     "name": "ATLASSession",     "version": "v0.5.0", "status": "ready",     "description": "Progress tracking & subsystem status"},
    {"id": "plant_seed_agent",  "name": "PlantSeedAgent",   "version": "v0.6.2", "status": "ready",     "description": "Seed sourcing, planting schedules"},
    {"id": "market_intel_agent","name": "MarketIntelAgent", "version": "v0.3.0", "status": "ready",     "description": "Price feeds, market analysis"},
    {"id": "cortex_router",     "name": "CortexRouter",     "version": "v1.0.0", "status": "active",   "description": "Intent-based routing layer"},
    {"id": "engine_registry",   "name": "EngineRegistry",   "version": "v1.0.0", "status": "active",   "description": "Discovers and registers engine classes"},
]


@app.get("/api/modules")
async def get_modules():
    module_map: Dict[str, Dict[str, Any]] = {}
    manifest_map: Dict[str, Any] = {}
    for item in _STATIC_MODULES:
        module = dict(item)
        workflow = _workflow_state_for_agent(module["id"])
        module.update(workflow)
        module_map[module["id"]] = module

    if _agent_registry_ok:
        try:
            manifests = await agent_registry.list_agents()
        except Exception:
            manifests = []
        for manifest in manifests:
            agent_id = str(getattr(manifest, "agent_id", "") or "").strip()
            if not agent_id:
                continue
            workflow = _workflow_state_for_agent(agent_id)
            module = module_map.get(agent_id, {
                "id": agent_id,
                "name": getattr(manifest, "name", agent_id),
                "version": getattr(manifest, "version", "v1.0.0"),
                "status": "ready",
                "description": "Registered agent",
            })
            module.update({
                "id": agent_id,
                "name": getattr(manifest, "name", module.get("name", agent_id)),
                "version": getattr(manifest, "version", module.get("version", "v1.0.0")),
                "status": _normalize_module_status(getattr(manifest, "status", None)),
                "description": module.get("description") or "Registered agent",
                "capabilities": getattr(manifest, "capabilities", []),
                "level": getattr(manifest, "level", 1),
                "endpoint": getattr(manifest, "endpoint", ""),
                "source": "registry",
            })
            manifest_map[agent_id] = manifest
            module.update(_agent_quality_snapshot(agent_id))
            module.update(workflow)
            module_map[agent_id] = module

    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            mid = f.stem
            if mid in module_map:
                continue
            workflow = _workflow_state_for_agent(mid)
            module_map[mid] = {
                "id": mid,
                "name": "".join(w.title() for w in mid.split("_")),
                "version": "v1.0.0",
                "status": "ready",
                "description": f"Agent: {mid}",
                "source": "discovered",
                **workflow,
                **_agent_quality_snapshot(mid),
            }

    activity_index = _build_activity_index()
    for module in module_map.values():
        module_id = str(module.get("id") or "")
        status = str(module.get("status") or "ready")
        module.update(
            _module_observability_snapshot(
                module_id,
                status,
                manifest=manifest_map.get(module_id),
                activity_index=activity_index,
            )
        )

    return list(module_map.values())



# ─────────────────────────────────────────────────────────────────────────────
# /api/terminal/exec  (HTTP fallback — returns full output at once)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/terminal/exec")
async def terminal_exec(body: Dict[str, Any]):
    cmd = str(body.get("cmd", "")).strip()
    if not cmd:
        return {"stdout": "", "stderr": "No command provided.", "exit_code": 1}
    if not _is_allowed(cmd):
        _append_audit_event(
            kind="terminal_exec_denied",
            message="Terminal command blocked by allow-list",
            details={"cmd": cmd},
            source="terminal",
            actor="user",
        )
        return {
            "stdout": "",
            "stderr": f"Not in allow-list: {cmd}\nAllowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}",
            "exit_code": 1,
        }
    result = await _execute_terminal_command(cmd)
    _append_audit_event(
        kind="terminal_exec",
        message="Terminal command executed",
        details={"cmd": cmd, "exit_code": result["exit_code"]},
        source="terminal",
        actor="user",
    )
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


@app.get("/api/audit")
async def get_audit_log():
    entries = _load_audit_log()
    return {"status": "ok", "entries": entries[-80:]}


@app.get("/api/audit/export")
async def export_audit_log_csv():
    entries = _load_audit_log()
    csv_payload = _audit_entries_to_csv(entries[-250:])
    return PlainTextResponse(
        content=csv_payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="mammoth-audit-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.csv"'},
    )


@app.post("/api/audit")
async def append_audit_log(body: Dict[str, Any]):
    kind = str(body.get("kind") or "generic").strip() or "generic"
    message = str(body.get("message") or f"{kind} event").strip() or f"{kind} event"
    details = body.get("details") if isinstance(body.get("details"), dict) else {}
    source = str(body.get("source") or "system").strip() or "system"
    actor = str(body.get("actor") or "system").strip() or "system"
    tier = str(body.get("tier") or "").strip() or None
    entry = _append_audit_event(kind=kind, message=message, details=details, source=source, actor=actor, tier=tier)
    return {"status": "ok", "entry": entry}


@app.get("/api/entitlements")
async def get_entitlements():
    """Return the current user's tier and feature entitlements."""
    state = _load_atlas_state()
    tier = str(state.get("tier") or "explorer").strip().lower()
    if tier not in {"explorer", "pro", "enterprise"}:
        tier = "explorer"
    base_features = {
        "atlas_tutor": True,
        "adaptive_pacing": True,
        "lesson_resume": True,
        "flashcards_quiz": True,
        "basic_evals": True,
        "local_storage": True,
    }
    pro_features = {
        "multi_agent_orchestration": tier in {"pro", "enterprise"},
        "plan_execute_all_profiles": tier in {"pro", "enterprise"},
        "supabase_sync": tier in {"pro", "enterprise"},
        "eval_history_dashboard": tier in {"pro", "enterprise"},
        "audit_log_export": tier in {"pro", "enterprise"},
        "coding_agent_approval": tier in {"pro", "enterprise"},
    }
    enterprise_features = {
        "team_dashboards": tier == "enterprise",
        "custom_curriculum": tier == "enterprise",
        "lms_integration": tier == "enterprise",
        "white_label": tier == "enterprise",
    }
    return {
        "status": "ok",
        "tier": tier,
        "features": {**base_features, **pro_features, **enterprise_features},
        "upgrade_cta": "pricing" if tier == "explorer" else None,
    }


@app.post("/api/entitlements/tier")
async def set_tier(body: Dict[str, Any]):
    """Set the user's tier (for testing / admin use)."""
    tier = str(body.get("tier") or "explorer").strip().lower()
    if tier not in {"explorer", "pro", "enterprise"}:
        return {"status": "error", "error": "Invalid tier. Use: explorer, pro, enterprise"}
    state = _load_atlas_state()
    state["tier"] = tier
    state["tier_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="tier_change",
        message="Entitlement tier updated",
        details={"tier": tier},
        source="entitlements",
        actor="user",
        tier=tier,
    )
    return {"status": "ok", "tier": tier}


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
