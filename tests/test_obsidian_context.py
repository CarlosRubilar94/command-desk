"""Tests for agent.obsidian_context — read-only Obsidian vault bridge.

Uses a temporary fake vault so no real vault is required.  Confirms:
  * Vault-absent path → VaultContext with error, no crash.
  * Structure scan populates folder/note counts correctly.
  * Operational note extraction returns title + sanitized summary.
  * Secret-looking lines are stripped from summaries.
  * YAML front-matter keys (NOT values) are captured.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.obsidian_context import (  # noqa: E402
    ObsidianContextBridge,
    OperationalNote,
    VaultContext,
    _extract_frontmatter_keys,
    _extract_summary,
    _extract_title,
    _looks_like_secret,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal fake vault under *tmp_path*."""
    vault = tmp_path / "fake-vault"
    vault.mkdir()

    # .obsidian config dir — must be ignored
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "config").write_text("{}")

    # Root-level note
    (vault / "README.md").write_text("# Root Note\nRoot content here.\n")

    # Folder with notes
    ops = vault / "00-Ops"
    ops.mkdir()
    (ops / "Status.md").write_text(
        "---\ntags: [ops]\ncreated: 2026-06-01\n---\n# Status\nSystem is healthy.\n"
    )
    (ops / "Secrets.md").write_text(
        "# Secrets\napi_key: sk-super-secret-value\npassword: hunter2\n"
    )

    # Nested folder
    nested = vault / "projects" / "alpha"
    nested.mkdir(parents=True)
    (nested / "Plan.md").write_text("# Alpha Plan\nBuild the thing.\n")

    return vault


# ---------------------------------------------------------------------------
# _looks_like_secret
# ---------------------------------------------------------------------------


class TestLooksLikeSecret:
    def test_api_key_detected(self):
        assert _looks_like_secret("api_key: sk-abc123") is True

    def test_cursor_key_detected(self):
        assert _looks_like_secret("cursor_test_key_abc123") is True

    def test_normal_line_safe(self):
        assert _looks_like_secret("System is healthy.") is False

    def test_empty_safe(self):
        assert _looks_like_secret("") is False


# ---------------------------------------------------------------------------
# _extract_frontmatter_keys
# ---------------------------------------------------------------------------


class TestExtractFrontmatterKeys:
    def test_reads_keys_not_values(self):
        lines = ["---", "tags: [ops, dev]", "created: 2026-01-01", "---", "# Body"]
        keys, body = _extract_frontmatter_keys(lines)
        assert "tags" in keys
        assert "created" in keys
        # Values must NOT appear
        assert "ops" not in keys
        assert "2026-01-01" not in keys
        assert body == 4

    def test_no_frontmatter(self):
        keys, body = _extract_frontmatter_keys(["# Title", "body"])
        assert keys == []
        assert body == 0


# ---------------------------------------------------------------------------
# _extract_title
# ---------------------------------------------------------------------------


class TestExtractTitle:
    def test_picks_h1(self):
        lines = ["---", "---", "# My Great Note"]
        assert _extract_title(lines, "fallback") == "My Great Note"

    def test_falls_back_to_stem(self):
        lines = ["no heading here"]
        assert _extract_title(lines, "my_stem") == "my_stem"


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------


class TestExtractSummary:
    def test_skips_secret_lines(self):
        lines = ["api_key: sk-abc", "Normal content here."]
        result = _extract_summary(lines)
        assert len(result) == 1
        assert "Normal content" in result[0]

    def test_max_lines_respected(self):
        lines = [f"Line {i}" for i in range(10)]
        result = _extract_summary(lines)
        assert len(result) <= 3

    def test_caps_line_length(self):
        lines = ["A" * 300]
        result = _extract_summary(lines)
        assert len(result) == 1
        assert len(result[0]) <= 200


# ---------------------------------------------------------------------------
# ObsidianContextBridge
# ---------------------------------------------------------------------------


class TestObsidianContextBridgeAbsent:
    def test_missing_vault_returns_error_context(self, tmp_path):
        bridge = ObsidianContextBridge(vault_path=str(tmp_path / "does-not-exist"))
        ctx = bridge.load()
        assert isinstance(ctx, VaultContext)
        assert ctx.error is not None
        assert ctx.note_count == 0


class TestObsidianContextBridgeStructure:
    def test_note_count(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(vault_path=str(vault))
        ctx = bridge.load()
        # 4 notes: README, Status, Secrets, Plan (dotfiles excluded)
        assert ctx.note_count == 4

    def test_folder_structure_populated(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(vault_path=str(vault))
        ctx = bridge.load()
        assert ctx.folder_count >= 1
        # Dotfiles folder excluded
        assert all(not k.startswith(".") for k in ctx.structure)

    def test_summary_text_is_non_empty(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(vault_path=str(vault))
        ctx = bridge.load()
        summary = ctx.summary_text
        assert "Obsidian vault" in summary
        assert str(vault) in summary

    def test_no_error_on_valid_vault(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(vault_path=str(vault))
        ctx = bridge.load()
        assert ctx.error is None


class TestObsidianContextBridgeOperationalNotes:
    def test_operational_note_loaded(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(
            vault_path=str(vault),
            operational_paths=("00-Ops/Status.md",),
        )
        ctx = bridge.load()
        assert len(ctx.operational_notes) == 1
        note = ctx.operational_notes[0]
        assert isinstance(note, OperationalNote)
        assert note.title == "Status"
        # Front-matter keys present, not values
        assert "tags" in note.frontmatter_keys or "created" in note.frontmatter_keys

    def test_secrets_stripped_from_operational_note(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(
            vault_path=str(vault),
            operational_paths=("00-Ops/Secrets.md",),
        )
        ctx = bridge.load()
        note = ctx.operational_notes[0]
        # Secret lines must not appear in summary
        for line in note.summary_lines:
            assert "sk-" not in line
            assert "hunter2" not in line

    def test_missing_operational_note_skipped_gracefully(self, tmp_path):
        vault = _make_vault(tmp_path)
        bridge = ObsidianContextBridge(
            vault_path=str(vault),
            operational_paths=("does-not-exist.md", "00-Ops/Status.md"),
        )
        ctx = bridge.load()
        # Only the existing note loads; no crash
        assert len(ctx.operational_notes) == 1
