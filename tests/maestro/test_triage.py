"""Tests for triage: heuristic classification + Gemini parsing (mocked)."""

from __future__ import annotations

import json

import pytest

from maestro import triage
from maestro.models import EmailItem
from maestro.triage import (
    GeminiTriager,
    extract_json_array,
    heuristic_triage_one,
    parse_triage_results,
    triage_items,
)


def _item(subject, sender_email="x@corp.com", snippet="", msg_id="m1"):
    return EmailItem(
        account="acc", source_kind="mock", msg_id=msg_id,
        subject=subject, sender_email=sender_email, snippet=snippet,
    )


def test_heuristic_finance_beats_newsletter_for_noreply_sender():
    # An invoice from a no-reply@ sender must be finance, not newsletter.
    r = heuristic_triage_one(_item("Sua fatura vence amanhã", "no-reply@bank.com"))
    assert r.category == "finance"
    assert r.needs_action is True


def test_heuristic_priorities_and_categories():
    assert heuristic_triage_one(_item("Proposta urgente, prazo hoje")).priority == "high"
    assert heuristic_triage_one(_item("DevWeekly newsletter #1")).category == "newsletter"
    assert heuristic_triage_one(_item("DevWeekly newsletter #1")).priority == "low"
    assert heuristic_triage_one(_item("Promoção: 50% desconto")).category == "promo"
    assert heuristic_triage_one(_item("Convite para reunião quinta")).category == "calendar"


def test_extract_json_array_handles_fences_and_prose():
    assert extract_json_array('```json\n[{"a":1}]\n```') == [{"a": 1}]
    assert extract_json_array('lixo antes [{"a":1}] lixo depois') == [{"a": 1}]
    assert extract_json_array('{"items":[{"a":1}]}') == [{"a": 1}]


def test_parse_triage_results_filters_unknown_ids_and_clamps():
    raw = [
        {"msg_id": "m1", "priority": "HIGH", "category": "Work", "needs_action": True},
        {"msg_id": "bogus", "priority": "high"},
        {"priority": "low"},
    ]
    out = parse_triage_results(raw, ["m1"])
    assert len(out) == 1
    assert out[0].priority == "high"
    assert out[0].category == "work"


def test_gemini_triager_parses_mocked_response(monkeypatch):
    items = [_item("Proposta", msg_id="m1"), _item("Newsletter", msg_id="m2")]
    fake_text = json.dumps(
        [
            {"msg_id": "m1", "priority": "high", "category": "work", "needs_action": True,
             "suggested_action": "Responder", "reason": "cliente"},
            {"msg_id": "m2", "priority": "low", "category": "newsletter", "needs_action": False},
        ]
    )
    fake_resp = {"candidates": [{"content": {"parts": [{"text": fake_text}]}}]}
    monkeypatch.setattr(triage, "_http_post_json", lambda *a, **k: fake_resp)

    results = GeminiTriager(api_key="k", model="gemini-2.5-flash", base_url="http://x").triage(items)
    by_id = {r.msg_id: r for r in results}
    assert by_id["m1"].priority == "high" and by_id["m1"].needs_action
    assert by_id["m2"].category == "newsletter"


def test_triage_items_falls_back_to_heuristic_without_key():
    items = [_item("Fatura vence")]
    results, backend = triage_items(items, api_key="")
    assert backend == "heuristic"
    assert results[0].category == "finance"


def test_triage_items_falls_back_when_gemini_raises(monkeypatch):
    def boom(*a, **k):
        raise triage.TriageError("network down")

    monkeypatch.setattr(triage, "_http_post_json", boom)
    results, backend = triage_items([_item("Proposta")], api_key="k")
    assert "heuristic" in backend
    assert results
