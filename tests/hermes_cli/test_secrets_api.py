import json
import logging

import pytest


@pytest.fixture
def client(monkeypatch, _isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_state
    from hermes_constants import get_hermes_home
    import hermes_cli.web_server as ws

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", get_hermes_home() / "state.db")
    ws._secrets_reveal_timestamps.clear()
    ws._reveal_timestamps.clear()

    c = TestClient(ws.app)
    c.headers[ws._SESSION_HEADER_NAME] = ws._SESSION_TOKEN
    try:
        yield c
    finally:
        c.close()


def test_get_secrets_names_only_no_values(client, monkeypatch):
    from hermes_cli.config import save_env_value
    import hermes_cli.web_server as ws

    fixture_env_value = "fixture-env-secret-value-123"
    save_env_value("TEST_ENV_LIST_ONLY", fixture_env_value)

    monkeypatch.setattr(
        ws,
        "_list_bitwarden_secret_refs",
        lambda profile=None: (
            {"TEST_BW_SECRET": "bw-secret-id-1"},
            {"available": True, "locked": False, "message": "Bitwarden Secrets Manager is available."},
        ),
    )

    resp = client.get("/api/secrets")
    assert resp.status_code == 200
    payload = resp.json()
    payload_text = json.dumps(payload)

    assert fixture_env_value not in payload_text
    assert "value" not in payload["items"][0]
    assert any(item["name"] == "TEST_BW_SECRET" and item["source"] == "bitwarden" for item in payload["items"])
    assert any(item["name"] == "TEST_ENV_LIST_ONLY" and item["source"] == "env" for item in payload["items"])


def test_reveal_secret_requires_auth_rate_limits_and_logs_name_only(client, caplog):
    from starlette.testclient import TestClient
    from hermes_cli.config import save_env_value
    import hermes_cli.web_server as ws

    secret_name = "TEST_ENV_REVEAL_AUTH"
    secret_value = "fixture-reveal-secret-value-999"
    save_env_value(secret_name, secret_value)

    unauth_client = TestClient(ws.app)
    unauth_resp = unauth_client.post("/api/secrets/reveal", json={"name": secret_name})
    assert unauth_resp.status_code == 401
    unauth_client.close()

    ws._secrets_reveal_timestamps.clear()
    with caplog.at_level(logging.INFO, logger="hermes_cli.web_server"):
        ok_resp = client.post("/api/secrets/reveal", json={"name": secret_name})
    assert ok_resp.status_code == 200
    assert ok_resp.json()["value"] == secret_value
    assert any("secrets/reveal: TEST_ENV_REVEAL_AUTH" in rec.getMessage() for rec in caplog.records)
    assert all(secret_value not in rec.getMessage() for rec in caplog.records)

    ws._secrets_reveal_timestamps.clear()
    for _ in range(5):
        resp = client.post("/api/secrets/reveal", json={"name": secret_name})
        assert resp.status_code == 200
    blocked = client.post("/api/secrets/reveal", json={"name": secret_name})
    assert blocked.status_code == 429


def test_bitwarden_locked_state_is_structured_and_safe(client, monkeypatch):
    import hermes_cli.web_server as ws

    monkeypatch.setattr(
        ws,
        "_list_bitwarden_secret_refs",
        lambda profile=None: (
            {},
            {
                "available": False,
                "locked": True,
                "message": "Bitwarden is locked or unavailable. Unlock in your own terminal.",
            },
        ),
    )

    resp = client.get("/api/secrets")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["bitwarden"] == {
        "available": False,
        "locked": True,
        "message": "Bitwarden is locked or unavailable. Unlock in your own terminal.",
    }
    assert "master password" not in json.dumps(payload).lower()


def test_reveal_secret_env_fallback_uses_existing_loader(client, monkeypatch):
    from hermes_cli.config import save_env_value
    import hermes_cli.web_server as ws

    save_env_value("TEST_ENV_FALLBACK_REVEAL", "fallback-secret-value")

    monkeypatch.setattr(
        ws,
        "_list_bitwarden_secret_refs",
        lambda profile=None: (
            {},
            {"available": False, "locked": False, "message": "Bitwarden unavailable."},
        ),
    )

    resp = client.post("/api/secrets/reveal", json={"name": "TEST_ENV_FALLBACK_REVEAL"})
    assert resp.status_code == 200
    assert resp.json()["value"] == "fallback-secret-value"
