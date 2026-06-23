"""Wave 9 — Mission Builder API tests.

Covers:
  GET  /api/templates/{template_id}   — full template detail
  POST /api/templates                 — save custom template
  POST /api/templates/instantiate-draft — create mission from builder draft
"""
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


# ── GET /api/templates/{template_id} ─────────────────────────────────────────


def test_get_template_detail_known(clients):
    auth_client, unauth_client = clients

    resp = auth_client.get("/api/templates/research")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "research"
    assert data["name"] == "Research Sprint"
    assert "creates" in data
    tasks = data["creates"]["tasks"]
    assert isinstance(tasks, list)
    assert len(tasks) == 3
    for task in tasks:
        assert "title" in task


def test_get_template_detail_unknown(clients):
    auth_client, _ = clients
    resp = auth_client.get("/api/templates/does-not-exist")
    assert resp.status_code == 404


def test_get_template_detail_auth(clients):
    _, unauth_client = clients
    assert unauth_client.get("/api/templates/research").status_code == 401


# ── POST /api/templates (save custom) ────────────────────────────────────────


def test_save_custom_template_roundtrip(clients, tmp_path, monkeypatch):
    auth_client, unauth_client = clients

    payload = {
        "name": "My Custom Sprint",
        "description": "A builder-created template",
        "board": "Custom Board",
        "tasks": [
            {"title": "First step", "status": "todo"},
            {"title": "Second step", "assignee": "agent-a", "status": "todo"},
        ],
        "defaults": {"assignee": "agent-a", "model_tier": "balanced"},
    }
    resp = auth_client.post("/api/templates", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["name"] == "My Custom Sprint"
    template_id = data["id"]
    assert template_id.startswith("custom-")

    # The template should now appear in the catalog
    catalog_resp = auth_client.get("/api/templates")
    assert catalog_resp.status_code == 200
    ids = {t["id"] for t in catalog_resp.json()["templates"]}
    assert template_id in ids

    # And be retrievable via the detail endpoint
    detail_resp = auth_client.get(f"/api/templates/{template_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["name"] == "My Custom Sprint"
    assert len(detail["creates"]["tasks"]) == 2


def test_save_custom_template_auth(clients):
    _, unauth_client = clients
    resp = unauth_client.post("/api/templates", json={"name": "x"})
    assert resp.status_code == 401


# ── POST /api/templates/instantiate-draft ────────────────────────────────────


def test_instantiate_draft_creates_mission(clients):
    auth_client, _ = clients
    from hermes_cli import kanban_db, traces_store

    payload = {
        "name": "Builder Mission",
        "description": "From the mission builder",
        "board": "Builder Board",
        "owner": "tester",
        "tasks": [
            {"title": "Plan", "status": "todo", "assignee": "planner"},
            {"title": "Execute", "status": "todo"},
        ],
        "defaults": {"model_tier": "balanced"},
    }
    resp = auth_client.post("/api/templates/instantiate-draft", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "mission_id" in data
    assert "board_slug" in data

    # Board should exist
    board_slug = data["board_slug"]
    assert kanban_db.board_exists(board_slug)

    # Tasks should exist on the board
    conn = kanban_db.connect(board=board_slug)
    try:
        rows = conn.execute("SELECT title FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()
    titles = [r[0] for r in rows]
    assert "Plan" in titles
    assert "Execute" in titles

    # Mission should be registered
    missions = traces_store.list_missions(board_slug=board_slug, include_rollup=False, limit=1, offset=0)
    assert len(missions) == 1
    assert missions[0]["title"] == "Builder Board"


def test_instantiate_draft_blank_tasks(clients):
    auth_client, _ = clients
    payload = {"name": "Blank Mission", "tasks": []}
    resp = auth_client.post("/api/templates/instantiate-draft", json=payload)
    assert resp.status_code == 200
    assert "mission_id" in resp.json()


def test_instantiate_draft_auth(clients):
    _, unauth_client = clients
    resp = unauth_client.post("/api/templates/instantiate-draft", json={"name": "x"})
    assert resp.status_code == 401
