"""Regression test: the `cursor-cli` provider must NOT require an API key at
AIAgent init.

The cursor-cli drives the turn via the `cursor-agent` CLI subprocess (Cursor
subscription, no API key). It must bypass the OpenAI-client construction +
the "no API key was found" credential gate, mirroring the bedrock/claude-cli
paths.
"""

import pytest
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_tool_defs():
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "search",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def _common_patches():
    return (
        patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(None, None),
        ),
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI", return_value=MagicMock()),
    )


def test_cursor_cli_init_does_not_require_api_key(monkeypatch):
    """provider='cursor-cli' with no env key must initialize without raising."""
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.delenv("CURSOR_CLI_API_KEY", raising=False)

    p1, p2, p3, p4 = _common_patches()
    with p1, p2, p3, p4:
        agent = AIAgent(
            provider="cursor-cli",
            model="cursor-small",
            api_key=None,
            base_url=None,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=None,
        )

    assert agent.provider == "cursor-cli"
    assert agent.api_mode == "cursor_cli"
    assert agent.client is None
    assert agent.api_key == ""


def test_cursor_cli_init_forces_cursor_cli_mode_over_stale_api_mode(monkeypatch):
    """A stale persisted api_mode (e.g. chat_completions from a previous
    provider) must NOT route cursor-cli down the HTTP/OpenAI path."""
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)

    p1, p2, p3, p4 = _common_patches()
    with p1, p2, p3, p4:
        agent = AIAgent(
            provider="cursor-cli",
            model="cursor-small",
            api_key=None,
            base_url=None,
            api_mode="chat_completions",  # stale / leaked from prior provider
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=None,
        )

    assert agent.api_mode == "cursor_cli"
    assert agent.client is None


def test_cursor_cli_init_honors_explicit_cursor_cli_api_mode(monkeypatch):
    """When api_mode='cursor_cli' is passed explicitly, it is preserved."""
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)

    p1, p2, p3, p4 = _common_patches()
    with p1, p2, p3, p4:
        agent = AIAgent(
            provider="cursor-cli",
            model="cursor-small",
            api_key=None,
            base_url=None,
            api_mode="cursor_cli",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=None,
        )

    assert agent.api_mode == "cursor_cli"
    assert agent.client is None
