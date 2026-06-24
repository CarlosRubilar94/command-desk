"""Digest delivery: WhatsApp self-chat (live) or a preview file (dry-run).

Live delivery reuses the **existing Hermes WhatsApp bridge** exactly like the
gateway's standalone cron path: an HTTP ``POST http://localhost:<port>/send``
with ``{"chatId": <jid>, "message": <text>}``. We use stdlib ``urllib`` (no
aiohttp dependency in this code path) and chunk long messages.

Dry-run never touches the network: it writes the full digest to a timestamped
preview file under ``<HERMES_HOME>/maestro/preview/`` and returns its path.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List

from .digest import chunk_message

logger = logging.getLogger(__name__)


def to_jid(target: str) -> str:
    """Normalize a phone number / id to a WhatsApp JID.

    Pass-through if it already looks like a JID (contains '@'); otherwise keep
    digits only and append the user domain. For a self-chat this is the user's
    own number.
    """
    target = (target or "").strip()
    if not target:
        return ""
    if "@" in target:
        return target
    digits = re.sub(r"\D", "", target)
    return f"{digits}@s.whatsapp.net" if digits else ""


class PreviewDelivery:
    """Dry-run sink: writes the digest to a file, sends nothing."""

    def __init__(self, preview_dir: Path):
        self.preview_dir = Path(preview_dir)

    def deliver(self, text: str) -> dict:
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.preview_dir / f"digest-{ts}.md"
        path.write_text(text, encoding="utf-8")
        logger.info("Maestro dry-run: digest written to %s", path)
        return {"delivered": False, "dry_run": True, "preview_path": str(path)}


class WhatsAppBridgeDelivery:
    """Live delivery to the WhatsApp self-chat via the local bridge."""

    def __init__(self, *, target: str, bridge_port: int = 3000, timeout: int = 30):
        self.target = target
        self.bridge_port = bridge_port
        self.timeout = timeout

    def _post(self, chat_id: str, message: str) -> dict:
        url = f"http://localhost:{self.bridge_port}/send"
        data = json.dumps({"chatId": chat_id, "message": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except ValueError:
            return {"raw": body}

    def deliver(self, text: str) -> dict:
        jid = to_jid(self.target)
        if not jid:
            return {
                "delivered": False,
                "error": "MAESTRO_WHATSAPP_TARGET not set (self-chat number/JID required)",
            }
        chunks: List[str] = chunk_message(text)
        message_ids = []
        for chunk in chunks:
            try:
                resp = self._post(jid, chunk)
            except (urllib.error.URLError, OSError) as exc:
                return {
                    "delivered": False,
                    "error": f"WhatsApp bridge send failed (port {self.bridge_port}): {exc}",
                    "sent_chunks": len(message_ids),
                }
            message_ids.append(resp.get("messageId") or resp.get("raw") or "ok")
        return {
            "delivered": True,
            "chat_id": jid,
            "sent_chunks": len(chunks),
            "message_ids": message_ids,
        }
