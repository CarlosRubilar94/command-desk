"""Tests for the MCP Control Center API endpoint and supporting helpers.

Covers:
- /api/mcp/control-center status resolution (_resolve_server_status)
- Bitwarden locked/unlocked state reporting
- Env var redaction (no secret leakage)
- Windows-only servers on non-Windows
- Credential-waiting detection
- No secret values in any response field
"""

import json
import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers imported from the module under test
# ---------------------------------------------------------------------------


def _import_helpers():
    from hermes_cli.web_server import (
        _bw_status,
        _is_platform_windows,
        _redact_mcp_env,
        _resolve_server_status,
        _WINDOWS_ONLY_SERVERS,
        _CREDENTIAL_ENV_HINTS,
        _BITWARDEN_DEPENDENT_SERVERS,
        _MCP_STATUS_READY,
        _MCP_STATUS_DISABLED,
        _MCP_STATUS_WAITING_CREDENTIAL,
        _MCP_STATUS_WAITING_SERVICE,
        _MCP_STATUS_WAITING_BITWARDEN,
    )
    # Returns tuple indexed as:
    # [0] _bw_status
    # [1] _is_platform_windows
    # [2] _redact_mcp_env
    # [3] _resolve_server_status
    # [4] _WINDOWS_ONLY_SERVERS
    # [5] _CREDENTIAL_ENV_HINTS
    # [6] _BITWARDEN_DEPENDENT_SERVERS
    # [7] _MCP_STATUS_READY
    # [8] _MCP_STATUS_DISABLED
    # [9] _MCP_STATUS_WAITING_CREDENTIAL
    # [10] _MCP_STATUS_WAITING_SERVICE
    # [11] _MCP_STATUS_WAITING_BITWARDEN
    return (
        _bw_status,
        _is_platform_windows,
        _redact_mcp_env,
        _resolve_server_status,
        _WINDOWS_ONLY_SERVERS,
        _CREDENTIAL_ENV_HINTS,
        _BITWARDEN_DEPENDENT_SERVERS,
        _MCP_STATUS_READY,
        _MCP_STATUS_DISABLED,
        _MCP_STATUS_WAITING_CREDENTIAL,
        _MCP_STATUS_WAITING_SERVICE,
        _MCP_STATUS_WAITING_BITWARDEN,
    )


# ---------------------------------------------------------------------------
# Env redaction — no secret leakage
# ---------------------------------------------------------------------------


