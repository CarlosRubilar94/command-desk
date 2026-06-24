"""Pre-flight credential checks must not raise a false alarm for claude-cli.

`claude-cli` is a keyless subprocess provider (Pro/OAuth via the `claude`
CLI). It resolves with an empty ``api_key`` by design, so the TUI pre-flight
warning and the ``setup.runtime_check`` RPC must treat it as OK rather than
reporting "No API key configured" / "No usable credentials found".
"""

import types
from unittest.mock import patch

from tui_gateway import server


# ── _probe_credentials ──────────────────────────────────────────────────────

def _agent(**kw):
    return types.SimpleNamespace(**kw)


def test_probe_credentials_silent_for_claude_cli_provider():
    agent = _agent(provider="claude-cli", api_mode="claude_cli", api_key="")
    assert server._probe_credentials(agent) == ""


def test_probe_credentials_silent_when_api_mode_is_claude_cli():
    # Even if provider label differs, the resolved api_mode is authoritative.
    agent = _agent(provider="anthropic", api_mode="claude_cli", api_key="")
    assert server._probe_credentials(agent) == ""


def test_probe_credentials_still_warns_for_normal_keyless_provider():
    # Regression: a genuine missing key for an HTTP provider must still warn.
    agent = _agent(provider="anthropic", api_mode="anthropic_messages", api_key="")
    msg = server._probe_credentials(agent)
    assert "No API key configured" in msg
    assert "anthropic" in msg


def test_probe_credentials_ok_for_provider_with_key():
    agent = _agent(provider="openrouter", api_mode="chat_completions", api_key="sk-or-123")
    assert server._probe_credentials(agent) == ""


# ── setup.runtime_check ───────────────────────────────────────────────────────

def _runtime_check(rid="r1"):
    return server._methods["setup.runtime_check"](rid, {})


def test_runtime_check_ok_for_claude_cli_without_api_key():
    claude_runtime = {
        "provider": "claude-cli",
        "api_mode": "claude_cli",
        "base_url": "",
        "api_key": "",
        "model": "claude-sonnet-4-5",
        "source": "claude-cli-subprocess",
    }
    with (
        patch("hermes_cli.runtime_provider.resolve_runtime_provider", return_value=claude_runtime),
        patch("hermes_cli.main._has_any_provider_configured", return_value=True),
        patch("hermes_cli.auth.has_usable_secret", return_value=False),
    ):
        resp = _runtime_check()

    assert "result" in resp, resp
    result = resp["result"]
    assert result["ok"] is True
    assert result["provider"] == "claude-cli"


def test_runtime_check_still_fails_for_normal_provider_without_key():
    # Regression: an HTTP provider with no usable key must still report not-ok.
    runtime = {
        "provider": "anthropic",
        "api_mode": "anthropic_messages",
        "base_url": "https://api.anthropic.com",
        "api_key": "",
        "model": "claude-sonnet-4-6",
        "source": "config",
    }
    with (
        patch("hermes_cli.runtime_provider.resolve_runtime_provider", return_value=runtime),
        patch("hermes_cli.main._has_any_provider_configured", return_value=True),
        patch("hermes_cli.auth.has_usable_secret", return_value=False),
    ):
        resp = _runtime_check()

    result = resp["result"]
    assert result["ok"] is False
    assert "credentials" in result["error"].lower()
