"""Unit tests for agent.cursor_adapter.

The cursor-sdk package is NOT a hard dependency of Hermes; all live SDK
calls are mocked.  The suite validates:

  * Import and construction succeed without cursor-sdk installed.
  * Credential guard raises CursorAdapterCredentialError when key absent.
  * Not-installed guard raises CursorAdapterNotInstalledError.
  * start_task / stream_events / resume_task / cancel_task / get_status /
    collect_cost_estimate behave correctly with a mocked SDK.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make the repo root importable without installing the wheel.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.cursor_adapter import (  # noqa: E402
    CursorAdapterCredentialError,
    CursorAdapterError,
    CursorAdapterNotInstalledError,
    CursorAgentAdapter,
    CursorCostEstimate,
    CursorRunResult,
    CursorStatusResult,
    _get_cursor_sdk,
)
import agent.cursor_adapter as _adapter_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sdk_cache():
    """Reset the module-level SDK cache before each test."""
    original = _adapter_mod._cursor_sdk
    _adapter_mod._cursor_sdk = ...  # reset to sentinel
    yield
    _adapter_mod._cursor_sdk = original


def _make_fake_sdk() -> MagicMock:
    """Build a minimal mock that quacks like cursor_sdk."""
    sdk = MagicMock(name="cursor_sdk")

    # AgentOptions / LocalAgentOptions — simple pass-through
    sdk.AgentOptions = MagicMock(side_effect=lambda **kw: kw)
    sdk.LocalAgentOptions = MagicMock(side_effect=lambda **kw: kw)

    # Agent.prompt (one-shot)
    prompt_result = MagicMock()
    prompt_result.id = "run-001"
    prompt_result.agent_id = "agent-abc"
    prompt_result.status = "finished"
    prompt_result.result = "Task complete."
    sdk.Agent.prompt.return_value = prompt_result

    # Agent.create context manager
    fake_agent = MagicMock()
    fake_agent.agent_id = "agent-abc"
    fake_run = MagicMock()
    fake_run.id = "run-002"
    # messages() yields one assistant message with one text block
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "hello from cursor"
    msg_content = MagicMock()
    msg_content.content = [text_block]
    message = MagicMock()
    message.type = "assistant"
    message.message = msg_content
    fake_run.messages.return_value = [message]
    wait_result = MagicMock()
    wait_result.status = "finished"
    wait_result.result = "done"
    fake_run.wait.return_value = wait_result
    fake_agent.send.return_value = fake_run
    sdk.Agent.create.return_value.__enter__ = MagicMock(return_value=fake_agent)
    sdk.Agent.create.return_value.__exit__ = MagicMock(return_value=False)

    # Agent.resume context manager
    sdk.Agent.resume.return_value.__enter__ = MagicMock(return_value=fake_agent)
    sdk.Agent.resume.return_value.__exit__ = MagicMock(return_value=False)

    # CursorClient.launch_bridge context manager
    fake_client = MagicMock()
    agent_info = MagicMock()
    agent_info.status = "finished"
    agent_info.model = "composer-2.5"
    agent_info.created_at = "2026-06-23"
    fake_client.agents.get.return_value = agent_info
    sdk.CursorClient.launch_bridge.return_value.__enter__ = MagicMock(
        return_value=fake_client
    )
    sdk.CursorClient.launch_bridge.return_value.__exit__ = MagicMock(return_value=False)

    return sdk


@pytest.fixture
def fake_sdk() -> MagicMock:
    return _make_fake_sdk()


@pytest.fixture
def adapter_with_key(fake_sdk) -> CursorAgentAdapter:
    """Adapter wired to the fake SDK and a dummy key."""
    _adapter_mod._cursor_sdk = fake_sdk
    return CursorAgentAdapter(api_key="cursor_test_key_abc123")


@pytest.fixture
def adapter_no_key(fake_sdk) -> CursorAgentAdapter:
    """Adapter wired to the fake SDK but NO key."""
    _adapter_mod._cursor_sdk = fake_sdk
    return CursorAgentAdapter(api_key="")


# ---------------------------------------------------------------------------
# _get_cursor_sdk
# ---------------------------------------------------------------------------


class TestGetCursorSdk:
    def test_returns_none_when_not_installed(self):
        with patch.dict("sys.modules", {"cursor_sdk": None}):
            _adapter_mod._cursor_sdk = ...  # re-trigger lazy load
            result = _get_cursor_sdk()
        assert result is None

    def test_returns_module_when_installed(self, fake_sdk):
        with patch.dict("sys.modules", {"cursor_sdk": fake_sdk}):
            _adapter_mod._cursor_sdk = ...
            result = _get_cursor_sdk()
        assert result is fake_sdk


# ---------------------------------------------------------------------------
# Construction and credential guard
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_construction_succeeds_without_sdk(self, monkeypatch):
        _adapter_mod._cursor_sdk = None
        monkeypatch.delenv("CURSOR_API_KEY", raising=False)
        adapter = CursorAgentAdapter()  # must not raise
        assert adapter is not None

    def test_construction_succeeds_without_key(self, monkeypatch):
        monkeypatch.delenv("CURSOR_API_KEY", raising=False)
        adapter = CursorAgentAdapter(api_key="")
        assert adapter is not None


class TestCredentialGuard:
    def test_start_task_raises_on_absent_key(self, adapter_no_key):
        with pytest.raises(CursorAdapterCredentialError, match="CURSOR_API_KEY"):
            adapter_no_key.start_task("do something")

    def test_start_task_raises_when_sdk_absent(self, monkeypatch):
        _adapter_mod._cursor_sdk = None
        monkeypatch.delenv("CURSOR_API_KEY", raising=False)
        adapter = CursorAgentAdapter(api_key="some_key")
        with pytest.raises(CursorAdapterNotInstalledError):
            adapter.start_task("do something")


# ---------------------------------------------------------------------------
# start_task
# ---------------------------------------------------------------------------


class TestStartTask:
    def test_returns_run_result(self, adapter_with_key):
        result = adapter_with_key.start_task("refactor utils.py")
        assert isinstance(result, CursorRunResult)
        assert result.status == "finished"
        assert result.run_id == "run-001"
        assert result.agent_id == "agent-abc"
        assert result.result_text == "Task complete."

    def test_raises_credential_error_on_sdk_cursor_error(self, adapter_with_key, fake_sdk):
        class FakeCursorAgentError(Exception):
            pass

        fake_sdk.CursorAgentError = FakeCursorAgentError
        fake_sdk.Agent.prompt.side_effect = FakeCursorAgentError("auth failed")
        with pytest.raises(CursorAdapterCredentialError, match="startup failed"):
            adapter_with_key.start_task("something")


# ---------------------------------------------------------------------------
# stream_events
# ---------------------------------------------------------------------------


class TestStreamEvents:
    def test_yields_text_events(self, adapter_with_key):
        events = list(adapter_with_key.stream_events("summarise main.py"))
        assert len(events) == 1
        assert events[0] == {"type": "text", "text": "hello from cursor"}

    def test_generator_return_value_is_run_result(self, adapter_with_key):
        gen = adapter_with_key.stream_events("summarise main.py")
        try:
            while True:
                next(gen)
        except StopIteration as exc:
            result = exc.value
        assert isinstance(result, CursorRunResult)
        assert result.status == "finished"


# ---------------------------------------------------------------------------
# resume_task
# ---------------------------------------------------------------------------


class TestResumeTask:
    def test_resumes_and_returns_result(self, adapter_with_key, fake_sdk):
        result = adapter_with_key.resume_task("agent-abc", "add changelog")
        assert isinstance(result, CursorRunResult)
        assert result.agent_id == "agent-abc"
        fake_sdk.Agent.resume.assert_called_once()


# ---------------------------------------------------------------------------
# cancel_task
# ---------------------------------------------------------------------------


class TestCancelTask:
    def test_cancel_succeeds_when_supported(self, adapter_with_key):
        fake_run = MagicMock()
        fake_run.supports.return_value = True
        assert adapter_with_key.cancel_task(fake_run) is True
        fake_run.cancel.assert_called_once()

    def test_cancel_returns_false_when_not_supported(self, adapter_with_key):
        fake_run = MagicMock()
        fake_run.supports.return_value = False
        assert adapter_with_key.cancel_task(fake_run) is False

    def test_cancel_returns_false_for_none(self, adapter_with_key):
        assert adapter_with_key.cancel_task(None) is False


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_returns_status_result(self, adapter_with_key):
        result = adapter_with_key.get_status("agent-abc")
        assert isinstance(result, CursorStatusResult)
        assert result.agent_id == "agent-abc"
        assert result.status == "finished"

    def test_raises_adapter_error_on_failure(self, adapter_with_key, fake_sdk):
        fake_sdk.CursorClient.launch_bridge.return_value.__enter__.side_effect = (
            RuntimeError("network timeout")
        )
        with pytest.raises(CursorAdapterError, match="get_status failed"):
            adapter_with_key.get_status("agent-abc")


# ---------------------------------------------------------------------------
# collect_cost_estimate
# ---------------------------------------------------------------------------


class TestCollectCostEstimate:
    def test_returns_estimate_with_note(self, adapter_with_key):
        result = adapter_with_key.collect_cost_estimate("run-001")
        assert isinstance(result, CursorCostEstimate)
        assert result.run_id == "run-001"
        assert result.input_tokens is None
        assert "cursor-sdk" in result.note.lower() or "Cursor SDK" in result.note
