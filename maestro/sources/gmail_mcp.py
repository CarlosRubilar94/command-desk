"""Gmail (personal) source via the Hermes ``user-google-tools`` MCP server.

The OAuth session for ``user-google-tools`` is owned by Hermes' MCP layer, so we
never handle a Google secret here. This module is decoupled from the MCP
transport via a pluggable ``mcp_call`` callable::

    mcp_call(server: str, tool: str, arguments: dict) -> Any

so it is fully unit-testable with a fake client, and the live binding
(:func:`build_hermes_mcp_client`) degrades to ``None`` when the MCP/OAuth
session is unavailable (the pipeline then simply skips Gmail with a warning).

Token economy: triage uses ``list_messages`` with ``format=metadata`` (no
bodies); bodies are fetched per-item only after triage via ``get_message``
with a ``maxBodyChars`` cap.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Optional

from ..models import EmailItem
from ..normalize import clean_body
from .base import EmailSource, SourceError, SourceResult
from .imap_source import parse_date, parse_sender

logger = logging.getLogger(__name__)

McpCall = Callable[[str, str, dict], Any]


def _as_obj(value: Any) -> Any:
    """Coerce an MCP tool result (often a JSON string) into a Python object."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _headers_map(message: dict) -> dict:
    """Return a case-insensitive header dict from a raw Gmail payload, if present."""
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else None
    headers = (payload or {}).get("headers") if payload else message.get("headers")
    out = {}
    if isinstance(headers, list):
        for h in headers:
            if isinstance(h, dict) and "name" in h:
                out[str(h["name"]).lower()] = h.get("value", "")
    elif isinstance(headers, dict):
        out = {str(k).lower(): v for k, v in headers.items()}
    return out


def _field(message: dict, *names: str) -> str:
    """Pick the first present field from the message body or its headers."""
    for n in names:
        if message.get(n):
            return str(message[n])
    hdrs = _headers_map(message)
    for n in names:
        if hdrs.get(n.lower()):
            return str(hdrs[n.lower()])
    return ""


def parse_gmail_messages(payload: Any, *, account: str) -> List[EmailItem]:
    """Tolerant parser for ``list_messages`` / ``list_threads`` responses."""
    obj = _as_obj(payload)
    messages: List[dict] = []
    if isinstance(obj, dict):
        for key in ("messages", "items", "threads", "results"):
            seq = obj.get(key)
            if isinstance(seq, list):
                for entry in seq:
                    if isinstance(entry, dict) and isinstance(entry.get("messages"), list):
                        messages.extend(m for m in entry["messages"] if isinstance(m, dict))
                    elif isinstance(entry, dict):
                        messages.append(entry)
                break
    elif isinstance(obj, list):
        messages = [m for m in obj if isinstance(m, dict)]

    items: List[EmailItem] = []
    for m in messages:
        from_raw = _field(m, "from", "From")
        display, addr = parse_sender(from_raw)
        date_raw = _field(m, "date", "Date", "internalDate")
        labels = m.get("labelIds") or m.get("labels") or []
        if not isinstance(labels, list):
            labels = [str(labels)]
        msg_id = str(m.get("id") or m.get("messageId") or _field(m, "message-id", "Message-ID"))
        items.append(
            EmailItem(
                account=account,
                source_kind="gmail_mcp",
                msg_id=msg_id or f"{account}:nomid",
                sender=display or from_raw,
                sender_email=addr,
                subject=_field(m, "subject", "Subject"),
                snippet=str(m.get("snippet", "")),
                date=parse_date(date_raw),
                date_raw=date_raw,
                thread_id=str(m["threadId"]) if m.get("threadId") else None,
                labels=[str(x) for x in labels],
                unread=("UNREAD" in [str(x).upper() for x in labels]) or True,
                extra={"gmail_id": msg_id},
            )
        )
    return items


