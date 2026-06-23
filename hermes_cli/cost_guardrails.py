"""Pure decision logic for cost guardrails.

This module intentionally avoids I/O so it can be unit-tested in isolation and
reused by runtime routing and dashboard API layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

PREMIUM_MODEL_PREFIXES = (
    "claude-3-5-sonnet",
    "claude-3-opus",
    "claude-opus",
    "gpt-4",
    "gpt-4o",
    "gpt-4.1",
    "o1",
    "o3",
)

ECONOMY_MODEL_PREFIXES = (
    "google/gemini-2.5-flash",
    "google/gemini-3-flash",
    "google/gemini-3-flash-preview",
    "qwen/qwen3-coder:free",
)

DEFAULT_TOKEN_RATES_USD_PER_MTOKEN = {
    "economy": (0.20, 0.80),
    "performance": (3.00, 15.00),
    "premium": (15.00, 75.00),
}

KNOWN_MODEL_TOKEN_RATES_USD_PER_MTOKEN = {
    "google/gemini-3-flash-preview": (0.15, 0.60),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "google/gemini-3-flash": (0.30, 2.50),
    "openai/gpt-4o": (5.00, 15.00),
    "openai/gpt-4.1": (2.00, 8.00),
    "openai/gpt-5.5-medium": (5.00, 20.00),
    "openai/gpt-5.5-pro": (25.00, 125.00),
    "anthropic/claude-opus-4": (15.00, 75.00),
    "anthropic/claude-opus-4.8": (15.00, 75.00),
    "anthropic/claude-3-5-sonnet": (3.00, 15.00),
}


@dataclass(frozen=True)
class GuardrailDecision:
    allow: bool
    action: str  # none | warn | block | fallback
    fallback_model: Optional[str]
    reason: Optional[str]


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _budget_value(value: Any) -> Optional[float]:
    budget = _safe_float(value)
    if budget is None:
        return None
    return budget if budget > 0 else None


def is_premium_model(model: str, config: Optional[Dict[str, Any]] = None) -> bool:
    raw = str(model or "").strip().lower()
    if not raw:
        return False
    cfg = config if isinstance(config, dict) else {}
    custom = cfg.get("premium_model_prefixes")
    if isinstance(custom, list) and custom:
        prefixes = tuple(str(item).strip().lower() for item in custom if str(item).strip())
    else:
        prefixes = PREMIUM_MODEL_PREFIXES
    return any(raw.startswith(prefix) for prefix in prefixes)


def model_tier_for_pricing(model: str, config: Optional[Dict[str, Any]] = None) -> str:
    raw = str(model or "").strip().lower()
    if not raw:
        return "performance"
    if is_premium_model(raw, config):
        return "premium"
    if any(raw.startswith(prefix) for prefix in ECONOMY_MODEL_PREFIXES):
        return "economy"
    return "performance"


def token_rates_for_model(model: str, config: Optional[Dict[str, Any]] = None) -> tuple[float, float]:
    raw = str(model or "").strip().lower()
    if not raw:
        return DEFAULT_TOKEN_RATES_USD_PER_MTOKEN["performance"]
    known = KNOWN_MODEL_TOKEN_RATES_USD_PER_MTOKEN.get(raw)
    if known is not None:
        return known
    tier = model_tier_for_pricing(raw, config)
    return DEFAULT_TOKEN_RATES_USD_PER_MTOKEN[tier]


def evaluate_guardrails(
    spend_today: float,
    daily_budget: Optional[float],
    mission_spend: float,
    mission_budget: Optional[float],
    model: str,
    is_premium: bool,
    config: Optional[Dict[str, Any]],
) -> GuardrailDecision:
    cfg = config if isinstance(config, dict) else {}
    if not bool(cfg.get("enabled", False)):
        return GuardrailDecision(True, "none", None, None)

    daily_cap = _budget_value(daily_budget)
    mission_cap = _budget_value(mission_budget)
    spend_today_v = float(spend_today or 0.0)
    mission_spend_v = float(mission_spend or 0.0)

    over_daily = daily_cap is not None and spend_today_v > daily_cap
    over_mission = mission_cap is not None and mission_spend_v > mission_cap
    over_budget = over_daily or over_mission

    premium_alert = bool(cfg.get("premium_alert", False))
    block_expensive = bool(cfg.get("block_expensive", False))
    auto_fallback = bool(cfg.get("auto_fallback", False))
    fallback_model = str(cfg.get("fallback_model") or "").strip() or None

    blocked_expensive = block_expensive and is_premium
    warn_only = (premium_alert and is_premium) or over_budget

    if (over_budget or blocked_expensive) and auto_fallback and fallback_model:
        reason_parts = []
        if over_daily:
            reason_parts.append("daily_budget_exceeded")
        if over_mission:
            reason_parts.append("mission_budget_exceeded")
        if blocked_expensive:
            reason_parts.append("expensive_model_blocked")
        return GuardrailDecision(
            True,
            "fallback",
            fallback_model,
            ",".join(reason_parts) or "fallback_requested",
        )

    if blocked_expensive:
        return GuardrailDecision(False, "block", None, "expensive_model_blocked")

    if warn_only:
        reason_parts = []
        if over_daily:
            reason_parts.append("daily_budget_exceeded")
        if over_mission:
            reason_parts.append("mission_budget_exceeded")
        if premium_alert and is_premium:
            reason_parts.append("premium_model_usage")
        return GuardrailDecision(True, "warn", None, ",".join(reason_parts))

    return GuardrailDecision(True, "none", None, None)


def decision_to_dict(decision: GuardrailDecision) -> Dict[str, Any]:
    return asdict(decision)
