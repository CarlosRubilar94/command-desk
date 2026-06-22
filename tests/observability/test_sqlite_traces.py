from __future__ import annotations

import importlib
import sqlite3
import time
from pathlib import Path

import pytest


def _reload_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hermes_home = tmp_path / "hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    import hermes_cli.traces_store as traces_store

    traces_store = importlib.reload(traces_store)
    return traces_store


def _reload_plugin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _reload_store(monkeypatch, tmp_path)
    import plugins.observability.sqlite_traces as sqlite_traces

    sqlite_traces = importlib.reload(sqlite_traces)
    sqlite_traces.reset_for_tests()
    return sqlite_traces


def test_span_crud_and_get_trace(monkeypatch, tmp_path):
    store = _reload_store(monkeypatch, tmp_path)
    now = time.time()

    store.insert_span(
        {
            "span_id": "root-1",
            "trace_id": "trace-1",
            "session_id": "sess-1",
            "kind": "agent_turn",
            "name": "turn",
            "status": "ok",
            "started_at": now - 2,
            "ended_at": now - 1,
            "duration_ms": 1000,
            "attributes": {"trace_id": "trace-1", "tool_args": "blocked"},
        }
    )
    store.insert_span(
        {
            "span_id": "child-1",
            "trace_id": "trace-1",
            "parent_id": "root-1",
            "session_id": "sess-1",
            "kind": "tool_call",
            "name": "read_file",
            "status": "ok",
            "started_at": now - 1,
            "ended_at": now,
            "duration_ms": 500,
            "input_tokens": 10,
            "output_tokens": 3,
            "total_tokens": 13,
            "attributes": {"tool_call_id": "tool-1", "status": "ok"},
        }
    )

    trace = store.get_trace("trace-1")
    assert len(trace) == 2
    assert trace[0]["span_id"] == "root-1"
    assert "tool_args" not in trace[0]["attributes"]
    assert trace[1]["attributes"]["tool_call_id"] == "tool-1"


def test_query_traces_shape(monkeypatch, tmp_path):
    store = _reload_store(monkeypatch, tmp_path)
    now = time.time()
    for idx in range(3):
        store.insert_span(
            {
                "span_id": f"span-{idx}",
                "trace_id": f"trace-{idx}",
                "session_id": "sess-a",
                "kind": "llm_call",
                "name": "llm",
                "status": "ok",
                "started_at": now - idx,
                "ended_at": now - idx + 0.1,
                "duration_ms": 100,
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            }
        )

    result = store.query_traces(filters={"session_id": "sess-a"}, paging={"limit": 2, "offset": 0})
    assert "items" in result and "paging" in result
    assert result["paging"]["limit"] == 2
    assert isinstance(result["paging"]["total"], int)
    assert len(result["items"]) == 2
    assert set(result["items"][0].keys()) >= {
        "trace_id",
        "span_count",
        "duration_ms",
        "total_tokens",
        "cost_usd",
        "status",
    }


def test_retention_prune_by_age_and_cap(monkeypatch, tmp_path):
    store = _reload_store(monkeypatch, tmp_path)
    now = time.time()
    store.insert_span(
        {
            "span_id": "very-old",
            "trace_id": "trace-old",
            "kind": "agent_turn",
            "status": "ok",
            "started_at": now - (30 * 86400),
            "ended_at": now - (30 * 86400) + 1,
        }
    )
    for idx in range(4):
        store.insert_span(
            {
                "span_id": f"recent-{idx}",
                "trace_id": f"trace-recent-{idx}",
                "kind": "agent_turn",
                "status": "ok",
                "started_at": now - idx,
                "ended_at": now - idx + 1,
            }
        )

    stats = store.retention_prune(retention_days=14, row_cap=2)
    assert stats["deleted_by_age"] >= 1
    assert stats["remaining"] <= 2


def test_recorder_best_effort_on_write_failure(monkeypatch, tmp_path):
    store = _reload_store(monkeypatch, tmp_path)
    plugin = _reload_plugin(monkeypatch, tmp_path)

    def _boom(_span):
        raise OSError("disk full")

    monkeypatch.setattr(store, "insert_span", _boom)
    recorder = plugin._SpanRecorder(
        plugin._TraceConfig(
            enabled=True,
            sample_rate=1.0,
            capture_payloads=False,
            retention_days=0,
            queue_max=32,
        )
    )
    recorder.enqueue(
        {
            "span_id": "fail-1",
            "trace_id": "trace-fail",
            "kind": "tool_call",
            "status": "ok",
            "started_at": time.time(),
        }
    )
    time.sleep(0.2)
    recorder.shutdown()
    assert plugin.get_dropped_spans() >= 1


