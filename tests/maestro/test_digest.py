"""Tests for digest formatting and WhatsApp chunking."""

from __future__ import annotations

from maestro.digest import chunk_message, format_digest
from maestro.models import EmailItem, TriageResult, TriagedItem


def _ti(subject="Assunto", category="work", priority="high"):
    return TriagedItem(
        email=EmailItem(account="acc", source_kind="mock", msg_id="m1", subject=subject, sender="Ana"),
        triage=TriageResult(msg_id="m1", category=category, priority=priority),
    )


def test_format_digest_has_header_and_footer():
    md = format_digest(
        reasoning_summary="Resumo do dia.",
        items=[_ti()],
        tz_name="America/Sao_Paulo",
        accounts=["gmail_pessoal", "hostinger_empresa"],
        total_fetched=10,
        total_new=4,
        window_hours=24,
        warnings=["[gmail] indisponível"],
    )
    assert "Maestro" in md
    assert "gmail_pessoal" in md
    assert "Novos (últimas 24h): 4 de 10" in md
    assert "Resumo do dia." in md
    assert "indisponível" in md
    assert "somente leitura" in md


def test_chunk_message_single_when_short():
    assert chunk_message("curto") == ["curto"]


def test_chunk_message_splits_and_numbers():
    para = "A" * 1000
    text = "\n\n".join([para] * 10)  # ~10k chars
    chunks = chunk_message(text, max_chars=3000)
    assert len(chunks) > 1
    assert all(len(c) <= 3000 + 20 for c in chunks)  # allow numbering prefix
    assert chunks[0].startswith("(1/")


def test_chunk_message_hard_splits_giant_line():
    giant = "x" * 8000  # single line, no break points
    chunks = chunk_message(giant, max_chars=3000)
    assert len(chunks) >= 3
