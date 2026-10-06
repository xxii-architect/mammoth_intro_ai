from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api_server


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": "tenant-a", "email": "tenant@example.test", "is_admin": False,
    } if token == "tenant" else None)
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)

    async def manifests():
        return [
            SimpleNamespace(agent_id=agent_id, name=agent_id, status="IDLE",
                            capabilities=["learning"], endpoint="private-host-path")
            for agent_id in ["tutor_agent", "curriculum_agent", "research_agent",
                             "reflection_agent", "coding_agent", "browser_agent",
                             "shell_agent", "custodial_agent", "community_engine_agent"]
        ]

    monkeypatch.setattr(api_server.agent_registry, "list_agents", manifests)
    with TestClient(api_server.app) as test_client:
        yield test_client


def test_learning_catalog_requires_sign_in(client):
    assert client.get("/api/atlas/agents").status_code == 401


def test_tenant_gets_curated_catalog_without_host_metadata(client):
    response = client.get("/api/atlas/agents", headers={"Authorization": "Bearer tenant"})
    assert response.status_code == 200
    agents = response.json()["agents"]
    assert {agent["id"] for agent in agents} == {
        "tutor_agent", "curriculum_agent", "research_agent",
        "reflection_agent", "coding_agent", "browser_agent",
    }
    assert all(set(agent) == {"id", "name", "status", "capabilities"} for agent in agents)
    assert "private-host-path" not in response.text
    assert client.get("/api/agents", headers={"Authorization": "Bearer tenant"}).status_code == 403


def test_unavailable_registry_is_explicit(client, monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", False)
    response = client.get("/api/atlas/agents", headers={"Authorization": "Bearer tenant"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["error"]


def test_failed_registry_is_not_empty_success(client, monkeypatch):
    async def broken():
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr(api_server.agent_registry, "list_agents", broken)
    response = client.get("/api/atlas/agents", headers={"Authorization": "Bearer tenant"})
    assert response.status_code == 503
    assert "private diagnostic" not in response.text
