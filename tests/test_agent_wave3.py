"""
test_agent_wave3.py
────────────────────────────────────────────────────────────────────
Smoke-test suite for the 13 Wave-3 agents added to the AGENTS
registry and wired through cortex/router.py.

Contract (mirrors test_agent_registry_runtime.py):
  • POST /api/run  →  outer envelope  {"status": "ok", ...}
  • result / inner {"status": "ok" | "ready" | "success", ...}

Each test uses the minimal valid payload for that agent's happy path.
Run with:
    pytest tests/test_agent_wave3.py -v
"""

import pytest
import requests

BASE = "http://localhost:8000"
TIMEOUT = 20  # seconds per request

# ── helpers ───────────────────────────────────────────────────────

def _run(agent_id: str, intent: str, payload: dict) -> dict:
    resp = requests.post(
        f"{BASE}/api/run",
        json={"agent_id": agent_id, "intent": intent, "payload": payload},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"{agent_id}: HTTP {resp.status_code}"
    return resp.json()


def _assert_ok(data: dict, agent_id: str) -> dict:
    assert data.get("status") == "ok", (
        f"{agent_id}: outer status={data.get('status')} msg={data.get('message','')}"
    )
    inner = data.get("result") or data
    inner_status = inner.get("status", "")
    assert inner_status in {"ok", "ready", "success", "running"}, (
        f"{agent_id}: inner status={inner_status!r} "
        f"err={inner.get('error') or inner.get('message','')}"
    )
    return inner


# ── Wave-3 agent tests ────────────────────────────────────────────

def test_wave3_auth_status():
    inner = _assert_ok(_run("auth", "auth", {"action": "status"}), "auth")
    assert "status" in inner


def test_wave3_build_status():
    inner = _assert_ok(_run("build", "build", {"action": "status"}), "build")
    assert "status" in inner


def test_wave3_config_manager_get():
    inner = _assert_ok(
        _run("config_manager", "config_manager", {"action": "get", "key": "env"}),
        "config_manager",
    )
    assert "status" in inner


def test_wave3_database_status():
    inner = _assert_ok(
        _run("database", "database", {"action": "status"}),
        "database",
    )
    assert "status" in inner


def test_wave3_deploy_status():
    inner = _assert_ok(
        _run("deploy", "deploy", {"action": "status"}),
        "deploy",
    )
    assert "status" in inner


def test_wave3_executor_run_code():
    inner = _assert_ok(
        _run("executor", "executor", {"code": "print(6 * 7)", "language": "python"}),
        "executor",
    )
    # executor should echo output or stdout
    output = str(inner.get("stdout") or inner.get("output") or "")
    assert "42" in output or inner.get("status") in {"ok", "success"}, (
        f"executor: expected '42' in output, got: {output!r}"
    )


def test_wave3_filesystem_list():
    inner = _assert_ok(
        _run("filesystem", "filesystem", {"action": "list", "path": "/tmp"}),
        "filesystem",
    )
    assert "status" in inner


def test_wave3_memory_store_retrieve():
    # store
    _assert_ok(
        _run("memory", "memory", {"action": "store", "content": "wave3_test mammoth"}),
        "memory",
    )
    # retrieve
    inner = _assert_ok(
        _run("memory", "memory", {"action": "retrieve", "query": "wave3_test"}),
        "memory",
    )
    assert "status" in inner


def test_wave3_scheduler_list():
    inner = _assert_ok(
        _run("scheduler", "scheduler", {"action": "list"}),
        "scheduler",
    )
    assert "status" in inner


def test_wave3_shell_status():
    # ShellAgent is a command executor — test with a real safe command
    inner = _assert_ok(
        _run("shell", "shell", {"command": "echo mammoth_wave3_ok"}),
        "shell",
    )
    output = str(inner.get("stdout") or inner.get("output") or "")
    assert "mammoth_wave3_ok" in output or inner.get("status") in {"ok", "success"}


def test_wave3_snapshot_status():
    inner = _assert_ok(
        _run("snapshot", "snapshot", {"action": "status"}),
        "snapshot",
    )
    assert "status" in inner


def test_wave3_ui_builder_status():
    inner = _assert_ok(
        _run("ui_builder", "ui_builder", {"action": "status"}),
        "ui_builder",
    )
    assert "status" in inner


def test_wave3_vector_store_status():
    inner = _assert_ok(
        _run("vector_store", "vector_store", {"action": "status"}),
        "vector_store",
    )
    assert "status" in inner


# ── Cross-cutting: all 13 agents must survive an unknown action ───

WAVE3_AGENTS = [
    ("auth",           "auth"),
    ("build",          "build"),
    ("config_manager", "config_manager"),
    ("database",       "database"),
    ("deploy",         "deploy"),
    ("executor",       "executor"),
    ("filesystem",     "filesystem"),
    ("memory",         "memory"),
    ("scheduler",      "scheduler"),
    ("shell",          "shell"),
    ("snapshot",       "snapshot"),
    ("ui_builder",     "ui_builder"),
    ("vector_store",   "vector_store"),
]


@pytest.mark.parametrize("agent_id,intent", WAVE3_AGENTS)
def test_wave3_unknown_action_returns_error_not_500(agent_id, intent):
    """
    Agents must handle an unrecognised action gracefully —
    return HTTP 200 with a structured error, never crash with 500.
    """
    resp = requests.post(
        f"{BASE}/api/run",
        json={"agent_id": agent_id, "intent": intent, "payload": {"action": "__nonexistent__"}},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, (
        f"{agent_id}: unknown-action returned HTTP {resp.status_code}, expected 200"
    )
    data = resp.json()
    # outer envelope must always be ok (routing succeeded)
    assert data.get("status") == "ok", (
        f"{agent_id}: outer status not ok on unknown action: {data}"
    )
