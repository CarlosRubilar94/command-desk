"""sqlite_traces — Hermes observability plugin backed by SQLite.

This plugin emits observability spans to ``traces.db`` using the existing
Hermes plugin hook bus (no agent-loop edits required). It is intentionally
best-effort: write failures never raise into the agent path.

Enablement:
  bundled and enabled by default (can be disabled via plugins.disabled).

Tracing config defaults (``~/.hermes/config.yaml``):
  tracing:
    enabled: true
    sample_rate: 1.0
    capture_payloads: false
    retention_days: 14
    queue_max: 1024
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from hermes_cli import traces_store

logger = logging.getLogger(__name__)

DEFAULT_TRACING_CONFIG = {
    "enabled": True,
    "sample_rate": 1.0,
    "capture_payloads": False,
    "retention_days": 14,
    "queue_max": 1024,
}

_dropped_spans = 0
_DROP_LOCK = threading.Lock()


def _inc_dropped_spans() -> None:
    global _dropped_spans
    with _DROP_LOCK:
        _dropped_spans += 1


def get_dropped_spans() -> int:
    with _DROP_LOCK:
        return int(_dropped_spans)


def _estimate_cost_usd(
    *,
    model: str,
    provider: str,
    base_url: str,
    usage: dict[str, Any],
) -> float | None:
    try:
        from decimal import Decimal

        from agent.usage_pricing import CanonicalUsage, estimate_usage_cost

        canonical = CanonicalUsage(
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            cache_read_tokens=int(usage.get("cache_read_tokens") or 0),
            cache_write_tokens=int(usage.get("cache_write_tokens") or 0),
            reasoning_tokens=int(usage.get("reasoning_tokens") or 0),
            request_count=1,
        )
        cost = estimate_usage_cost(
            model,
            canonical,
            provider=provider,
            base_url=base_url,
            api_key="",
        )
        if isinstance(cost.amount_usd, Decimal):
            return float(cost.amount_usd)
        if cost.amount_usd is not None:
            return float(cost.amount_usd)
    except Exception:
        return None
    return None


@dataclass
class _TraceConfig:
    enabled: bool = True
    sample_rate: float = 1.0
    capture_payloads: bool = False
    retention_days: int = 14
    queue_max: int = 1024


def _load_trace_config() -> _TraceConfig:
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly()
    except Exception:
        cfg = {}
    tracing_cfg = cfg.get("tracing") if isinstance(cfg, dict) else {}
    if not isinstance(tracing_cfg, dict):
        tracing_cfg = {}
    merged = {**DEFAULT_TRACING_CONFIG, **tracing_cfg}
    queue_max = int(merged.get("queue_max", 1024) or 1024)
    queue_max = max(16, queue_max)
    sample_rate = float(merged.get("sample_rate", 1.0) or 1.0)
    sample_rate = max(0.0, min(1.0, sample_rate))
    return _TraceConfig(
        enabled=bool(merged.get("enabled", True)),
        sample_rate=sample_rate,
        capture_payloads=bool(merged.get("capture_payloads", False)),
        retention_days=max(0, int(merged.get("retention_days", 14) or 14)),
        queue_max=queue_max,
    )


class _SpanRecorder:
    def __init__(self, config: _TraceConfig) -> None:
        self.config = config
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=config.queue_max)
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._watchdog: threading.Thread | None = None
        self._start_worker_locked()
        self._start_watchdog_locked()

    def _start_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        worker = threading.Thread(
            target=self._worker_loop,
            name="sqlite-traces-recorder",
            daemon=True,
        )
        self._worker = worker
        worker.start()

    def _start_watchdog_locked(self) -> None:
        if self._watchdog is not None and self._watchdog.is_alive():
            return
        watchdog = threading.Thread(
            target=self._watchdog_loop,
            name="sqlite-traces-watchdog",
            daemon=True,
        )
        self._watchdog = watchdog
        watchdog.start()

    def _watchdog_loop(self) -> None:
        while not self._stop.wait(2.0):
            with self._lock:
                if self._worker is None or not self._worker.is_alive():
                    self._start_worker_locked()

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                span = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                traces_store.insert_span(span)
            except Exception as exc:
                _inc_dropped_spans()
                logger.debug("sqlite_traces write dropped: %s", exc)
            finally:
                self._queue.task_done()

    def enqueue(self, span: dict[str, Any]) -> None:
        if not self.config.enabled:
            return
        if self.config.sample_rate < 1.0 and random.random() > self.config.sample_rate:
            return
        with self._lock:
            self._start_worker_locked()
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            _inc_dropped_spans()

    def shutdown(self) -> None:
        self._stop.set()
        with self._lock:
            worker = self._worker
            watchdog = self._watchdog
        for thread in (worker, watchdog):
            if thread is not None and thread.is_alive():
                thread.join(timeout=0.5)


class _Runtime:
    def __init__(self, config: _TraceConfig) -> None:
        self.config = config
        self.recorder = _SpanRecorder(config)
        self._tool_starts: dict[str, float] = {}
        self._session_spans: dict[str, dict[str, Any]] = {}
        self._turn_spans: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        if self.config.retention_days > 0:
            try:
                traces_store.retention_prune(retention_days=self.config.retention_days)
            except Exception as exc:
                logger.debug("sqlite_traces prune failed: %s", exc)

    @staticmethod
    def _trace_id(kwargs: dict[str, Any]) -> str:
        turn_id = str(kwargs.get("turn_id") or "").strip()
        if turn_id:
            return turn_id
        session_id = str(kwargs.get("session_id") or "").strip() or "sessionless"
        api_request_id = str(kwargs.get("api_request_id") or "").strip()
        if api_request_id:
            return f"{session_id}:{api_request_id}"
        return session_id

    @staticmethod
    def _tool_key(kwargs: dict[str, Any]) -> str:
        key = str(kwargs.get("tool_call_id") or "").strip()
        if key:
            return key
        session_id = str(kwargs.get("session_id") or "")
        turn_id = str(kwargs.get("turn_id") or "")
        tool_name = str(kwargs.get("tool_name") or "tool")
        return f"{session_id}:{turn_id}:{tool_name}"

    def _queue_span(self, span: dict[str, Any]) -> None:
        self.recorder.enqueue(span)

    def _ensure_session_span(self, session_id: str, at_ts: float) -> str:
        with self._lock:
            existing = self._session_spans.get(session_id)
            if existing:
                return str(existing["span_id"])
            span_id = f"session:{session_id}"
            span = {
                "span_id": span_id,
                "trace_id": session_id,
                "parent_id": None,
                "session_id": session_id,
                "kind": "agent_turn",
                "name": "session_scope",
                "status": "running",
                "started_at": at_ts,
                "ended_at": None,
                "duration_ms": None,
                "attributes": {
                    "trace_id": session_id,
                    "session_id": session_id,
                    "kind": "agent_turn",
                    "status": "running",
                },
                "_upsert": True,
            }
            self._session_spans[session_id] = {
                "span_id": span_id,
                "started_at": at_ts,
            }
        self._queue_span(span)
        return span_id

    def _ensure_turn_span(self, kwargs: dict[str, Any], started_at: float) -> tuple[str, str]:
        session_id = str(kwargs.get("session_id") or "").strip() or "sessionless"
        trace_id = self._trace_id(kwargs)
        with self._lock:
            existing = self._turn_spans.get(trace_id)
            if existing:
                return str(existing["span_id"]), trace_id
        session_span_id = self._ensure_session_span(session_id, started_at)
        turn_span_id = f"turn:{trace_id}"
        span = {
            "span_id": turn_span_id,
            "trace_id": trace_id,
            "parent_id": session_span_id,
            "session_id": session_id,
            "kind": "agent_turn",
            "name": "turn_scope",
            "status": "running",
            "started_at": started_at,
            "ended_at": None,
            "duration_ms": None,
            "attributes": {
                "trace_id": trace_id,
                "parent_id": session_span_id,
                "session_id": session_id,
                "turn_id": kwargs.get("turn_id"),
                "kind": "agent_turn",
                "status": "running",
            },
            "_upsert": True,
        }
        with self._lock:
            self._turn_spans[trace_id] = {
                "span_id": turn_span_id,
                "started_at": started_at,
            }
        self._queue_span(span)
        return turn_span_id, trace_id

    def _touch_turn(self, kwargs: dict[str, Any], ended_at: float, status: str = "ok") -> None:
        trace_id = self._trace_id(kwargs)
        with self._lock:
            turn = self._turn_spans.get(trace_id)
        if not turn:
            return
        started_at = float(turn["started_at"])
        self._queue_span(
            {
                "span_id": turn["span_id"],
                "trace_id": trace_id,
                "parent_id": f"session:{kwargs.get('session_id') or 'sessionless'}",
                "session_id": kwargs.get("session_id"),
                "kind": "agent_turn",
                "name": "turn_scope",
                "status": status,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": max(0, int((ended_at - started_at) * 1000)),
                "attributes": {
                    "trace_id": trace_id,
                    "session_id": kwargs.get("session_id"),
                    "turn_id": kwargs.get("turn_id"),
                    "kind": "agent_turn",
                    "status": status,
                    "duration_ms": max(0, int((ended_at - started_at) * 1000)),
                },
                "_upsert": True,
            }
        )

    def close_session(self, kwargs: dict[str, Any], *, status: str = "ok") -> None:
        session_id = str(kwargs.get("session_id") or "").strip()
        if not session_id:
            return
        with self._lock:
            session = self._session_spans.pop(session_id, None)
        if not session:
            return
        ended_at = float(time.time())
        started_at = float(session["started_at"])
        self._queue_span(
            {
                "span_id": session["span_id"],
                "trace_id": session_id,
                "parent_id": None,
                "session_id": session_id,
                "kind": "agent_turn",
                "name": "session_scope",
                "status": status,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": max(0, int((ended_at - started_at) * 1000)),
                "attributes": {
                    "trace_id": session_id,
                    "session_id": session_id,
                    "kind": "agent_turn",
                    "status": status,
                    "duration_ms": max(0, int((ended_at - started_at) * 1000)),
                },
                "_upsert": True,
            }
        )

    def on_post_api_request(self, kwargs: dict[str, Any]) -> None:
        ended_at = float(kwargs.get("ended_at") or time.time())
        started_at = float(kwargs.get("started_at") or ended_at)
        turn_span_id, trace_id = self._ensure_turn_span(kwargs, started_at)
        usage = kwargs.get("usage") if isinstance(kwargs.get("usage"), dict) else {}

        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

        cost_value = _estimate_cost_usd(
            model=str(kwargs.get("model") or ""),
            provider=str(kwargs.get("provider") or ""),
            base_url=str(kwargs.get("base_url") or ""),
            usage=usage,
        )

        self._queue_span(
            {
                "span_id": str(uuid4()),
                "trace_id": trace_id,
                "parent_id": turn_span_id,
                "session_id": kwargs.get("session_id"),
                "kind": "llm_call",
                "name": "post_api_request",
                "agent": kwargs.get("platform"),
                "model": kwargs.get("model"),
                "provider": kwargs.get("provider"),
                "status": "ok",
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": max(0, int((ended_at - started_at) * 1000)),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_value,
                "error": None,
                "attributes": {
                    "trace_id": trace_id,
                    "parent_id": turn_span_id,
                    "session_id": kwargs.get("session_id"),
                    "turn_id": kwargs.get("turn_id"),
                    "api_request_id": kwargs.get("api_request_id"),
                    "kind": "llm_call",
                    "status": "ok",
                    "model": kwargs.get("model"),
                    "provider": kwargs.get("provider"),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_value,
                    "duration_ms": max(0, int((ended_at - started_at) * 1000)),
                },
            }
        )
        self._touch_turn(kwargs, ended_at, status="ok")

    def on_pre_tool_call(self, kwargs: dict[str, Any]) -> None:
        now_ts = float(time.time())
        self._ensure_turn_span(kwargs, now_ts)
        with self._lock:
            self._tool_starts[self._tool_key(kwargs)] = now_ts

    def on_post_tool_call(self, kwargs: dict[str, Any]) -> None:
        ended_at = float(time.time())
        tool_key = self._tool_key(kwargs)
        with self._lock:
            started_at = self._tool_starts.pop(tool_key, None)
        duration_ms = int(kwargs.get("duration_ms") or 0)
        if started_at is None:
            started_at = ended_at - (duration_ms / 1000.0 if duration_ms > 0 else 0.0)
        if duration_ms <= 0:
            duration_ms = max(0, int((ended_at - started_at) * 1000))

        turn_span_id, trace_id = self._ensure_turn_span(kwargs, started_at)
        status = str(kwargs.get("status") or "ok")
        if status not in {"ok", "error", "blocked"}:
            status = "ok"
        error_type = kwargs.get("error_type")
        bounded_error = str(error_type or "tool_error") if status != "ok" else None
        self._queue_span(
            {
                "span_id": str(uuid4()),
                "trace_id": trace_id,
                "parent_id": turn_span_id,
                "session_id": kwargs.get("session_id"),
                "kind": "tool_call",
                "name": str(kwargs.get("tool_name") or "tool"),
                "agent": kwargs.get("platform"),
                "model": kwargs.get("model"),
                "provider": kwargs.get("provider"),
                "status": "error" if status != "ok" else "ok",
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": None,
                "error": bounded_error,
                "attributes": {
                    "trace_id": trace_id,
                    "parent_id": turn_span_id,
                    "session_id": kwargs.get("session_id"),
                    "turn_id": kwargs.get("turn_id"),
                    "tool_call_id": kwargs.get("tool_call_id"),
                    "kind": "tool_call",
                    "status": "error" if status != "ok" else "ok",
                    "error_class": bounded_error,
                    "duration_ms": duration_ms,
                },
            }
        )
        self._touch_turn(kwargs, ended_at, status="error" if status != "ok" else "ok")

    def on_subagent_stop(self, kwargs: dict[str, Any]) -> None:
        parent_session = str(kwargs.get("parent_session_id") or "").strip()
        if not parent_session:
            return
        ended_at = float(time.time())
        duration_ms = int(kwargs.get("duration_ms") or 0)
        started_at = ended_at - (duration_ms / 1000.0 if duration_ms > 0 else 0.0)
        turn_like = {
            "session_id": parent_session,
            "turn_id": kwargs.get("parent_turn_id"),
        }
        turn_span_id, trace_id = self._ensure_turn_span(turn_like, started_at)
        status = str(kwargs.get("child_status") or "ok")
        if status not in {"ok", "done", "error", "blocked"}:
            status = "ok"
        normalized_status = "ok" if status in {"ok", "done"} else "error"
        self._queue_span(
            {
                "span_id": str(uuid4()),
                "trace_id": trace_id,
                "parent_id": turn_span_id,
                "session_id": parent_session,
                "kind": "delegation",
                "name": "subagent_stop",
                "status": normalized_status,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": max(0, duration_ms),
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": None,
                "error": "delegation_error" if normalized_status == "error" else None,
                "attributes": {
                    "trace_id": trace_id,
                    "parent_id": turn_span_id,
                    "session_id": parent_session,
                    "parent_session_id": parent_session,
                    "child_session_id": kwargs.get("child_session_id"),
                    "child_role": kwargs.get("child_role"),
                    "child_status": kwargs.get("child_status"),
                    "kind": "delegation",
                    "status": normalized_status,
                    "duration_ms": max(0, duration_ms),
                },
            }
        )
        self._touch_turn(turn_like, ended_at, status=normalized_status)

    def shutdown(self) -> None:
        self.recorder.shutdown()


_RUNTIME_LOCK = threading.RLock()
_RUNTIME: _Runtime | None = None


def _get_runtime() -> _Runtime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            config = _load_trace_config()
            _RUNTIME = _Runtime(config=config)
        return _RUNTIME


def on_session_start(**kwargs: Any) -> None:
    runtime = _get_runtime()
    session_id = str(kwargs.get("session_id") or "").strip()
    if not session_id:
        return
    runtime._ensure_session_span(session_id, float(time.time()))


def on_session_end(**kwargs: Any) -> None:
    _get_runtime().close_session(kwargs, status="ok")


def on_session_finalize(**kwargs: Any) -> None:
    _get_runtime().close_session(kwargs, status="ok")


def on_session_reset(**kwargs: Any) -> None:
    _get_runtime().close_session(kwargs, status="ok")


def on_post_api_request(**kwargs: Any) -> None:
    try:
        _get_runtime().on_post_api_request(dict(kwargs))
    except Exception as exc:
        _inc_dropped_spans()
        logger.debug("sqlite_traces post_api_request dropped: %s", exc)


def on_pre_tool_call(**kwargs: Any) -> None:
    try:
        _get_runtime().on_pre_tool_call(dict(kwargs))
    except Exception as exc:
        _inc_dropped_spans()
        logger.debug("sqlite_traces pre_tool_call dropped: %s", exc)


def on_post_tool_call(**kwargs: Any) -> None:
    try:
        _get_runtime().on_post_tool_call(dict(kwargs))
    except Exception as exc:
        _inc_dropped_spans()
        logger.debug("sqlite_traces post_tool_call dropped: %s", exc)


def on_subagent_stop(**kwargs: Any) -> None:
    try:
        _get_runtime().on_subagent_stop(dict(kwargs))
    except Exception as exc:
        _inc_dropped_spans()
        logger.debug("sqlite_traces subagent_stop dropped: %s", exc)


def register(ctx) -> None:
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("on_session_finalize", on_session_finalize)
    ctx.register_hook("on_session_reset", on_session_reset)
    ctx.register_hook("post_api_request", on_post_api_request)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("subagent_stop", on_subagent_stop)


def reset_for_tests() -> None:
    global _RUNTIME, _dropped_spans
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            _RUNTIME.shutdown()
        _RUNTIME = None
    with _DROP_LOCK:
        _dropped_spans = 0

