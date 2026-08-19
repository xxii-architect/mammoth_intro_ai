from fastapi.testclient import TestClient

import api_server


def test_auth_guard_blocks_unauthenticated_requests(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: None)

    client = TestClient(api_server.app)
    response = client.get("/api/entitlements")

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == "error"


def test_auth_guard_scopes_workspace_state_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas_cli_session.json")
    monkeypatch.setattr(api_server, "ATLAS_STATE_DIR", tmp_path / "atlas_state")
    api_server.ATLAS_STATE_DIR.mkdir(exist_ok=True)

    def _fake_user(token: str):
        mapping = {
            "token-alpha": {"id": "user-alpha", "email": "alpha@example.com", "is_admin": False},
            "token-beta": {"id": "user-beta", "email": "beta@example.com", "is_admin": True},
        }
        return mapping.get(token)

    monkeypatch.setattr(api_server, "_resolve_supabase_user", _fake_user)

    client = TestClient(api_server.app)

    alpha_headers = {"Authorization": "Bearer token-alpha"}
    beta_headers = {"Authorization": "Bearer token-beta"}

    alpha_entitlements = client.get("/api/entitlements", headers=alpha_headers)
    assert alpha_entitlements.status_code == 200
    alpha_payload = alpha_entitlements.json()
    assert alpha_payload["admin_controls_enabled"] is False
    assert alpha_payload["session_scope"] == "workspace_multi_account"

    denied_tier = client.post("/api/entitlements/tier", headers=alpha_headers, json={"tier": "pro"})
    assert denied_tier.status_code == 200
    assert denied_tier.json()["status"] == "error"

    beta_entitlements = client.get("/api/entitlements", headers=beta_headers)
    assert beta_entitlements.status_code == 200
    assert beta_entitlements.json()["admin_controls_enabled"] is True

    assert client.post(
        "/api/account/profile",
        headers=alpha_headers,
        json={"display_name": "Alpha User", "email": "alpha@example.com", "organization": "Alpha Org"},
    ).status_code == 200
    assert client.post(
        "/api/account/profile",
        headers=beta_headers,
        json={"display_name": "Beta User", "email": "beta@example.com", "organization": "Beta Org"},
    ).status_code == 200

    alpha_profile = client.get("/api/account/profile", headers=alpha_headers).json()
    beta_profile = client.get("/api/account/profile", headers=beta_headers).json()

    assert alpha_profile["profile"]["display_name"] == "Alpha User"
    assert beta_profile["profile"]["display_name"] == "Beta User"
