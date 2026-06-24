"""Source abstraction: every backend yields normalized :class:`EmailItem`s.

A source must implement metadata-first fetching (cheap) and an optional
``fetch_body`` for the items that survive triage (token economy). Sources never
modify mailbox state in Phase 1 (read-only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..models import EmailItem


class SourceError(Exception):
    """Raised when a source cannot fetch (auth/network/config)."""


@dataclass
class SourceResult:
    account: str
    items: List[EmailItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class EmailSource:
    """Base class for email sources."""

    #: logical account label, e.g. "hostinger_empresa"
    account: str = "unknown"
    #: backend kind, e.g. "imap" | "gmail_mcp" | "mock"
    kind: str = "unknown"

    def fetch_metadata(self, *, window_hours: int, max_items: int) -> SourceResult:
        """Return unread/recent messages as metadata-only EmailItems."""
        raise NotImplementedError

    def fetch_body(self, item: EmailItem, *, max_chars: int) -> str:
        """Return the cleaned body for one item (read-only). Default: snippet."""
        return item.snippet or ""

    def close(self) -> None:  # pragma: no cover - trivial
        """Release any resources (connections). Safe to call multiple times."""
        return None
