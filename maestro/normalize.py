"""Normalization + token-economy helpers.

Pure functions (no I/O) so they are trivially unit-testable: subject
normalization, body cleanup (strip HTML / quoted replies / signatures),
dedupe-by-thread, and hard caps on volume.
"""

from __future__ import annotations

import re
from html import unescape
from typing import Dict, List, Sequence

from .models import EmailItem

# ---------------------------------------------------------------------------
# Subject / sender normalization
# ---------------------------------------------------------------------------

_REPLY_PREFIX_RE = re.compile(
    r"^\s*(re|fw|fwd|enc|encaminhada|res|rv)\s*(\[\d+\])?\s*:\s*",
    re.IGNORECASE,
)


def normalize_subject(subject: str) -> str:
    """Lower-case, strip reply/forward prefixes and collapse whitespace."""
    text = subject or ""
    prev = None
    while prev != text:
        prev = text
        text = _REPLY_PREFIX_RE.sub("", text, count=1)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


# ---------------------------------------------------------------------------
# Body cleanup
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")

# A quoted-reply boundary: once we hit one, everything after is older context.
_QUOTE_BOUNDARY_RE = re.compile(
    r"(?im)^\s*(?:"
    r">.*"                                              # >-quoted lines
    r"|on .+ wrote:"                                     # "On <date> X wrote:"
    r"|em .+ escreveu:"                                  # pt-BR variant
    r"|el .+ escribió:"                                  # es variant
    r"|-{2,}\s*original message\s*-{2,}"
    r"|_{5,}"                                            # Outlook divider
    r"|from:\s.+"                                         # forwarded header block
    r")\s*$"
)

# Common signature delimiters.
_SIGNATURE_RE = re.compile(r"(?m)^\s*--\s*$")


def html_to_text(html: str) -> str:
    """Very small HTML→text reducer (no external deps)."""
    text = _STYLE_SCRIPT_RE.sub(" ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    return text


def clean_body(body: str, *, is_html: bool = False, max_chars: int = 1200) -> str:
    """Strip HTML, quoted replies and signatures; collapse whitespace; truncate.

    Conservative: it never raises and always returns a string. Truncation is
    marked so the downstream model knows the body was cut.
    """
    if not body:
        return ""
    text = html_to_text(body) if is_html else body

    # Cut at the first quoted-reply boundary (older context is noise/cost).
    m = _QUOTE_BOUNDARY_RE.search(text)
    if m:
        text = text[: m.start()]

    # Drop signature block.
    sig = _SIGNATURE_RE.search(text)
    if sig:
        text = text[: sig.start()]

    text = _WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    text = text.strip()

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + " […]"
    return text


# ---------------------------------------------------------------------------
# Dedupe + caps
# ---------------------------------------------------------------------------

def dedupe_by_thread(items: Sequence[EmailItem]) -> List[EmailItem]:
    """Collapse a thread to a single representative (the most recent message).

    The kept item records ``extra['thread_count']`` so the digest can say
    "(+3 mensagens)". Items with no date sort last within their thread.
    """
    groups: Dict[str, List[EmailItem]] = {}
    order: List[str] = []
    for it in items:
        key = it.thread_key()
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(it)

    result: List[EmailItem] = []
    for key in order:
        members = groups[key]
        members_sorted = sorted(
            members,
            key=lambda e: (e.date is not None, e.date or _MIN_DT),
            reverse=True,
        )
        rep = members_sorted[0]
        rep.extra["thread_count"] = len(members)
        result.append(rep)
    return result


def sort_for_triage(items: Sequence[EmailItem]) -> List[EmailItem]:
    """Newest first (unknown dates last) for stable, bounded processing."""
    return sorted(
        items,
        key=lambda e: (e.date is not None, e.date or _MIN_DT),
        reverse=True,
    )


def cap_items(items: Sequence[EmailItem], max_items: int) -> List[EmailItem]:
    """Hard cap on emails processed per run (token economy)."""
    if max_items <= 0:
        return list(items)
    return list(items)[:max_items]


# Timezone-naive sentinel only used as a sort fallback for date-less items.
from datetime import datetime as _datetime  # noqa: E402

_MIN_DT = _datetime.min
