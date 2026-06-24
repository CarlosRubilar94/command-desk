"""Tests for agent/smart_model_routing.py."""

from unittest.mock import patch

import pytest


@pytest.fixture
def routing_config(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text(
        "smart_model_routing:\n  enabled: true\n  delegation_tier: economy\n",
        encoding="utf-8",
    )
    return home


def test_economy_task_routes_to_cheaper_model(routing_config):
    from agent.smart_model_routing import consume_routing_annotation, resolve_aux_routing

    provider, model = resolve_aux_routing(
        "compression",
        "openrouter",
        "anthropic/claude-opus-4",
    )
    assert provider == "openrouter"
    assert model == "google/gemini-3-flash-preview"
    annotation = consume_routing_annotation("compression", model)
    assert annotation["baseline_model"] == "anthropic/claude-opus-4"
    assert annotation["selected_model"] == "google/gemini-3-flash-preview"


def test_performance_task_keeps_main_model(routing_config):
    from agent.smart_model_routing import resolve_aux_routing

    provider, model = resolve_aux_routing(
        "web_extract",
        "openrouter",
        "anthropic/claude-opus-4",
    )
    assert provider == "openrouter"
    assert model == "anthropic/claude-opus-4"


def test_routing_disabled_keeps_main_model(routing_config):
    config_path = routing_config / "config.yaml"
    config_path.write_text(
        "smart_model_routing:\n  enabled: false\n",
        encoding="utf-8",
    )
    from hermes_cli.config import _RAW_CONFIG_CACHE
    _RAW_CONFIG_CACHE.clear()

    from agent.smart_model_routing import resolve_aux_routing

    provider, model = resolve_aux_routing(
        "compression",
        "openrouter",
        "anthropic/claude-opus-4",
    )
    assert model == "anthropic/claude-opus-4"


def test_delegation_economy_model(routing_config):
    from agent.smart_model_routing import resolve_delegation_model

    parent = type("Agent", (), {"provider": "openrouter", "model": "anthropic/claude-opus-4"})()
    model = resolve_delegation_model(parent)
    assert model == "google/gemini-3-flash-preview"


def test_delegation_inherit_tier_returns_none(routing_config):
    config_path = routing_config / "config.yaml"
    config_path.write_text(
        "smart_model_routing:\n  enabled: true\n  delegation_tier: inherit\n",
        encoding="utf-8",
    )
    from hermes_cli.config import _RAW_CONFIG_CACHE
    _RAW_CONFIG_CACHE.clear()

    from agent.smart_model_routing import resolve_delegation_model

    parent = type("Agent", (), {"provider": "openrouter", "model": "anthropic/claude-opus-4"})()
    assert resolve_delegation_model(parent) is None


def test_get_cron_ticker_interval_default(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text("_config_version: 31\n", encoding="utf-8")

    from hermes_cli.config import get_cron_ticker_interval, _RAW_CONFIG_CACHE
    _RAW_CONFIG_CACHE.clear()

    assert get_cron_ticker_interval() == 30


def test_get_cron_ticker_interval_from_config(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text(
        "cron:\n  ticker_interval_seconds: 30\n",
        encoding="utf-8",
    )

    from hermes_cli.config import get_cron_ticker_interval, _RAW_CONFIG_CACHE
    _RAW_CONFIG_CACHE.clear()

    assert get_cron_ticker_interval() == 30


def test_routing_cli_enable_disable(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text("smart_model_routing:\n  enabled: false\n", encoding="utf-8")

    from argparse import Namespace
    from hermes_cli.config import load_config, _RAW_CONFIG_CACHE
    from hermes_cli.subcommands.routing import handle_routing

    _RAW_CONFIG_CACHE.clear()
    handle_routing(Namespace(enable=True, disable=False, delegation_tier=None))
    assert load_config()["smart_model_routing"]["enabled"] is True

    _RAW_CONFIG_CACHE.clear()
    handle_routing(Namespace(enable=False, disable=True, delegation_tier=None))
    assert load_config()["smart_model_routing"]["enabled"] is False


def test_guardrails_fallback_downgrades_model(routing_config):
    from agent.smart_model_routing import resolve_aux_routing
    from hermes_cli.cost_guardrails import GuardrailDecision

    with patch(
        "agent.smart_model_routing._guardrail_decision_for_model",
        return_value=GuardrailDecision(
            allow=True,
            action="fallback",
            fallback_model="google/gemini-2.5-flash",
            reason="daily_budget_exceeded",
        ),
    ):
        provider, model = resolve_aux_routing(
            "compression",
            "openrouter",
            "anthropic/claude-opus-4",
        )
    assert provider == "openrouter"
    assert model == "google/gemini-2.5-flash"


def test_guardrails_block_raises_runtime_error(routing_config):
    from agent.smart_model_routing import resolve_aux_routing
    from hermes_cli.cost_guardrails import GuardrailDecision

    with patch(
        "agent.smart_model_routing._guardrail_decision_for_model",
        return_value=GuardrailDecision(
            allow=False,
            action="block",
            fallback_model=None,
            reason="expensive_model_blocked",
        ),
    ):
        with pytest.raises(RuntimeError):
            resolve_aux_routing(
                "compression",
                "openrouter",
                "anthropic/claude-opus-4",
            )
