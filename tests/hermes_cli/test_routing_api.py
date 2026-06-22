"""Tests for /api/ops/routing dashboard endpoint."""

import pytest


@pytest.fixture
def routing_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text(
        "smart_model_routing:\n  enabled: false\n  delegation_tier: economy\n",
        encoding="utf-8",
    )
    return home


def test_update_routing_enable_and_tier(routing_env):
    from hermes_cli.config import _RAW_CONFIG_CACHE, load_config
    from hermes_cli.web_server import RoutingUpdate, update_routing_status

    _RAW_CONFIG_CACHE.clear()

    import asyncio

    result = asyncio.run(
        update_routing_status(
            RoutingUpdate(enabled=True, delegation_tier="performance"),
        ),
    )
    assert result["ok"] is True
    assert isinstance(result["lines"], list)

    _RAW_CONFIG_CACHE.clear()
    cfg = load_config()
    assert cfg["smart_model_routing"]["enabled"] is True
    assert cfg["smart_model_routing"]["delegation_tier"] == "performance"


def test_update_routing_disable(routing_env):
    from hermes_cli.config import _RAW_CONFIG_CACHE, load_config
    from hermes_cli.web_server import RoutingUpdate, update_routing_status

    _RAW_CONFIG_CACHE.clear()
    import asyncio

    asyncio.run(update_routing_status(RoutingUpdate(enabled=True)))
    _RAW_CONFIG_CACHE.clear()
    asyncio.run(update_routing_status(RoutingUpdate(enabled=False)))

    _RAW_CONFIG_CACHE.clear()
    cfg = load_config()
    assert cfg["smart_model_routing"]["enabled"] is False
