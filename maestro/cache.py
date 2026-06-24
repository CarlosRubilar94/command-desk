"""Seen-id cache so already-digested messages are not reprocessed.

Stored as JSON at ``<HERMES_HOME>/maestro/seen.json`` mapping ``msg_id`` →
ISO timestamp of first sighting. Entries older than ``ttl_days`` are pruned on
save. stdlib-only; safe to disable (dry-run) by passing ``persist=False``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .models import EmailItem


class SeenCache:
    def __init__(self, path: Path, *, ttl_days: int = 14, persist: bool = True):
        self.path = Path(path)
        self.ttl_days = ttl_days
        self.persist = persist
        self._seen: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.is_file():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._seen = {str(k): str(v) for k, v in data.get("seen", {}).items()}
        except (OSError, ValueError):
            self._seen = {}

    def is_seen(self, msg_id: str) -> bool:
        return bool(msg_id) and msg_id in self._seen

    def filter_new(self, items: Sequence[EmailItem]) -> List[EmailItem]:
        """Return only items whose msg_id has not been seen before."""
        return [it for it in items if not self.is_seen(it.msg_id)]

    def mark_seen(self, items: Iterable[EmailItem]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for it in items:
            if it.msg_id:
                self._seen.setdefault(it.msg_id, now)

    def _prune(self) -> None:
        if self.ttl_days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)
        kept: Dict[str, str] = {}
        for mid, ts in self._seen.items():
            try:
                seen_at = datetime.fromisoformat(ts)
                if seen_at.tzinfo is None:
                    seen_at = seen_at.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if seen_at >= cutoff:
                kept[mid] = ts
        self._seen = kept

    def save(self) -> None:
        if not self.persist:
            return
        self._prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"seen": self._seen, "updated_at": datetime.now(timezone.utc).isoformat()}
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".seen_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
