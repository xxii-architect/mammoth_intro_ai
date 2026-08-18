import asyncio

import api_server


def test_operator_health_defaults_and_updates(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "OPERATOR_HEALTH_FILE", tmp_path / "operator_health.json")

    initial = asyncio.run(api_server.get_operator_health())
    assert initial["status"] == "ok"
    assert initial["data"]["energy"] == 50
    assert initial["data"]["uptime"] == 0

    updated = asyncio.run(api_server.set_operator_health({"energy": 72, "uptime": 9}))
    assert updated["status"] == "ok"
    assert updated["data"]["energy"] == 72
    assert updated["data"]["uptime"] == 9

    loaded = asyncio.run(api_server.get_operator_health())
    assert loaded["data"]["energy"] == 72
    assert loaded["data"]["uptime"] == 9


def test_log_sale_persists_ledger_and_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "SALES_FILE", tmp_path / "sales_log.json")

    first = asyncio.run(
        api_server.log_sale(
            {"item": "Tomato starts", "amount": 120.5, "ledger": "business", "category": "produce", "date": "2026-08-17"}
        )
    )
    second = asyncio.run(
        api_server.log_sale(
            {"item": "Yard tools", "amount": 40, "ledger": "personal", "category": "household", "date": "2026-08-17"}
        )
    )
    assert first["ledger"] == "business"
    assert second["ledger"] == "personal"

    sales = asyncio.run(api_server.get_sales())
    assert len(sales) == 2

    summary = asyncio.run(api_server.get_sales_summary())
    assert summary["status"] == "ok"
    assert summary["summary"]["ledger_totals"]["business"] == 120.5
    assert summary["summary"]["ledger_totals"]["personal"] == 40.0


def test_entitlements_respect_developer_access(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas_state.json")

    asyncio.run(api_server.set_tier({"tier": "explorer"}))
    explorer = asyncio.run(api_server.get_entitlements())
    assert explorer["tier"] == "explorer"
    assert explorer["auth_mode"] == "local_operator"
    assert explorer["session_scope"] == "workspace_local"
    assert explorer["features"]["team_dashboards"] is False

    enabled = asyncio.run(api_server.set_developer_access({"enabled": True}))
    assert enabled["status"] == "ok"
    assert enabled["developer_access"] is True
    assert enabled["auth_mode"] == "developer_override"

    dev = asyncio.run(api_server.get_entitlements())
    assert dev["developer_access"] is True
    assert dev["effective_tier"] == "developer"
    assert dev["features"]["team_dashboards"] is True
    assert dev["upgrade_cta"] is None
    assert dev["account_profile_complete"] is False


def test_account_profile_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "ATLAS_FILE", tmp_path / "atlas_state.json")
    result = asyncio.run(
        api_server.set_account_profile(
            {"display_name": "Operator One", "email": "operator@example.com", "organization": "Mammoth Lab"}
        )
    )
    assert result["status"] == "ok"

    profile = asyncio.run(api_server.get_account_profile())
    assert profile["profile"]["display_name"] == "Operator One"
    assert profile["profile"]["email"] == "operator@example.com"
    assert profile["profile"]["organization"] == "Mammoth Lab"
    assert profile["profile_complete"] is True
    assert profile["auth_mode"] == "local_operator"
    assert profile["session_scope"] == "workspace_local"
    assert profile["updated_at"]
