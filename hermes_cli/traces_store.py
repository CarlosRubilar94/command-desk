from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from hermes_constants import get_hermes_home

_DB_LOCK = threading.RLock()
_DB_INITIALIZED = False

TRACE_DB_NAME = "traces.db"
DEFAULT_ROW_CAP = 250_000

_ALLOWED_ATTRIBUTE_KEYS = {
    "trace_id",
    "parent_id",
    "session_id",
    "turn_id",
    "api_request_id",
    "tool_call_id",
    "kind",
    "status",
    "model",
    "provider",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "error_class",
    "parent_session_id",
    "child_session_id",
    "child_role",
    "child_status",
}

_SPAN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_id TEXT,
    session_id TEXT,
    kind TEXT NOT NULL,
    name TEXT,
    agent TEXT,
    model TEXT,
    provider TEXT,
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    duration_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd REAL,
    error TEXT,
    attributes TEXT
);

CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_session_id ON spans(session_id);
CREATE INDEX IF NOT EXISTS idx_spans_started_kind_status ON spans(started_at, kind, status);
"""

_MISSIONS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    board_slug TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    owner TEXT,
    created_at REAL NOT NULL,
    tags TEXT,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_missions_board_status_created
    ON missions(board_slug, status, created_at);
"""


def traces_db_path() -> Path:
    return get_hermes_home() / TRACE_DB_NAME


def _secure_owner_only(path: Path) -> None:
    if not path.exists():
        return
    try:
        if sys.platform == "win32":
            # Best effort on Windows: keep the file writable for the current user
            # and try to tighten ACL inheritance where icacls is available.
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            user = (os.environ.get("USERNAME") or "").strip()
            if user:
                subprocess.run(
                    [
                        "icacls",
                        str(path),
                        "/inheritance:r",
                        "/grant:r",
                        f"{user}:(R,W)",
                    ],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError, ValueError):
        pass


def _connect() -> sqlite3.Connection:
    db_path = traces_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    _secure_owner_only(db_path)
    return conn


def ensure_initialized() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with _DB_LOCK:
        if _DB_INITIALIZED:
            return
        conn = _connect()
        try:
            conn.executescript(_SPAN_SCHEMA_SQL)
            conn.executescript(_MISSIONS_SCHEMA_SQL)
        finally:
            conn.close()
        _DB_INITIALIZED = True


