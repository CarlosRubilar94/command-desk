from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import hermes_cli.gateway as gateway
import hermes_cli.main as main
import hermes_cli.web_server as ws
from hermes_cli.subprocess_utils import safe_run


def test_safe_run_replaces_invalid_utf8_bytes():
    cmd = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(b'bad:\\xd2\\n')",
    ]
    result = safe_run(cmd, capture_output=True)
    assert result.returncode == 0
    assert "bad:" in result.stdout
    assert "\ufffd" in result.stdout


def test_restart_returns_needs_service_install_without_prompt(monkeypatch):
    monkeypatch.setattr(ws.sys, "platform", "win32")
    monkeypatch.setattr(ws, "_gateway_service_is_installed", lambda profile=None: False)
    monkeypatch.setattr(ws, "_record_completed_action", lambda *a, **k: None)
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(AssertionError("input() should not be called")))

    payload = asyncio.run(ws.restart_gateway(profile=None))
    assert payload["ok"] is False
    assert payload["status"] == "needs_service_install"
    assert payload["action"] == "install_gateway_service"


def test_repair_install_degrades_when_optional_extras_fail(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n[project.optional-dependencies]\nvoice=[]\nvision=[]\n",
        encoding="utf-8",
    )

    def fake_safe_run(cmd, **kwargs):
        cmd_s = " ".join(cmd)
        if ".[all]" in cmd_s:
            return SimpleNamespace(returncode=1, stdout="", stderr="all extras failed")
        if ".[voice]" in cmd_s:
            return SimpleNamespace(returncode=1, stdout="", stderr="voice failed")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(main, "safe_run", fake_safe_run)
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)

    result = main.run_repair_install_sequence(project_root=tmp_path)
    assert result["status"] == "degraded_optional_extras_failed"
    assert "voice" in result["failed_extras"]


def test_kill_gateway_processes_ignores_already_exited_pid(monkeypatch, capsys):
    monkeypatch.setattr(gateway, "find_gateway_pids", lambda **_: [1234])
    monkeypatch.setattr(gateway, "terminate_pid", lambda *a, **k: (_ for _ in ()).throw(OSError("taskkill failed")))
    monkeypatch.setattr("gateway.status._pid_exists", lambda _pid: False)

    killed = gateway.kill_gateway_processes(force=True, all_profiles=False)
    out = capsys.readouterr().out
    assert killed == 1
    assert "Failed to kill PID 1234" not in out
