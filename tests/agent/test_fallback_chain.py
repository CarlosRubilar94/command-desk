"""Tests for the extended fallback chain in agent/claude_cli_runtime.py.

Chain logic: claude fails → openai-codex → cursor-cli (each tries in order).
Covers:
- Chain default (openai-codex,cursor-cli)
- Codex fails → cursor succeeds
- Codex absent → cursor succeeds
- Codex absent + cursor absent → all-failed result
- Single-value config (backward compat)
- Disable ("none")
- Chain ordering
"""

from __future__ import annotations

import subprocess
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.claude_cli_runtime import (
    _resolve_codex_fallback,
    _resolve_fallback_chain,
    run_claude_cli_turn,
    _is_usage_limit_error,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(**kwargs: Any):
    agent = MagicMock()
    agent.api_mode = "claude_cli"
    for k, v in kwargs.items():
        setattr(agent, k, v)
    return agent


def _ok_proc(stdout: str = "Claude reply") -> types.SimpleNamespace:
    return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _err_proc(rc: int = 1, stderr: str = "boom") -> types.SimpleNamespace:
    return types.SimpleNamespace(returncode=rc, stdout="", stderr=stderr)


def _cursor_ok(text: str = "Cursor answer") -> dict:
    return {
        "final_response": text,
        "messages": [],
        "api_calls": 1,
        "completed": True,
        "partial": False,
        "error": None,
    }


def _cursor_fail(error: str = "cursor-agent error") -> dict:
    return {
        "final_response": f"[cursor-cli error] {error}",
        "messages": [],
        "api_calls": 0,
        "completed": False,
        "partial": True,
        "error": error,
    }


def _codex_ok(text: str = "Codex answer") -> dict:
    return {
        "final_response": text,
        "messages": [],
        "api_calls": 1,
        "completed": True,
        "partial": False,
        "error": None,
    }


def _codex_fail(error: str = "codex boom") -> dict:
    return {
        "final_response": "[codex dead]",
        "messages": [],
        "api_calls": 0,
        "completed": False,
        "partial": True,
        "error": error,
    }


_LIMIT_STDERR = "You've hit your session limit · resets 7:50pm (America/Sao_Paulo)"


# ---------------------------------------------------------------------------
# _resolve_fallback_chain
# ---------------------------------------------------------------------------

class TestResolveFallbackChain:
    def test_default_chain_when_attr_absent(self):
        agent = _make_agent()
        del agent.claude_cli_fallback  # no attr → use default
        chain = _resolve_fallback_chain(agent)
        assert chain == ["openai-codex", "cursor-cli"]

    def test_single_codex_value_backward_compat(self):
        agent = _make_agent(claude_cli_fallback="openai-codex")
        chain = _resolve_fallback_chain(agent)
        assert chain == ["openai-codex"]

    def test_single_cursor_value(self):
        agent = _make_agent(claude_cli_fallback="cursor-cli")
        chain = _resolve_fallback_chain(agent)
        assert chain == ["cursor-cli"]

    def test_comma_separated_chain(self):
        agent = _make_agent(claude_cli_fallback="openai-codex,cursor-cli")
        chain = _resolve_fallback_chain(agent)
        assert chain == ["openai-codex", "cursor-cli"]

    def test_reverse_order(self):
        agent = _make_agent(claude_cli_fallback="cursor-cli,openai-codex")
        chain = _resolve_fallback_chain(agent)
        assert chain == ["cursor-cli", "openai-codex"]

    @pytest.mark.parametrize("val", ["none", "", "off", "false", "0", "disabled"])
    def test_disabled_values_return_empty(self, val):
        agent = _make_agent(claude_cli_fallback=val)
        assert _resolve_fallback_chain(agent) == []

    def test_codex_aliases_in_chain(self):
        agent = _make_agent(claude_cli_fallback="codex,cursor-cli")
        chain = _resolve_fallback_chain(agent)
        assert chain == ["openai-codex", "cursor-cli"]

    def test_cursor_alias_in_chain(self):
        agent = _make_agent(claude_cli_fallback="cursor,openai-codex")
        chain = _resolve_fallback_chain(agent)
        assert chain == ["cursor-cli", "openai-codex"]

    def test_duplicates_deduplicated(self):
        agent = _make_agent(claude_cli_fallback="openai-codex,codex,cursor-cli")
        chain = _resolve_fallback_chain(agent)
        assert chain.count("openai-codex") == 1

    def test_magicmock_treated_as_disabled(self):
        """A bare MagicMock agent returns non-string → chain disabled."""
        agent = _make_agent()
        assert _resolve_fallback_chain(agent) == []

    def test_unknown_tokens_skipped_with_warning(self):
        agent = _make_agent(claude_cli_fallback="unknown-provider,cursor-cli")
        chain = _resolve_fallback_chain(agent)
        assert "unknown-provider" not in chain
        assert "cursor-cli" in chain


# ---------------------------------------------------------------------------
# _resolve_codex_fallback — backward-compat (returns first entry or "")
# ---------------------------------------------------------------------------

class TestResolveCodexFallbackCompat:
    def test_default_returns_openai_codex(self):
        agent = _make_agent()
        del agent.claude_cli_fallback
        assert _resolve_codex_fallback(agent) == "openai-codex"

    def test_disabled_returns_empty(self):
        agent = _make_agent(claude_cli_fallback="none")
        assert _resolve_codex_fallback(agent) == ""

    def test_cursor_only_returns_cursor_cli(self):
        agent = _make_agent(claude_cli_fallback="cursor-cli")
        assert _resolve_codex_fallback(agent) == "cursor-cli"


# ---------------------------------------------------------------------------
# Chain execution: claude fails → codex → cursor
# ---------------------------------------------------------------------------

class TestFallbackChainExecution:
    def test_codex_success_chain_stops(self):
        """When Codex succeeds, cursor-cli must NOT be tried."""
        agent = _make_agent(claude_cli_fallback="openai-codex,cursor-cli")
        agent._run_codex_app_server_turn = MagicMock(return_value=_codex_ok("Codex win"))

        cursor_run = MagicMock()
        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
            patch("agent.cursor_cli_runtime.run_cursor_cli_turn", cursor_run),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        agent._run_codex_app_server_turn.assert_called_once()
        cursor_run.assert_not_called()
        assert result["completed"] is True
        assert "Codex win" in result["final_response"]

    def test_codex_absent_cursor_succeeds(self):
        """When Codex CLI is absent (FileNotFoundError), try cursor-cli."""
        agent = _make_agent(claude_cli_fallback="openai-codex,cursor-cli")
        agent._run_codex_app_server_turn = MagicMock(
            side_effect=FileNotFoundError(2, "não encontrado")
        )

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
            patch(
                "agent.cursor_cli_runtime.run_cursor_cli_turn",
                return_value=_cursor_ok("Cursor saved the day"),
            ),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        assert result["completed"] is True
        assert "Cursor saved the day" in result["final_response"]

    def test_codex_winerror2_cursor_succeeds(self):
        """WinError 2 from Codex → continue chain to cursor-cli."""
        agent = _make_agent(claude_cli_fallback="openai-codex,cursor-cli")
        exc = OSError()
        exc.errno = 2
        agent._run_codex_app_server_turn = MagicMock(side_effect=exc)

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr="boom")),
            patch(
                "agent.cursor_cli_runtime.run_cursor_cli_turn",
                return_value=_cursor_ok("Cursor backup"),
            ),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        assert result["completed"] is True
        assert "Cursor backup" in result["final_response"]

    def test_codex_absent_cursor_absent_all_failed(self):
        """When both Codex and cursor-cli are absent, surface a combined error."""
        agent = _make_agent(claude_cli_fallback="openai-codex,cursor-cli")
        agent._run_codex_app_server_turn = MagicMock(
            side_effect=FileNotFoundError(2, "não encontrado")
        )

        cursor_fail_result = _cursor_fail("Cursor CLI (cursor-agent) não encontrado no PATH")

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
            patch(
                "agent.cursor_cli_runtime.run_cursor_cli_turn",
                return_value=cursor_fail_result,
            ),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        assert result["completed"] is False
        # Must surface the cursor-cli install hint.
        combined = (result.get("error") or "") + (result.get("final_response") or "")
        assert "cursor" in combined.lower()

    def test_chain_disabled_shows_original_error(self):
        """When chain is disabled, original claude-cli error is surfaced."""
        agent = _make_agent(claude_cli_fallback="none")
        agent._run_codex_app_server_turn = MagicMock()

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        agent._run_codex_app_server_turn.assert_not_called()
        assert result["completed"] is False
        assert "[claude-cli error]" in result["final_response"]

    def test_single_codex_value_backward_compat_still_works(self):
        """A single 'openai-codex' value (old config) still triggers Codex only."""
        agent = _make_agent(claude_cli_fallback="openai-codex")
        agent._run_codex_app_server_turn = MagicMock(return_value=_codex_ok("Old-style codex"))

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr="boom")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        assert result["completed"] is True
        assert "Old-style codex" in result["final_response"]

    def test_cursor_only_fallback(self):
        """Chain with only cursor-cli: success."""
        agent = _make_agent(claude_cli_fallback="cursor-cli")
        agent._run_codex_app_server_turn = MagicMock()

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr="boom")),
            patch(
                "agent.cursor_cli_runtime.run_cursor_cli_turn",
                return_value=_cursor_ok("Cursor only"),
            ),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        agent._run_codex_app_server_turn.assert_not_called()
        assert result["completed"] is True
        assert "Cursor only" in result["final_response"]
