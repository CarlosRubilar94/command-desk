"""Tests for delivery: JID normalization, preview sink, bridge send (mocked)."""

from __future__ import annotations

from maestro.delivery import PreviewDelivery, WhatsAppBridgeDelivery, to_jid


def test_to_jid():
    assert to_jid("+55 (11) 99999-0000") == "5511999990000@s.whatsapp.net"
    assert to_jid("5511999990000@s.whatsapp.net") == "5511999990000@s.whatsapp.net"
    assert to_jid("") == ""


def test_preview_delivery_writes_file(tmp_path):
    out = PreviewDelivery(tmp_path).deliver("conteúdo do digest")
    assert out["delivered"] is False
    assert out["dry_run"] is True
    written = list(tmp_path.glob("digest-*.md"))
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8") == "conteúdo do digest"


def test_bridge_delivery_requires_target():
    out = WhatsAppBridgeDelivery(target="").deliver("x")
    assert out["delivered"] is False
    assert "TARGET" in out["error"]


def test_bridge_delivery_sends_chunks(monkeypatch):
    sent = []
    d = WhatsAppBridgeDelivery(target="5511999990000", bridge_port=3000)
    monkeypatch.setattr(d, "_post", lambda chat_id, message: sent.append((chat_id, message)) or {"messageId": "x"})
    out = d.deliver("mensagem curta")
    assert out["delivered"] is True
    assert out["chat_id"] == "5511999990000@s.whatsapp.net"
    assert out["sent_chunks"] == 1
    assert sent[0][0] == "5511999990000@s.whatsapp.net"


def test_bridge_delivery_reports_send_failure(monkeypatch):
    import urllib.error

    d = WhatsAppBridgeDelivery(target="5511999990000")

    def boom(chat_id, message):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(d, "_post", boom)
    out = d.deliver("x")
    assert out["delivered"] is False
    assert "failed" in out["error"]
