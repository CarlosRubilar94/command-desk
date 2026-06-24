"""Tests for agent/claude_cli_runtime.py — Claude Code CLI subprocess provider.

These tests are fully offline: subprocess.run is monkeypatched so no real
claude binary is needed.
"""

from __future__ import annotations

import subprocess
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.claude_cli_runtime import (
    DEFAULT_CLAUDE_BIN,
    _build_context_prompt,
    _find_claude_bin,
    _is_usage_limit_error,
    _resolve_codex_fallback,
    run_claude_cli_turn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(**kwargs: Any):
    """Minimal AIAgent stand-in sufficient for the runtime functions."""
    agent = MagicMock()
    agent.api_mode = "claude_cli"
    for k, v in kwargs.items():
        setattr(agent, k, v)
    return agent


def _ok_proc(stdout: str = "Hello from Claude") -> types.SimpleNamespace:
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
        # System block must precede the Human turn
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

    def test_tool_result_in_content_block(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "output text",
                    }
                ],
            }
        ]
        prompt = _build_context_prompt(messages, "Next")
        assert "[tool-result t1:" in prompt
        assert "output text" in prompt

    def test_prompt_truncated_when_over_limit(self):
        long_body = "x" * 30_000
        messages = [{"role": "user", "content": long_body}]
        prompt = _build_context_prompt(messages, "Short follow-up")
        # History is truncated, but the current user turn is preserved, so the
        # total stays within the history budget plus the small current turn.
        assert len(prompt) < 30_000
        assert "Human: Short follow-up" in prompt

    def test_large_system_prompt_never_drops_current_turn(self):
        # Regression: a system prompt larger than _HISTORY_MAX_CHARS previously
        # drove keep_tail negative and truncated away the user's actual
        # question. The system prompt and current turn must both survive.
        big_system = "S" * 61_525
        messages = [{"role": "system", "content": big_system}]
        prompt = _build_context_prompt(messages, "What is my balance?")
        assert big_system in prompt  # system prompt preserved in full
        assert "Human: What is my balance?" in prompt  # current turn preserved
        assert prompt.rstrip().endswith("Assistant:")

    def test_large_system_prompt_truncates_only_middle_history(self):
        big_system = "S" * 61_525
        messages = [
            {"role": "system", "content": big_system},
            {"role": "user", "content": "OLD-OLDEST " + ("h" * 30_000)},
            {"role": "assistant", "content": "older reply"},
        ]
        prompt = _build_context_prompt(messages, "latest question")
        # System + current turn intact; oldest history trimmed from the front.
        assert big_system in prompt
        assert "Human: latest question" in prompt
        assert "[...earlier turns truncated...]" in prompt
        assert "OLD-OLDEST" not in prompt


# ---------------------------------------------------------------------------
# _find_claude_bin
# ---------------------------------------------------------------------------

class TestFindClaudeBin:
    def test_finds_binary_on_path(self):
        agent = _make_agent()
        del agent.claude_bin  # not set
        with patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"):
            assert _find_claude_bin(agent) == "/usr/bin/claude"

    def test_returns_none_when_not_found(self):
        agent = _make_agent()
        del agent.claude_bin
        with patch("agent.claude_cli_runtime.shutil.which", return_value=None):
            assert _find_claude_bin(agent) is None

    def test_custom_bin_attribute_used(self):
        agent = _make_agent(claude_bin="/custom/claude")
        with (
            patch("agent.claude_cli_runtime.os.path.sep", "/"),
            patch("agent.claude_cli_runtime.os.path.exists", return_value=True),
        ):
            assert _find_claude_bin(agent) == "/custom/claude"


# ---------------------------------------------------------------------------
# run_claude_cli_turn — happy path
# ---------------------------------------------------------------------------