def extract_gmail_body(payload: Any) -> str:
    """Pull a body string out of a ``get_message`` response (tolerant)."""
    obj = _as_obj(payload)
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for key in ("body", "text", "cleanBody", "plain", "snippet"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return val
        # Raw Gmail payload: payload.body.data is base64; fall back to snippet.
        snippet = obj.get("snippet")
        if isinstance(snippet, str):
            return snippet
    return ""


class GmailMcpSource(EmailSource):
    def __init__(
        self,
        *,
        account: str = "gmail_pessoal",
        mcp_call: Optional[McpCall],
        server_name: str = "user-google-tools",
        query: str = "is:unread newer_than:1d",
    ):
        self.account = account
        self.kind = "gmail_mcp"
        self._mcp_call = mcp_call
        self.server_name = server_name
        self.query = query

    def fetch_metadata(self, *, window_hours: int, max_items: int) -> SourceResult:
        result = SourceResult(account=self.account)
        if self._mcp_call is None:
            result.warnings.append(
                f"[{self.account}] Gmail MCP client unavailable — skipping "
                f"(configure the '{self.server_name}' MCP + OAuth to enable)."
            )
            return result
        query = self.query or f"is:unread newer_than:{max(1, window_hours // 24)}d"
        args = {
            "q": query,
            "format": "metadata",
            "maxResults": max_items if max_items > 0 else 50,
        }
        try:
            raw = self._mcp_call(self.server_name, "list_messages", args)
        except Exception as exc:  # any transport/auth failure → degrade
            result.warnings.append(f"[{self.account}] list_messages failed: {exc}")
            return result

        items = parse_gmail_messages(raw, account=self.account)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        for it in items:
            if it.date and it.date < cutoff:
                continue
            result.items.append(it)
        if max_items > 0:
            result.items = result.items[:max_items]
        return result

    def fetch_body(self, item: EmailItem, *, max_chars: int) -> str:
        if self._mcp_call is None:
            return item.snippet or ""
        gmail_id = item.extra.get("gmail_id") or item.msg_id
        try:
            raw = self._mcp_call(
                self.server_name,
                "get_message",
                {"id": gmail_id, "format": "clean", "maxBodyChars": max_chars},
            )
        except Exception as exc:
            return item.snippet or f"(corpo indisponível: {exc})"
        body = extract_gmail_body(raw)
        return clean_body(body, is_html=False, max_chars=max_chars)


def build_hermes_mcp_client(server_name: str = "user-google-tools") -> Optional[McpCall]:
    """Best-effort live MCP client bound to a Hermes-configured server.

    Returns a synchronous ``mcp_call(server, tool, args)`` or ``None`` when the
    MCP SDK / server config / OAuth session is unavailable. Never raises — a
    missing live binding must only degrade Gmail ingestion, never crash the run.
    """
    try:
        from hermes_cli.config import load_config  # heavy import; only at runtime
    except Exception:
        logger.info("Maestro: hermes_cli.config unavailable; Gmail MCP disabled.")
        return None

    try:
        servers = (load_config() or {}).get("mcp_servers") or {}
        server_cfg = servers.get(server_name)
    except Exception:
        server_cfg = None
    if not isinstance(server_cfg, dict):
        logger.info("Maestro: MCP server '%s' not configured; Gmail MCP disabled.", server_name)
        return None

    try:
        # Reuse Hermes' own MCP machinery if it exposes a synchronous caller.
        from tools.mcp_tool import call_mcp_tool_sync  # type: ignore

        def _call(server: str, tool: str, arguments: dict) -> Any:
            return call_mcp_tool_sync(server, tool, arguments)

        return _call
    except Exception:
        # No simple synchronous entry point in this build — the live binding is
        # finalized at activation time. Degrade rather than guess the transport.
        logger.info(
            "Maestro: no synchronous MCP caller in tools.mcp_tool; Gmail MCP "
            "ingestion will be skipped until wired at activation."
        )
        return None
