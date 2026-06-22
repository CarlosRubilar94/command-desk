from __future__ import annotations

from starlette.testclient import TestClient


def test_command_deck_probe_rejects_unsafe_urls(monkeypatch):
    import hermes_cli.web_server as web_server

    bad_values = (
        "http://user:pass@127.0.0.1:8765",
        "http://127.0.0.1:8765/?q=1",
        "http://192.168.1.10:8765",
        "http://localhost:9999",
    )
    for value in bad_values:
        monkeypatch.setenv("COMMAND_DECK_URL", value)
        target, error = web_server._resolve_command_deck_target()
        assert target is None
        assert error == "unavailable"


def test_command_deck_probe_accepts_localhost_8765(monkeypatch):
    import hermes_cli.web_server as web_server

    for value in ("http://localhost:8765", "http://127.0.0.1:8765"):
        monkeypatch.setenv("COMMAND_DECK_URL", value)
        target, error = web_server._resolve_command_deck_target()
        assert error is None
        assert target is not None
        assert target.app_url in {"http://localhost:8765", "http://127.0.0.1:8765"}
        assert target.probe_url.endswith("/api/status")


def test_command_deck_overview_shape_and_auth(monkeypatch):
    import hermes_cli.web_server as web_server

    prev_auth_required = getattr(web_server.app.state, "auth_required", None)
    prev_bound_host = getattr(web_server.app.state, "bound_host", None)
    web_server.app.state.auth_required = False
    web_server.app.state.bound_host = None

    async def _fleet_stub(profile=None):  # noqa: ANN001
        return {
            "queue": {"ready": 1, "in_progress": 2, "blocked": 0},
            "throughput": {"spans_per_min": 3.0, "traces_today": 4},
            "bottlenecks": [],
            "recurring_errors": [],
            "cost_today_usd": 0.0,
            "tracer": {"dropped_spans": 0, "queue_size": 0, "healthy": True},
        }

    async def _costs_stub(profile=None):  # noqa: ANN001
        return {"spend_today": 1.2, "runs_today": 3, "tokens_today": 100}

    async def _missions_stub(profile=None):  # noqa: ANN001
        return {"missions": [], "total": 5}

    monkeypatch.setattr(
        web_server,
        "_probe_command_deck_status",
        lambda: {
            "available": True,
            "latency_ms": 9,
            "url": "http://127.0.0.1:8765/api/status",
            "app_url": "http://127.0.0.1:8765",
            "error": None,
        },
    )
    monkeypatch.setattr(web_server, "get_fleet_metrics", _fleet_stub)
    monkeypatch.setattr(web_server, "get_costs_summary", _costs_stub)
    monkeypatch.setattr(web_server, "get_missions", _missions_stub)

    auth_client = TestClient(web_server.app)
    auth_client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    unauth_client = TestClient(web_server.app)
    try:
        unauth = unauth_client.get("/api/command-deck/overview")
        assert unauth.status_code == 401

        resp = auth_client.get("/api/command-deck/overview")
        assert resp.status_code == 200
        payload = resp.json()
        assert {"deck", "fleet", "costs", "missions", "tracer"}.issubset(payload.keys())
        assert {"available", "status"}.issubset(payload["deck"].keys())
        assert payload["deck"]["available"] is True
        assert payload["deck"]["status"] == "ok"
        assert payload["missions"]["count"] == 5
        assert {"dropped_spans", "healthy"}.issubset(payload["tracer"].keys())
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
