"""Tests for agent/cursor_cli_runtime.py — Cursor CLI subprocess provider.

These tests are fully offline: subprocess.run is monkeypatched so no real
cursor-agent binary is needed.
"""

from __future__ import annotations

import subprocess
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.cursor_cli_runtime import (
    DEFAULT_CURSOR_BIN,
    _build_context_prompt,
    _find_cursor_bin,
    run_cursor_cli_turn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(**kwargs: Any):
    """Minimal agent stand-in sufficient for the runtime functions."""
    agent = MagicMock()
    agent.api_mode = "cursor_cli"
    for k, v in kwargs.items():
        setattr(agent, k, v)
    return agent


def _ok_proc(stdout: str = "Hello from Cursor") -> types.SimpleNamespace:
    return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _err_proc(rc: int = 1, stderr: str = "boom") -> types.SimpleNamespace:
    return types.SimpleNamespace(returncode=rc, stdout="", stderr=stderr)


# ---------------------------------------------------------------------------
# _build_context_prompt
# ---------------------------------------------------------------------------

class TestBuildContextPrompt:
    def test_simple_user_message(self):
        prompt = _build_context_prompt([], "Hello?")
        assert "Human: Hello?" in prompt
        assert "Assistant:" in prompt

    def test_system_message_appears_at_top(self):
        messages = [{"role": "system", "content": "You are helpful."}]
        prompt = _build_context_prompt(messages, "Hi")
        assert "[SYSTEM CONTEXT]" in prompt
        assert "You are helpful." in prompt
        assert prompt.index("[SYSTEM CONTEXT]") < prompt.index("Human: Hi")

    def test_multi_turn_history(self):
        messages = [
            {"role": "user", "content": "Who are you?"},
            {"role": "assistant", "content": "I am Hermes."},
        ]
        prompt = _build_context_prompt(messages, "Next question")
        assert "Human: Who are you?" in prompt
        assert "Assistant: I am Hermes." in prompt
        assert "Human: Next question" in prompt

    def test_list_content_blocks_text_extracted(self):
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Block content"}],
            }
        ]
        prompt = _build_context_prompt(messages, "Follow-up")
        assert "Block content" in prompt

    def test_tool_call_assistant_noted_inline(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "shell_exec"}},
                ],
            }
        ]
        prompt = _build_context_prompt(messages, "Done?")
        assert "[used tools: shell_exec]" in prompt

    def test_large_history_is_truncated(self):
        """History budget (8 KB) is enforced; system + current turn preserved."""
        from agent.cursor_cli_runtime import _HISTORY_MAX_CHARS, _TRUNCATION_MARKER

        system_msg = {"role": "system", "content": "System: " + "S" * 3000}
        big_history = [
            {"role": "user", "content": "Q" * 500},
            {"role": "assistant", "content": "A" * 500},
        ] * 20  # > 8 KB
        current_turn = "Current question"
        prompt = _build_context_prompt([system_msg] + big_history, current_turn)
        assert "[SYSTEM CONTEXT]" in prompt
        assert f"Human: {current_turn}" in prompt
        assert _TRUNCATION_MARKER in prompt

    def test_system_and_current_turn_never_truncated(self):
        """System prompt and current user turn must survive regardless of history size."""
        long_system = "SYSPROMPT" * 5000  # >> 8 KB
        messages = [
            {"role": "system", "content": long_system},
            *[{"role": "user", "content": "pad " * 100}] * 50,
        ]
        current = "THE_CURRENT_QUESTION"
        prompt = _build_context_prompt(messages, current)
        assert long_system in prompt
        assert f"Human: {current}" in prompt


# ---------------------------------------------------------------------------
# _find_cursor_bin
# ---------------------------------------------------------------------------

class TestFindCursorBin:
    def test_default_name_resolved_via_which(self, tmp_path):
        fake_bin = str(tmp_path / "cursor-agent")
        with patch("agent.cursor_cli_runtime.shutil.which", return_value=fake_bin):
            agent = _make_agent()
            assert _find_cursor_bin(agent) == fake_bin

    def test_windows_cmd_resolved_via_which(self, tmp_path):
        """shutil.which handles PATHEXT and returns cursor-agent.cmd on Windows."""
        fake_cmd = str(tmp_path / "cursor-agent.cmd")
        with patch("agent.cursor_cli_runtime.shutil.which", return_value=fake_cmd):
            agent = _make_agent()
            result = _find_cursor_bin(agent)
        assert result == fake_cmd

    def test_absolute_path_override(self, tmp_path):
        fake_bin = tmp_path / "my-cursor-agent"
        fake_bin.write_text("#!/bin/sh\necho hello")
        agent = _make_agent(cursor_bin=str(fake_bin))
        with patch("agent.cursor_cli_runtime.shutil.which") as mock_which:
            result = _find_cursor_bin(agent)
        assert result == str(fake_bin)
        mock_which.assert_not_called()

    def test_returns_none_when_not_found(self):
        with patch("agent.cursor_cli_runtime.shutil.which", return_value=None):
            agent = _make_agent()
            assert _find_cursor_bin(agent) is None


