"""Tests for normalization, body cleanup, dedupe and caps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from maestro.models import EmailItem
from maestro.normalize import (
    cap_items,
    clean_body,
    dedupe_by_thread,
    html_to_text,
    normalize_subject,
    sort_for_triage,
)


def test_normalize_subject_strips_reply_prefixes():
    assert normalize_subject("Re: Fwd:  Proposta") == "proposta"
    assert normalize_subject("RES: Enc: Olá Mundo") == "olá mundo"
    assert normalize_subject("  Assunto Simples ") == "assunto simples"
    assert normalize_subject("Re[2]: tópico") == "tópico"


def test_html_to_text_and_clean_body_html():
    html = "<html><body><p>Olá</p><br>Mundo<script>evil()</script></body></html>"
    text = html_to_text(html)
    assert "Olá" in text and "Mundo" in text
    assert "evil" not in text


def test_clean_body_strips_quote_and_signature():
    body = (
        "Resposta principal aqui.\n\n"
        "On Wed, 24 Jun 2026, Ana wrote:\n"
        "> linha citada\n> outra\n"
    )
    cleaned = clean_body(body)
    assert "Resposta principal" in cleaned
    assert "linha citada" not in cleaned

    sig = "Conteúdo útil.\n-- \nFulano\nEmpresa"
    assert "Fulano" not in clean_body(sig)


def test_clean_body_truncates():
    long = "x" * 5000
    out = clean_body(long, max_chars=100)
    assert len(out) <= 110
    assert out.endswith("[…]")


def _item(account, msg_id, thread_id=None, subject="", hours_ago=1):
    return EmailItem(
        account=account,
        source_kind="mock",
        msg_id=msg_id,
        subject=subject,
        thread_id=thread_id,
        date=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


def test_dedupe_by_thread_collapses_same_thread():
    items = [
        _item("a", "1", thread_id="t1", hours_ago=3),
        _item("a", "2", thread_id="t1", hours_ago=1),  # newest in t1
        _item("a", "3", thread_id="t2", hours_ago=2),
    ]
    out = dedupe_by_thread(items)
    assert len(out) == 2
    t1 = [i for i in out if i.thread_key().endswith("t1")][0]
    assert t1.msg_id == "2"  # most recent kept
    assert t1.extra["thread_count"] == 2


def test_dedupe_by_subject_when_no_thread_id_but_account_scoped():
    items = [
        _item("a", "1", subject="Re: Olá"),
        _item("a", "2", subject="Olá"),       # same thread by subject within account a
        _item("b", "3", subject="Olá"),       # different account → separate
    ]
    out = dedupe_by_thread(items)
    assert len(out) == 2


def test_cap_and_sort():
    items = [
        _item("a", "1", hours_ago=5),
        _item("a", "2", hours_ago=1),
        _item("a", "3", hours_ago=3),
    ]
    ordered = sort_for_triage(items)
    assert [i.msg_id for i in ordered] == ["2", "3", "1"]
    assert len(cap_items(items, 2)) == 2
    assert len(cap_items(items, 0)) == 3
