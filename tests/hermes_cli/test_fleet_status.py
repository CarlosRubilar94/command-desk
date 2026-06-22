"""Tests for /api/ops/fleet-status payload builder."""

import pytest


@pytest.fixture
def fleet_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text(
        "smart_model_routing:\n  enabled: true\n"
        "delegation:\n  max_concurrent_children: 4\n"
        "kanban:\n  dispatch_interval_seconds: 30\n",
        encoding="utf-8",
    )
    return home


def test_build_fleet_status_payload_shape(fleet_env):
    from hermes_cli.config import _RAW_CONFIG_CACHE
    from hermes_cli.web_server import _build_fleet_status_payload

    _RAW_CONFIG_CACHE.clear()
    payload = _build_fleet_status_payload()

    assert "active_agents" in payload
    assert "kanban" in payload
    assert "delegation" in payload
    assert "cron" in payload
    assert "smart_model_routing" in payload
    assert payload["smart_model_routing"]["enabled"] is True
    assert payload["delegation"]["max_concurrent_children"] == 4
    assert payload["kanban"]["dispatch_interval_seconds"] == 30
