"""Tests for cron registration helpers (no real gateway / jobs.json writes)."""

from __future__ import annotations

from maestro.config import MaestroConfig
from maestro.cron_install import (
    JOB_NAME,
    LAUNCHER_NAME,
    cron_expression,
    install_cron,
    plan,
    render_launcher,
    write_launcher,
)


def test_cron_expression():
    assert cron_expression(7) == "0 7 * * *"
    assert cron_expression(25) == "0 23 * * *"  # clamped
    assert cron_expression(9, 30) == "30 9 * * *"


def test_render_launcher_is_portable_and_imports_maestro():
    src = render_launcher(repo_root="/opt/hermes")
    assert "/opt/hermes" in src
    assert "MAESTRO_HERMES_ROOT" in src  # env override for portability (Hetzner)
    assert "from maestro.cli import main" in src
    assert 'main(["run"])' in src


def test_write_launcher(tmp_path):
    scripts = tmp_path / "scripts"
    path = write_launcher(scripts, repo_root=str(tmp_path))
    assert path.name == LAUNCHER_NAME
    assert path.is_file()
    assert "maestro.cli" in path.read_text(encoding="utf-8")


def test_install_cron_dry_run_makes_no_changes(tmp_path):
    cfg = MaestroConfig(home=tmp_path, digest_hour=7)
    info = install_cron(cfg, dry_run=True)
    assert info["dry_run"] is True
    assert info["schedule"] == "0 7 * * *"
    assert info["no_agent"] is True
    assert "local" in info["deliver"]
    # Nothing written
    assert not (tmp_path / "scripts" / LAUNCHER_NAME).exists()


def test_plan_mentions_timezone(tmp_path):
    cfg = MaestroConfig(home=tmp_path, timezone="America/Sao_Paulo")
    assert "America/Sao_Paulo" in plan(cfg)["timezone_note"]


def test_install_cron_live_writes_launcher_and_creates_job(tmp_path, monkeypatch):
    import cron.jobs

    created = {}

    def fake_create_job(**kwargs):
        created.update(kwargs)
        return {"id": "job123", "name": kwargs.get("name"), "schedule_display": "0 7 * * *"}

    monkeypatch.setattr(cron.jobs, "create_job", fake_create_job)

    cfg = MaestroConfig(home=tmp_path, digest_hour=7)
    info = install_cron(cfg, hour=7, dry_run=False)

    assert (tmp_path / "scripts" / LAUNCHER_NAME).is_file()
    assert created["schedule"] == "0 7 * * *"
    assert created["no_agent"] is True
    assert created["script"] == LAUNCHER_NAME
    assert created["deliver"] == "local"
    assert created["name"] == JOB_NAME
    assert info["job_id"] == "job123"
