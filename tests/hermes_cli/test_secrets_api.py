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
    # One shared reveal-rate-limit bucket governs both /api/env/reveal and
    # /api/secrets/reveal — reset it between tests.
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

    ws._reveal_timestamps.clear()
    with caplog.at_level(logging.INFO, logger="hermes_cli.web_server"):
        ok_resp = client.post("/api/secrets/reveal", json={"name": secret_name})
    assert ok_resp.status_code == 200
    assert ok_resp.json()["value"] == secret_value
    assert any("secrets/reveal: TEST_ENV_REVEAL_AUTH" in rec.getMessage() for rec in caplog.records)
    assert all(secret_value not in rec.getMessage() for rec in caplog.records)

    ws._reveal_timestamps.clear()
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


def test_reveal_rate_limit_is_shared_across_env_and_secrets(client, monkeypatch, caplog):
    """Interleaving /api/env/reveal and /api/secrets/reveal must draw from ONE
    5-per-30s budget — the 6th call across both endpoints is rejected."""
    from hermes_cli.config import save_env_value
    import hermes_cli.web_server as ws

    secret_value = "shared-budget-secret-value-abc"
    save_env_value("TEST_SHARED_BUDGET", secret_value)

    # Force the secrets endpoint down the .env fallback path (no real bws call).
    monkeypatch.setattr(
        ws,
        "_list_bitwarden_secret_refs",
        lambda profile=None: (
            {},
            {"available": False, "locked": False, "message": "Bitwarden unavailable."},
        ),
    )

    ws._reveal_timestamps.clear()

    # Alternate endpoints: env, secrets, env, secrets, env = 5 allowed reveals.
    sequence = ["env", "secrets", "env", "secrets", "env"]
    with caplog.at_level(logging.INFO, logger="hermes_cli.web_server"):
        for kind in sequence:
            if kind == "env":
                resp = client.post("/api/env/reveal", json={"key": "TEST_SHARED_BUDGET"})
            else:
                resp = client.post("/api/secrets/reveal", json={"name": "TEST_SHARED_BUDGET"})
            assert resp.status_code == 200

        # The 6th reveal — regardless of endpoint — is over the shared budget.
        blocked_secrets = client.post("/api/secrets/reveal", json={"name": "TEST_SHARED_BUDGET"})
        assert blocked_secrets.status_code == 429
        blocked_env = client.post("/api/env/reveal", json={"key": "TEST_SHARED_BUDGET"})
        assert blocked_env.status_code == 429

    # Five reveals consumed the single shared bucket.
    assert len(ws._reveal_timestamps) == ws._REVEAL_MAX_PER_WINDOW
    # Defense-in-depth: the plaintext value never lands in any log record.
    assert all(secret_value not in rec.getMessage() for rec in caplog.records)
