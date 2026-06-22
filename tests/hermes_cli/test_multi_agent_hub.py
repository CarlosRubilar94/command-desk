"""Tests for /api/ops/multi-agent-hub payload."""

import pytest


@pytest.fixture
def hub_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "config.yaml").write_text(
        "smart_model_routing:\n  enabled: true\n  delegation_tier: economy\n",
        encoding="utf-8",
    )
    return home


def test_build_multi_agent_hub_payload_shape(hub_env):
    from hermes_cli.config import _RAW_CONFIG_CACHE
    from hermes_cli.web_server import _build_multi_agent_hub_payload

    _RAW_CONFIG_CACHE.clear()
    payload = _build_multi_agent_hub_payload()

    assert "cursor_agents" in payload
    assert "playbooks" in payload
    assert "fleet" in payload
    assert "docs" in payload

    agents = payload["cursor_agents"]
    assert isinstance(agents, list)
    assert len(agents) >= 5
    ids = {a["id"] for a in agents}
    assert "orchestrator" in ids
    assert "implementer" in ids
    assert "project-analyst" in ids

    playbooks = payload["playbooks"]
    assert len(playbooks) >= 4
    assert any(p["id"] == "cursor-dev" for p in playbooks)

    fleet = payload["fleet"]
    assert fleet["smart_model_routing"]["enabled"] is True
    assert "active_agents" in fleet


def test_list_cursor_agents_skips_readme():
    from hermes_cli.web_server import _list_cursor_agents

    agents = _list_cursor_agents()
    assert all(a["file"].lower() != "readme.md" for a in agents)
    orchestrator = next(a for a in agents if a["id"] == "orchestrator")
    assert orchestrator["description"]
