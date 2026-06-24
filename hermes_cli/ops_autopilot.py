from __future__ import annotations

from typing import Any, TypedDict


class Incident(TypedDict):
    id: str
    kind: str
    severity: str
    title: str
    detail: str
    evidence: dict[str, Any]
    suggested_action: str


_SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def detect_incidents(
    fleet_metrics: dict[str, Any],
    cost_status: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[Incident]:
    cfg = config if isinstance(config, dict) else {}
    recurring_hits_threshold = max(1, _safe_int(cfg.get("recurring_error_hits_threshold"), 3))
    failed_runs_threshold = max(1, _safe_int(cfg.get("failed_runs_threshold"), 1))
    slow_span_ms_threshold = max(1.0, _safe_float(cfg.get("slow_span_ms_threshold"), 20_000.0))
    slow_span_samples_threshold = max(1, _safe_int(cfg.get("slow_span_samples_threshold"), 2))

    incidents: list[Incident] = []

    recurring_errors = fleet_metrics.get("recurring_errors")
    if isinstance(recurring_errors, list):
        for entry in recurring_errors:
            if not isinstance(entry, dict):
                continue
            count = _safe_int(entry.get("count"))
            if count < recurring_hits_threshold:
                continue
            error_name = str(entry.get("error") or "unknown")
            severity = "critical" if count >= (recurring_hits_threshold * 2) else "warning"
            incidents.append(
                {
                    "id": f"recurring-errors:{_slug(error_name)}",
                    "kind": "recurring_errors",
                    "severity": severity,
                    "title": f"Recurring error: {error_name}",
                    "detail": f"{count} failures detected in the recent window.",
                    "evidence": {
                        "error": error_name,
                        "count": count,
                        "last_seen": entry.get("last_seen"),
                    },
                    "suggested_action": "Create a diagnostic mission and inspect failing traces.",
                }
            )

    queue = fleet_metrics.get("queue")
    if isinstance(queue, dict):
        blocked = _safe_int(queue.get("blocked"))
        if blocked >= failed_runs_threshold:
            severity = "critical" if blocked >= (failed_runs_threshold * 3) else "warning"
            incidents.append(
                {
                    "id": "failed-runs:blocked-queue",
                    "kind": "failed_runs",
                    "severity": severity,
                    "title": "Blocked runs detected",
                    "detail": f"{blocked} run(s) are blocked in the queue.",
                    "evidence": {
                        "blocked": blocked,
                        "ready": _safe_int(queue.get("ready")),
                        "in_progress": _safe_int(queue.get("in_progress")),
                    },
                    "suggested_action": "Review blocked Kanban tasks and unblock dependencies.",
                }
            )

    mission_budgets = cost_status.get("mission_budgets")
    if isinstance(mission_budgets, list):
        for mission in mission_budgets:
            if not isinstance(mission, dict) or not bool(mission.get("over_budget")):
                continue
            mission_id = str(mission.get("mission_id") or "unknown")
            incidents.append(
                {
                    "id": f"over-budget:mission:{_slug(mission_id)}",
                    "kind": "over_budget",
                    "severity": "critical",
                    "title": f"Mission over budget: {mission.get('title') or mission_id}",
                    "detail": (
                        f"Mission spend ${_safe_float(mission.get('spend_usd')):.4f} exceeds "
                        f"budget ${_safe_float(mission.get('budget_usd')):.4f}."
                    ),
                    "evidence": {
                        "mission_id": mission_id,
                        "spend_usd": _safe_float(mission.get("spend_usd")),
                        "budget_usd": _safe_float(mission.get("budget_usd")),
                        "pct_used": _safe_float(mission.get("pct_used")),
                    },
                    "suggested_action": "Reduce model tier or split scope before continuing execution.",
                }
            )
            break

    daily_budget = cost_status.get("daily_budget_usd")
    spend_today = _safe_float(cost_status.get("spend_today_usd"))
    parsed_daily_budget = _safe_float(daily_budget, default=-1.0)
    if daily_budget is not None and parsed_daily_budget > 0 and spend_today >= parsed_daily_budget:
        incidents.append(
            {
                "id": "over-budget:daily",
                "kind": "over_budget",
                "severity": "critical",
                "title": "Daily budget exceeded",
                "detail": f"Spend today ${spend_today:.4f} is above budget ${parsed_daily_budget:.4f}.",
                "evidence": {
                    "spend_today_usd": spend_today,
                    "daily_budget_usd": parsed_daily_budget,
                },
                "suggested_action": "Apply fallback model/profile before running additional missions.",
            }
        )

    bottlenecks = fleet_metrics.get("bottlenecks")
    if isinstance(bottlenecks, list):
        for entry in bottlenecks:
            if not isinstance(entry, dict):
                continue
            avg_ms = _safe_float(entry.get("avg_duration_ms"))
            count = _safe_int(entry.get("count"))
            if avg_ms < slow_span_ms_threshold or count < slow_span_samples_threshold:
                continue
            incidents.append(
                {
                    "id": f"slow-agents:{_slug(str(entry.get('name') or 'span'))}",
                    "kind": "slow_agents",
                    "severity": "warning",
                    "title": f"Slow agent path: {entry.get('name') or 'unknown'}",
                    "detail": (
                        f"Average latency {avg_ms:.0f}ms across {count} sample(s) exceeds "
                        f"threshold {slow_span_ms_threshold:.0f}ms."
                    ),
                    "evidence": {
                        "name": entry.get("name"),
                        "kind": entry.get("kind"),
                        "avg_duration_ms": avg_ms,
                        "count": count,
                    },
                    "suggested_action": "Open traces for this path and inspect tool/model bottlenecks.",
                }
            )

    incidents.sort(
        key=lambda item: (
            -_SEVERITY_RANK.get(str(item.get("severity")), 0),
            str(item.get("title") or ""),
        )
    )
    return incidents