class TestRunClaudeCliTurnHappy:
    def test_returns_final_response(self):
        agent = _make_agent()
        messages: list = []

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_ok_proc("World!")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=messages,
                effective_task_id="t1",
            )

        assert result["final_response"] == "World!"
        assert result["completed"] is True
        assert result["error"] is None
        assert result["api_calls"] == 1

    def test_assistant_message_appended(self):
        agent = _make_agent()
        messages: list = []

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_ok_proc("Hi")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=messages,
                effective_task_id="t1",
            )

        assert any(
            m.get("role") == "assistant" and "Hi" in m.get("content", "")
            for m in result["messages"]
        )

    def test_subprocess_receives_disallowed_tools_flag(self):
        agent = _make_agent()
        captured: dict = {}

        def fake_run(cmd, **_):
            captured["cmd"] = cmd
            return _ok_proc("ok")

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            run_claude_cli_turn(
                agent,
                user_message="test",
                original_user_message="test",
                messages=[],
                effective_task_id="t1",
            )

        cmd = captured["cmd"]
        assert "--disallowedTools" in cmd
        assert "*" in cmd
        assert "--no-session-persistence" in cmd
        assert "-p" in cmd

    def test_model_override_passed_when_set(self):
        agent = _make_agent(claude_cli_model="claude-opus-4-8")
        captured: dict = {}

        def fake_run(cmd, **_):
            captured["cmd"] = cmd
            return _ok_proc("ok")

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            run_claude_cli_turn(
                agent,
                user_message="test",
                original_user_message="test",
                messages=[],
                effective_task_id="t1",
            )

        cmd = captured["cmd"]
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-opus-4-8"


# ---------------------------------------------------------------------------
# run_claude_cli_turn — error paths
# ---------------------------------------------------------------------------

class TestRunClaudeCliTurnErrors:
    def test_binary_not_found(self):
        agent = _make_agent()
        with patch("agent.claude_cli_runtime.shutil.which", return_value=None):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert "not found" in result["final_response"].lower()
        assert result["api_calls"] == 0

    def test_nonzero_exit_code(self):
        agent = _make_agent()
        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=2, stderr="auth failed")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert "claude-cli error" in result["final_response"]
        assert "auth failed" in result["final_response"] or result["error"]

    def test_timeout_handling(self):
        agent = _make_agent()

        def slow_run(*_, **__):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=slow_run),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert "timed out" in result["final_response"].lower()

    def test_oserror_handling(self):
        agent = _make_agent()

        def bad_run(*_, **__):
            raise OSError("permission denied")

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=bad_run),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )
        assert result["completed"] is False
        assert "permission denied" in result["final_response"].lower()

    def test_empty_output_graceful(self):
        agent = _make_agent()
        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_ok_proc("")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )
        # Empty response is not a hard failure, but error is recorded.
        assert "(empty response)" in result["final_response"]
        assert result["error"] is not None


# ---------------------------------------------------------------------------
# Usage-limit detection + fallback target resolution (pure helpers)
# ---------------------------------------------------------------------------

class TestUsageLimitDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "You've hit your session limit · resets 7:50pm (America/Sao_Paulo)",
            "Usage limit reached",
            "RATE LIMIT exceeded",
            "rate-limit hit",
            "429 Too Many Requests",
            "your quota has been exhausted",
            "You've reached your limit for today",
        ],
    )
    def test_detects_limit(self, text):
        assert _is_usage_limit_error(text) is True

    @pytest.mark.parametrize(
        "text",
        ["", "auth failed", "network error", "model not found", "boom"],
    )
    def test_non_limit_text(self, text):
        assert _is_usage_limit_error(text) is False


class TestResolveCodexFallback:
    def test_default_on_when_attr_absent(self):
        agent = _make_agent()
        del agent.claude_cli_fallback  # behave like a real agent without the attr
        assert _resolve_codex_fallback(agent) == "openai-codex"

    @pytest.mark.parametrize("val", ["none", "", "off", "false", "0", "disabled", "NONE"])
    def test_disabled_values(self, val):
        agent = _make_agent(claude_cli_fallback=val)
        assert _resolve_codex_fallback(agent) == ""

    @pytest.mark.parametrize(
        "val", ["openai-codex", "codex", "codex_app_server", "OpenAI-Codex"]
    )
    def test_codex_aliases(self, val):
        agent = _make_agent(claude_cli_fallback=val)
        assert _resolve_codex_fallback(agent) == "openai-codex"

    def test_magicmock_attr_treated_as_disabled(self):
        # A bare MagicMock agent yields a non-string sentinel → disabled, so
        # unit tests never spawn a real Codex subprocess unless they opt in.
        agent = _make_agent()
        assert _resolve_codex_fallback(agent) == ""

    def test_unsupported_value_disabled(self):
        agent = _make_agent(claude_cli_fallback="some-random-provider")
        assert _resolve_codex_fallback(agent) == ""


