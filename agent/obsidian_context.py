"""Read-only Obsidian vault context bridge for Hermes.

Extracts **operational context only** from an Obsidian vault so Hermes
can ground orchestration decisions in documented project state.  This
module is intentionally read-only and minimal:

  * It NEVER writes to the vault.
  * It NEVER copies sensitive note content into Hermes memory.
  * It extracts ONLY structural metadata: folder tree, note titles,
    YAML front-matter keys, and short (≤3-line) summaries from a
    configurable set of operational files.
  * It NEVER logs or returns secret-shaped strings (values that look
    like tokens, API keys, passwords, or similar).

Typical usage
-------------
    from agent.obsidian_context import ObsidianContextBridge, VaultContext

    bridge = ObsidianContextBridge(vault_path="/path/to/vault")
    ctx: VaultContext = bridge.load()
    # ctx.structure — dict of folder→[note_titles]
    # ctx.operational_notes — list of OperationalNote summaries
    # ctx.summary_text — plain-text digest for prompt injection

Design notes
------------
The control-center repo has a richer JS collector (lib/collectors/obsidian.js)
for pipeline use.  This Python module is the Hermes-side read path; it does
NOT call into the JS code — it reads the vault directly via stdlib so there
are no Node dependencies.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SUMMARY_LINES = 3  # lines of body text kept per operational note
_MAX_NOTES_PER_FOLDER = 200  # guard against massive vaults
_SECRET_PATTERN = re.compile(
    r"""(?xi)
    # common secret shapes — reject lines containing these
    (?: api[_\-]?key | access[_\-]?token | password | secret | bearer\s | sk- | ghp_ |
        cursor_ | bws? | AKIA[0-9A-Z]{16} | -----BEGIN )
    """,
    re.IGNORECASE,
)


def _looks_like_secret(text: str) -> bool:
    """Return True if *text* appears to contain a credential value."""
    return bool(_SECRET_PATTERN.search(text))


def _sanitize_line(line: str) -> Optional[str]:
    """Return *line* unchanged if safe, None if it looks like a secret."""
    if _looks_like_secret(line):
        return None
    return line


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class OperationalNote:
    """Structural summary of a single vault note.  Never holds raw content."""

    path: str  # relative path inside the vault
    title: str  # first H1 or filename stem
    frontmatter_keys: List[str] = field(default_factory=list)  # YAML keys only
    summary_lines: List[str] = field(default_factory=list)  # ≤3 sanitized lines


@dataclass
class VaultContext:
    """Structural snapshot of an Obsidian vault."""

    vault_path: str
    structure: Dict[str, List[str]] = field(
        default_factory=dict
    )  # folder → [note title, ...]
    operational_notes: List[OperationalNote] = field(default_factory=list)
    note_count: int = 0
    folder_count: int = 0
    error: Optional[str] = None  # non-None → partial/failed load

    @property
    def summary_text(self) -> str:
        """Plain-text digest suitable for injection into a Hermes prompt."""
        lines: List[str] = [
            f"Obsidian vault: {self.vault_path}",
            f"  Notes: {self.note_count}, Folders: {self.folder_count}",
        ]
        for folder, titles in sorted(self.structure.items()):
            preview = ", ".join(titles[:5])
            extra = f" (+{len(titles) - 5} more)" if len(titles) > 5 else ""
            lines.append(f"  {folder or '(root)'}: {preview}{extra}")
        if self.operational_notes:
            lines.append("Operational notes:")
            for note in self.operational_notes:
                lines.append(f"  [{note.title}] {note.path}")
                if note.summary_lines:
                    lines.append("    " + " / ".join(note.summary_lines))
        if self.error:
            lines.append(f"(load error: {self.error})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# YAML front-matter parser (minimal — no pyyaml dependency at module level)
# ---------------------------------------------------------------------------

_FM_START = re.compile(r"^---\s*$")
_FM_END = re.compile(r"^(?:---|\.\.\.)s*$")
_FM_KEY = re.compile(r"^([A-Za-z_][\w\- ]*):")


def _extract_frontmatter_keys(lines: List[str]) -> Tuple[List[str], int]:
    """Return (yaml_keys, body_start_line_index) from *lines*.

    Reads only the first YAML block (``---`` … ``---``).  Returns keys only,
    never values (values may contain secrets).
    """
    if not lines or not _FM_START.match(lines[0]):
        return [], 0
    keys: List[str] = []
    for i, line in enumerate(lines[1:], start=1):
        if _FM_END.match(line):
            return keys, i + 1
        m = _FM_KEY.match(line)
        if m:
            keys.append(m.group(1).strip())
    return keys, len(lines)


def _extract_title(lines: List[str], stem: str) -> str:
    """Return the first H1 heading, or fall back to *stem*."""
    for line in lines[:20]:
        stripped = line.lstrip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return stem


def _extract_summary(body_lines: List[str]) -> List[str]:
    """Return up to _MAX_SUMMARY_LINES sanitized non-empty content lines."""
    results: List[str] = []
    for raw in body_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        safe = _sanitize_line(stripped)
        if safe is None:
            continue  # skip secret-looking lines
        results.append(safe[:200])  # cap at 200 chars per line
        if len(results) >= _MAX_SUMMARY_LINES:
            break
    return results


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class ObsidianContextBridge:
    """Read-only bridge that extracts operational context from an Obsidian vault.

    Parameters
    ----------
    vault_path:
        Filesystem path to the vault root.  Defaults to the
        ``OBSIDIAN_VAULT_PATH`` environment variable, then
        ``~/Documents/Obsidian`` as a fallback.
    operational_paths:
        Relative paths inside the vault to treat as operational notes
        (deeper summary extraction).  Defaults to a standard DevSSD set.
    """

    _DEFAULT_OPERATIONAL_PATHS = (
        "00-AI/START-HERE.md",
        "00-AI/working-context.md",
        "07-Inventario/Inventario DevSSD.md",
        "08-Memoria/Memoria OpenClaw.md",
        "09-Missoes/Missoes OpenClaw.md",
        "AGENTS.md",
    )

    def __init__(
        self,
        vault_path: Optional[str] = None,
        operational_paths: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self._vault_path = Path(
            vault_path
            or os.environ.get("OBSIDIAN_VAULT_PATH", "")
            or Path.home() / "Documents" / "Obsidian"
        ).expanduser().resolve()
        self._operational_paths: Tuple[str, ...] = (
            operational_paths or self._DEFAULT_OPERATIONAL_PATHS
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load(self) -> VaultContext:
        """Load and return a VaultContext from the vault.

        Always returns a VaultContext; sets ``.error`` on partial failures
        rather than raising (fail-open, same philosophy as bitwarden.py).
        """
        ctx = VaultContext(vault_path=str(self._vault_path))

        if not self._vault_path.is_dir():
            ctx.error = f"vault path does not exist: {self._vault_path}"
            logger.warning("Obsidian vault not found at %s", self._vault_path)
            return ctx

        try:
            self._scan_structure(ctx)
            self._load_operational_notes(ctx)
        except OSError as exc:
            ctx.error = f"IO error during vault scan: {exc}"
            logger.warning("Obsidian vault scan failed: %s", exc)

        return ctx

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan_structure(self, ctx: VaultContext) -> None:
        """Walk the vault and populate ``ctx.structure``."""
        seen_folders: set[str] = set()

        for note_path in sorted(self._vault_path.rglob("*.md")):
            # Skip dotfiles / hidden directories (e.g. .obsidian, .trash)
            rel = note_path.relative_to(self._vault_path)
            parts = rel.parts
            if any(p.startswith(".") for p in parts):
                continue

            folder = str(rel.parent) if rel.parent != Path(".") else ""
            seen_folders.add(folder)

            title = note_path.stem
            # Try a quick peek for the H1 title without reading the whole file
            try:
                with note_path.open(encoding="utf-8", errors="replace") as fh:
                    head = [fh.readline() for _ in range(10)]
                title = _extract_title(head, note_path.stem)
            except OSError:
                pass

            bucket = ctx.structure.setdefault(folder, [])
            if len(bucket) < _MAX_NOTES_PER_FOLDER:
                bucket.append(title)
            ctx.note_count += 1

        ctx.folder_count = len(seen_folders)

    def _load_operational_notes(self, ctx: VaultContext) -> None:
        """Read full content of configured operational notes."""
        for rel_path in self._operational_paths:
            abs_path = self._vault_path / rel_path
            if not abs_path.is_file():
                logger.debug("Operational note not found: %s", rel_path)
                continue
            try:
                with abs_path.open(encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                lines = [l.rstrip("\n") for l in lines]
                fm_keys, body_start = _extract_frontmatter_keys(lines)
                title = _extract_title(lines, abs_path.stem)
                summary = _extract_summary(lines[body_start:])
                ctx.operational_notes.append(
                    OperationalNote(
                        path=rel_path,
                        title=title,
                        frontmatter_keys=fm_keys,
                        summary_lines=summary,
                    )
                )
            except OSError as exc:
                logger.debug("Could not read operational note %s: %s", rel_path, exc)