def _clean_attributes(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in _ALLOWED_ATTRIBUTE_KEYS:
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            cleaned[str(key)] = value
    return cleaned


def _row_to_span_dict(row: sqlite3.Row) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    raw_attributes = row["attributes"]
    if isinstance(raw_attributes, str) and raw_attributes:
        try:
            parsed = json.loads(raw_attributes)
            if isinstance(parsed, dict):
                attributes = parsed
        except Exception:
            attributes = {}
    return {
        "span_id": row["span_id"],
        "trace_id": row["trace_id"],
        "parent_id": row["parent_id"],
        "session_id": row["session_id"],
        "kind": row["kind"],
        "name": row["name"],
        "agent": row["agent"],
        "model": row["model"],
        "provider": row["provider"],
        "status": row["status"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_ms": row["duration_ms"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "total_tokens": row["total_tokens"],
        "cost_usd": row["cost_usd"],
        "error": row["error"],
        "attributes": attributes,
    }


def insert_span(span: Mapping[str, Any]) -> dict[str, Any]:
    ensure_initialized()
    now = float(time.time())
    span_id = str(span.get("span_id") or uuid4())
    trace_id = str(span.get("trace_id") or "")
    if not trace_id:
        raise ValueError("trace_id is required")

    started_at = float(span.get("started_at") or now)
    ended_at = span.get("ended_at")
    ended_at_value = float(ended_at) if ended_at is not None else None

    input_tokens = int(span.get("input_tokens") or 0)
    output_tokens = int(span.get("output_tokens") or 0)
    total_tokens = span.get("total_tokens")
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    values = {
        "span_id": span_id,
        "trace_id": trace_id,
        "parent_id": span.get("parent_id"),
        "session_id": span.get("session_id"),
        "kind": str(span.get("kind") or "agent_turn"),
        "name": span.get("name"),
        "agent": span.get("agent"),
        "model": span.get("model"),
        "provider": span.get("provider"),
        "status": str(span.get("status") or "ok"),
        "started_at": started_at,
        "ended_at": ended_at_value,
        "duration_ms": span.get("duration_ms"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(total_tokens or 0),
        "cost_usd": span.get("cost_usd"),
        "error": span.get("error"),
        "attributes": json.dumps(
            _clean_attributes(span.get("attributes")),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    replace_sql = "INSERT OR REPLACE" if bool(span.get("_upsert")) else "INSERT"
    conn = _connect()
    try:
        conn.execute(
            f"""
            {replace_sql} INTO spans (
                span_id, trace_id, parent_id, session_id, kind, name, agent, model, provider,
                status, started_at, ended_at, duration_ms, input_tokens, output_tokens,
                total_tokens, cost_usd, error, attributes
            ) VALUES (
                :span_id, :trace_id, :parent_id, :session_id, :kind, :name, :agent, :model, :provider,
                :status, :started_at, :ended_at, :duration_ms, :input_tokens, :output_tokens,
                :total_tokens, :cost_usd, :error, :attributes
            )
            """,
            values,
        )
    finally:
        conn.close()
    return values


def query_traces(
    filters: Mapping[str, Any] | None = None,
    paging: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_initialized()
    filters = filters or {}
    paging = paging or {}
    where: list[str] = []
    params: list[Any] = []

    if filters.get("start_time") is not None:
        where.append("started_at >= ?")
        params.append(float(filters["start_time"]))
    if filters.get("end_time") is not None:
        where.append("started_at <= ?")
        params.append(float(filters["end_time"]))
    for key in ("model", "provider", "agent", "status", "kind", "session_id"):
        value = filters.get(key)
        if value:
            where.append(f"{key} = ?")
            params.append(str(value))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    limit = int(paging.get("limit", 50) or 50)
    limit = max(1, min(limit, 200))
    offset = int(paging.get("offset", 0) or 0)
    offset = max(0, offset)

    conn = _connect()
    try:
        total_row = conn.execute(
            f"SELECT COUNT(DISTINCT trace_id) AS total FROM spans {where_sql}",
            params,
        ).fetchone()
        total = int(total_row["total"] if total_row else 0)

        rows = conn.execute(
            f"""
            SELECT
                trace_id,
                MIN(started_at) AS started_at,
                MAX(ended_at) AS ended_at,
                COUNT(*) AS span_count,
                SUM(COALESCE(duration_ms, 0)) AS duration_ms,
                SUM(COALESCE(input_tokens, 0)) AS input_tokens,
                SUM(COALESCE(output_tokens, 0)) AS output_tokens,
                SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                SUM(COALESCE(cost_usd, 0.0)) AS cost_usd,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_spans
            FROM spans
            {where_sql}
            GROUP BY trace_id
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    finally:
        conn.close()

    items = [
        {
            "trace_id": row["trace_id"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "span_count": int(row["span_count"] or 0),
            "duration_ms": int(row["duration_ms"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "total_tokens": int(row["total_tokens"] or 0),
            "cost_usd": float(row["cost_usd"] or 0.0),
            "status": "error" if int(row["error_spans"] or 0) > 0 else "ok",
        }
        for row in rows
    ]
    return {
        "items": items,
        "paging": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": (offset + len(items)) < total,
        },
    }


def get_trace(trace_id: str) -> list[dict[str, Any]]:
    ensure_initialized()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY started_at ASC, span_id ASC",
            (trace_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_span_dict(row) for row in rows]


def fleet_bottlenecks(*, limit: int = 10, window_minutes: int = 60) -> list[dict[str, Any]]:
    ensure_initialized()
    cutoff = time.time() - max(1, int(window_minutes)) * 60
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT
                kind,
                COALESCE(name, kind) AS name,
                AVG(COALESCE(duration_ms, 0)) AS avg_duration_ms,
                COUNT(*) AS samples
            FROM spans
            WHERE started_at >= ? AND duration_ms IS NOT NULL
            GROUP BY kind, name
            ORDER BY avg_duration_ms DESC
            LIMIT ?
            """,
            (cutoff, max(1, int(limit))),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "kind": row["kind"],
            "name": row["name"],
            "avg_duration_ms": float(row["avg_duration_ms"] or 0.0),
            "samples": int(row["samples"] or 0),
        }
        for row in rows
    ]


def fleet_throughput(*, window_minutes: int = 60) -> dict[str, Any]:
    ensure_initialized()
    window_minutes = max(1, int(window_minutes))
    cutoff = time.time() - window_minutes * 60
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS total_spans FROM spans WHERE started_at >= ?",
            (cutoff,),
        ).fetchone()
    finally:
        conn.close()
    total = int(row["total_spans"] if row else 0)
    return {
        "window_minutes": window_minutes,
        "total_spans": total,
        "spans_per_minute": total / float(window_minutes),
    }


def fleet_recurring_errors(*, limit: int = 10, window_minutes: int = 60) -> list[dict[str, Any]]:
    ensure_initialized()
    cutoff = time.time() - max(1, int(window_minutes)) * 60
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT
                kind,
                COALESCE(error, 'unknown') AS error_class,
                COUNT(*) AS hits
            FROM spans
            WHERE started_at >= ? AND status = 'error'
            GROUP BY kind, error_class
            ORDER BY hits DESC
            LIMIT ?
            """,
            (cutoff, max(1, int(limit))),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "kind": row["kind"],
            "error_class": row["error_class"],
            "hits": int(row["hits"] or 0),
        }
        for row in rows
    ]


def fleet_metrics(*, dropped_spans: int = 0, window_minutes: int = 60) -> dict[str, Any]:
    return {
        "throughput": fleet_throughput(window_minutes=window_minutes),
        "bottlenecks": fleet_bottlenecks(window_minutes=window_minutes),
        "recurring_errors": fleet_recurring_errors(window_minutes=window_minutes),
        "dropped_spans": int(dropped_spans or 0),
    }


def retention_prune(retention_days: int = 14, row_cap: int = DEFAULT_ROW_CAP) -> dict[str, int]:
    ensure_initialized()
    retention_days = max(0, int(retention_days))
    row_cap = max(0, int(row_cap))
    conn = _connect()
    deleted_by_age = 0
    deleted_by_cap = 0
    try:
        if retention_days > 0:
            cutoff = time.time() - retention_days * 86400
            cur = conn.execute("DELETE FROM spans WHERE started_at < ?", (cutoff,))
            deleted_by_age = int(cur.rowcount or 0)
        if row_cap > 0:
            cur = conn.execute(
                """
                DELETE FROM spans
                WHERE span_id IN (
                    SELECT span_id FROM spans
                    ORDER BY started_at DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (row_cap,),
            )
            deleted_by_cap = int(cur.rowcount or 0)
        remaining_row = conn.execute("SELECT COUNT(*) AS total FROM spans").fetchone()
        remaining = int(remaining_row["total"] if remaining_row else 0)
    finally:
        conn.close()
    return {
        "deleted_by_age": deleted_by_age,
        "deleted_by_cap": deleted_by_cap,
        "remaining": remaining,
    }


def purge_for_sessions(session_ids: Sequence[str]) -> int:
    ensure_initialized()
    ids = [str(sid) for sid in session_ids if str(sid).strip()]
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    conn = _connect()
    try:
        cur = conn.execute(
            f"DELETE FROM spans WHERE session_id IN ({placeholders})",
            ids,
        )
        return int(cur.rowcount or 0)
    finally:
        conn.close()


def upsert_mission(mission: Mapping[str, Any]) -> dict[str, Any]:
    ensure_initialized()
    mission_id = str(mission.get("id") or "").strip()
    board_slug = str(mission.get("board_slug") or "").strip()
    title = str(mission.get("title") or "").strip()
    if not mission_id or not board_slug or not title:
        raise ValueError("mission id, board_slug, and title are required")
    status = str(mission.get("status") or "todo").strip() or "todo"
    owner = mission.get("owner")
    created_at = float(mission.get("created_at") or time.time())
    tags = mission.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    updated_at = float(time.time())
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO missions (
                id, board_slug, title, status, owner, created_at, tags, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                board_slug=excluded.board_slug,
                title=excluded.title,
                status=excluded.status,
                owner=excluded.owner,
                tags=excluded.tags,
                updated_at=excluded.updated_at
            """,
            (
                mission_id,
                board_slug,
                title,
                status,
                owner,
                created_at,
                json.dumps(tags, ensure_ascii=False, separators=(",", ":")),
                updated_at,
            ),
        )
    finally:
        conn.close()
    return get_mission(mission_id) or {}


def _mission_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    tags: list[str] = []
    if isinstance(row["tags"], str) and row["tags"]:
        try:
            parsed = json.loads(row["tags"])
            if isinstance(parsed, list):
                tags = [str(item) for item in parsed]
        except Exception:
            tags = []
    return {
        "id": row["id"],
        "board_slug": row["board_slug"],
        "title": row["title"],
        "status": row["status"],
        "owner": row["owner"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "tags": tags,
    }


def list_missions(
    *,
    board_slug: str | None = None,
    status: str | None = None,
    include_rollup: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    ensure_initialized()
    where: list[str] = []
    params: list[Any] = []
    if board_slug:
        where.append("board_slug = ?")
        params.append(board_slug)
    if status:
        where.append("status = ?")
        params.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM missions
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, max(1, int(limit)), max(0, int(offset))],
        ).fetchall()
    finally:
        conn.close()

    missions = [_mission_row_to_dict(row) for row in rows]
    if include_rollup:
        for mission in missions:
            mission["rollup"] = mission_rollup(mission)
    return missions


def get_mission(mission_id: str, *, include_rollup: bool = False) -> dict[str, Any] | None:
    ensure_initialized()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    mission = _mission_row_to_dict(row)
    if include_rollup:
        mission["rollup"] = mission_rollup(mission)
    return mission


def _resolve_board_db_path(board_slug: str) -> Path:
    from hermes_cli.kanban_db import kanban_db_path

    return kanban_db_path(board=board_slug)


def mission_rollup(mission: Mapping[str, Any]) -> dict[str, Any]:
    board_slug = str(mission.get("board_slug") or "").strip()
    if not board_slug:
        return {
            "task_total": 0,
            "status_counts": {},
            "owners": [],
            "event_count": 0,
        }
    board_path = _resolve_board_db_path(board_slug)
    if not board_path.exists():
        return {
            "task_total": 0,
            "status_counts": {},
            "owners": [],
            "event_count": 0,
        }

    conn = sqlite3.connect(str(board_path))
    conn.row_factory = sqlite3.Row
    try:
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
        ).fetchall()
        owner_rows = conn.execute(
            "SELECT DISTINCT assignee FROM tasks WHERE assignee IS NOT NULL AND assignee != ''"
        ).fetchall()
        events_row = conn.execute("SELECT COUNT(*) AS count FROM task_events").fetchone()
    finally:
        conn.close()

    status_counts = {
        str(row["status"]): int(row["count"] or 0)
        for row in status_rows
    }
    task_total = int(sum(status_counts.values()))
    owners = sorted(str(row["assignee"]) for row in owner_rows if row["assignee"])
    return {
        "task_total": task_total,
        "status_counts": status_counts,
        "owners": owners,
        "event_count": int(events_row["count"] if events_row else 0),
    }

