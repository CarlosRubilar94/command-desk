"""Maestro — thin orchestration layer over Hermes for an email → WhatsApp daily digest.

Phase 1 (MVP) is **read-only**: it ingests unread/recent email from one or more
accounts, runs a cheap triage pass (Gemini Flash), reasons over the triaged
material with the Claude Code CLI (headless subprocess), formats a digest and
delivers it to the user's WhatsApp self-chat via the existing Hermes bridge.

No email is ever modified/archived/deleted in Phase 1. Phase 2 action stubs
exist in :mod:`maestro.actions_phase2` but are disabled by default.

Design doc: ``docs/automations/maestro-email-whatsapp.md`` (PR #40).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
