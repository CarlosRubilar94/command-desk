"""Maestro command-line entry point.

    python -m maestro.cli run [--dry-run] [--mock] [--no-cache]
    python -m maestro.cli install-cron [--hour 7] [--dry-run]
    python -m maestro.cli print-config
    python -m maestro.cli version

``run`` defaults to LIVE delivery (this is what the cron launcher calls).
``--dry-run`` (or ``--mock``, or ``MAESTRO_DRY_RUN=true``) writes a preview file
and sends nothing. ``--mock`` additionally uses built-in sample data and stays
fully offline (no Gemini / Claude CLI), which is the credential-free validation
path.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from .config import MaestroConfig
from .env import get_bool, load_env


def _mask(value: str, *, keep: int = 0) -> str:
    if not value:
        return "(unset)"
    if keep and len(value) > keep:
        return value[:keep] + "…"
    return "set" if value else "(unset)"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maestro", description="Maestro email→WhatsApp digest")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run the digest pipeline")
    mode = p_run.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write a preview file, send nothing")
    mode.add_argument("--live", action="store_true", help="Force live WhatsApp delivery")
    p_run.add_argument("--mock", action="store_true", help="Use sample data, fully offline (implies --dry-run)")
    p_run.add_argument("--no-cache", action="store_true", help="Ignore/skip the seen-id cache")
    p_run.add_argument("-v", "--verbose", action="store_true")

    p_cron = sub.add_parser("install-cron", help="Register the daily digest cron job")
    p_cron.add_argument("--hour", type=int, default=None, help="Local hour (0-23), default from config")
    p_cron.add_argument("--dry-run", action="store_true", help="Show the plan, write/create nothing")

    sub.add_parser("print-config", help="Print resolved config (secrets masked)")
    sub.add_parser("version", help="Print version")
    return parser


def _cmd_run(args) -> int:
    env = load_env()
    config = MaestroConfig.from_env(env)
    mock = bool(args.mock)
    dry_run = bool(args.dry_run) or mock or get_bool(env, "MAESTRO_DRY_RUN", False)
    if args.live and not mock:
        dry_run = False

    from .pipeline import run_pipeline

    result = run_pipeline(config, dry_run=dry_run, mock=mock, use_cache=not args.no_cache)
    print(result.summary_line())
    if result.preview_path:
        print(f"preview: {result.preview_path}")
    for w in result.warnings:
        print(f"warning: {w}")
    # Live runs fail loudly if nothing was delivered (so cron surfaces it).
    if not dry_run and not result.delivered:
        return 1
    return 0


def _cmd_install_cron(args) -> int:
    config = MaestroConfig.from_env()
    from .cron_install import install_cron

    info = install_cron(config, hour=args.hour, dry_run=args.dry_run)
    for k, v in info.items():
        print(f"{k}: {v}")
    if args.dry_run:
        print("\n(use without --dry-run to write the launcher and create the job)")
    return 0


def _cmd_print_config(_args) -> int:
    config = MaestroConfig.from_env()
    print("Maestro config (secrets masked):")
    print(f"  window_hours        = {config.window_hours}")
    print(f"  max_emails          = {config.max_emails}")
    print(f"  timezone            = {config.timezone}")
    print(f"  digest_hour         = {config.digest_hour}")
    print(f"  triage_model        = {config.triage_model}")
    print(f"  gemini_api_key      = {_mask(config.gemini_api_key)}")
    print(f"  reasoning_enabled   = {config.reasoning_enabled}")
    print(f"  claude_bin          = {config.claude_bin} (args={config.claude_args})")
    print(f"  whatsapp_target     = {_mask(config.whatsapp_target, keep=4)}")
    print(f"  whatsapp_bridge_port= {config.whatsapp_bridge_port}")
    print(f"  phase2_actions      = {config.phase2_actions_enabled} (Phase 1 is read-only)")
    print(f"  preview_dir         = {config.preview_path_dir}")
    print("  accounts:")
    for a in config.imap_accounts:
        status = "ready" if a.is_complete else "INCOMPLETE"
        print(f"    - imap '{a.account}' host={a.host}:{a.port} ssl={a.use_ssl} [{status}]")
    if config.gmail.enabled:
        print(f"    - gmail '{config.gmail.account}' via MCP '{config.gmail.server_name}' (q={config.gmail.query!r})")
    if not config.imap_accounts and not config.gmail.enabled:
        print("    (none configured — set MAESTRO_HOSTINGER_EMPRESA_* and/or MAESTRO_GMAIL_PESSOAL_ENABLED)")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "install-cron":
        return _cmd_install_cron(args)
    if args.command == "print-config":
        return _cmd_print_config(args)
    if args.command == "version":
        from . import __version__

        print(__version__)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
