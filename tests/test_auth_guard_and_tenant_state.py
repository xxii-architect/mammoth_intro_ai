from fastapi.testclient import TestClient
from datetime import datetime, timezone
from types import SimpleNamespace

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


def test_optional_admin_routes_do_not_leak_to_anonymous_users(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: None)

    client = TestClient(api_server.app)
    response = client.get("/api/modules")

    assert response.status_code == 403
    assert response.json()["error"] == "Admin privileges required."

    approvals_response = client.get("/api/approvals")
    assert approvals_response.status_code == 401
    assert approvals_response.json()["error"] == "Authentication required"

    atlas_apply_response = client.post(
        "/api/atlas/apply",
        json={"operation": "write_file", "file_path": "README.md", "content": "x"},
    )
    assert atlas_apply_response.status_code == 401
    assert atlas_apply_response.json()["error"] == "Authentication required"


def test_supabase_admin_resolution_reads_policy_file(monkeypatch, tmp_path):
    policy_file = tmp_path / "auth_admin_policy.json"
    policy_file.write_text(
        '{"admin_user_ids":["c5b0576d-728d-48d8-bfa9-2689d57dddcb"],"admin_emails":["truexxiisupply@gmail.com"]}',
        encoding="utf-8",
    )

    class _FakeAuth:
        @staticmethod
        def get_user(_token):
            return SimpleNamespace(user=SimpleNamespace(
                id="c5b0576d-728d-48d8-bfa9-2689d57dddcb",
                email="truexxiisupply@gmail.com",
            ))

    monkeypatch.setattr(api_server, "AUTH_ADMIN_POLICY_FILE", policy_file)
    monkeypatch.setattr(api_server, "get_supabase", lambda: SimpleNamespace(auth=_FakeAuth()))

    resolved = api_server._resolve_supabase_user("token-owner")

    assert resolved == {
        "id": "c5b0576d-728d-48d8-bfa9-2689d57dddcb",
        "email": "truexxiisupply@gmail.com",
        "is_admin": True,
    }


def test_optional_admin_routes_still_honor_admin_tokens(monkeypatch):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)

    def _fake_user(token: str):
        if token == "token-admin":
            return {"id": "user-admin", "email": "admin@example.com", "is_admin": True}
        return None

    monkeypatch.setattr(api_server, "_resolve_supabase_user", _fake_user)

    client = TestClient(api_server.app)
    response = client.get("/api/modules", headers={"Authorization": "Bearer token-admin"})

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_operator_health_requires_admin_when_auth_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "OPERATOR_HEALTH_FILE", tmp_path / "operator_health.json")

    def _fake_user(token: str):
        mapping = {
            "token-member": {"id": "user-member", "email": "member@example.com", "is_admin": False},
            "token-admin": {"id": "user-admin", "email": "admin@example.com", "is_admin": True},
        }
        return mapping.get(token)

    monkeypatch.setattr(api_server, "_resolve_supabase_user", _fake_user)

    client = TestClient(api_server.app)

    denied = client.get("/api/operator/health", headers={"Authorization": "Bearer token-member"})
    assert denied.status_code == 403

    updated = client.post("/api/operator/health", headers={"Authorization": "Bearer token-admin"}, json={"energy": 61})
    assert updated.status_code == 200
    assert updated.json()["status"] == "ok"

    loaded = client.get("/api/operator/health", headers={"Authorization": "Bearer token-admin"})
    assert loaded.status_code == 200
    assert loaded.json()["data"]["energy"] == 61


def test_billing_usage_is_scoped_per_authenticated_user(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "ATLAS_STATE_DIR", tmp_path / "atlas_state")
    api_server.ATLAS_STATE_DIR.mkdir(exist_ok=True)

    def _fake_user(token: str):
        mapping = {
            "token-alpha": {"id": "user-alpha", "email": "alpha@example.com", "is_admin": False},
            "token-beta": {"id": "user-beta", "email": "beta@example.com", "is_admin": False},
        }
        return mapping.get(token)

    monkeypatch.setattr(api_server, "_resolve_supabase_user", _fake_user)

    alpha_file = api_server.ATLAS_STATE_DIR / "atlas_state_user-alpha.json"
    beta_file = api_server.ATLAS_STATE_DIR / "atlas_state_user-beta.json"
    now = datetime.now(timezone.utc)
    alpha_day_one = now.replace(day=3, hour=0, minute=0, second=0, microsecond=0).isoformat()
    alpha_day_two = now.replace(day=4, hour=0, minute=0, second=0, microsecond=0).isoformat()
    beta_day_one = now.replace(day=2, hour=0, minute=0, second=0, microsecond=0).isoformat()
    alpha_file.write_text(
        f"""{{
  "tier": "pro",
  "active_account_id": "default",
  "fab_usage_events": [
    {{"created_at": "{alpha_day_one}", "request_units": 2, "tokens_in": 100, "tokens_out": 60}},
    {{"created_at": "{alpha_day_two}", "request_units": 1, "tokens_in": 40, "tokens_out": 10}}
  ]
}}""",
        encoding="utf-8",
    )
    beta_file.write_text(
        f"""{{
  "tier": "explorer",
  "active_account_id": "default",
  "fab_usage_events": [
    {{"created_at": "{beta_day_one}", "request_units": 1, "tokens_in": 10, "tokens_out": 5}}
  ]
}}""",
        encoding="utf-8",
    )

    client = TestClient(api_server.app)

    alpha = client.get("/api/billing/usage/current", headers={"Authorization": "Bearer token-alpha"})
    beta = client.get("/api/billing/usage/current", headers={"Authorization": "Bearer token-beta"})

    assert alpha.status_code == 200
    assert beta.status_code == 200
    assert alpha.json()["usage"]["requests"] == 3
    assert alpha.json()["usage"]["tokens"] == 210
    assert alpha.json()["plan"] == "pro"
    assert alpha.json()["metering_mode"] == "workspace_state_preview"
    assert "warning_message" in alpha.json()
    assert "forecast" in alpha.json()
    assert "recommended_action" in alpha.json()
    assert beta.json()["usage"]["requests"] == 1
    assert beta.json()["usage"]["tokens"] == 15
    assert beta.json()["plan"] == "explorer"
