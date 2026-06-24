"""Maestro daily-digest pipeline orchestration.

    ingest (multi-account, metadata-first)
      → dedupe-by-thread → seen-id cache → cap
      → cheap triage (Gemini Flash / heuristic)
      → fetch bodies ONLY for items that passed triage (token economy)
      → reasoning (Claude CLI / template) → digest → deliver

Every source is isolated: a failing account contributes a warning, never a
crash. Phase 1 is strictly read-only.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

from .cache import SeenCache
from .config import MaestroConfig
from .delivery import PreviewDelivery, WhatsAppBridgeDelivery
from .digest import format_digest
from .models import DigestResult, EmailItem, TriagedItem
from .normalize import cap_items, dedupe_by_thread, sort_for_triage
from .reason import generate_reasoning
from .sources.base import EmailSource
from .triage import attach_thread_keys, triage_items

logger = logging.getLogger(__name__)


def build_sources(config: MaestroConfig, *, mock: bool = False) -> List[EmailSource]:
    """Construct the configured ingestion sources (or mock sources)."""
    if mock:
        from .sources.mock_source import MockSource

        return [MockSource("hostinger_empresa"), MockSource("gmail_pessoal")]

    sources: List[EmailSource] = []
    from .sources.imap_source import build_imap_source_from_config

    for acct in config.imap_accounts:
        if acct.is_complete:
            sources.append(build_imap_source_from_config(acct))

    if config.gmail.enabled:
        from .sources.gmail_mcp import GmailMcpSource, build_hermes_mcp_client

        mcp_call = build_hermes_mcp_client(config.gmail.server_name)
        sources.append(
            GmailMcpSource(
                account=config.gmail.account,
                mcp_call=mcp_call,
                server_name=config.gmail.server_name,
                query=config.gmail.query,
            )
        )
    return sources


def _needs_body(ti: TriagedItem) -> bool:
    return ti.triage.priority == "high" or ti.triage.needs_action


def run_pipeline(
    config: MaestroConfig,
    *,
    dry_run: bool = True,
    mock: bool = False,
    use_cache: bool = True,
    sources: Optional[Sequence[EmailSource]] = None,
    delivery=None,
    force_heuristic_triage: Optional[bool] = None,
    force_template_reasoning: Optional[bool] = None,
) -> DigestResult:
    # Mock runs are fully hermetic (no network / no CLI) unless overridden.
    if force_heuristic_triage is None:
        force_heuristic_triage = mock
    if force_template_reasoning is None:
        force_template_reasoning = mock

    result = DigestResult(dry_run=dry_run)
    owned_sources = sources is None
    srcs = list(sources) if sources is not None else build_sources(config, mock=mock)

    # ---- 1. Ingestion (per-source isolation) ---------------------------
    all_items: List[EmailItem] = []
    source_by_account: Dict[str, EmailSource] = {}
    try:
        for src in srcs:
            source_by_account[src.account] = src
            try:
                sr = src.fetch_metadata(window_hours=config.window_hours, max_items=config.max_emails)
                all_items.extend(sr.items)
                result.warnings.extend(sr.warnings)
            except Exception as exc:  # never let one account kill the run
                logger.warning("Maestro: source %s failed: %s", getattr(src, "account", "?"), exc)
                result.warnings.append(f"[{getattr(src, 'account', '?')}] falhou: {exc}")

        result.total_fetched = len(all_items)
        result.accounts = sorted({it.account for it in all_items}) or config.account_labels()

        # ---- 2. Dedupe + cache + cap -----------------------------------
        deduped = dedupe_by_thread(all_items)
        result.total_after_dedupe = len(deduped)
        deduped = sort_for_triage(deduped)

        cache: Optional[SeenCache] = None
        if use_cache:
            cache = SeenCache(
                config.seen_cache_path,
                ttl_days=config.cache_ttl_days,
                persist=not dry_run,
            )
            fresh = cache.filter_new(deduped)
        else:
            fresh = deduped
        result.total_after_cache = len(fresh)

        capped = cap_items(fresh, config.max_emails)

        # ---- 3. Triage -------------------------------------------------
        triage_results, triage_backend = triage_items(
            capped,
            api_key=config.gemini_api_key,
            model=config.triage_model,
            base_url=config.gemini_base_url,
            force_heuristic=force_heuristic_triage,
        )
        attach_thread_keys(triage_results, capped)
        result.triage_backend = triage_backend

        by_id = {it.msg_id: it for it in capped}
        triaged: List[TriagedItem] = []
        triage_by_id = {r.msg_id: r for r in triage_results}
        for it in capped:
            tr = triage_by_id.get(it.msg_id)
            if tr is None:
                continue
            triaged.append(TriagedItem(email=it, triage=tr))

        # Priority order: high → normal → low, newest first within a rank.
        triaged.sort(
            key=lambda ti: (ti.triage.rank(), -(ti.email.date.timestamp() if ti.email.date else 0))
        )

        # ---- 4. Fetch bodies ONLY for items that passed triage ---------
        for ti in triaged:
            if not _needs_body(ti) or ti.email.body:
                continue
            src = source_by_account.get(ti.email.account)
            if src is None:
                continue
            try:
                ti.email.body = src.fetch_body(ti.email, max_chars=config.body_max_chars)
            except Exception as exc:
                logger.info("Maestro: body fetch failed for %s: %s", ti.email.msg_id, exc)

        # ---- 5. Reasoning ----------------------------------------------
        summary, reasoning_backend = generate_reasoning(
            triaged,
            enabled=config.reasoning_enabled,
            claude_bin=config.claude_bin,
            claude_args=config.claude_args,
            timeout=config.claude_timeout,
            body_max_chars=config.body_max_chars,
            force_template=force_template_reasoning,
        )
        result.reasoning_backend = reasoning_backend

        # ---- 6. Digest -------------------------------------------------
        markdown = format_digest(
            reasoning_summary=summary,
            items=triaged,
            tz_name=config.timezone,
            accounts=result.accounts,
            total_fetched=result.total_fetched,
            total_new=result.total_after_cache,
            window_hours=config.window_hours,
            warnings=result.warnings,
        )
        result.markdown = markdown

        # ---- 7. Delivery -----------------------------------------------
        if delivery is None:
            delivery = (
                PreviewDelivery(config.preview_path_dir)
                if dry_run
                else WhatsAppBridgeDelivery(
                    target=config.whatsapp_target, bridge_port=config.whatsapp_bridge_port
                )
            )
        outcome = delivery.deliver(markdown)
        result.delivered = bool(outcome.get("delivered"))
        if outcome.get("preview_path"):
            result.preview_path = outcome["preview_path"]
        if outcome.get("error"):
            result.warnings.append(f"entrega: {outcome['error']}")

        # ---- 8. Mark seen (only on a real, non-dry delivery) -----------
        if cache is not None and not dry_run and result.delivered:
            cache.mark_seen(capped)
            cache.save()

        return result
    finally:
        if owned_sources:
            for src in srcs:
                try:
                    src.close()
                except Exception:
                    pass
