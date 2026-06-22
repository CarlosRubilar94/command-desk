from __future__ import annotations

import importlib
import time

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


def _seed_state() -> None:
    from hermes_state import SessionDB

    db = SessionDB()
    try:
        db.create_session(session_id="sess-ok", source="cli", model="gpt-4o")
        db.create_session(session_id="sess-error", source="cli", model="claude-3-5-sonnet")
        db.end_session("sess-error", "failed")
    finally:
        db.close()


def _seed_traces() -> None:
    from hermes_cli import traces_store

    now = time.time()
    traces_store.insert_span(
        {
            "span_id": "span-ok-1",
            "trace_id": "trace-ok",
            "session_id": "sess-ok",
            "kind": "agent_turn",
            "model": "gpt-4o",
            "status": "ok",
            "started_at": now - 240,
            "ended_at": now - 230,
            "duration_ms": 10_000,
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "cost_usd": 0.8,
        }
    )
    traces_store.insert_span(
        {
            "span_id": "span-ok-2",
            "trace_id": "trace-ok",
            "session_id": "sess-ok",
            "kind": "tool_call",
            "model": "gpt-4o",
            "status": "ok",
            "started_at": now - 225,
            "ended_at": now - 220,
            "duration_ms": 5_000,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }
    )
    traces_store.insert_span(
        {
            "span_id": "span-err-1",
            "trace_id": "trace-err",
            "session_id": "sess-error",
            "kind": "llm_call",
            "model": "claude-3-5-sonnet",
            "status": "error",
            "started_at": now - 180,
            "ended_at": now - 170,
            "duration_ms": 10_000,
            "input_tokens": 80,
            "output_tokens": 20,
            "total_tokens": 100,
            "cost_usd": 0.6,
            "error": "provider_error",
        }
    )
    traces_store.insert_span(
        {
            "span_id": "span-del-1",
            "trace_id": "trace-del",
            "session_id": "sess-ok",
            "kind": "delegation",
            "status": "ok",
            "started_at": now - 120,
            "ended_at": now - 110,
            "duration_ms": 10_000,
            "input_tokens": 5,
            "output_tokens": 2,
            "total_tokens": 7,
            "cost_usd": 0.05,
            "attributes": {"child_session_id": "sess-child"},
        }
    )


def _seed_task_events() -> None:
    from hermes_cli import kanban_db

    conn = kanban_db.connect(board="alpha")
    try:
        task_id = kanban_db.create_task(
            conn,
            title="Investigate run",
            initial_status="running",
            session_id="sess-ok",
            board="alpha",
        )
        conn.execute(
            """
            INSERT INTO task_events (task_id, run_id, kind, payload, created_at)
            VALUES (?, NULL, ?, NULL, ?)
            """,
            (task_id, "blocked", int(time.time()) - 60),
        )
        conn.commit()
    finally:
        conn.close()


def test_analytics_observability_endpoints_shape(clients):
    auth_client, _ = clients
    _seed_state()
    _seed_traces()
    _seed_task_events()

    overview = auth_client.get("/api/analytics/overview", params={"days": 7})
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert {
        "throughput",
        "success_rate",
        "latency",
        "token_usage",
        "model_efficiency",
    }.issubset(overview_payload.keys())
    assert {"traces_per_day", "spans_total", "traces_total"}.issubset(overview_payload["throughput"].keys())
    assert {"ok", "error", "rate"}.issubset(overview_payload["success_rate"].keys())
    assert {"avg_ms", "p50_ms", "p95_ms"}.issubset(overview_payload["latency"].keys())
    assert isinstance(overview_payload["token_usage"], list)
    assert isinstance(overview_payload["model_efficiency"], list)

    alerts = auth_client.get("/api/observability/alerts")
    assert alerts.status_code == 200
    alerts_payload = alerts.json()
    assert "alerts" in alerts_payload
    assert isinstance(alerts_payload["alerts"], list)
    if alerts_payload["alerts"]:
        first_alert = alerts_payload["alerts"][0]
        assert {
            "id",
            "severity",
            "kind",
            "title",
            "detail",
            "value",
            "threshold",
            "ts",
        }.issubset(first_alert.keys())

    events = auth_client.get("/api/observability/events", params={"limit": 20})
    assert events.status_code == 200
    events_payload = events.json()
    assert "events" in events_payload
    assert isinstance(events_payload["events"], list)
    assert events_payload["events"]
    first_event = events_payload["events"][0]
    assert {"ts", "kind", "label", "severity"}.issubset(first_event.keys())
    assert any(event.get("kind") == "task_event" for event in events_payload["events"])
    assert any(event.get("kind") in {"error", "delegation"} for event in events_payload["events"])


def test_analytics_observability_endpoints_require_auth(clients):
    _, unauth_client = clients
    for path in (
        "/api/analytics/overview",
        "/api/observability/alerts",
        "/api/observability/events",
    ):
        resp = unauth_client.get(path)
        assert resp.status_code == 401, f"{path} should be auth-protected"
