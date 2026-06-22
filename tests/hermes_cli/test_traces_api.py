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


def _seed_traces() -> None:
    from hermes_cli import traces_store

    now = time.time()
    traces_store.insert_span(
        {
            "span_id": "root-a",
            "trace_id": "trace-a",
            "session_id": "sess-a",
            "kind": "agent_turn",
            "name": "turn",
            "agent": "planner",
            "model": "gpt-4o",
            "provider": "openai",
            "status": "ok",
            "started_at": now - 120,
            "ended_at": now - 110,
            "duration_ms": 10_000,
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "cost_usd": 0.5,
        }
    )
    traces_store.insert_span(
        {
            "span_id": "tool-a",
            "trace_id": "trace-a",
            "parent_id": "root-a",
            "session_id": "sess-a",
            "kind": "tool_call",
            "name": "read_file",
            "agent": "planner",
            "model": "gpt-4o",
            "provider": "openai",
            "status": "error",
            "started_at": now - 109,
            "ended_at": now - 105,
            "duration_ms": 4_000,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "error": "tool_error",
        }
    )
    traces_store.insert_span(
        {
            "span_id": "root-b",
            "trace_id": "trace-b",
            "session_id": "sess-b",
            "kind": "llm_call",
            "name": "post_api_request",
            "agent": "executor",
            "model": "claude-3-5-sonnet",
            "provider": "anthropic",
            "status": "ok",
            "started_at": now - 80,
            "ended_at": now - 70,
            "duration_ms": 10_000,
            "input_tokens": 50,
            "output_tokens": 10,
            "total_tokens": 60,
            "cost_usd": 0.2,
        }
    )


def test_traces_list_and_detail_shape(clients):
    auth_client, _ = clients
    _seed_traces()

    traces_resp = auth_client.get("/api/traces", params={"limit": 10, "offset": 0})
    assert traces_resp.status_code == 200
    traces_payload = traces_resp.json()
    assert {"traces", "total", "limit", "offset"}.issubset(traces_payload.keys())
    assert isinstance(traces_payload["traces"], list)
    assert traces_payload["traces"]
    trace = traces_payload["traces"][0]
    assert {
        "trace_id",
        "root_kind",
        "agent",
        "model",
        "started_at",
        "ended_at",
        "duration_ms",
        "span_count",
        "total_tokens",
        "cost_usd",
        "status",
    }.issubset(trace.keys())

    detail_resp = auth_client.get("/api/traces/trace-a")
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert {"trace_id", "spans", "totals"}.issubset(detail_payload.keys())
    assert detail_payload["trace_id"] == "trace-a"
    assert isinstance(detail_payload["spans"], list)
    assert detail_payload["spans"]
    span = detail_payload["spans"][0]
    assert {
        "span_id",
        "parent_id",
        "session_id",
        "kind",
        "name",
        "agent",
        "model",
        "provider",
        "status",
        "started_at",
        "ended_at",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
        "error",
    }.issubset(span.keys())
    assert {
        "duration_ms",
        "total_tokens",
        "cost_usd",
        "span_count",
        "error_count",
    }.issubset(detail_payload["totals"].keys())


def test_fleet_metrics_shape(clients):
    auth_client, _ = clients
    _seed_traces()

    resp = auth_client.get("/api/ops/fleet-metrics")
    assert resp.status_code == 200
    payload = resp.json()
    assert {"queue", "throughput", "bottlenecks", "recurring_errors", "cost_today_usd", "tracer"}.issubset(
        payload.keys()
    )
    assert {"ready", "in_progress", "blocked"}.issubset(payload["queue"].keys())
    assert {"spans_per_min", "traces_today"}.issubset(payload["throughput"].keys())
    assert isinstance(payload["bottlenecks"], list)
    assert isinstance(payload["recurring_errors"], list)
    assert {"dropped_spans", "queue_size", "healthy"}.issubset(payload["tracer"].keys())


def test_traces_endpoints_require_auth(clients):
    _, unauth_client = clients

    for path in ("/api/traces", "/api/traces/trace-a", "/api/ops/fleet-metrics"):
        resp = unauth_client.get(path)
        assert resp.status_code == 401, f"{path} should be auth-protected"