# ---------------------------------------------------------------------------
# run_cursor_cli_turn — success path
# ---------------------------------------------------------------------------

class TestRunCursorCliTurnSuccess:
    def test_returns_expected_shape(self):
        agent = _make_agent()
        messages: list = []
        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/usr/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", return_value=_ok_proc("Answer")),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=messages,
                effective_task_id="t1",
            )
        assert result["completed"] is True
        assert result["final_response"] == "Answer"
        assert result["error"] is None
        assert result["api_calls"] == 1

    def test_appends_assistant_message(self):
        agent = _make_agent()
        messages: list = []
        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/usr/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", return_value=_ok_proc("Reply")),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Q",
                original_user_message="Q",
                messages=messages,
                effective_task_id="t1",
            )
        assert any(m.get("role") == "assistant" for m in result["messages"])

    def test_cmd_includes_print_flag_and_trust(self):
        agent = _make_agent()
        calls: list = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _ok_proc()

        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", side_effect=fake_run),
        ):
            run_cursor_cli_turn(
                agent,
                user_message="test",
                original_user_message="test",
                messages=[],
                effective_task_id="t1",
            )
        assert len(calls) == 1
        cmd = calls[0]
        assert "-p" in cmd
        assert "--trust" in cmd
        assert "--output-format" in cmd
        assert "text" in cmd

    def test_model_override_is_passed(self):
        agent = _make_agent(cursor_cli_model="cursor-small")
        calls: list = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _ok_proc()

        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", side_effect=fake_run),
        ):
            run_cursor_cli_turn(
                agent,
                user_message="test",
                original_user_message="test",
                messages=[],
                effective_task_id="t1",
            )
        cmd = calls[0]
        assert "--model" in cmd
        assert "cursor-small" in cmd

    def test_empty_output_is_partial(self):
        agent = _make_agent()
        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", return_value=_ok_proc("")),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Q",
                original_user_message="Q",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is True
        assert "empty" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# run_cursor_cli_turn — error paths
# ---------------------------------------------------------------------------

class TestRunCursorCliTurnErrors:
    def test_clear_error_when_binary_absent(self):
        """Clear actionable message emitted when cursor-agent is not on PATH."""
        agent = _make_agent()
        with patch("agent.cursor_cli_runtime.shutil.which", return_value=None):
            result = run_cursor_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        err = result["error"] or result["final_response"]
        # Must mention cursor-agent + actionable install/login hint.
        assert "cursor-agent" in err.lower() or "cursor" in err.lower()
        assert "login" in err.lower() or "instale" in err.lower() or "install" in err.lower()

    def test_oserror_winerror2_gives_actionable_message(self):
        """WinError 2 (binary not executable) → clear message, no raw OSError."""
        agent = _make_agent()
        exc = OSError()
        exc.errno = 2

        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", side_effect=exc),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert result["api_calls"] == 0

    def test_timeout_returns_failure(self):
        agent = _make_agent()
        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch(
                "agent.cursor_cli_runtime.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="cursor-agent", timeout=120),
            ),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert "timeout" in (result.get("error") or "").lower() or "timed" in (result.get("final_response") or "").lower()

    def test_nonzero_exit_with_auth_hint(self):
        """Non-zero exit with 'login' in stderr → actionable auth message."""
        agent = _make_agent()
        err_p = types.SimpleNamespace(
            returncode=1, stdout="", stderr="not logged in — please run cursor-agent login"
        )
        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", return_value=err_p),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        err = result["error"] or result["final_response"]
        assert "login" in err.lower() or "autenticado" in err.lower()

    def test_nonzero_exit_generic(self):
        agent = _make_agent()
        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", return_value=_err_proc(1, "something bad")),
        ):
            result = run_cursor_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert "1" in result.get("error", "")


# ---------------------------------------------------------------------------
# Prompt structure: system prompt + current turn always preserved
# ---------------------------------------------------------------------------

class TestPromptPreservesCriticalParts:
    def test_system_and_current_turn_in_prompt_sent_to_binary(self):
        """The cmd passed to cursor-agent must contain the system prompt and
        the current user message — regardless of history size."""
        agent = _make_agent()
        big_history = [{"role": "user", "content": "pad " * 200}] * 30
        system_msg = {"role": "system", "content": "SENTINEL_SYSTEM"}
        messages = [system_msg] + big_history
        current = "SENTINEL_CURRENT"
        captured_cmd: list = []

        def fake_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return _ok_proc("ok")

        with (
            patch("agent.cursor_cli_runtime.shutil.which", return_value="/bin/cursor-agent"),
            patch("agent.cursor_cli_runtime.subprocess.run", side_effect=fake_run),
        ):
            run_cursor_cli_turn(
                agent,
                user_message=current,
                original_user_message=current,
                messages=messages,
                effective_task_id="t1",
            )

        # The prompt is the last element of cmd (positional arg).
        full_cmd_str = " ".join(captured_cmd)
        assert "SENTINEL_SYSTEM" in full_cmd_str
        assert current in full_cmd_str
