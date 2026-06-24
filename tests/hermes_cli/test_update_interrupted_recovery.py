"""Tests for interrupted-install self-heal (the ``.update-incomplete`` marker)."""

from __future__ import annotations

import hermes_cli.main as m


def test_marker_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    marker = m._update_marker_path()
    assert marker == tmp_path / ".update-incomplete"
    assert not marker.exists()

    m._write_update_incomplete_marker()
    assert marker.exists()
    body = marker.read_text()
    assert "started=" in body
    assert "pid=" in body

    m._clear_update_incomplete_marker()
    assert not marker.exists()


def test_clear_when_absent_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    m._clear_update_incomplete_marker()
    assert not m._update_marker_path().exists()


def test_recovery_noop_without_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    called = {"repair": False}
    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: called.__setitem__("repair", True),
    )
    m._recover_from_interrupted_install()
    assert called["repair"] is False


def test_recovery_clears_stray_marker_without_pyproject(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    m._write_update_incomplete_marker()
    called = {"repair": False}
    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: called.__setitem__("repair", True),
    )
    m._recover_from_interrupted_install()
    assert called["repair"] is False
    assert not m._update_marker_path().exists()


def test_recovery_runs_install_and_clears_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    m._write_update_incomplete_marker()
    seen = {"repair": False}

    def fake_repair(**_):
        seen["repair"] = True
        return {"status": "ok", "message": "ok", "log_lines": [], "failed_extras": []}

    monkeypatch.setattr(m, "run_repair_install_sequence", fake_repair)
    m._recover_from_interrupted_install()

    assert seen["repair"] is True
    assert not m._update_marker_path().exists()


def test_recovery_keeps_marker_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    m._write_update_incomplete_marker()

    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: {
            "status": "failed",
            "message": "install died",
            "log_lines": [],
            "failed_extras": [],
        },
    )
    m._recover_from_interrupted_install()
    assert m._update_marker_path().exists()


def test_recovery_skips_when_lock_held(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    m._write_update_incomplete_marker()
    lock = tmp_path / ".update-incomplete.lock"
    lock.write_text("12345\n")

    seen = {"repair": False}
    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: seen.__setitem__("repair", True),
    )
    m._recover_from_interrupted_install()

    assert seen["repair"] is False
    assert m._update_marker_path().exists()
    assert lock.exists()


def test_recovery_breaks_stale_lock(tmp_path, monkeypatch):
    import os as _os

    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    m._write_update_incomplete_marker()
    lock = tmp_path / ".update-incomplete.lock"
    lock.write_text("12345\n")
    stale = m._time.time() - 7200
    _os.utime(lock, (stale, stale))

    seen = {"repair": False}
    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: {
            "status": "ok",
            "message": "ok",
            "log_lines": [],
            "failed_extras": [],
        },
    )
    m._recover_from_interrupted_install()
    assert not lock.exists()
    assert m._update_marker_path().exists()

    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: seen.__setitem__("repair", True)
        or {"status": "ok", "message": "ok", "log_lines": [], "failed_extras": []},
    )
    m._recover_from_interrupted_install()
    assert seen["repair"] is True
    assert not m._update_marker_path().exists()


def test_recovery_releases_lock_after_run(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    m._write_update_incomplete_marker()
    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: {"status": "ok", "message": "ok", "log_lines": [], "failed_extras": []},
    )
    m._recover_from_interrupted_install()
    assert not (tmp_path / ".update-incomplete.lock").exists()


def test_recovery_output_goes_to_stderr(tmp_path, monkeypatch, capfd):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    m._write_update_incomplete_marker()
    monkeypatch.setattr(
        m,
        "run_repair_install_sequence",
        lambda **_: {"status": "ok", "message": "ok", "log_lines": [], "failed_extras": []},
    )
    m._recover_from_interrupted_install()

    out, err = capfd.readouterr()
    assert "interrupted mid-install" not in out
    assert "interrupted mid-install" in err
    assert "recovered" in err
