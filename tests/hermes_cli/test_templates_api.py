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


def _seed_trace_sessions() -> None:
    from hermes_cli import traces_store

    now = time.time()
    traces_store.insert_span(
        {
            "span_id": "session-a-root",
            "trace_id": "trace-session-a",
            "session_id": "session-a",
            "kind": "agent_turn",
            "status": "ok",
            "started_at": now - 60,
            "ended_at": now - 50,
            "duration_ms": 10_000,
            "total_tokens": 40,
            "cost_usd": 0.1,
        }
    )
    traces_store.insert_span(
        {
            "span_id": "session-b-root",
            "trace_id": "trace-session-b",
            "session_id": "session-b",
            "kind": "agent_turn",
            "status": "ok",
            "started_at": now - 40,
            "ended_at": now - 30,
            "duration_ms": 10_000,
            "total_tokens": 50,
            "cost_usd": 0.2,
        }
    )


def test_get_templates_shape_and_auth(clients):
    auth_client, unauth_client = clients

    resp = auth_client.get("/api/templates")
    assert resp.status_code == 200
    payload = resp.json()
    assert "templates" in payload
    assert isinstance(payload["templates"], list)

    items = payload["templates"]
    ids = {item["id"] for item in items}
    assert ids == {
        "research",
        "code-review",
        "feature-build",
        "ops-watchdog",
        "content",
        "growth",
        "affiliate",
    }
    for item in items:
        assert {"id", "name", "description", "creates"}.issubset(item.keys())
        assert {"board", "tasks_count", "cron"}.issubset(item["creates"].keys())

    assert unauth_client.get("/api/templates").status_code == 401
    assert unauth_client.post("/api/templates/research/instantiate", json={}).status_code == 401


@pytest.mark.parametrize("template_id", ["research", "ops-watchdog"])
def test_instantiate_template_creates_board_and_mission(clients, template_id):
    auth_client, _ = clients
    from hermes_cli import kanban_db, mission_templates, traces_store

    template = mission_templates.get_template(template_id)
    assert template is not None

    custom_title = f"{template_id}-mission"
    resp = auth_client.post(
        f"/api/templates/{template_id}/instantiate",
        json={"title": custom_title, "owner": "agent-owner"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert {"mission_id", "board_slug"}.issubset(payload.keys())

    board_slug = payload["board_slug"]
    mission_id = payload["mission_id"]

    conn = kanban_db.connect(board=board_slug)
    try:
        tasks = kanban_db.list_tasks(conn, include_archived=True)
    finally:
        conn.close()
    expected_count = len(template.get("creates", {}).get("tasks", []))
    assert len(tasks) == expected_count

    mission = traces_store.get_mission(mission_id)
    assert mission is not None
    assert mission["board_slug"] == board_slug
    assert mission["title"] == custom_title
    assert mission["owner"] == "agent-owner"

    if template_id == "ops-watchdog" and "warning" not in payload:
        assert payload.get("cron_job_id")


def test_traces_session_id_filter(clients):
    auth_client, _ = clients
    _seed_trace_sessions()

    resp = auth_client.get("/api/traces", params={"session_id": "session-a"})
    assert resp.status_code == 200
    payload = resp.json()
    assert {"traces", "total", "limit", "offset"}.issubset(payload.keys())
    trace_ids = {row["trace_id"] for row in payload["traces"]}
    assert trace_ids == {"trace-session-a"}
    assert payload["total"] == 1
