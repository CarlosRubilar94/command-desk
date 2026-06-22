"""Tests for delegation status API payload."""

import pytest


@pytest.fixture
def fleet_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text("_config_version: 31\n", encoding="utf-8")
    return home


def test_delegation_status_payload_shape(fleet_env):
    from hermes_cli.web_server import get_delegation_status
    import asyncio

    result = asyncio.run(get_delegation_status())
    assert "running" in result
    assert "total" in result
    assert "items" in result
    assert isinstance(result["items"], list)
