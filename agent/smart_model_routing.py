"""Task-aware model tier routing for auxiliary tasks and delegation.

When ``smart_model_routing.enabled`` is true, high-volume side tasks route to
an economy-tier model (cheap/fast) while quality-sensitive tasks keep the main
chat model. Delegation can inherit the same economy tier so subagents do not
burn the parent's premium model by default.
"""

from __future__ import annotations

import logging
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
        return main_provider, main_model

    routing = get_routing_config()
    economy_provider = str(routing.get("economy_provider") or "").strip()
    resolved_provider = economy_provider or main_provider
    economy_model = _resolve_economy_model(resolved_provider)

    if economy_model and economy_model != main_model:
        logger.info(
            "smart_model_routing: task=%s tier=economy %s/%s → %s/%s",
            task, main_provider, main_model, resolved_provider, economy_model,
        )
    return resolved_provider, economy_model


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