# ---------------------------------------------------------------------------
# Automatic fallback to Codex when the Pro session/usage limit is hit
# ---------------------------------------------------------------------------

# Exact stderr observed live when the Pro quota is exhausted.
_LIMIT_STDERR = "You've hit your session limit · resets 7:50pm (America/Sao_Paulo)"

_LIMIT_BANNER = "[claude-cli no limite Pro — respondendo via Codex]"
_ERROR_BANNER = "[claude-cli falhou — respondendo via Codex]"


def _codex_ok(text: str = "Codex answer") -> dict:
    return {
        "final_response": text,
        "messages": [],
        "api_calls": 1,
        "completed": True,
        "partial": False,
        "error": None,
    }


def _codex_fail(error: str = "codex app-server boom") -> dict:
    return {
        "final_response": "[codex] dead",
        "messages": [],
        "api_calls": 0,
        "completed": False,
        "partial": True,
        "error": error,
    }


class TestClaudeCliCodexFallback:
    def test_limit_error_triggers_codex_fallback(self):
        agent = _make_agent(claude_cli_fallback="openai-codex")
        agent._run_codex_app_server_turn = MagicMock(return_value=_codex_ok("Codex says hi"))

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )

        agent._run_codex_app_server_turn.assert_called_once()
        assert result["final_response"].startswith(_LIMIT_BANNER)
        assert "Codex says hi" in result["final_response"]
        assert result["completed"] is True
        assert result["claude_cli_fallback"] == "openai-codex"

    def test_success_does_not_trigger_fallback(self):
        agent = _make_agent(claude_cli_fallback="openai-codex")
        agent._run_codex_app_server_turn = MagicMock()

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_ok_proc("Claude direct answer")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hello",
                original_user_message="Hello",
                messages=[],
                effective_task_id="t1",
            )

        agent._run_codex_app_server_turn.assert_not_called()
        assert result["final_response"] == "Claude direct answer"
        assert result["completed"] is True
        assert _LIMIT_BANNER not in result["final_response"]

    def test_codex_fallback_also_fails_combined_error(self):
        agent = _make_agent(claude_cli_fallback="openai-codex")
        agent._run_codex_app_server_turn = MagicMock(return_value=_codex_fail("codex app-server boom"))

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        assert result["completed"] is False
        # Both failures are surfaced — neither is swallowed.
        assert "session limit" in result["error"].lower()
        assert "codex app-server boom" in result["error"]
        assert "claude-cli" in result["final_response"]
        assert "codex" in result["final_response"].lower()

    def test_codex_fallback_raises_combined_error(self):
        agent = _make_agent(claude_cli_fallback="openai-codex")
        agent._run_codex_app_server_turn = MagicMock(side_effect=RuntimeError("spawn failed"))

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=1, stderr=_LIMIT_STDERR)),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        assert result["completed"] is False
        assert "[claude-cli error]" in result["final_response"]
        assert "spawn failed" in result["final_response"]
        assert "spawn failed" in result["error"]

    def test_fallback_disabled_shows_original_error(self):
        agent = _make_agent(claude_cli_fallback="none")
        agent._run_codex_app_server_turn = MagicMock()

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
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
        assert "session limit" in result["final_response"].lower()

    def test_nonlimit_exit_uses_generic_banner(self):
        agent = _make_agent(claude_cli_fallback="openai-codex")
        agent._run_codex_app_server_turn = MagicMock(return_value=_codex_ok("Codex generic answer"))

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=_err_proc(rc=2, stderr="auth failed")),
        ):
            result = run_claude_cli_turn(
                agent,
                user_message="Hi",
                original_user_message="Hi",
                messages=[],
                effective_task_id="t1",
            )

        agent._run_codex_app_server_turn.assert_called_once()
        assert result["final_response"].startswith(_ERROR_BANNER)
        assert "no limite Pro" not in result["final_response"]
        assert "Codex generic answer" in result["final_response"]
        assert result["completed"] is True

    def test_unsupported_fallback_value_treated_as_disabled(self):
        agent = _make_agent(claude_cli_fallback="some-random-provider")
        agent._run_codex_app_server_turn = MagicMock()

        with (
            patch("agent.claude_cli_runtime.shutil.which", return_value="/usr/bin/claude"),
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
