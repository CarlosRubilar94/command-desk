from __future__ import annotations

import importlib
import time

import pytest


@pytest.fixture()
def clients(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text(
        "cost_guardrails:\n  enabled: true\n  daily_budget_usd: 1.0\n",
        encoding="utf-8",
    )

    import hermes_state
    from hermes_cli.config import _RAW_CONFIG_CACHE
    import hermes_cli.traces_store as traces_store
    import hermes_cli.web_server as web_server
    from starlette.testclient import TestClient

    importlib.reload(traces_store)
    _RAW_CONFIG_CACHE.clear()
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


def _seed_incident_data() -> None:
    from hermes_state import SessionDB
    from hermes_cli import traces_store

    now = time.time()
    for idx in range(3):
        traces_store.insert_span(
            {
                "span_id": f"auto-error-{idx}",
                "trace_id": f"auto-trace-{idx}",
                "session_id": f"auto-session-{idx}",
                "kind": "agent_turn",
                "status": "error",
                "error": "mission_timeout",
                "started_at": now - 90 + idx,
                "ended_at": now - 85 + idx,
                "duration_ms": 5_000,
                "cost_usd": 0.1,
            }
        )

    db = SessionDB()
    try:
        db.create_session(session_id="budget-run", source="cli", model="gpt-4o")
        db.update_token_counts(
            "budget-run",
            input_tokens=120,
            output_tokens=30,
            estimated_cost_usd=2.5,
            actual_cost_usd=2.5,
            api_call_count=1,
            absolute=True,
        )
    finally:
        db.close()


def test_autopilot_incidents_empty(clients):
    auth_client, _ = clients

    resp = auth_client.get("/api/ops/autopilot/incidents")
    assert resp.status_code == 200
    payload = resp.json()
    assert "incidents" in payload
    assert isinstance(payload["incidents"], list)


def test_autopilot_incidents_seeded(clients):
    auth_client, _ = clients
    _seed_incident_data()

    resp = auth_client.get("/api/ops/autopilot/incidents")
    assert resp.status_code == 200
    payload = resp.json()
    assert "incidents" in payload
    assert isinstance(payload["incidents"], list)
    assert payload["incidents"]
    first = payload["incidents"][0]
    assert {
        "id",
        "kind",
        "severity",
        "title",
        "detail",
        "evidence",
        "suggested_action",
    }.issubset(first.keys())


def test_autopilot_diagnose_creates_mission_and_report(clients):
    auth_client, _ = clients
    _seed_incident_data()

    incidents_resp = auth_client.get("/api/ops/autopilot/incidents")
    assert incidents_resp.status_code == 200
    incidents = incidents_resp.json().get("incidents", [])
    assert incidents

    incident_id = incidents[0]["id"]
    diagnose_resp = auth_client.post(
        "/api/ops/autopilot/diagnose",
        json={"incident_id": incident_id, "assignee_profile": "ops"},
    )
    assert diagnose_resp.status_code == 200
    payload = diagnose_resp.json()
    assert {"mission_id", "kanban_task_id", "report"}.issubset(payload.keys())
    assert payload["mission_id"]
    assert {"summary", "suspected_cause", "suggested_fix", "next_steps"}.issubset(
        payload["report"].keys()
    )

    from hermes_cli import traces_store

    mission = traces_store.get_mission(payload["mission_id"])
    assert mission is not None
    assert mission.get("owner") == "ops"


def test_autopilot_endpoints_require_auth(clients):
    _, unauth_client = clients

    get_resp = unauth_client.get("/api/ops/autopilot/incidents")
    assert get_resp.status_code == 401

    post_resp = unauth_client.post(
        "/api/ops/autopilot/diagnose",
        json={"incident_id": "recurring-errors:test"},
    )
    assert post_resp.status_code == 401
