"""Tests for IMAP message parsing (pure functions, fixtures, no server)."""

from __future__ import annotations

import email
from pathlib import Path

from maestro.normalize import clean_body
from maestro.sources.imap_source import (
    _first_fetch_payload,
    build_item_from_message,
    extract_text_from_message,
    imap_since_date,
    parse_date,
    parse_sender,
    thread_id_for,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return email.message_from_bytes((FIXTURES / name).read_bytes())


def test_parse_sender_and_date():
    display, addr = parse_sender('"Ana Souza" <ana@cliente.com>')
    assert display == "Ana Souza"
    assert addr == "ana@cliente.com"
    dt = parse_date("Wed, 24 Jun 2026 10:00:00 -0300")
    assert dt is not None and dt.tzinfo is not None
    assert parse_date("") is None


def test_build_item_from_plain_fixture():
    msg = _load("plain_signature.eml")
    item = build_item_from_message(msg, account="hostinger_empresa", uid="7")
    assert item.account == "hostinger_empresa"
    assert item.sender_email == "ana@cliente.com"
    assert item.subject == "Proposta comercial"
    assert item.msg_id == "abc123@cliente.com"
    assert item.uid == "7"
    assert item.date is not None


def test_extract_text_prefers_plain_and_clean_body_cuts_quote():
    msg = _load("multipart_quoted.eml")
    text, is_html = extract_text_from_message(msg)
    assert is_html is False
    assert "Minha resposta importante" in text
    cleaned = clean_body(text, is_html=is_html)
    assert "Minha resposta importante" in cleaned
    assert "texto antigo citado" not in cleaned  # quoted reply removed


def test_thread_id_uses_first_reference():
    msg = _load("multipart_quoted.eml")
    assert thread_id_for(msg) == "root000@cliente.com"


def test_signature_is_stripped_from_plain_body():
    msg = _load("plain_signature.eml")
    text, is_html = extract_text_from_message(msg)
    cleaned = clean_body(text, is_html=is_html)
    assert "proposta comercial revisada" in cleaned.lower()
    assert "Cliente Corp" not in cleaned  # signature block removed


def test_imap_since_date_format():
    token = imap_since_date(24)
    # DD-Mon-YYYY, e.g. 23-Jun-2026
    assert len(token.split("-")) == 3


def test_first_fetch_payload_extracts_bytes():
    msg_data = [(b"7 (UID 7 BODY[])", b"raw-bytes-here"), b")"]
    assert _first_fetch_payload(msg_data) == b"raw-bytes-here"
    assert _first_fetch_payload([]) is None
