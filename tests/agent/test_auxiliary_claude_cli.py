"""Auxiliary client must keep claude-cli zero-cost.

claude-cli drives the MAIN turn via the `claude` CLI subprocess (Pro/OAuth,
no per-token billing). It has no HTTP endpoint, so it cannot back auxiliary
tasks (compression, memory/skill review, vision, ...).

The owner is Pro-only and does NOT want hidden per-token spend, so when the
main provider is claude-cli the auxiliary path must:
  1. NOT resolve a client for `claude-cli` (returns None),
  2. NOT fall through to the paid Step-2/Step-3 fallback chain
     (OpenRouter / Nous / ...), and
  3. surface a NEUTRAL error (not the misleading "set CLAUDE_CLI_API_KEY").

Users who want auxiliary on a free/local model can still set an explicit
``auxiliary.<task>.provider`` (e.g. ollama), which bypasses the auto path.
"""

import asyncio

import pytest

from agent import auxiliary_client as ac


# ── resolve_provider_client: no HTTP client for claude-cli ───────────────────

def test_resolve_provider_client_claude_cli_returns_none():
    client, model = ac.resolve_provider_client("claude-cli", model="claude-sonnet-4-5")
    assert client is None
    assert model is None


# ── _resolve_auto: never fall through to the paid chain ──────────────────────

def test_resolve_auto_skips_paid_chain_for_claude_cli_main(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError(
            "paid fallback chain must NOT run when main provider is claude-cli"
        )

    # Any attempt to reach Step-2 / Step-3 (configured fallback or the
    # hardcoded OpenRouter/Nous discovery chain) is a hidden-cost regression.
    monkeypatch.setattr(ac, "_try_configured_fallback_chain", _boom)
    monkeypatch.setattr(ac, "_try_main_fallback_chain", _boom)
    monkeypatch.setattr(ac, "_get_provider_chain", _boom)

    client, model = ac._resolve_auto(
        main_runtime={"provider": "claude-cli", "model": "claude-sonnet-4-5"},
        task="compression",
    )
    assert client is None
    assert model is None


# ── call_llm / acall_llm gate: neutral message, no paid retry ────────────────

def test_call_llm_claude_cli_neutral_error(monkeypatch):
    # Force the client resolution to fail so we hit the gate.
    monkeypatch.setattr(ac, "_get_cached_client", lambda *a, **k: (None, None))

    with pytest.raises(RuntimeError) as ei:
        ac.call_llm(
            task=None,
            provider="claude-cli",
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": "hi"}],
        )

    msg = str(ei.value)
    assert "claude-cli" in msg
    assert "Auxiliary tasks are unavailable" in msg
    # The misleading per-key hint must NOT appear.
    assert "CLAUDE_CLI_API_KEY" not in msg


def test_acall_llm_claude_cli_neutral_error(monkeypatch):
    monkeypatch.setattr(ac, "_get_cached_client", lambda *a, **k: (None, None))

    async def _run():
        return await ac.async_call_llm(
            task=None,
            provider="claude-cli",
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": "hi"}],
        )

    with pytest.raises(RuntimeError) as ei:
        asyncio.run(_run())

    msg = str(ei.value)
    assert "claude-cli" in msg
    assert "Auxiliary tasks are unavailable" in msg
    assert "CLAUDE_CLI_API_KEY" not in msg
