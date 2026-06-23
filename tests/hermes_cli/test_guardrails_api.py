from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def clients(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))

    import hermes_state
    import hermes_cli.traces_store as traces_store
    import hermes_cli.web_server as web_server
    from starlette.testclient import TestClient

    importlib.reload(traces_store)
    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", home / "state.db")

    prev_auth_required = getattr(web_server.app.state, "auth_required", None)
    prev_bound_host = getattr(web_server.app.state, "bound_host", None)
    web_server.app.state.auth_required = False
    web_server.app.state.bound_host = None

    auth_client = TestClient(web_server.app)
    auth_client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    unauth_client = TestClient(web_server.app)
    try:
        yield auth_client, unauth_client
    finally:
        auth_client.close()
        unauth_client.close()
        if prev_auth_required is None:
            try:
                delattr(web_server.app.state, "auth_required")
            except AttributeError:
                pass
        else:
            web_server.app.state.auth_required = prev_auth_required
        if prev_bound_host is None:
            try:
                delattr(web_server.app.state, "bound_host")
            except AttributeError:
                pass
        else:
            web_server.app.state.bound_host = prev_bound_host


def test_guardrails_get_defaults(clients):
    auth_client, _ = clients
    resp = auth_client.get("/api/costs/guardrails")
    assert resp.status_code == 200
    payload = resp.json()
    assert "cost_guardrails" in payload
    assert "status" in payload
    cfg = payload["cost_guardrails"]
    assert cfg["enabled"] is False
    assert cfg["daily_budget_usd"] is None
    assert cfg["mission_budgets_usd"] == {}


def test_guardrails_put_and_get_roundtrip(clients):
    auth_client, _ = clients
    update = {
        "enabled": True,
        "daily_budget_usd": 12.5,
        "mission_budgets_usd": {"mission-alpha": 3.25},
        "premium_alert": True,
        "block_expensive": True,
        "auto_fallback": True,
        "fallback_model": "google/gemini-2.5-flash",
        "fallback_provider": "openrouter",
    }
    put_resp = auth_client.put("/api/costs/guardrails", json=update)
    assert put_resp.status_code == 200

    get_resp = auth_client.get("/api/costs/guardrails")
    assert get_resp.status_code == 200
    cfg = get_resp.json()["cost_guardrails"]
    assert cfg["enabled"] is True
    assert cfg["daily_budget_usd"] == 12.5
    assert cfg["mission_budgets_usd"]["mission-alpha"] == 3.25
    assert cfg["premium_alert"] is True
    assert cfg["block_expensive"] is True
    assert cfg["auto_fallback"] is True
    assert cfg["fallback_model"] == "google/gemini-2.5-flash"
    assert cfg["fallback_provider"] == "openrouter"


def test_guardrails_endpoints_require_auth(clients):
    _, unauth_client = clients
    assert unauth_client.get("/api/costs/guardrails").status_code == 401
    assert unauth_client.put("/api/costs/guardrails", json={"enabled": True}).status_code == 401
