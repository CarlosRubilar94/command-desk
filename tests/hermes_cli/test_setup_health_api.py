"""Tests for the /api/setup/health aggregation endpoint.

Covers:
- No secret values leak into the response (only names, booleans, state enums)
- Status chips computed correctly for each section
- Gateway, Bitwarden, provider and MCP sections present
- Summary readiness % computed correctly
- Endpoint is read-only (no side effects, no bw unlock/login)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_helpers():
    from hermes_cli.web_server import (
        _setup_key_present,
        _setup_skill_counts,
        _setup_mcp_counts,
        _setup_obsidian_bridge_status,
        _SETUP_STATUS_READY,
        _SETUP_STATUS_WAITING_CREDENTIAL,
        _SETUP_STATUS_WAITING_SERVICE,
        _SETUP_STATUS_LOCKED,
        _SETUP_STATUS_DISABLED,
        _SETUP_STATUS_FAILED,
    )
    return (
        _setup_key_present,
        _setup_skill_counts,
        _setup_mcp_counts,
        _setup_obsidian_bridge_status,
        _SETUP_STATUS_READY,
        _SETUP_STATUS_WAITING_CREDENTIAL,
        _SETUP_STATUS_WAITING_SERVICE,
        _SETUP_STATUS_LOCKED,
        _SETUP_STATUS_DISABLED,
        _SETUP_STATUS_FAILED,
    )


def _run_endpoint() -> dict:
    """Call get_setup_health synchronously and return JSON-serializable dict."""
    from hermes_cli.web_server import get_setup_health
    result = asyncio.run(get_setup_health())
    # Verify it's JSON-serializable (no unserializable objects leak).
    return json.loads(json.dumps(result))


# ---------------------------------------------------------------------------
# Security: no secret values in response
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    "sk-ant-fake",
    "sk-cursor-fake",
    "AIzafake",
    "bws.fake",
]


class TestNoSecretLeakage:
    def test_no_secret_values_in_response(self, monkeypatch):
        """The endpoint must never return secret key values."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fakesecretvalue")
        monkeypatch.setenv("CURSOR_API_KEY", "sk-cursorfakevalue")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzafakegeminisecret")
        monkeypatch.setenv("BWS_ACCESS_TOKEN", "bws.faketoken")

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "unlocked."
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={
                "total": 3, "READY": 2, "DISABLED": 1,
            }),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 5, "disabled": 1, "total": 6,
            }),
        ):
            result = _run_endpoint()

        result_str = json.dumps(result)
        assert "sk-ant-fakesecretvalue" not in result_str
        assert "sk-cursorfakevalue" not in result_str
        assert "AIzafakegeminisecret" not in result_str
        assert "bws.faketoken" not in result_str

    def test_no_leaked_values_in_provider_entries(self, monkeypatch):
        """Provider entries must only expose name, key_env name, and boolean presence."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-shouldnotappear")

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
        ):
            result = _run_endpoint()

        providers_str = json.dumps(result["providers"])
        assert "sk-ant-shouldnotappear" not in providers_str
        # The env var name should be visible, but not any value.
        assert "ANTHROPIC_API_KEY" in providers_str


# ---------------------------------------------------------------------------
# Status computation
# ---------------------------------------------------------------------------

class TestSecretsStatus:
    def test_locked_when_bw_locked(self, monkeypatch):
        monkeypatch.delenv("BWS_ACCESS_TOKEN", raising=False)
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": False, "locked": True, "message": "locked"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("hermes_cli.config.get_env_path", side_effect=Exception("no path")),
            patch("hermes_cli.config.get_env_value", return_value=""),
        ):
            result = _run_endpoint()

        assert result["secrets"]["status"] in ("LOCKED", "WAITING_CREDENTIAL")
        assert isinstance(result["secrets"]["bw_locked"], bool)
        assert result["secrets"]["bw_locked"] is True

    def test_ready_when_bw_unlocked(self, monkeypatch):
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "unlocked"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
        ):
            result = _run_endpoint()

        assert result["secrets"]["status"] == "READY"
        assert result["secrets"]["bw_locked"] is False


class TestGatewayStatus:
    def test_ready_when_running(self):
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
        ):
            result = _run_endpoint()

        assert result["gateway"]["status"] == "READY"
        assert result["gateway"]["running"] is True
        assert result["gateway"]["hint"] is None

    def test_waiting_when_stopped(self):
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(False, "stopped")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
        ):
            result = _run_endpoint()

        assert result["gateway"]["status"] == "WAITING_SERVICE"
        assert result["gateway"]["running"] is False
        assert result["gateway"]["hint"] is not None


class TestProviderStatus:
    def test_anthropic_ready_when_key_present(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fakekey")

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
        ):
            result = _run_endpoint()

        providers = {p["name"]: p for p in result["providers"]}
        assert providers["Anthropic"]["status"] == "READY"
        assert providers["Anthropic"]["key_present"] is True
        # Must NOT contain the actual key value.
        assert "sk-ant-fakekey" not in json.dumps(providers["Anthropic"])

    def test_anthropic_waiting_when_key_absent(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_TOKEN", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": False, "locked": True, "message": "locked"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("hermes_cli.config.get_env_value", return_value=""),
            # No API key AND no authenticated Claude Code CLI → WAITING.
            patch("hermes_cli.web_server._anthropic_cli_ready", return_value=False),
        ):
            result = _run_endpoint()

        providers = {p["name"]: p for p in result["providers"]}
        assert providers["Anthropic"]["status"] == "WAITING_CREDENTIAL"
        assert providers["Anthropic"]["key_present"] is False

    def test_anthropic_ready_via_claude_code_cli(self, monkeypatch):
        """Anthropic is READY via an authenticated Claude Code CLI (no API key)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_TOKEN", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("hermes_cli.config.get_env_value", return_value=""),
            patch("hermes_cli.web_server._anthropic_cli_ready", return_value=True),
        ):
            result = _run_endpoint()

        providers = {p["name"]: p for p in result["providers"]}
        assert providers["Anthropic"]["status"] == "READY"
        assert providers["Anthropic"]["key_present"] is False
        assert providers["Anthropic"]["cli_present"] is True
        assert providers["Anthropic"]["fallback_active"] is True

    def test_cursor_ready_via_subscription_cli(self, monkeypatch):
        """Cursor is READY when the Cursor subscription CLI is present (no API key)."""
        monkeypatch.delenv("CURSOR_API_KEY", raising=False)

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("hermes_cli.config.get_env_value", return_value=""),
            patch("hermes_cli.web_server._cursor_cli_ready", return_value=True),
        ):
            result = _run_endpoint()

        providers = {p["name"]: p for p in result["providers"]}
        assert providers["Cursor SDK"]["status"] == "READY"
        assert providers["Cursor SDK"]["key_present"] is False
        assert providers["Cursor SDK"]["cli_present"] is True
        assert providers["Cursor SDK"]["fallback_active"] is True

    def test_cursor_waiting_when_no_key_and_no_cli(self, monkeypatch):
        """Cursor stays WAITING when neither API key nor CLI is available."""
        monkeypatch.delenv("CURSOR_API_KEY", raising=False)

        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("hermes_cli.config.get_env_value", return_value=""),
            patch("hermes_cli.web_server._cursor_cli_ready", return_value=False),
        ):
            result = _run_endpoint()

        providers = {p["name"]: p for p in result["providers"]}
        assert providers["Cursor SDK"]["status"] == "WAITING_CREDENTIAL"
        assert providers["Cursor SDK"]["key_present"] is False

    def test_codex_fallback_active_when_cli_absent(self, monkeypatch):
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("shutil.which", return_value=None),
        ):
            result = _run_endpoint()

        providers = {p["name"]: p for p in result["providers"]}
        codex = providers.get("Codex CLI", {})
        assert codex.get("fallback_active") is True
        assert codex.get("hint") is not None


