"""Pure model pricing helpers for cost calculations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from hermes_cli.cost_guardrails import token_rates_for_model


def price_for_model(model: str, config: Optional[Dict[str, Any]] = None) -> tuple[float, float]:
    """Return ``(input_rate, output_rate)`` in USD per million tokens."""
    cfg = config if isinstance(config, dict) else {}
    return token_rates_for_model(model, cfg)