def test_recorder_queue_cap_drops(monkeypatch, tmp_path):
    store = _reload_store(monkeypatch, tmp_path)
    plugin = _reload_plugin(monkeypatch, tmp_path)

    def _slow_insert(_span):
        time.sleep(0.15)
        return {}

    monkeypatch.setattr(store, "insert_span", _slow_insert)
    recorder = plugin._SpanRecorder(
        plugin._TraceConfig(
            enabled=True,
            sample_rate=1.0,
            capture_payloads=False,
            retention_days=0,
            queue_max=1,
        )
    )
    for idx in range(12):
        recorder.enqueue(
            {
                "span_id": f"q-{idx}",
                "trace_id": "trace-q",
                "kind": "tool_call",
                "status": "ok",
                "started_at": time.time(),
            }
        )
    time.sleep(0.3)
    recorder.shutdown()
    assert plugin.get_dropped_spans() >= 1


def test_mission_rollup_from_seeded_board(monkeypatch, tmp_path):
    store = _reload_store(monkeypatch, tmp_path)
    board_db = tmp_path / "seeded-board.db"
    conn = sqlite3.connect(str(board_db))
    try:
        conn.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, assignee TEXT, status TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, created_at INTEGER)"
        )
        conn.executemany(
            "INSERT INTO tasks (id, assignee, status) VALUES (?, ?, ?)",
            [
                ("t1", "alice", "ready"),
                ("t2", "alice", "running"),
                ("t3", "bob", "done"),
                ("t4", "", "blocked"),
            ],
        )
        conn.executemany(
            "INSERT INTO task_events (task_id, created_at) VALUES (?, ?)",
            [("t1", 1), ("t2", 2), ("t2", 3)],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(store, "_resolve_board_db_path", lambda _slug: board_db)
    store.upsert_mission(
        {
            "id": "mission-1",
            "board_slug": "test-board",
            "title": "Ship tracing",
            "status": "in_progress",
            "owner": "alice",
            "tags": ["wave-1"],
        }
    )
    mission = store.get_mission("mission-1", include_rollup=True)
    assert mission is not None
    rollup = mission["rollup"]
    assert rollup["task_total"] == 4
    assert rollup["status_counts"]["done"] == 1
    assert rollup["event_count"] == 3
    assert rollup["owners"] == ["alice", "bob"]


def test_register_hook_bus_records_span(monkeypatch, tmp_path):
    _reload_store(monkeypatch, tmp_path)
    plugin = _reload_plugin(monkeypatch, tmp_path)
    import hermes_cli.traces_store as store

    class _Ctx:
        def __init__(self) -> None:
            self.hooks = {}

        def register_hook(self, hook_name, callback):
            self.hooks[hook_name] = callback

    ctx = _Ctx()
    plugin.register(ctx)

    pre = ctx.hooks["pre_tool_call"]
    post = ctx.hooks["post_tool_call"]
    pre(
        session_id="sess-hook",
        turn_id="turn-hook",
        tool_call_id="tool-hook",
        tool_name="read_file",
    )
    post(
        session_id="sess-hook",
        turn_id="turn-hook",
        tool_call_id="tool-hook",
        tool_name="read_file",
        status="ok",
    )

    time.sleep(0.3)
    spans = store.get_trace("turn-hook")
    assert any(
        span.get("kind") == "tool_call" and span.get("name") == "read_file"
        for span in spans
    )
    plugin.reset_for_tests()


def test_sqlite_traces_plugin_default_enabled(monkeypatch, tmp_path):
    hermes_home = tmp_path / "hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import hermes_cli.plugins as plugin_system

    plugin_system = importlib.reload(plugin_system)
    manager = plugin_system.PluginManager()
    manager.discover_and_load(force=True)

    listing = {item["key"]: item for item in manager.list_plugins()}
    assert "observability/sqlite_traces" in listing
    assert listing["observability/sqlite_traces"]["enabled"] is True

    import plugins.observability.sqlite_traces as sqlite_traces

    sqlite_traces.reset_for_tests()

