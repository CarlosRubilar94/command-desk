"""Regression test: the `claude-cli` provider must NOT require an API key at
AIAgent init.

Bug: agent init failed with::

    Provider 'claude-cli' is set in config.yaml but no API key was found.
    Set the CLAUDE_CLI_API_KEY environment variable, ...

`claude-cli` drives the turn via the `claude` CLI subprocess (Pro/OAuth, no
API key).  It must bypass the OpenAI-client construction + the "no API key
was found" credential gate, mirroring the bedrock/anthropic-native paths.
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
    # resolve_provider_client returns (None, None) to PROVE that init does not
    # depend on any resolvable credential for claude-cli — it must never reach
    # that path.  OpenAI is patched so an accidental client build would not hit
    # the network.
    return (
        patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(None, None),
        ),
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI", return_value=MagicMock()),
    )


def test_claude_cli_init_does_not_require_api_key(monkeypatch):
    """provider='claude-cli' with no env key must initialize without raising."""
    # Ensure the placeholder env key is absent so the test proves the fix.
    monkeypatch.delenv("CLAUDE_CLI_API_KEY", raising=False)

    p1, p2, p3, p4 = _common_patches()
    with p1, p2, p3, p4:
        agent = AIAgent(
            provider="claude-cli",
            model="claude-sonnet-4-5",
            api_key=None,
            base_url=None,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=None,
        )

    assert agent.provider == "claude-cli"
    assert agent.api_mode == "claude_cli"
    # Subprocess runtime: no HTTP client is built.
    assert agent.client is None
    assert agent.api_key == ""


def test_claude_cli_init_forces_claude_cli_mode_over_stale_api_mode(monkeypatch):
    """A stale persisted api_mode (e.g. chat_completions from a previous
    provider) must NOT route claude-cli down the HTTP/OpenAI path."""
    monkeypatch.delenv("CLAUDE_CLI_API_KEY", raising=False)

    p1, p2, p3, p4 = _common_patches()
    with p1, p2, p3, p4:
        agent = AIAgent(
            provider="claude-cli",
            model="claude-sonnet-4-5",
            api_key=None,
            base_url=None,
            api_mode="chat_completions",  # stale / leaked from prior provider
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=None,
        )

    assert agent.api_mode == "claude_cli"
    assert agent.client is None


def test_claude_cli_init_honors_explicit_claude_cli_api_mode(monkeypatch):
    """When api_mode='claude_cli' is passed explicitly, it is preserved."""
    monkeypatch.delenv("CLAUDE_CLI_API_KEY", raising=False)

    p1, p2, p3, p4 = _common_patches()
    with p1, p2, p3, p4:
        agent = AIAgent(
            provider="claude-cli",
            model="claude-sonnet-4-5",
            api_key=None,
            base_url=None,
            api_mode="claude_cli",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=None,
        )

    assert agent.api_mode == "claude_cli"
    assert agent.client is None
