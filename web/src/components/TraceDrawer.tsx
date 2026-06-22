import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type { TraceDetailResponse, SpanRow } from "@/lib/api";
import { Drawer } from "@/components/ds/Drawer";
import { StatusPill } from "@/components/ds/StatusPill";
import type { StatusVariant } from "@/components/ds/StatusPill";

// ── Helpers ───────────────────────────────────────────────────────────────────

function spanStatusVariant(status: string): StatusVariant {
  if (status === "ok") return "success";
  if (status === "error") return "error";
  if (status === "running") return "info";
  return "neutral";
}

function kindVariant(kind: string): StatusVariant {
  if (kind === "llm_call") return "model";
  if (kind === "tool_call") return "tool";
  if (kind === "delegation") return "mission";
  if (kind === "agent_turn") return "agent";
  return "trace";
}

/** CSS category token suffix for the bar fill */
function kindCatToken(kind: string): string {
  if (kind === "llm_call") return "model";
  if (kind === "tool_call") return "tool";
  if (kind === "delegation") return "mission";
  if (kind === "agent_turn") return "agent";
  return "trace";
}

function fmtMs(ms: number): string {
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`;
  if (ms >= 1_000) return `${(ms / 1_000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

function fmtTokens(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  if (n < 0.0001) return "<$0.0001";
  return `$${n.toFixed(4)}`;
}

/**
 * Compute tree depth for each span via its parent_id chain.
 * Root spans (no parent or parent not in set) get depth 0.
 */
function buildDepthMap(spans: SpanRow[]): Map<string, number> {
  const depthMap = new Map<string, number>();
  const parentMap = new Map<string, string | null>();
  const spanIds = new Set<string>(spans.map((s) => s.span_id));

  for (const s of spans) {
    parentMap.set(s.span_id, s.parent_id);
  }

  function getDepth(id: string, visited = new Set<string>()): number {
    if (depthMap.has(id)) return depthMap.get(id)!;
    if (visited.has(id)) {
      depthMap.set(id, 0);
      return 0;
    }
    visited.add(id);
    const parent = parentMap.get(id);
    if (!parent || !spanIds.has(parent)) {
      depthMap.set(id, 0);
      return 0;
    }
    const d = getDepth(parent, visited) + 1;
    depthMap.set(id, d);
    return d;
  }

  for (const s of spans) getDepth(s.span_id);
  return depthMap;
}

// ── WaterfallRow ──────────────────────────────────────────────────────────────

interface WaterfallRowProps {
  span: SpanRow;
  depth: number;
  traceStartSec: number;
  totalMs: number;
}

function WaterfallRow({ span, depth, traceStartSec, totalMs }: WaterfallRowProps) {
  const spanOffsetMs = (span.started_at - traceStartSec) * 1000;
  const spanDurationMs = span.duration_ms ?? 0;
  const safeTotal = totalMs > 0 ? totalMs : 1;
  const leftPct = Math.max(0, Math.min(99, (spanOffsetMs / safeTotal) * 100));
  const widthPct = Math.max(0.5, Math.min(100 - leftPct, (spanDurationMs / safeTotal) * 100));
  const catToken = kindCatToken(span.kind);

  return (
    <div
      className="flex items-start gap-2 py-1.5 border-b border-[var(--dsd-border-subtle)]/40 hover:bg-[var(--dsd-layer-overlay)]/30 transition-colors duration-[var(--dsd-dur-fast)]"
      style={{ paddingLeft: `${depth * 14 + 8}px` }}
    >
      {/* Kind + name */}
      <div className="min-w-0 w-[200px] shrink-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <StatusPill variant={kindVariant(span.kind)} label={span.kind} size="sm" />
          <span
            className="text-[11px] font-mono truncate text-[var(--dsd-text-base)]"
            title={span.name}
          >
            {span.name}
          </span>
        </div>
        {(span.model ?? span.agent) && (
          <span className="text-[10px] text-[var(--dsd-text-faint)] font-mono pl-0.5">
            {span.model ?? span.agent}
          </span>
        )}
        {span.error && (
          <span
            className="text-[10px] text-[var(--dsd-status-error)] font-mono pl-0.5 truncate block"
            title={span.error}
          >
            {span.error}
          </span>
        )}
      </div>

      {/* Waterfall bar track */}
      <div
        className="flex-1 min-w-0 relative flex items-center"
        style={{ height: 20 }}
        aria-hidden
      >
        {/* Track background */}
        <div className="absolute inset-0 rounded-sm bg-[var(--dsd-layer-surface)]" />
        {/* Span bar */}
        <div
          className="absolute rounded-sm"
          style={{
            left: `${leftPct}%`,
            width: `${widthPct}%`,
            top: 4,
            height: 12,
            background: `var(--dsd-cat-${catToken})`,
            opacity: span.status === "error" ? 0.9 : 0.65,
          }}
        />
        {/* Error outline on error spans */}
        {span.status === "error" && (
          <div
            className="absolute rounded-sm"
            style={{
              left: `${leftPct}%`,
              width: `${widthPct}%`,
              top: 4,
              height: 12,
              border: `1px solid var(--dsd-status-error)`,
              boxSizing: "border-box",
            }}
          />
        )}
      </div>

      {/* Metrics */}
      <div className="shrink-0 flex flex-col items-end text-[10px] font-mono w-[88px]">
        <span className="text-[var(--dsd-text-dim)]">{fmtMs(spanDurationMs)}</span>
        <span className="text-[var(--dsd-text-faint)]">{fmtTokens(span.total_tokens)}</span>
        <span className="text-[var(--dsd-cat-cost)]">{fmtUsd(span.cost_usd)}</span>
      </div>

      {/* Status pill */}
      <div className="shrink-0 w-[52px] flex items-start justify-end pt-0.5">
        <StatusPill
          variant={spanStatusVariant(span.status)}
          label={span.status}
          dot
          size="sm"
        />
      </div>
    </div>
  );
}

// ── TraceDrawer ───────────────────────────────────────────────────────────────

export interface TraceDrawerProps {
  /** trace_id to display; null = closed */
  traceId: string | null;
  onClose: () => void;
}

export function TraceDrawer({ traceId, onClose }: TraceDrawerProps) {
  const [detail, setDetail] = useState<TraceDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getTrace(id);
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (traceId) {
      void load(traceId);
    } else {
      setDetail(null);
      setError(null);
    }
  }, [traceId, load]);

  const open = traceId !== null;

  const depthMap = detail ? buildDepthMap(detail.spans) : new Map<string, number>();
  const traceStartSec =
    detail && detail.spans.length > 0
      ? Math.min(...detail.spans.map((s) => s.started_at))
      : 0;
  const totalMs = detail ? Math.max(detail.totals.duration_ms, 1) : 1;
  const shortId = traceId ? traceId.slice(0, 12) : "";

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={traceId ? `Trace ${shortId}…` : "Trace Detail"}
      width={660}
    >
      {loading && (
        <div className="flex items-center gap-2 py-8">
          <Spinner />
          <span className="text-sm text-[var(--dsd-text-secondary)]">Loading spans…</span>
        </div>
      )}

      {error && !loading && (
        <div className="py-4 text-sm text-[var(--dsd-status-error)]" role="alert">
          {error}
        </div>
      )}

      {detail && !loading && (
        <>
          {/* Trace totals header */}
          <div className="flex flex-wrap gap-4 mb-3 pb-3 border-b border-[var(--dsd-border-subtle)] text-xs font-mono">
            <span>
              <span className="text-[var(--dsd-text-faint)]">spans </span>
              <span className="text-[var(--dsd-text-base)]">{detail.totals.span_count}</span>
            </span>
            <span>
              <span className="text-[var(--dsd-text-faint)]">duration </span>
              <span className="text-[var(--dsd-text-base)]">{fmtMs(detail.totals.duration_ms)}</span>
            </span>
            <span>
              <span className="text-[var(--dsd-text-faint)]">tokens </span>
              <span className="text-[var(--dsd-text-base)]">{fmtTokens(detail.totals.total_tokens)}</span>
            </span>
            <span>
              <span className="text-[var(--dsd-text-faint)]">cost </span>
              <span className="text-[var(--dsd-cat-cost)]">{fmtUsd(detail.totals.cost_usd)}</span>
            </span>
            {detail.totals.error_count > 0 && (
              <span className="text-[var(--dsd-status-error)]">
                {detail.totals.error_count} error
                {detail.totals.error_count > 1 ? "s" : ""}
              </span>
            )}
          </div>

          {/* Column headers */}
          <div className="flex items-center gap-2 mb-1 text-[10px] uppercase tracking-wide text-[var(--dsd-text-faint)] px-2">
            <div className="w-[200px] shrink-0">Span</div>
            <div className="flex-1">Timeline</div>
            <div className="w-[88px] text-right">Dur / Tok / Cost</div>
            <div className="w-[52px] text-right">Status</div>
          </div>

          {/* Waterfall rows */}
          <div role="list" aria-label="Span waterfall">
            {detail.spans.map((span) => (
              <WaterfallRow
                key={span.span_id}
                span={span}
                depth={depthMap.get(span.span_id) ?? 0}
                traceStartSec={traceStartSec}
                totalMs={totalMs}
              />
            ))}
          </div>
        </>
      )}
    </Drawer>
  );
}
