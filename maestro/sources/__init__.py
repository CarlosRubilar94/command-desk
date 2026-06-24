"""Email ingestion sources for Maestro."""

from __future__ import annotations

from .base import EmailSource, SourceError, SourceResult

__all__ = ["EmailSource", "SourceError", "SourceResult"]
