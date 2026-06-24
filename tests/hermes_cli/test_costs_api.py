from __future__ import annotations

import importlib
import sqlite3
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


def _seed_session_costs() -> None:
    from hermes_state import SessionDB

    db = SessionDB()
    try:
        db.create_session(session_id="run-1", source="cli", model="gpt-4o")
        db.update_token_counts(
            "run-1",
            input_tokens=120,
            output_tokens=30,
            estimated_cost_usd=1.25,
            actual_cost_usd=1.1,
            api_call_count=2,
            absolute=True,
        )
        db.create_session(session_id="run-2", source="cli", model="claude-3-5-sonnet")
        db.update_token_counts(
            "run-2",
            input_tokens=80,
            output_tokens=20,
            estimated_cost_usd=0.7,
            actual_cost_usd=0.65,
            api_call_count=1,
            absolute=True,
        )
    finally:
        db.close()


def _seed_missions_with_board_sessions() -> None:
    from hermes_cli import traces_store
    from hermes_cli.kanban_db import kanban_db_path

    traces_store.upsert_mission(
        {
            "id": "mission-alpha",
            "board_slug": "alpha",
            "title": "Alpha Mission",
            "status": "in_progress",
        }
    )

    board_db = kanban_db_path(board="alpha")
    board_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(board_db))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                assignee TEXT,
                status TEXT NOT NULL,
                session_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                created_at INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO tasks (id, assignee, status, session_id) VALUES (?, ?, ?, ?)",
            ("task-1", "alice", "ready", "run-1"),
        )
        conn.execute(
            "INSERT INTO tasks (id, assignee, status, session_id) VALUES (?, ?, ?, ?)",
            ("task-2", "bob", "running", "run-2"),
        )
        conn.execute(
            "INSERT INTO task_events (task_id, created_at) VALUES (?, ?)",
            ("task-1", 1),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_span_costs() -> None:
    from hermes_cli import traces_store

    now = time.time()
    traces_store.insert_span(
        {
            "span_id": "span-run-1",
            "trace_id": "trace-run-1",
            "session_id": "run-1",
            "kind": "llm_call",
            "name": "post_api_request",
            "status": "ok",
            "model": "gpt-4o",
            "started_at": now - 5,
            "ended_at": now - 4.5,
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "cost_usd": 0.42,
            "savings_usd": 0.18,
            "attributes": {
                "baseline_model": "anthropic/claude-opus-4",
                "baseline_tier": "premium",
                "selected_tier": "economy",
                "savings_usd": 0.18,
            },
        }
    )


def test_costs_endpoints_shape(clients):
    auth_client, _ = clients
    _seed_session_costs()
    _seed_missions_with_board_sessions()

    summary = auth_client.get("/api/costs/summary")
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert {
        "spend_today",
        "runs_today",
        "tokens_today",
        "spend_total",
        "actual_total",
        "tokens_total",
        "runs_total",
    }.issubset(summary_payload.keys())

    by_model = auth_client.get("/api/costs/by-model", params={"days": 30})
    assert by_model.status_code == 200
    by_model_payload = by_model.json()
    assert "by_model" in by_model_payload
    assert "period_days" in by_model_payload
    assert isinstance(by_model_payload["by_model"], list)

    by_day = auth_client.get("/api/costs/by-day", params={"days": 30})
    assert by_day.status_code == 200
    by_day_payload = by_day.json()
    assert "by_day" in by_day_payload
    assert "period_days" in by_day_payload
    assert isinstance(by_day_payload["by_day"], list)

    savings = auth_client.get("/api/costs/savings", params={"days": 30})
    assert savings.status_code == 200
    savings_payload = savings.json()
    assert {
        "estimated_savings_usd",
        "premium_spend_usd",
        "premium_runs",
        "mid_cost_factor",
        "is_estimate",
        "period_days",
    }.issubset(savings_payload.keys())

    by_mission = auth_client.get("/api/costs/by-mission", params={"days": 30})
    assert by_mission.status_code == 200
    by_mission_payload = by_mission.json()
    assert "missions" in by_mission_payload
    assert "is_estimate" in by_mission_payload
    assert isinstance(by_mission_payload["missions"], list)
    assert by_mission_payload["missions"]
    mission = by_mission_payload["missions"][0]
    assert {
        "mission_id",
        "title",
        "status",
        "cost_usd",
        "total_tokens",
        "run_count",
        "top_runs",
    }.issubset(mission.keys())


def test_costs_endpoints_prefer_recorded_spans(clients):
    auth_client, _ = clients
    _seed_session_costs()
    _seed_missions_with_board_sessions()
    _seed_span_costs()

    summary = auth_client.get("/api/costs/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["spend_total"] > 0
    assert payload["actual_total"] == payload["spend_total"]

    savings = auth_client.get("/api/costs/savings", params={"days": 30})
    assert savings.status_code == 200
    savings_payload = savings.json()
    assert savings_payload["is_estimate"] is False
    assert savings_payload["estimated_savings_usd"] > 0

    by_mission = auth_client.get("/api/costs/by-mission", params={"days": 30})
    assert by_mission.status_code == 200
    by_mission_payload = by_mission.json()
    assert by_mission_payload["is_estimate"] is False
    assert any(mission.get("is_estimate") is False for mission in by_mission_payload["missions"])


def test_costs_endpoints_require_auth(clients):
    _, unauth_client = clients

    paths = [
        "/api/costs/summary",
        "/api/costs/by-model",
        "/api/costs/by-day",
        "/api/costs/savings",
        "/api/costs/by-mission",
    ]
    for path in paths:
        resp = unauth_client.get(path)
        assert resp.status_code == 401, f"{path} should be auth-protected"
