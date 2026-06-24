from __future__ import annotations

import json

from starlette.testclient import TestClient


def test_secrets_status_counts_metadata_without_leaking_secret_values(monkeypatch):
    import hermes_cli.web_server as web_server

    prev_auth_required = getattr(web_server.app.state, "auth_required", None)
    prev_bound_host = getattr(web_server.app.state, "bound_host", None)
    web_server.app.state.auth_required = False
    web_server.app.state.bound_host = None

    monkeypatch.setattr(
        web_server,
        "OPTIONAL_ENV_VARS",
        {
            "OPENAI_API_KEY": {"description": "OpenAI"},
            "ANTHROPIC_API_KEY": {"description": "Anthropic"},
        },
    )
    monkeypatch.setattr(
        web_server,
        "_catalog_provider_env_metadata",
        lambda: {
            "OPENAI_API_KEY": {"provider": "openai"},
            "GITHUB_TOKEN": {"provider": "github"},
        },
    )
    monkeypatch.setattr(web_server, "load_env", lambda: {"OPENAI_API_KEY": "sk-real-secret"})
    monkeypatch.setattr(
        web_server,
        "_bitwarden_cli_status",
        lambda: {"installed": True, "state": "unlocked", "version": "2026.1.0"},
    )

    auth_client = TestClient(web_server.app)
    auth_client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    unauth_client = TestClient(web_server.app)
    try:
        unauth = unauth_client.get("/api/secrets/status")
        assert unauth.status_code == 401

        resp = auth_client.get("/api/secrets/status")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["provider"] == "bitwarden"
        assert payload["bitwarden"]["state"] == "unlocked"
        assert payload["env"] == {
            "fallback_enabled": True,
            "known": 3,
            "set": 1,
            "missing": 2,
        }

        encoded = json.dumps(payload)
        assert "sk-real-secret" not in encoded
        assert "OPENAI_API_KEY" not in encoded
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
