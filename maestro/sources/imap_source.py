"""Hostinger / Titan IMAP source — stdlib only, strictly read-only.

Read-only guarantees (Phase 1 must never alter mailbox state):

* the mailbox is opened with ``readonly=True`` (IMAP ``EXAMINE``), and
* every fetch uses ``BODY.PEEK[...]`` so the ``\\Seen`` flag is never set.

The message→:class:`EmailItem` parsing is split into module-level pure
functions so it can be unit-tested from ``.eml`` fixtures without a server.
"""

from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from typing import List, Optional, Tuple

from ..models import EmailItem
from ..normalize import clean_body
from .base import EmailSource, SourceError, SourceResult

# Default IMAP hosts keyed by the Hostinger-vs-Titan flag.
PROVIDER_HOSTS = {
    "hostinger": "imap.hostinger.com",
    "titan": "imap.titan.email",
}
DEFAULT_PORT = 993


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable without a live server)
# ---------------------------------------------------------------------------

def decode_mime(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return str(value).strip()


def header_value(msg: Message, name: str) -> str:
    return decode_mime(msg.get(name, ""))


def parse_sender(from_header: str) -> Tuple[str, str]:
    """Return ``(display, email)`` from a raw From header."""
    pairs = getaddresses([from_header or ""])
    if not pairs:
        return (from_header or "").strip(), ""
    display, addr = pairs[0]
    display = decode_mime(display) or addr
    return display.strip(), (addr or "").strip().lower()


def parse_date(date_header: str) -> Optional[datetime]:
    if not date_header:
        return None
    try:
        dt = parsedate_to_datetime(date_header)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:  # treat naive dates as UTC for safe comparison
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _first_message_id(refs: str) -> Optional[str]:
    if not refs:
        return None
    ids = re.findall(r"<[^>]+>", refs)
    if ids:
        return ids[0].strip("<>")
    return None


def thread_id_for(msg: Message) -> Optional[str]:
    """Best-effort thread root from References / In-Reply-To."""
    root = _first_message_id(header_value(msg, "References"))
    if root:
        return root
    return _first_message_id(header_value(msg, "In-Reply-To"))


def build_item_from_message(
    msg: Message,
    *,
    account: str,
    uid: Optional[str] = None,
    kind: str = "imap",
) -> EmailItem:
    """Construct a metadata-only :class:`EmailItem` from a parsed message."""
    display, addr = parse_sender(header_value(msg, "From"))
    msg_id = header_value(msg, "Message-ID").strip("<>") or (f"uid:{uid}" if uid else "")
    return EmailItem(
        account=account,
        source_kind=kind,
        msg_id=msg_id or (f"{account}:uid:{uid}" if uid else f"{account}:nomid"),
        sender=display,
        sender_email=addr,
        subject=header_value(msg, "Subject"),
        snippet="",
        date=parse_date(header_value(msg, "Date")),
        date_raw=header_value(msg, "Date"),
        thread_id=thread_id_for(msg),
        unread=True,
        uid=str(uid) if uid is not None else None,
    )


def extract_text_from_message(msg: Message) -> Tuple[str, bool]:
    """Return ``(text, is_html)`` preferring text/plain over text/html."""
    plain: Optional[str] = None
    html: Optional[str] = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp.lower():
                continue
            if ctype == "text/plain" and plain is None:
                plain = _decode_part(part)
            elif ctype == "text/html" and html is None:
                html = _decode_part(part)
    else:
        payload = _decode_part(msg)
        if msg.get_content_type() == "text/html":
            html = payload
        else:
            plain = payload
    if plain:
        return plain, False
    if html:
        return html, True
    return "", False


def _decode_part(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return ""
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def imap_since_date(window_hours: int, *, now: Optional[datetime] = None) -> str:
    """IMAP SINCE token (date-granular) covering the window with a 1-day margin."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=window_hours) - timedelta(days=1)
    return since.strftime("%d-%b-%Y")


# ---------------------------------------------------------------------------
# Live IMAP source
# ---------------------------------------------------------------------------

class ImapSource(EmailSource):
    def __init__(
        self,
        *,
        account: str,
        host: str,
        port: int = DEFAULT_PORT,
        user: str,
        password: str,
        use_ssl: bool = True,
        mailbox: str = "INBOX",
        timeout: int = 30,
    ):
        self.account = account
        self.kind = "imap"
        self.host = host
        self.port = port
        self.user = user
        self._password = password
        self.use_ssl = use_ssl
        self.mailbox = mailbox or "INBOX"
        self.timeout = timeout
        self._conn: Optional[imaplib.IMAP4] = None

    def _connect(self) -> imaplib.IMAP4:
        if self._conn is not None:
            return self._conn
        if not self.host or not self.user or not self._password:
            raise SourceError(f"[{self.account}] missing IMAP host/user/password")
        try:
            if self.use_ssl:
                conn = imaplib.IMAP4_SSL(self.host, self.port, timeout=self.timeout)
            else:
                conn = imaplib.IMAP4(self.host, self.port, timeout=self.timeout)
                try:
                    conn.starttls()
                except Exception:
                    pass
            conn.login(self.user, self._password)
            # readonly=True → EXAMINE, never alters \Seen on select.
            conn.select(self.mailbox, readonly=True)
        except (imaplib.IMAP4.error, OSError) as exc:
            raise SourceError(f"[{self.account}] IMAP connect/login failed: {exc}") from exc
        self._conn = conn
        return conn

    def fetch_metadata(self, *, window_hours: int, max_items: int) -> SourceResult:
        result = SourceResult(account=self.account)
        try:
            conn = self._connect()
        except SourceError as exc:
            result.warnings.append(str(exc))
            return result

        since = imap_since_date(window_hours)
        try:
            typ, data = conn.uid("search", None, "UNSEEN", "SINCE", since)
        except imaplib.IMAP4.error as exc:
            result.warnings.append(f"[{self.account}] IMAP search failed: {exc}")
            return result
        if typ != "OK" or not data or not data[0]:
            return result

        uids = data[0].split()
        # Newest UIDs last in IMAP; take the most recent `max_items`.
        if max_items > 0:
            uids = uids[-max_items:]

        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        header_fields = "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID REFERENCES IN-REPLY-TO)])"
        for uid_b in uids:
            uid = uid_b.decode() if isinstance(uid_b, bytes) else str(uid_b)
            try:
                typ, msg_data = conn.uid("fetch", uid, header_fields)
            except imaplib.IMAP4.error as exc:
                result.warnings.append(f"[{self.account}] fetch uid {uid} failed: {exc}")
                continue
            raw = _first_fetch_payload(msg_data)
            if not raw:
                continue
            msg = email.message_from_bytes(raw)
            item = build_item_from_message(msg, account=self.account, uid=uid, kind=self.kind)
            if item.date and item.date < cutoff:
                continue
            result.items.append(item)
        return result

    def fetch_body(self, item: EmailItem, *, max_chars: int) -> str:
        if not item.uid:
            return item.snippet or ""
        try:
            conn = self._connect()
            typ, msg_data = conn.uid("fetch", item.uid, "(BODY.PEEK[])")
        except (SourceError, imaplib.IMAP4.error) as exc:
            return f"(corpo indisponível: {exc})"
        raw = _first_fetch_payload(msg_data)
        if not raw:
            return ""
        msg = email.message_from_bytes(raw)
        text, is_html = extract_text_from_message(msg)
        return clean_body(text, is_html=is_html, max_chars=max_chars)

    def close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass


def _first_fetch_payload(msg_data) -> Optional[bytes]:
    """Pull the raw RFC822 bytes out of an imaplib fetch response tuple."""
    if not msg_data:
        return None
    for part in msg_data:
        if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
            return bytes(part[1])
    return None


def build_imap_source_from_config(acct_cfg) -> ImapSource:
    """Build an :class:`ImapSource` from an ``ImapAccountConfig``."""
    return ImapSource(
        account=acct_cfg.account,
        host=acct_cfg.host,
        port=acct_cfg.port,
        user=acct_cfg.user,
        password=acct_cfg.password,
        use_ssl=acct_cfg.use_ssl,
        mailbox=acct_cfg.mailbox,
    )
