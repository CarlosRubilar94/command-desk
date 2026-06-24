"""Core data models for the Maestro pipeline (stdlib-only dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class EmailItem:
    """A normalized email record shared across all sources.

    ``body`` stays ``None`` until it is fetched on demand (token economy:
    metadata-first). All sources must produce this shape so triage / digest
    code is source-agnostic.
    """

    account: str                      # logical account, e.g. "hostinger_empresa"
    source_kind: str                  # "imap" | "gmail_mcp" | "mock"
    msg_id: str                       # provider message id (stable, for dedupe/cache)
    sender: str = ""                  # raw From header (display + addr)
    sender_email: str = ""            # parsed address only
    subject: str = ""
    snippet: str = ""                 # short preview, metadata-cheap
    date: Optional[datetime] = None   # timezone-aware when known
    date_raw: str = ""
    thread_id: Optional[str] = None   # provider thread id when available
    labels: List[str] = field(default_factory=list)
    unread: bool = True
    uid: Optional[str] = None         # IMAP UID (read-only fetch by UID)
    body: Optional[str] = None        # filled only for items passing triage
    extra: Dict[str, Any] = field(default_factory=dict)

    def thread_key(self) -> str:
        """Stable grouping key for dedupe-by-thread.

        Prefers the provider thread id; otherwise falls back to a normalized
        subject (Re:/Fwd: stripped) scoped by account so unrelated mailboxes
        never collide.
        """
        if self.thread_id:
            return f"{self.account}:tid:{self.thread_id}"
        from .normalize import normalize_subject

        return f"{self.account}:subj:{normalize_subject(self.subject)}"


@dataclass
class TriageResult:
    """Cheap-model classification for a single (deduped) email/thread."""

    msg_id: str
    priority: str = "normal"          # "high" | "normal" | "low"
    category: str = "other"           # work|personal|newsletter|promo|finance|calendar|notification|other
    needs_action: bool = False
    suggested_action: str = ""
    thread_key: str = ""
    reason: str = ""

    PRIORITIES = ("high", "normal", "low")
    PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}

    def rank(self) -> int:
        return self.PRIORITY_RANK.get(self.priority, 1)


@dataclass
class TriagedItem:
    """An email joined with its triage verdict."""

    email: EmailItem
    triage: TriageResult


@dataclass
class DigestResult:
    """Outcome of a pipeline run."""

    markdown: str = ""
    delivered: bool = False
    dry_run: bool = False
    preview_path: Optional[str] = None
    total_fetched: int = 0
    total_after_dedupe: int = 0
    total_after_cache: int = 0
    accounts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    triage_backend: str = ""
    reasoning_backend: str = ""

    def summary_line(self) -> str:
        status = "DRY-RUN" if self.dry_run else ("delivered" if self.delivered else "not delivered")
        return (
            f"maestro digest [{status}] accounts={','.join(self.accounts) or 'none'} "
            f"fetched={self.total_fetched} deduped={self.total_after_dedupe} "
            f"new={self.total_after_cache} triage={self.triage_backend} "
            f"reason={self.reasoning_backend} warnings={len(self.warnings)}"
        )
