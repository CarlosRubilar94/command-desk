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


def _seed_missions_data() -> None:
    from hermes_state import SessionDB
    from hermes_cli import kanban_db, traces_store

    now = time.time()
    session_db = SessionDB()
    try:
        session_db.create_session(session_id="run-root", source="cli", model="gpt-4o")
        session_db.update_token_counts(
            "run-root",
            input_tokens=120,
            output_tokens=30,
            estimated_cost_usd=1.25,
            actual_cost_usd=1.10,
            api_call_count=2,
            absolute=True,
        )
        session_db.end_session("run-root", "completed")

        session_db.create_session(
            session_id="run-child",
            source="cli",
            model="claude-3-5-sonnet",
            parent_session_id="run-root",
        )
        session_db.update_token_counts(
            "run-child",
            input_tokens=80,
            output_tokens=20,
            estimated_cost_usd=0.70,
            actual_cost_usd=0.65,
            api_call_count=1,
            absolute=True,
        )
    finally:
        session_db.close()

    kanban_db.create_board("alpha", name="Alpha Board")
    conn = kanban_db.connect(board="alpha")
    try:
        task_a = kanban_db.create_task(
            conn,
            title="Design mission API",
            assignee="alice",
            session_id="run-root",
            initial_status="running",
        )
        task_b = kanban_db.create_task(
            conn,
            title="Implement mission detail",
            assignee="bob",
            session_id="run-child",
            initial_status="running",
        )
        conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_a,))
        conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (task_b,))
        conn.commit()
    finally:
        conn.close()

    kanban_db.create_board("orphan-board", name="Orphan Board")
    orphan_conn = kanban_db.connect(board="orphan-board")
    try:
        kanban_db.create_task(
            orphan_conn,
            title="Unregistered board task",
            assignee="ops",
            initial_status="running",
        )
        orphan_conn.commit()
    finally:
        orphan_conn.close()

    traces_store.upsert_mission(
        {
            "id": "mission-alpha",
            "board_slug": "alpha",
            "title": "Alpha Mission",
            "owner": "alice",
            "status": "in_progress",
            "tags": ["wave3"],
        }
    )
    traces_store.insert_span(
        {
            "span_id": "span-root",
            "trace_id": "trace-alpha",
            "session_id": "run-root",
            "kind": "agent_turn",
            "agent": "planner",
            "model": "gpt-4o",
            "status": "ok",
            "started_at": now - 120,
            "ended_at": now - 100,
            "duration_ms": 20_000,
            "cost_usd": 0.20,
            "total_tokens": 150,
        }
    )
    traces_store.insert_span(
        {
            "span_id": "span-delegation",
            "trace_id": "trace-alpha",
            "session_id": "run-root",
            "kind": "delegation",
            "agent": "planner",
            "model": "claude-3-5-sonnet",
            "status": "ok",
            "started_at": now - 90,
            "ended_at": now - 85,
            "duration_ms": 5_000,
            "cost_usd": 0.05,
            "attributes": {
                "parent_session_id": "run-root",
                "child_session_id": "run-child",
                "child_status": "running",
            },
        }
    )


def test_missions_list_shape_and_rollup(clients):
    auth_client, _ = clients
    _seed_missions_data()

    resp = auth_client.get("/api/missions")
    assert resp.status_code == 200
    payload = resp.json()
    assert {"missions", "total"}.issubset(payload.keys())
    assert isinstance(payload["missions"], list)
    assert payload["total"] == len(payload["missions"])

    missions_by_id = {
        item["mission_id"]: item
        for item in payload["missions"]
    }
    alpha = missions_by_id["mission-alpha"]
    assert {
        "mission_id",
        "board_slug",
        "title",
        "status",
        "owner",
        "progress",
        "models",
        "cost_usd",
        "total_tokens",
        "run_count",
        "updated_at",
    }.issubset(alpha.keys())
    assert alpha["progress"]["done"] == 1
    assert alpha["progress"]["total"] == 2
    assert alpha["run_count"] == 2
    assert alpha["total_tokens"] == 250
    assert "gpt-4o" in alpha["models"]
    assert "claude-3-5-sonnet" in alpha["models"]

    orphan = missions_by_id["board:orphan-board"]
    assert orphan["title"] == "Orphan Board"
    assert orphan["board_slug"] == "orphan-board"


def test_mission_detail_shape(clients):
    auth_client, _ = clients
    _seed_missions_data()

    resp = auth_client.get("/api/missions/mission-alpha")
    assert resp.status_code == 200
    payload = resp.json()
    assert {"mission", "tasks", "delegation_tree", "timeline", "top_runs"}.issubset(payload.keys())
    mission = payload["mission"]
    assert mission["mission_id"] == "mission-alpha"
    assert mission["board_slug"] == "alpha"
    assert isinstance(payload["tasks"], list) and payload["tasks"]
    assert {"id", "title", "status", "assignee", "session_id"}.issubset(payload["tasks"][0].keys())

    assert isinstance(payload["delegation_tree"], list) and payload["delegation_tree"]
    delegation = payload["delegation_tree"][0]
    assert {
        "session_id",
        "parent_session_id",
        "agent",
        "model",
        "cost_usd",
        "status",
    }.issubset(delegation.keys())

    assert isinstance(payload["timeline"], list) and payload["timeline"]
    assert {"ts", "kind", "label"}.issubset(payload["timeline"][0].keys())

    assert isinstance(payload["top_runs"], list) and payload["top_runs"]
    assert {"session_id", "cost_usd", "status", "duration_ms"}.issubset(payload["top_runs"][0].keys())


def test_post_mission_upsert(clients):
    auth_client, _ = clients
    _seed_missions_data()

    resp = auth_client.post(
        "/api/missions",
        json={
            "board_slug": "alpha",
            "title": "Alpha Mission Updated",
            "owner": "bob",
            "status": "blocked",
            "tags": ["ship"],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "mission" in payload
    assert payload["mission"]["id"] == "mission-alpha"
    assert payload["mission"]["title"] == "Alpha Mission Updated"
    assert payload["mission"]["owner"] == "bob"
    assert payload["mission"]["status"] == "blocked"
    assert payload["mission"]["tags"] == ["ship"]


def test_missions_endpoints_require_auth(clients):
    _, unauth_client = clients

    for method, path in [
        ("GET", "/api/missions"),
        ("GET", "/api/missions/mission-alpha"),
        ("POST", "/api/missions"),
    ]:
        if method == "GET":
            resp = unauth_client.get(path)
        else:
            resp = unauth_client.post(path, json={"board_slug": "alpha"})
        assert resp.status_code == 401, f"{method} {path} should be auth-protected"
