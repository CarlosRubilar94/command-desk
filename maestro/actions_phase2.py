"""Phase 2 action stubs — DISABLED in Phase 1 (read-only).

This module sketches the architecture for *conversational, confirmed* mailbox
actions (trash / archive / mark-read / create calendar event) without enabling
any of it. Every entry point hard-refuses unless BOTH:

  * ``MAESTRO_PHASE2_ACTIONS_ENABLED=true`` (config flag), and
  * an explicit per-call double confirmation token is supplied.

Design guarantees carried over from the architecture doc (§5.2):
  * "apagar" maps to **trash** (reversible), never permanent delete;
  * permanent delete would require a second, separate explicit confirmation;
  * every action is meant to be dry-run previewed and ``/approve``-gated, and
    appended to an audit log.

None of this executes in Phase 1. The functions exist so Phase 2 can be wired
without reshaping the pipeline, and so tests can assert the safety refusals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence


class Phase2Disabled(RuntimeError):
    """Raised whenever a Phase 2 action is attempted while disabled."""


@dataclass
class ActionPlan:
    """A dry-run description of what an action *would* do (never executed)."""

    operation: str            # "trash" | "archive" | "mark_read" | "create_event"
    account: str
    targets: List[str] = field(default_factory=list)   # msg/thread ids
    description: str = ""
    reversible: bool = True
    requires_double_confirm: bool = False

    def preview(self) -> str:
        kind = "PERMANENTE (irreversível)" if not self.reversible else "reversível"
        return (
            f"[DRY-RUN/{kind}] {self.operation} em '{self.account}': "
            f"{len(self.targets)} item(ns). {self.description}".strip()
        )


def _guard(enabled: bool, confirm_token: str) -> None:
    if not enabled:
        raise Phase2Disabled(
            "Ações do Maestro estão DESABILITADAS (Fase 1 é somente leitura). "
            "Defina MAESTRO_PHASE2_ACTIONS_ENABLED=true para habilitar a Fase 2."
        )
    if not confirm_token or confirm_token != "CONFIRMO":
        raise Phase2Disabled(
            "Ação requer dupla confirmação explícita (token 'CONFIRMO')."
        )


def plan_trash(account: str, target_ids: Sequence[str], *, reason: str = "") -> ActionPlan:
    """Build a (non-executing) plan to move messages to Trash (reversible)."""
    return ActionPlan(
        operation="trash",
        account=account,
        targets=list(target_ids),
        description=reason or "Mover para a lixeira (recuperável).",
        reversible=True,
        requires_double_confirm=False,
    )


def execute_trash(plan: ActionPlan, *, enabled: bool = False, confirm_token: str = "") -> dict:
    """DISABLED in Phase 1 — always refuses unless explicitly enabled + confirmed."""
    _guard(enabled, confirm_token)
    # Phase 2 implementation would call the MCP `trash_message`/`trash_thread`
    # (Gmail) or IMAP COPY-to-Trash + flag, append an audit line, and support
    # undo. Intentionally NOT implemented in Phase 1.
    raise Phase2Disabled("execute_trash not implemented in Phase 1 (read-only).")


def execute_permanent_delete(plan: ActionPlan, *, enabled: bool = False, confirm_token: str = "") -> dict:
    """DISABLED — permanent delete would need a second, separate confirmation."""
    raise Phase2Disabled(
        "Exclusão permanente nunca é executada na Fase 1; exigirá dupla "
        "confirmação separada na Fase 2."
    )
