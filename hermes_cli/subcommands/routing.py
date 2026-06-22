"""``hermes routing`` — smart model routing status and toggles."""

from __future__ import annotations

import argparse
from typing import Callable


def build_routing_parser(subparsers, *, cmd_routing: Callable) -> None:
    routing_parser = subparsers.add_parser(
        "routing",
        help="Smart model routing for aux tasks and delegation",
        description=(
            "Show or configure task-aware model tier routing. When enabled, "
            "high-volume auxiliary tasks and subagents use an economy-tier model "
            "while quality-sensitive tasks keep your main chat model."
        ),
    )
    routing_parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable smart model routing",
    )
    routing_parser.add_argument(
        "--disable",
        action="store_true",
        help="Disable smart model routing",
    )
    routing_parser.add_argument(
        "--delegation-tier",
        choices=["economy", "inherit", "performance"],
        metavar="TIER",
        help="Subagent tier when delegation.model is unset",
    )
    routing_parser.set_defaults(func=cmd_routing)


def handle_routing(args: argparse.Namespace) -> int:
    from hermes_cli.config import load_config, save_config
    from agent.smart_model_routing import routing_status_lines

    config = load_config()
    routing = config.setdefault("smart_model_routing", {})
    if not isinstance(routing, dict):
        routing = {}
        config["smart_model_routing"] = routing

    changed = False
    if getattr(args, "enable", False):
        routing["enabled"] = True
        changed = True
    if getattr(args, "disable", False):
        routing["enabled"] = False
        changed = True
    tier = getattr(args, "delegation_tier", None)
    if tier:
        routing["delegation_tier"] = tier
        changed = True

    if changed:
        save_config(config)
        print("Smart model routing config saved.")

    for line in routing_status_lines():
        print(line)
    return 0