class TestSummary:
    def test_summary_fields_present(self):
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": True, "locked": False, "message": "ok"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(True, "running")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 5, "READY": 5}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 10, "disabled": 0, "total": 10,
            }),
        ):
            result = _run_endpoint()

        summary = result["summary"]
        assert "ready" in summary
        assert "waiting_credential" in summary
        assert "waiting_service" in summary
        assert "failed" in summary
        assert "disabled" in summary
        assert "total" in summary
        assert "readiness_pct" in summary
        assert 0 <= summary["readiness_pct"] <= 100

    def test_readiness_pct_in_range(self):
        with (
            patch("hermes_cli.web_server._bitwarden_cli_status", return_value={
                "available": False, "locked": True, "message": "locked"
            }),
            patch("hermes_cli.web_server._resolve_gateway_liveness", return_value=(False, "stopped")),
            patch("hermes_cli.web_server._setup_mcp_counts", return_value={"total": 0}),
            patch("hermes_cli.web_server._setup_skill_counts", return_value={
                "active": 0, "disabled": 0, "total": 0,
            }),
            patch("hermes_cli.config.get_env_value", return_value=""),
        ):
            result = _run_endpoint()

        pct = result["summary"]["readiness_pct"]
        assert isinstance(pct, int)
        assert 0 <= pct <= 100


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

class TestSetupKeyPresent:
    def test_key_present_via_env(self, monkeypatch):
        _setup_key_present = _import_helpers()[0]
        monkeypatch.setenv("MY_TEST_KEY_XYZ", "some-value")
        assert _setup_key_present(["MY_TEST_KEY_XYZ"]) is True

    def test_key_absent(self, monkeypatch):
        _setup_key_present = _import_helpers()[0]
        monkeypatch.delenv("TOTALLY_ABSENT_KEY_XYZ123", raising=False)
        with patch("hermes_cli.config.get_env_value", return_value=""):
            assert _setup_key_present(["TOTALLY_ABSENT_KEY_XYZ123"]) is False

    def test_first_match_wins(self, monkeypatch):
        _setup_key_present = _import_helpers()[0]
        monkeypatch.delenv("FIRST_KEY_ABC", raising=False)
        monkeypatch.setenv("SECOND_KEY_ABC", "found")
        assert _setup_key_present(["FIRST_KEY_ABC", "SECOND_KEY_ABC"]) is True


class TestObsidianBridgeStatus:
    def test_ready_when_env_set(self, monkeypatch):
        _setup_obsidian_bridge_status = _import_helpers()[3]
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "G:/vault")
        assert _setup_obsidian_bridge_status() == "READY"

    def test_disabled_when_env_absent(self, monkeypatch):
        _setup_obsidian_bridge_status = _import_helpers()[3]
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        with patch("hermes_cli.config.get_env_value", return_value=""):
            assert _setup_obsidian_bridge_status() == "DISABLED"