class TestRedactMcpEnv:
    def test_redacts_values(self):
        _redact_mcp_env = _import_helpers()[2]
        # Use a long secret that mask_secret will definitely abbreviate.
        raw = {"API_KEY": "sk-" + "x" * 40, "DEBUG": "1"}
        redacted = _redact_mcp_env(raw)
        assert "API_KEY" in redacted
        # The value is masked (partial display), not the literal full secret.
        assert redacted["API_KEY"] != "sk-" + "x" * 40

    def test_keys_preserved(self):
        _redact_mcp_env = _import_helpers()[2]
        raw = {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxx", "FOO": "bar"}
        redacted = _redact_mcp_env(raw)
        assert set(redacted.keys()) == {"GITHUB_PERSONAL_ACCESS_TOKEN", "FOO"}

    def test_empty_env(self):
        _redact_mcp_env = _import_helpers()[2]
        assert _redact_mcp_env({}) == {}

    def test_no_secret_in_values(self):
        _redact_mcp_env = _import_helpers()[2]
        raw = {"SECRET": "top-secret-value-abc123"}
        redacted = _redact_mcp_env(raw)
        assert "top-secret-value-abc123" not in json.dumps(redacted)


# ---------------------------------------------------------------------------
# Status resolution
# ---------------------------------------------------------------------------


class TestResolveServerStatus:
    def test_disabled_server(self):
        _resolve_server_status = _import_helpers()[3]
        status = _resolve_server_status("github", {"enabled": False}, bw_locked=False)
        assert status == "DISABLED"

    def test_bitwarden_dependent_when_locked(self):
        _resolve_server_status = _import_helpers()[3]
        status = _resolve_server_status("github", {"enabled": True}, bw_locked=True)
        assert status == "WAITING_BITWARDEN"

    def test_bitwarden_dependent_when_unlocked_no_env(self, monkeypatch):
        _resolve_server_status = _import_helpers()[3]
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        with patch("hermes_cli.web_server._is_platform_windows", return_value=True):
            with patch("hermes_cli.config.get_env_value", return_value=None):
                status = _resolve_server_status(
                    "github", {"enabled": True}, bw_locked=False
                )
        assert status == "WAITING_CREDENTIAL"

    def test_windows_only_on_linux(self):
        _resolve_server_status = _import_helpers()[3]
        with patch("hermes_cli.web_server._is_platform_windows", return_value=False):
            status = _resolve_server_status(
                "windows-admin", {"enabled": True}, bw_locked=False
            )
        assert status == "WAITING_SERVICE"

    def test_windows_only_on_windows(self):
        _resolve_server_status = _import_helpers()[3]
        with patch("hermes_cli.web_server._is_platform_windows", return_value=True):
            status = _resolve_server_status(
                "windows-admin", {"enabled": True}, bw_locked=False
            )
        # windows-admin has no CREDENTIAL_ENV_HINTS → READY on Windows
        assert status == "READY"

    def test_ready_when_credential_present(self, monkeypatch):
        _resolve_server_status = _import_helpers()[3]
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
        with patch("hermes_cli.web_server._is_platform_windows", return_value=True):
            status = _resolve_server_status(
                "openrouter", {"enabled": True}, bw_locked=False
            )
        assert status == "READY"

    def test_no_credential_required_server(self):
        _resolve_server_status = _import_helpers()[3]
        with patch("hermes_cli.web_server._is_platform_windows", return_value=True):
            status = _resolve_server_status(
                "project-inspector", {"enabled": True}, bw_locked=True
            )
        assert status == "READY"


# ---------------------------------------------------------------------------
# Bitwarden status helper
# ---------------------------------------------------------------------------


class TestBwStatus:
    def test_bw_not_installed(self):
        _bw_status = _import_helpers()[0]
        with patch("shutil.which", return_value=None):
            result = _bw_status()
        assert result["status"] == "not_installed"
        assert result["locked"] is True

    def test_bw_unauthenticated(self):
        _bw_status = _import_helpers()[0]
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps({"status": "unauthenticated"})
        with patch("shutil.which", return_value="/usr/bin/bw"):
            with patch("subprocess.run", return_value=mock_proc):
                result = _bw_status()
        assert result["status"] == "unauthenticated"
        assert result["locked"] is True

    def test_bw_unlocked(self):
        _bw_status = _import_helpers()[0]
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps({"status": "unlocked"})
        with patch("shutil.which", return_value="/usr/bin/bw"):
            with patch("subprocess.run", return_value=mock_proc):
                result = _bw_status()
        assert result["status"] == "unlocked"
        assert result["locked"] is False

    def test_bw_timeout_returns_unknown(self):
        _bw_status = _import_helpers()[0]
        import subprocess
        with patch("shutil.which", return_value="/usr/bin/bw"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("bw", 5)):
                result = _bw_status()
        assert result["locked"] is True


# ---------------------------------------------------------------------------
# Control center invariants
# ---------------------------------------------------------------------------


class TestControlCenterInvariants:
    """Structural invariants for _resolve_server_status."""

    def test_disabled_always_disabled(self):
        _resolve_server_status = _import_helpers()[3]
        for name in ["github", "vercel", "project-inspector", "ssh-servers"]:
            status = _resolve_server_status(name, {"enabled": False}, bw_locked=True)
            assert status == "DISABLED", f"{name}: expected DISABLED, got {status}"

    def test_catalog_manifests_have_valid_auth(self):
        """Every optional-mcps manifest has a known auth type."""
        import yaml
        from pathlib import Path as P
        manifest_dir = P(__file__).parent.parent.parent / "optional-mcps"
        if not manifest_dir.exists():
            pytest.skip("optional-mcps dir not present")
        valid_auth = {"api_key", "oauth", "none"}
        for manifest_file in manifest_dir.rglob("manifest.yaml"):
            data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
            auth = data.get("auth", {})
            auth_type = auth.get("type", "none")
            assert auth_type in valid_auth, (
                f"{manifest_file}: unknown auth type '{auth_type}'"
            )

    def test_catalog_manifests_have_transport(self):
        """Every manifest declares a transport type."""
        import yaml
        from pathlib import Path as P
        manifest_dir = P(__file__).parent.parent.parent / "optional-mcps"
        if not manifest_dir.exists():
            pytest.skip("optional-mcps dir not present")
        valid_transport = {"stdio", "http"}
        for manifest_file in manifest_dir.rglob("manifest.yaml"):
            data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
            transport = data.get("transport", {})
            t_type = transport.get("type", "")
            assert t_type in valid_transport, (
                f"{manifest_file}: unknown transport type '{t_type}'"
            )

    def test_bitwarden_dependent_servers_subset_of_credential_hints(self):
        """All Bitwarden-dependent servers also have credential env hints."""
        helpers = _import_helpers()
        # helpers order: _bw_status, _is_platform_windows, _redact_mcp_env,
        # _resolve_server_status, _WINDOWS_ONLY_SERVERS, _CREDENTIAL_ENV_HINTS,
        # _BITWARDEN_DEPENDENT_SERVERS, ...
        _WINDOWS_ONLY_SERVERS = helpers[4]
        _CREDENTIAL_ENV_HINTS = helpers[5]
        _BITWARDEN_DEPENDENT_SERVERS = helpers[6]
        # Bitwarden-dependent servers should have credential hints OR be bitwarden itself.
        for name in _BITWARDEN_DEPENDENT_SERVERS:
            if name == "bitwarden":
                continue
            assert name in _CREDENTIAL_ENV_HINTS, (
                f"Bitwarden-dependent server '{name}' has no credential hint"
            )
