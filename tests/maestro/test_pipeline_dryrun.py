"""Integration tests for the pipeline in dry-run / mock mode (no creds, no net)."""

from __future__ import annotations

import json

from maestro.config import MaestroConfig
from maestro.models import EmailItem
from maestro.pipeline import run_pipeline
from maestro.sources.base import EmailSource, SourceResult
from maestro.sources.mock_source import MockSource


def _config(tmp_path):
    return MaestroConfig(home=tmp_path, preview_dir=str(tmp_path / "preview"))


class _CapturingDelivery:
    def __init__(self):
        self.text = None

    def deliver(self, text):
        self.text = text
        return {"delivered": False, "dry_run": True, "preview_path": "captured"}


class _FailingSource(EmailSource):
    account = "broken_acct"
    kind = "imap"

    def fetch_metadata(self, *, window_hours, max_items):
        raise RuntimeError("IMAP exploded")


def test_mock_dry_run_end_to_end(tmp_path):
    cfg = _config(tmp_path)
    result = run_pipeline(cfg, dry_run=True, mock=True)
    assert result.dry_run is True
    assert result.delivered is False
    assert result.total_fetched == 8
    assert result.total_after_dedupe == 6  # t-001 thread collapses per account
    assert result.triage_backend == "heuristic"
    assert result.reasoning_backend.startswith("template")
    assert result.preview_path
    # Preview file actually written
    previews = list((tmp_path / "preview").glob("digest-*.md"))
    assert len(previews) == 1
    assert "Maestro" in previews[0].read_text(encoding="utf-8")


def test_dry_run_never_marks_cache(tmp_path):
    cfg = _config(tmp_path)
    run_pipeline(cfg, dry_run=True, mock=True)
    assert not cfg.seen_cache_path.exists()  # dry-run must not persist seen-ids


def test_source_isolation_failing_source_warns_but_completes(tmp_path):
    cfg = _config(tmp_path)
    delivery = _CapturingDelivery()
    sources = [_FailingSource(), MockSource("hostinger_empresa")]
    result = run_pipeline(
        cfg, dry_run=True, mock=False, sources=sources, delivery=delivery,
        force_heuristic_triage=True, force_template_reasoning=True,
    )
    assert any("broken_acct" in w for w in result.warnings)
    assert delivery.text is not None  # digest still produced
    assert result.total_fetched == 4  # only the mock account contributed


def test_seen_cache_filters_already_processed(tmp_path):
    cfg = _config(tmp_path)
    cfg.seen_cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Pre-seed the cache with two of the mock message ids.
    cfg.seen_cache_path.write_text(
        json.dumps({"seen": {"hostinger_empresa-002": "2026-06-24T00:00:00+00:00",
                             "gmail_pessoal-002": "2026-06-24T00:00:00+00:00"}}),
        encoding="utf-8",
    )
    result = run_pipeline(cfg, dry_run=True, mock=True, use_cache=True)
    assert result.total_after_dedupe == 6
    assert result.total_after_cache == 4  # two filtered out by cache


def test_no_cache_flag_skips_filtering(tmp_path):
    cfg = _config(tmp_path)
    result = run_pipeline(cfg, dry_run=True, mock=True, use_cache=False)
    assert result.total_after_cache == result.total_after_dedupe


def test_injected_sources_metadata_first(tmp_path):
    # MockSource.fetch_metadata must not leak bodies (token economy).
    src = MockSource("acc")
    meta = src.fetch_metadata(window_hours=24, max_items=10)
    assert all(isinstance(i, EmailItem) for i in meta.items)
    assert all(i.body is None for i in meta.items)
