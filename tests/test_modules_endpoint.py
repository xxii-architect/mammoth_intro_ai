import asyncio
from datetime import datetime, timezone

import api_server


class DummyManifest:
    def __init__(self, agent_id, name, version, status, capabilities=None, level=1, endpoint="internal://demo", last_heartbeat=None, metadata=None):
        self.agent_id = agent_id
        self.name = name
        self.version = version
        self.status = status
        self.capabilities = capabilities or []
        self.level = level
        self.endpoint = endpoint
        self.last_heartbeat = last_heartbeat or datetime.now(timezone.utc)
        self.metadata = metadata or {}


class DummyRegistry:
    async def list_agents(self):
        return [
            DummyManifest("coding_agent", "CodingAgent", "v1.2.0", "ACTIVE", capabilities=["code"], level=2),
            DummyManifest("tutor_agent", "TutorAgent", "v1.0.0", "IDLE", capabilities=["coach"], level=2),
            DummyManifest("atlas_session", "ATLASSession", "v0.5.0", "IDLE", capabilities=["state"], level=1),
        ]


def test_get_modules_uses_registry_status_and_workflow_state(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "agent_registry", DummyRegistry())
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [])

    modules = asyncio.run(api_server.get_modules())
    by_id = {module["id"]: module for module in modules}

    assert by_id["coding_agent"]["status"] == "active"
    assert by_id["coding_agent"]["workflow_ready"] is True
    assert by_id["coding_agent"]["workflow_stage"] == "autonomous"
    assert by_id["coding_agent"]["quality_tier"] in {"strong", "top-tier", "developing"}
    assert by_id["coding_agent"]["source"] == "registry"
    assert by_id["tutor_agent"]["workflow_ready"] is True
    assert by_id["tutor_agent"]["workflow_path"] == "atlas_lesson"
    assert by_id["tutor_agent"]["quality_tier"] in {"strong", "top-tier"}
    assert by_id["atlas_session"]["status"] == "ready"
    assert by_id["atlas_session"]["workflow_ready"] is False
    assert "last_activity_at" in by_id["coding_agent"]
    assert "last_heartbeat_at" in by_id["coding_agent"]


def test_get_modules_promotes_recent_activity_to_active(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "agent_registry", DummyRegistry())
    now_iso = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        api_server,
        "_load_activity_events",
        lambda: [
            {
                "id": "a1",
                "agent_id": "tutor_agent",
                "kind": "task_completed",
                "message": "Completed tutor cycle",
                "created_at": now_iso,
            }
        ],
    )

    modules = asyncio.run(api_server.get_modules())
    by_id = {module["id"]: module for module in modules}

    assert by_id["tutor_agent"]["status"] == "active"
    assert by_id["tutor_agent"]["observed_active"] is True
    assert by_id["tutor_agent"]["last_activity_kind"] == "task_completed"
    assert by_id["tutor_agent"]["last_activity_message"] == "Completed tutor cycle"


def test_get_modules_promotes_recent_heartbeat_when_agent_ran(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    class HeartbeatRegistry:
        async def list_agents(self):
            return [
                DummyManifest(
                    "curriculum_agent",
                    "CurriculumAgent",
                    "v1.0.0",
                    "IDLE",
                    capabilities=["curriculum"],
                    last_heartbeat=datetime.now(timezone.utc),
                    metadata={"last_run_at": datetime.now(timezone.utc).isoformat()},
                )
            ]

    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "agent_registry", HeartbeatRegistry())
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [])

    modules = asyncio.run(api_server.get_modules())
    by_id = {module["id"]: module for module in modules}

    assert by_id["curriculum_agent"]["status"] == "active"
    assert by_id["curriculum_agent"]["observed_active"] is True
    assert by_id["curriculum_agent"]["last_heartbeat_at"]


def test_unregistered_catalog_entries_do_not_claim_runtime_readiness(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "agent_registry", DummyRegistry())
    monkeypatch.setattr(api_server, "_load_activity_events", lambda: [])
    modules = {item["id"]: item for item in asyncio.run(api_server.get_modules())}
    assert modules["field_ops_agent"]["status"] == "unknown"
    assert modules["repo_context_engine"]["status"] == "integrated"
    assert api_server._normalize_module_status(None) == "unknown"


def test_registry_failure_is_explicit(monkeypatch):
    class UnavailableRegistry:
        async def list_agents(self):
            raise RuntimeError("Database unavailable")

    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "agent_registry", UnavailableRegistry())
    assert asyncio.run(api_server.get_modules()).status_code == 503


def test_mcp_catalog_uses_runtime_bridge_not_launcher_as_health(monkeypatch, tmp_path):
    from mammoth_os.agent_loop.mcp_client import MCPBridge, MCPServerConfig

    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr("shutil.which", lambda command: str(tmp_path / command))
    bridge = MCPBridge(tmp_path, [MCPServerConfig(id="browser", label="Browser", command="npx", tools=["read", "git_push"], category="browser")])
    monkeypatch.setattr(api_server, "_AGENT_MCP", bridge)
    monkeypatch.setattr(api_server, "_load_mcp_index", lambda: {"servers": [{"id": "browser", "config": "browser", "enabled": True}]})
    monkeypatch.setattr(api_server, "_load_mcp_server_config", lambda path: {"command": "npx"})
    result = asyncio.run(api_server.get_mcp_servers())["servers"][0]
    assert result["status"] == "configured"
    assert result["available"] is True
    assert result["health_verified"] is False
    assert result["tools"] == ["read"]


def test_mcp_runtime_state_distinguishes_context_connection_and_setup(monkeypatch, tmp_path):
    from mammoth_os.agent_loop.mcp_client import MCPBridge, MCPServerConfig
    from mammoth_os.agent_loop.tools import ToolContext

    server = MCPServerConfig(id="repo", label="Repo", command="npx", category="repo")
    bridge = MCPBridge(tmp_path, [server])
    monkeypatch.setattr("shutil.which", lambda command: command)
    no_repo = ToolContext(user_id="owner", is_admin=True)
    assert bridge.runtime_state(server, no_repo)["status"] == "needs_context"
    ctx = ToolContext(user_id="owner", is_admin=True, repo_root=tmp_path, repo_scope="platform")
    assert bridge.runtime_state(server, ctx)["status"] == "configured"
    class ConnectedClient:
        running = True
        initialized = True
        last_error = False
    bridge._clients[("repo", str(tmp_path))] = ConnectedClient()
    assert bridge.runtime_state(server, ctx)["status"] == "connected"
    assert bridge.runtime_state(server, ctx)["health_verified"] is True
    assert bridge.runtime_state(server, no_repo)["connected"] is False
    monkeypatch.setattr("shutil.which", lambda command: None)
    assert bridge.runtime_state(server, ctx)["status"] == "needs_setup"
