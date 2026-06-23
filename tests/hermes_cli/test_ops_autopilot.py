from __future__ import annotations

from hermes_cli.ops_autopilot import detect_incidents


def test_detect_incidents_empty():
    incidents = detect_incidents(
        fleet_metrics={"queue": {}, "bottlenecks": [], "recurring_errors": []},
        cost_status={"mission_budgets": []},
        config={},
    )
    assert incidents == []


def test_detect_incidents_recurring_error():
    incidents = detect_incidents(
        fleet_metrics={
            "queue": {"blocked": 0},
            "bottlenecks": [],
            "recurring_errors": [{"error": "timeout_error", "count": 4, "last_seen": 1000}],
        },
        cost_status={"mission_budgets": []},
        config={"recurring_error_hits_threshold": 3},
    )
    assert incidents
    assert incidents[0]["kind"] == "recurring_errors"
    assert incidents[0]["severity"] in {"warning", "critical"}


def test_detect_incidents_failed_runs():
    incidents = detect_incidents(
        fleet_metrics={
            "queue": {"blocked": 2, "ready": 1, "in_progress": 0},
            "bottlenecks": [],
            "recurring_errors": [],
        },
        cost_status={"mission_budgets": []},
        config={"failed_runs_threshold": 1},
    )
    kinds = [item["kind"] for item in incidents]
    assert "failed_runs" in kinds


def test_detect_incidents_over_budget():
    incidents = detect_incidents(
        fleet_metrics={"queue": {}, "bottlenecks": [], "recurring_errors": []},
        cost_status={
            "spend_today_usd": 10.0,
            "daily_budget_usd": 8.0,
            "mission_budgets": [
                {
                    "mission_id": "mission-alpha",
                    "title": "Alpha Mission",
                    "spend_usd": 5.0,
                    "budget_usd": 4.0,
                    "pct_used": 125.0,
                    "over_budget": True,
                }
            ],
        },
        config={},
    )
    assert incidents
    assert incidents[0]["kind"] == "over_budget"
    assert incidents[0]["severity"] == "critical"


def test_detect_incidents_severity_ordering():
    incidents = detect_incidents(
        fleet_metrics={
            "queue": {"blocked": 1},
            "bottlenecks": [{"name": "planner", "kind": "agent_turn", "avg_duration_ms": 25000, "count": 3}],
            "recurring_errors": [{"error": "fatal", "count": 7, "last_seen": 1000}],
        },
        cost_status={
            "spend_today_usd": 9.0,
            "daily_budget_usd": 5.0,
            "mission_budgets": [],
        },
        config={},
    )
    severities = [item["severity"] for item in incidents]
    assert severities == sorted(
        severities,
        key=lambda value: {"critical": 3, "warning": 2, "info": 1}.get(value, 0),
        reverse=True,
    )
