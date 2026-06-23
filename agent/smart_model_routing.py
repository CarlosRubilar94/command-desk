"""Task-aware model tier routing for auxiliary tasks and delegation.

When ``smart_model_routing.enabled`` is true, high-volume side tasks route to
an economy-tier model (cheap/fast) while quality-sensitive tasks keep the main
chat model. Delegation can inherit the same economy tier so subagents do not
burn the parent's premium model by default.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, FrozenSet, Optional, Tuple

logger = logging.getLogger(__name__)

# High-volume, low-complexity auxiliary tasks → economy tier.
ECONOMY_TASKS: FrozenSet[str] = frozenset({
    "compression",
    "approval",
    "title_generation",
    "goal_judge",
    "monitor",
    "tts_audio_tags",
    "skills_hub",
    "profile_describer",
    "triage_specifier",
    "mcp",
})

# Quality-sensitive auxiliary tasks → main / performance tier.
PERFORMANCE_TASKS: FrozenSet[str] = frozenset({
    "web_extract",
    "kanban_decomposer",
    "curator",
    "vision",
})

_DEFAULT_OPENROUTER_ECONOMY = "google/gemini-3-flash-preview"


def _load_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def get_routing_config() -> Dict[str, Any]:
    """Return the ``smart_model_routing`` section from config."""
    cfg = _load_config()
    section = cfg.get("smart_model_routing", {})
    return section if isinstance(section, dict) else {}


def get_cost_guardrails_config() -> Dict[str, Any]:
    cfg = _load_config()
    section = cfg.get("cost_guardrails", {})
    return section if isinstance(section, dict) else {}


def is_routing_enabled() -> bool:
    return bool(get_routing_config().get("enabled", False))


def get_task_tier(task: Optional[str]) -> str:
    """Return ``economy``, ``performance``, or ``inherit`` for *task*."""
    if not task:
        return "inherit"
    if task in ECONOMY_TASKS:
        return "economy"
    if task in PERFORMANCE_TASKS:
        return "performance"
    return "inherit"


def _resolve_economy_model(provider: str) -> str:
    """Pick a cheap model for *provider* (profile default_aux_model first)."""
    routing = get_routing_config()
    explicit = str(routing.get("economy_model") or "").strip()
    if explicit:
        return explicit

    provider_key = str(provider or "").strip().lower()
    if provider_key in {"openrouter", "nous"}:
        return _DEFAULT_OPENROUTER_ECONOMY

    try:
        from agent.auxiliary_client import _get_aux_model_for_provider
        aux = _get_aux_model_for_provider(provider_key)
        if aux:
            return aux
    except Exception:
        pass

    return _DEFAULT_OPENROUTER_ECONOMY


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return default


def _today_start_epoch_local() -> float:
    now = datetime.now().astimezone()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return float(today.timestamp())


def _budget_value(value: Any) -> Optional[float]:
    try:
        num = float(value)
    except Exception:
        return None
    return num if num > 0 else None


def _mission_budget_for_id(cfg: Dict[str, Any], mission_id: Optional[str]) -> Optional[float]:
    if not mission_id:
        return None
    raw = cfg.get("mission_budgets_usd")
    if not isinstance(raw, dict):
        return None
    return _budget_value(raw.get(mission_id))


def _current_mission_id() -> Optional[str]:
    for key in ("HERMES_MISSION_ID", "KANBAN_MISSION_ID", "MISSION_ID"):
        val = str(os.getenv(key) or "").strip()
        if val:
            return val
    return None


def _mission_spend_today(mission_id: Optional[str]) -> float:
    if not mission_id:
        return 0.0
    try:
        from hermes_cli import traces_store
        from hermes_cli.kanban_db import kanban_db_path
        from hermes_constants import get_hermes_home
    except Exception:
        return 0.0

    mission = traces_store.get_mission(mission_id)
    if not mission:
        return 0.0
    board_slug = str(mission.get("board_slug") or "").strip()
    if not board_slug:
        return 0.0
    board_path = kanban_db_path(board=board_slug)
    if not board_path.exists():
        return 0.0

    session_ids: list[str] = []
    conn = sqlite3.connect(str(board_path))
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT session_id
            FROM tasks
            WHERE session_id IS NOT NULL AND TRIM(session_id) != ''
            """
        ).fetchall()
        session_ids = [str(row[0]) for row in rows if row and row[0]]
    except Exception:
        return 0.0
    finally:
        conn.close()

    if not session_ids:
        return 0.0

    try:
        from hermes_state import SessionDB

        db = SessionDB(db_path=get_hermes_home() / "state.db")
        try:
            placeholders = ",".join("?" for _ in session_ids)
            today_start = _today_start_epoch_local()
            row = db._conn.execute(
                f"""
                SELECT COALESCE(SUM(estimated_cost_usd), 0.0) AS total
                FROM sessions
                WHERE id IN ({placeholders}) AND started_at >= ?
                """,
                [*session_ids, today_start],
            ).fetchone()
            return _safe_float(row["total"] if row is not None else 0.0)
        finally:
            db.close()
    except Exception:
        return 0.0


