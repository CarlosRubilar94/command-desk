"""Tests for the ``lsp_diagnostics`` field on WriteResult / PatchResult.

The field exists so the agent can read syntax errors (``lint``) and
semantic errors (``lsp_diagnostics``) as separate signals rather than
having LSP output prepended to the lint string.
"""
from __future__ import annotations

import shutil
import sys
from unittest.mock import patch

import pytest

from tools.environments.local import LocalEnvironment
from tools.file_operations import (
    PatchResult,
    ShellFileOperations,
    WriteResult,
)

# Tests that exercise write_file / patch_file go through the bash-backed shell
# pipeline.  On Windows, even when bash.EXE exists (WSL or Git Bash), the
# ShellFileOperations atomic-write pipeline passes native Windows paths to
# bash which WSL bash cannot resolve.  Skip on Windows unless a working Git
# Bash that understands native paths is confirmed.
def _git_bash_works() -> bool:
    """Return True iff a bash that handles native Windows paths is available."""
    if sys.platform != "win32":
        return shutil.which("bash") is not None
    import subprocess, tempfile, os as _os
    bash = shutil.which("bash")
    if not bash:
        return False
    # WSL bash cannot access C:\ paths directly; Git Bash can.
    try:
        r = subprocess.run(
            [bash, "-c", f"test -d '{_os.environ.get('TEMP', 'C:\\Temp')}'"],
            timeout=5, capture_output=True,
        )
        return r.returncode == 0
    except Exception:
        return False

_bash_available = _git_bash_works()
_requires_bash = pytest.mark.skipif(
    not _bash_available,
    reason="requires bash capable of Windows native paths (Git Bash); WSL bash cannot handle C:\\ paths",
)


# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------


def test_writeresult_lsp_diagnostics_optional():
    r = WriteResult()
    assert r.lsp_diagnostics is None


def test_writeresult_to_dict_omits_field_when_none():
    r = WriteResult(bytes_written=10)
    assert "lsp_diagnostics" not in r.to_dict()


def test_writeresult_to_dict_includes_field_when_set():
    r = WriteResult(bytes_written=10, lsp_diagnostics="<diagnostics>...</diagnostics>")
    d = r.to_dict()
    assert d["lsp_diagnostics"] == "<diagnostics>...</diagnostics>"


def test_patchresult_to_dict_includes_field_when_set():
    r = PatchResult(success=True, lsp_diagnostics="ERROR [1:1] thing")
    d = r.to_dict()
    assert d["lsp_diagnostics"] == "ERROR [1:1] thing"


def test_patchresult_to_dict_omits_field_when_none():
    r = PatchResult(success=True)
    assert "lsp_diagnostics" not in r.to_dict()


def test_patchresult_to_dict_omits_field_when_empty_string():
    """Empty string counts as falsy — agent shouldn't see an empty field."""
    r = PatchResult(success=True, lsp_diagnostics="")
    assert "lsp_diagnostics" not in r.to_dict()


# ---------------------------------------------------------------------------
# Channel separation: lint and lsp_diagnostics stay independent
# ---------------------------------------------------------------------------


def test_lint_and_lsp_diagnostics_are_separate_channels():
    """A WriteResult can carry BOTH a syntax-error lint AND an LSP
    diagnostic block.  They belong in separate fields."""
    r = WriteResult(
        bytes_written=42,
        lint={"status": "error", "output": "SyntaxError: ..."},
        lsp_diagnostics="<diagnostics>ERROR [1:5] type mismatch</diagnostics>",
    )
    d = r.to_dict()
    assert "lint" in d
    assert "lsp_diagnostics" in d
    assert d["lint"]["output"] == "SyntaxError: ..."
    assert "type mismatch" in d["lsp_diagnostics"]


# ---------------------------------------------------------------------------
# write_file populates the field via _maybe_lsp_diagnostics
# ---------------------------------------------------------------------------


@_requires_bash
def test_write_file_populates_lsp_diagnostics_when_layer_returns_block(tmp_path):
    """When the LSP layer returns a non-empty block, write_file puts it
    into the ``lsp_diagnostics`` field — NOT into ``lint.output``."""
    fops = ShellFileOperations(LocalEnvironment(cwd=str(tmp_path)))
    target = tmp_path / "x.py"

    block = "<diagnostics file=\"x.py\">\nERROR [1:1] problem\n</diagnostics>"

    with patch.object(fops, "_maybe_lsp_diagnostics", return_value=block):
        res = fops.write_file(str(target), "x = 1\n")

    assert res.lsp_diagnostics == block
    # Lint is the syntax check, which is clean for "x = 1" — must NOT
    # have the LSP block folded into it.
    assert res.lint == {"status": "ok", "output": ""}


@_requires_bash
def test_write_file_lsp_diagnostics_none_when_layer_returns_empty(tmp_path):
    fops = ShellFileOperations(LocalEnvironment(cwd=str(tmp_path)))
    target = tmp_path / "x.py"

    with patch.object(fops, "_maybe_lsp_diagnostics", return_value=""):
        res = fops.write_file(str(target), "x = 1\n")

    assert res.lsp_diagnostics is None


@_requires_bash
def test_write_file_skips_lsp_when_syntax_failed(tmp_path):
    """If the syntax check finds errors, the LSP layer should not be
    consulted (a file that won't parse won't yield meaningful semantic
    diagnostics)."""
    fops = ShellFileOperations(LocalEnvironment(cwd=str(tmp_path)))
    target = tmp_path / "broken.py"

    with patch.object(fops, "_maybe_lsp_diagnostics") as mock_lsp:
        res = fops.write_file(str(target), "def x(:\n")  # syntax error
    assert mock_lsp.call_count == 0
    assert res.lsp_diagnostics is None
    assert res.lint["status"] == "error"


# ---------------------------------------------------------------------------
# patch_replace propagates the field from the inner write_file
# ---------------------------------------------------------------------------


@_requires_bash
def test_patch_replace_propagates_lsp_diagnostics(tmp_path):
    """patch_replace's internal write_file populates lsp_diagnostics —
    the outer PatchResult must carry it forward."""
    fops = ShellFileOperations(LocalEnvironment(cwd=str(tmp_path)))
    target = tmp_path / "x.py"
    target.write_text("x = 1\n")

    block = "<diagnostics>ERROR [1:5] semantic issue</diagnostics>"

    with patch.object(fops, "_maybe_lsp_diagnostics", return_value=block):
        res = fops.patch_replace(str(target), "x = 1", "x = 2")

    assert res.success is True
    assert res.lsp_diagnostics == block
