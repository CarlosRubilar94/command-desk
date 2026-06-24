"""Format the final WhatsApp digest and split it into sendable chunks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from .models import TriagedItem

_PT_WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# WhatsApp hard limit is ~65k chars; we chunk well under that for readability.
DEFAULT_CHUNK_CHARS = 3500


def _resolve_now(tz_name: str) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now(timezone.utc)


def format_timestamp(dt: datetime, tz_name: str) -> str:
    weekday = _PT_WEEKDAYS[dt.weekday()]
    return f"{weekday}, {dt.strftime('%d/%m/%Y %H:%M')} ({tz_name})"


def _category_counts(items: Sequence[TriagedItem]) -> str:
    counts: dict[str, int] = {}
    for ti in items:
        counts[ti.triage.category] = counts.get(ti.triage.category, 0) + 1
    if not counts:
        return ""
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return " · ".join(f"{cat}: {n}" for cat, n in ordered)


def format_digest(
    *,
    reasoning_summary: str,
    items: Sequence[TriagedItem],
    tz_name: str,
    accounts: Sequence[str],
    total_fetched: int,
    total_new: int,
    window_hours: int,
    warnings: Optional[Sequence[str]] = None,
    now: Optional[datetime] = None,
) -> str:
    now = now or _resolve_now(tz_name)
    header_lines = [
        "🎼 *Maestro — Resumo diário*",
        format_timestamp(now, tz_name),
        f"Contas: {', '.join(accounts) if accounts else 'nenhuma'}",
        f"Novos (últimas {window_hours}h): {total_new} de {total_fetched} buscados",
    ]
    cats = _category_counts(items)
    if cats:
        header_lines.append(f"Categorias: {cats}")

    parts = ["\n".join(header_lines), reasoning_summary.strip()]

    if warnings:
        warn_block = "\n".join(f"⚠️ {w}" for w in warnings)
        parts.append("*Avisos*\n" + warn_block)

    parts.append(
        "_Fase 1 (somente leitura): nenhum e-mail foi modificado. "
        "Responda a este chat para conversar sobre os itens._"
    )
    return "\n\n".join(p for p in parts if p.strip())


def chunk_message(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> List[str]:
    """Split a long message on paragraph/line boundaries, never mid-word."""
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    current = ""
    for para in text.split("\n\n"):
        candidate = para if not current else current + "\n\n" + para
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(para) <= max_chars:
            current = para
            continue
        # Paragraph itself too big: split on single newlines, then hard-cut.
        for line in para.split("\n"):
            cand2 = line if not current else current + "\n" + line
            if len(cand2) <= max_chars:
                current = cand2
            else:
                if current:
                    chunks.append(current)
                while len(line) > max_chars:
                    chunks.append(line[:max_chars])
                    line = line[max_chars:]
                current = line
    if current:
        chunks.append(current)
    total = len(chunks)
    if total > 1:
        chunks = [f"({i}/{total}) {c}" for i, c in enumerate(chunks, start=1)]
    return chunks