def _guardrail_decision_for_model(model: str):
    cfg = get_cost_guardrails_config()
    if not bool(cfg.get("enabled", False)):
        return None
    try:
        from hermes_state import SessionDB
        from hermes_cli.cost_guardrails import evaluate_guardrails, is_premium_model
    except Exception as exc:
        logger.debug("cost_guardrails unavailable: %s", exc)
        return None

    mission_id = _current_mission_id()
    mission_budget = _mission_budget_for_id(cfg, mission_id)
    mission_spend = _mission_spend_today(mission_id) if mission_budget is not None else 0.0
    daily_budget = _budget_value(cfg.get("daily_budget_usd"))

    spend_today = 0.0
    try:
        db = SessionDB()
        try:
            today_start = _today_start_epoch_local()
            row = db._conn.execute(
                """
                SELECT COALESCE(SUM(estimated_cost_usd), 0.0) AS spend_today
                FROM sessions WHERE started_at >= ?
                """,
                (today_start,),
            ).fetchone()
            spend_today = _safe_float(row["spend_today"] if row is not None else 0.0)
        finally:
            db.close()
    except Exception as exc:
        logger.debug("cost_guardrails spend query skipped: %s", exc)

    return evaluate_guardrails(
        spend_today=spend_today,
        daily_budget=daily_budget,
        mission_spend=mission_spend,
        mission_budget=mission_budget,
        model=model,
        is_premium=is_premium_model(model, cfg),
        config=cfg,
    )


def resolve_aux_routing(
    task: Optional[str],
    main_provider: str,
    main_model: str,
) -> Tuple[str, str]:
    """Apply tier routing for an auxiliary task with provider ``auto``.

    Returns ``(provider, model)`` — unchanged when routing is off or the task
    is performance/inherit tier.
    """
    if not is_routing_enabled() or not task:
        return main_provider, main_model

    tier = get_task_tier(task)
    if tier in {"inherit", "performance"}:
        resolved_provider, resolved_model = main_provider, main_model
    else:
        routing = get_routing_config()
        economy_provider = str(routing.get("economy_provider") or "").strip()
        resolved_provider = economy_provider or main_provider
        resolved_model = _resolve_economy_model(resolved_provider)

    if resolved_model and resolved_model != main_model:
        logger.info(
            "smart_model_routing: task=%s tier=economy %s/%s → %s/%s",
            task, main_provider, main_model, resolved_provider, resolved_model,
        )

    decision = _guardrail_decision_for_model(resolved_model)
    if decision is None or decision.action == "none":
        return resolved_provider, resolved_model

    if decision.action == "warn":
        logger.warning(
            "cost_guardrails: task=%s action=warn model=%s reason=%s",
            task,
            resolved_model,
            decision.reason or "unspecified",
        )
        return resolved_provider, resolved_model

    guard_cfg = get_cost_guardrails_config()
    if decision.action == "fallback":
        fallback_provider = str(guard_cfg.get("fallback_provider") or "").strip() or resolved_provider
        fallback_model = str(decision.fallback_model or "").strip() or _resolve_economy_model(fallback_provider)
        logger.warning(
            "cost_guardrails: task=%s action=fallback %s/%s → %s/%s reason=%s",
            task,
            resolved_provider,
            resolved_model,
            fallback_provider,
            fallback_model,
            decision.reason or "fallback_requested",
        )
        return fallback_provider, fallback_model

    logger.warning(
        "cost_guardrails: task=%s action=block model=%s reason=%s",
        task,
        resolved_model,
        decision.reason or "expensive_model_blocked",
    )
    raise RuntimeError(
        f"Cost guardrails blocked model '{resolved_model}'"
        f"{f': {decision.reason}' if decision.reason else ''}"
    )


def resolve_delegation_model(parent_agent: Any) -> Optional[str]:
    """Return an economy model for subagents when delegation is unconfigured.

    Only applies when ``delegation.model`` and ``delegation.provider`` are both
    empty and ``smart_model_routing.delegation_tier`` is ``economy``.
    """
    if not is_routing_enabled():
        return None

    routing = get_routing_config()
    tier = str(routing.get("delegation_tier") or "economy").strip().lower()
    if tier != "economy":
        return None

    parent_provider = str(getattr(parent_agent, "provider", "") or "").strip()
    parent_model = str(getattr(parent_agent, "model", "") or "").strip()
    if not parent_provider or not parent_model:
        return None

    economy_model = _resolve_economy_model(parent_provider)
    if economy_model and economy_model != parent_model:
        logger.info(
            "smart_model_routing: delegation tier=economy %s/%s → %s",
            parent_provider, parent_model, economy_model,
        )
        return economy_model
    return None


def get_economy_extra_body() -> Dict[str, Any]:
    """OpenRouter-style extra_body for economy-tier aux calls."""
    routing = get_routing_config()
    extra = routing.get("economy_extra_body", {})
    return dict(extra) if isinstance(extra, dict) else {}


def routing_status_lines() -> list[str]:
    """Human-readable routing summary for CLI / doctor."""
    routing = get_routing_config()
    enabled = bool(routing.get("enabled", False))
    lines = [
        f"Smart model routing: {'enabled' if enabled else 'disabled'}",
    ]
    if not enabled:
        lines.append("  Enable with: command-desk routing --enable")
        return lines

    lines.append(f"  Delegation tier: {routing.get('delegation_tier', 'economy')}")
    economy_model = str(routing.get("economy_model") or "").strip()
    if economy_model:
        lines.append(f"  Economy model override: {economy_model}")
    else:
        lines.append("  Economy model: auto (provider default_aux_model)")

    lines.append(f"  Economy tasks ({len(ECONOMY_TASKS)}): "
                 f"{', '.join(sorted(ECONOMY_TASKS))}")
    lines.append(f"  Performance tasks ({len(PERFORMANCE_TASKS)}): "
                 f"{', '.join(sorted(PERFORMANCE_TASKS))}")
    return lines
