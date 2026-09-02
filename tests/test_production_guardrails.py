import asyncio
import json

import api_server


def test_health_exposes_runtime_snapshot(monkeypatch):
    monkeypatch.setattr(api_server, "_read_env_vars", lambda: {"DEEPSEEK_API_KEY": "x", "OPENAI_API_KEY": "y"})
    monkeypatch.setattr(
        api_server,
        "_models_snapshot",
        lambda: {
            "active_adapter": "openai",
            "active_model": "gpt-4o-mini",
            "ollama_base_url": "http://localhost:11434",
            "ollama_running": False,
            "openai_key_present": True,
            "local_models_installed": [],
            "models": [],
        },
    )
    monkeypatch.setattr(api_server, "_port_open", lambda port: port in {8000, 5173})

    health = asyncio.run(api_server.get_health())

    assert health["runtime"]["state"] == "ready"
    assert health["summary"]["healthy_services"] >= 2
    assert "React Dev Server (5174)" in health["summary"]["yellow_services"]
    assert health["health_gate"]["status"] in {"ready", "blocked"}


def test_release_readiness_scorecard_uses_runtime_modules_and_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas_state.json")
    monkeypatch.setattr(api_server, "_read_env_vars", lambda: {})
    monkeypatch.setattr(
        api_server,
        "_models_snapshot",
        lambda: {
            "active_adapter": "local",
            "active_model": "local-adapter",
            "ollama_base_url": "http://localhost:11434",
            "ollama_running": False,
            "openai_key_present": False,
            "local_models_installed": [],
            "models": [],
        },
    )
    monkeypatch.setattr(api_server, "_port_open", lambda port: port == 8000)
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [{"id": "evt-1", "message": "runtime ready", "kind": "event"}])
    monkeypatch.setattr(api_server, "_load_tasks", lambda: [{"id": "task-1", "title": "Verify runtime", "status": "queued"}])
    monkeypatch.setattr(api_server, "_load_approvals", lambda: [])
    monkeypatch.setattr(api_server, "_load_audit_log", lambda: [{"id": "audit-1", "message": "audit ready"}])
    monkeypatch.setattr(api_server, "_load_eval_history", lambda: [])

    async def fake_modules():
        return [
            {"id": "atlas_chat", "name": "ATLAS Chat", "quality_score": 60, "quality_tier": "developing", "quality_findings": ["Needs better error surfaces."]},
            {"id": "command_center", "name": "Command Center", "quality_score": 75, "quality_tier": "strong", "quality_findings": ["Chat UX improved."]},
            {"id": "coding_agent", "name": "CodingAgent", "quality_score": 88, "quality_tier": "top-tier", "quality_findings": ["Stable plan/execute path."]},
        ]

    monkeypatch.setattr(api_server, "get_modules", fake_modules)

    snapshot = asyncio.run(api_server.get_release_readiness())

    assert snapshot["status"] == "ok"
    assert snapshot["score"] < 8
    assert snapshot["release_gate"]["passed"] is False
    assert snapshot["release_gate"]["status"] == "blocked"
    assert snapshot["runtime"]["state"] == "degraded"
    assert snapshot["lowest_rated"][0]["name"] == "ATLAS Chat"
    assert any("Provider resilience" in blocker["title"] for blocker in snapshot["blockers"])
    assert snapshot["eval_gate"]["status"] == "blocked"
    assert snapshot["account"]["profile_complete"] is False


def test_release_readiness_requires_eval_history_even_when_runtime_is_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas_state.json")
    monkeypatch.setattr(api_server, "_load_eval_history", lambda: [])

    async def fake_health():
        return {
            "services": [
                {"label": "Backend API", "status": "green", "up": True},
                {"label": "React Dev Server (5173)", "status": "green", "up": True},
            ],
            "summary": {"healthy_services": 2, "total_services": 2, "red_services": [], "yellow_services": []},
            "runtime": {
                "state": "ready",
                "degraded_mode": False,
                "active_adapter": "openai",
                "active_model": "gpt-4o-mini",
                "providers": [
                    {"provider": "openai", "status": "ready", "available": True},
                    {"provider": "local", "status": "ready", "available": True},
                ],
                "available_providers": ["openai", "local"],
                "fallback_chain": ["deepseek", "openai", "ollama", "local"],
                "summary": {"openai_key_present": True, "deepseek_key_present": True, "ollama_running": False},
            },
            "health_gate": {"passed": True, "status": "ready", "blockers": []},
        }

    async def fake_modules():
        return [
            {"id": "atlas_chat", "name": "ATLAS Chat", "quality_score": 92, "quality_tier": "top-tier", "quality_findings": []},
            {"id": "command_center", "name": "Command Center", "quality_score": 90, "quality_tier": "top-tier", "quality_findings": []},
            {"id": "coding_agent", "name": "CodingAgent", "quality_score": 94, "quality_tier": "top-tier", "quality_findings": []},
        ]

    async def fake_entitlements():
        return {"plan": "pro", "usage": {"requests": 12, "request_limit": 100, "tokens": 1000, "token_limit": 10000}}

    async def fake_account():
        return {"auth_mode": "local_operator", "session_scope": "workspace_local", "profile_complete": True}

    monkeypatch.setattr(api_server, "get_health", fake_health)
    monkeypatch.setattr(api_server, "get_modules", fake_modules)
    monkeypatch.setattr(api_server, "get_entitlements", fake_entitlements)
    monkeypatch.setattr(api_server, "get_account_profile", fake_account)

    snapshot = asyncio.run(api_server.get_release_readiness())

    assert snapshot["score"] > 8
    assert snapshot["release_gate"]["passed"] is False
    assert snapshot["eval_gate"]["passed"] is False
    assert snapshot["eval_gate"]["eval_runs"] == 0
    assert any("ATLAS eval moat" in blocker["title"] for blocker in snapshot["blockers"])


def test_diagnostics_export_includes_release_readiness(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas_state.json")
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [])
    monkeypatch.setattr(api_server, "_load_tasks", lambda: [])
    monkeypatch.setattr(api_server, "_load_approvals", lambda: [])
    monkeypatch.setattr(api_server, "_load_audit_log", lambda: [])

    async def fake_release_snapshot():
        return {
            "status": "ok",
            "score": 7.9,
            "tier": "near-ready",
            "scores": {"runtime": 8.0, "modules": 7.8, "observability": 8.0},
            "summary": {"healthy_services": 2, "total_services": 2, "cloud_providers_ready": 1, "non_local_providers_ready": 1},
            "runtime": {"state": "ready"},
            "lowest_rated": [],
            "blockers": [],
            "strengths": [],
            "account": {"auth_mode": "local_operator", "session_scope": "workspace_local", "profile_complete": False},
            "recommended_next_action": "Continue incremental upgrade work on the next lowest-rated lane.",
        }

    monkeypatch.setattr(api_server, "_release_readiness_snapshot", fake_release_snapshot)
    monkeypatch.setattr(api_server, "get_health", fake_release_snapshot)
    monkeypatch.setattr(api_server, "get_entitlements", fake_release_snapshot)
    monkeypatch.setattr(api_server, "get_account_profile", fake_release_snapshot)

    response = asyncio.run(api_server.export_diagnostics_snapshot())
    payload = json.loads(response.body.decode())

    assert payload["status"] == "ok"
    assert payload["release_readiness"]["score"] == 7.9
    assert "generated_at" in payload
