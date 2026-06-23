from __future__ import annotations

from copy import deepcopy
from typing import Any


TemplateRecord = dict[str, Any]


TEMPLATES: list[TemplateRecord] = [
    {
        "id": "research",
        "name": "Research Sprint",
        "description": "Investigate a topic, validate evidence, and publish a decision-ready brief.",
        "defaults": {"assignee": "research-lead", "model_tier": "balanced"},
        "creates": {
            "board": "Research Mission",
            "columns": ["todo", "running", "review", "done"],
            "tasks": [
                {"title": "Frame research question", "status": "todo"},
                {"title": "Collect primary sources", "status": "todo"},
                {"title": "Write synthesis memo", "status": "review"},
            ],
        },
    },
    {
        "id": "code-review",
        "name": "Code Review Lane",
        "description": "Run a structured review workflow for risk, regressions, and release confidence.",
        "defaults": {"assignee": "reviewer", "model_tier": "high"},
        "creates": {
            "board": "Code Review Mission",
            "columns": ["todo", "running", "review", "done"],
            "tasks": [
                {"title": "Read change intent and diff", "status": "todo"},
                {"title": "Audit risks and regressions", "status": "running"},
                {"title": "Publish review outcomes", "status": "review"},
            ],
        },
    },
    {
        "id": "feature-build",
        "name": "Feature Build",
        "description": "Ship a scoped feature from acceptance criteria through verification and rollout.",
        "defaults": {"assignee": "builder", "model_tier": "high"},
        "creates": {
            "board": "Feature Build Mission",
            "columns": ["todo", "running", "review", "done"],
            "tasks": [
                {"title": "Define acceptance criteria", "status": "todo"},
                {"title": "Implement vertical slice", "status": "running"},
                {"title": "Add automated checks", "status": "review"},
                {"title": "Prepare rollout notes", "status": "todo"},
            ],
        },
    },
    {
        "id": "ops-watchdog",
        "name": "Ops Watchdog",
        "description": "Continuously watch operational signals and trigger remediation when health degrades.",
        "defaults": {"assignee": "ops", "model_tier": "fast"},
        "creates": {
            "board": "Ops Watchdog Mission",
            "columns": ["scheduled", "running", "blocked", "done"],
            "tasks": [
                {"title": "Define SLO checks", "status": "scheduled"},
                {"title": "Create incident runbook", "status": "todo"},
                {"title": "Wire escalation path", "status": "todo"},
            ],
            "cron": True,
        },
        "cron": {
            "name": "Ops watchdog heartbeat",
            "schedule": "every 15m",
            "deliver": "local",
            "prompt": (
                "Run an ops watchdog sweep. Check gateway health, pending queue pressure, recurring errors, "
                "and recent cost spikes. If all metrics are healthy, respond with [SILENT]. If not healthy, "
                "emit a concise incident summary with severity, suspected root cause, and next action."
            ),
        },
        "monitoring_defaults": {
            "latency_slo_ms": 5000,
            "error_rate_threshold": 0.05,
            "queue_depth_threshold": 25,
            "cost_spike_threshold_usd": 10.0,
        },
    },
    {
        "id": "content",
        "name": "Content Engine",
        "description": "Plan, draft, edit, and publish content with an editorial production loop.",
        "defaults": {"assignee": "editor", "model_tier": "balanced"},
        "creates": {
            "board": "Content Mission",
            "columns": ["todo", "running", "review", "done"],
            "tasks": [
                {"title": "Build topic brief", "status": "todo"},
                {"title": "Draft first version", "status": "running"},
                {"title": "Editorial QA pass", "status": "review"},
            ],
        },
    },
    {
        "id": "growth",
        "name": "Growth Experiments",
        "description": "Run growth hypotheses through experiment design, execution, and readout.",
        "defaults": {"assignee": "growth", "model_tier": "balanced"},
        "creates": {
            "board": "Growth Mission",
            "columns": ["todo", "running", "review", "done"],
            "tasks": [
                {"title": "Prioritize growth hypotheses", "status": "todo"},
                {"title": "Launch controlled experiment", "status": "running"},
                {"title": "Analyze experiment metrics", "status": "review"},
            ],
        },
    },
    {
        "id": "affiliate",
        "name": "Affiliate Pipeline",
        "description": "Source partners, launch campaigns, and monitor performance with compliance guardrails.",
        "defaults": {"assignee": "bizdev", "model_tier": "fast"},
        "creates": {
            "board": "Affiliate Mission",
            "columns": ["todo", "running", "review", "done"],
            "tasks": [
                {"title": "Shortlist partner opportunities", "status": "todo"},
                {"title": "Prepare creative + tracking", "status": "running"},
                {"title": "Compliance and attribution check", "status": "review"},
            ],
        },
    },
]


_TEMPLATES_BY_ID: dict[str, TemplateRecord] = {item["id"]: item for item in TEMPLATES}


def list_template_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for template in TEMPLATES:
        creates = template.get("creates", {})
        tasks = creates.get("tasks", [])
        items.append(
            {
                "id": template["id"],
                "name": template["name"],
                "description": template["description"],
                "creates": {
                    "board": creates.get("board") or template["name"],
                    "tasks_count": len(tasks) if isinstance(tasks, list) else 0,
                    "cron": bool(template.get("cron")),
                },
            }
        )
    return items


def get_template(template_id: str) -> dict[str, Any] | None:
    template = _TEMPLATES_BY_ID.get(str(template_id or "").strip())
    if template is None:
        return None
    return deepcopy(template)
