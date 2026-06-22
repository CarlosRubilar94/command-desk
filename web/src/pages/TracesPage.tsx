import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { DeckPageShell } from "@/components/DeckPageShell";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { TraceRow } from "@/lib/api";
import { DataTable } from "@/components/ds/DataTable";
import type { ColDef } from "@/components/ds/DataTable";
import { StatusPill } from "@/components/ds/StatusPill";
import type { StatusVariant } from "@/components/ds/StatusPill";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { SkeletonTable } from "@/components/ds/Skeleton";
import { TraceDrawer } from "@/components/TraceDrawer";
import { cn } from "@/lib/utils";

// ── Formatters ────────────────────────────────────────────────────────────────

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

function fmtTs(epoch: number): string {
  return new Date(epoch * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function traceStatusVariant(status: string): StatusVariant {
  if (status === "ok") return "success";
  if (status === "error") return "error";
  if (status === "running") return "info";
  return "neutral";
}

// ── Filter options ────────────────────────────────────────────────────────────

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "ok", label: "OK" },
  { value: "error", label: "Error" },
  { value: "running", label: "Running" },
];

const TIME_OPTIONS = [
  { value: "", label: "All time" },
  { value: "1h", label: "1h" },
  { value: "6h", label: "6h" },
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
];

function sinceForTimeFilter(t: string): string | undefined {
  if (!t) return undefined;
  const now = Math.floor(Date.now() / 1000);
  const offsets: Record<string, number> = {
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
  };
  const off = offsets[t];
  if (!off) return undefined;
  return String(now - off);
}

// ── Column definitions ────────────────────────────────────────────────────────

const COLS: ColDef<TraceRow>[] = [
  {
    key: "started_at",
    header: "Started",
    sortKey: "started_at",
    width: 150,
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-dim)]">
        {fmtTs(r.started_at)}
      </span>
    ),
  },
  {
    key: "agent",
    header: "Agent",
    sortKey: "agent",
    width: 120,
    cell: (r) => (
      <span className="text-xs font-mono truncate text-[var(--dsd-text-base)]">
        {r.agent || "—"}
      </span>
    ),
  },
  {
    key: "model",
    header: "Model",
    sortKey: "model",
    width: 130,
    cell: (r) => (
      <StatusPill variant="model" label={r.model || "—"} size="sm" />
    ),
  },
  {
    key: "duration_ms",
    header: "Duration",
    sortKey: "duration_ms",
    width: 80,
    align: "right",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-dim)]">
        {fmtMs(r.duration_ms)}
      </span>
    ),
  },
  {
    key: "total_tokens",
    header: "Tokens",
    sortKey: "total_tokens",
    width: 80,
    align: "right",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-dim)]">
        {fmtTokens(r.total_tokens)}
      </span>
    ),
  },
  {
    key: "cost_usd",
    header: "Cost",
    sortKey: "cost_usd",
    width: 80,
    align: "right",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-cat-cost)]">
        {fmtUsd(r.cost_usd)}
      </span>
    ),
  },
  {
    key: "span_count",
    header: "Spans",
    sortKey: "span_count",
    width: 60,
    align: "right",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-faint)]">
        {r.span_count}
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    sortKey: "status",
    width: 80,
    cell: (r) => (
      <StatusPill
        variant={traceStatusVariant(r.status)}
        label={r.status}
        dot
        size="sm"
      />
    ),
  },
];

// ── Filter chip component ─────────────────────────────────────────────────────

function FilterChip({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "px-2.5 py-1 text-[11px] font-medium rounded-[var(--dsd-radius-sm)] border transition-colors duration-[var(--dsd-dur-fast)]",
            value === opt.value
              ? "bg-[var(--dsd-accent-primary-bg)] text-[var(--dsd-accent-primary)] border-[var(--dsd-accent-primary)]/40"
              : "bg-transparent text-[var(--dsd-text-faint)] border-[var(--dsd-border-subtle)] hover:text-[var(--dsd-text-base)] hover:border-[var(--dsd-border-default)]",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── TracesPage ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

export default function TracesPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Filter state — synced to URL so cross-links (/traces?status=error) work
  const statusFilter = searchParams.get("status") ?? "";
  const modelFilter = searchParams.get("model") ?? "";
  const agentFilter = searchParams.get("agent") ?? "";
  const timeFilter = searchParams.get("since") ?? "";

  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  const setFilter = useCallback(
    (key: string, value: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (value) {
            next.set(key, value);
          } else {
            next.delete(key);
          }
          return next;
        },
        { replace: true },
      );
      setOffset(0);
    },
    [setSearchParams],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getTraces({
        limit: PAGE_SIZE,
        offset,
        status: statusFilter || undefined,
        model: modelFilter || undefined,
        agent: agentFilter || undefined,
        since: sinceForTimeFilter(timeFilter),
      });
      setTraces(result.traces);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [offset, statusFilter, modelFilter, agentFilter, timeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const { setEnd } = usePageHeader();
  useLayoutEffect(() => {
    setEnd(
      <button
        type="button"
        className="deck-btn-sm ghost"
        onClick={() => void load()}
      >
        <RefreshCw
          className={cn("h-3.5 w-3.5", loading && "animate-spin")}
        />
        Refresh
      </button>,
    );
    return () => setEnd(null);
  }, [load, setEnd, loading]);

  const hasFilters = !!(statusFilter || modelFilter || agentFilter || timeFilter);
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <DeckPageShell>
      <div className="deck-dashboard deck-animate">
        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-3 mb-4 pb-3 border-b border-[var(--dsd-border-subtle)]">
          <span className="text-[11px] text-[var(--dsd-text-faint)] uppercase tracking-wide">
            Status
          </span>
          <FilterChip
            options={STATUS_OPTIONS}
            value={statusFilter}
            onChange={(v) => setFilter("status", v)}
          />
          <span className="text-[11px] text-[var(--dsd-text-faint)] uppercase tracking-wide ml-2">
            Time
          </span>
          <FilterChip
            options={TIME_OPTIONS}
            value={timeFilter}
            onChange={(v) => setFilter("since", v)}
          />
          {modelFilter && (
            <span className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono bg-[var(--dsd-layer-raised)] border border-[var(--dsd-border-subtle)] rounded-[var(--dsd-radius-sm)] text-[var(--dsd-text-dim)]">
              model:{modelFilter}
              <button
                type="button"
                onClick={() => setFilter("model", "")}
                className="ml-0.5 text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-base)]"
                aria-label="Clear model filter"
              >
                ✕
              </button>
            </span>
          )}
          {agentFilter && (
            <span className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono bg-[var(--dsd-layer-raised)] border border-[var(--dsd-border-subtle)] rounded-[var(--dsd-radius-sm)] text-[var(--dsd-text-dim)]">
              agent:{agentFilter}
              <button
                type="button"
                onClick={() => setFilter("agent", "")}
                className="ml-0.5 text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-base)]"
                aria-label="Clear agent filter"
              >
                ✕
              </button>
            </span>
          )}
          {hasFilters && (
            <button
              type="button"
              className="text-[11px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-status-error)] transition-colors duration-[var(--dsd-dur-fast)]"
              onClick={() => setSearchParams({}, { replace: true })}
            >
              Clear all
            </button>
          )}
          <span className="ml-auto text-[11px] text-[var(--dsd-text-faint)]">
            {total} trace{total !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Body */}
        {loading && traces.length === 0 ? (
          <SkeletonTable rows={8} cols={8} />
        ) : error ? (
          <ErrorState error={error} onRetry={() => void load()} compact />
        ) : traces.length === 0 ? (
          <EmptyState
            icon="🔭"
            title="No traces found"
            description={
              hasFilters
                ? "Try clearing the filters to see all traces."
                : "Traces will appear here once the tracing plugin records spans."
            }
            compact
          />
        ) : (
          <DataTable
            cols={COLS}
            rows={traces}
            rowKey={(r) => r.trace_id}
            dense
            stickyHeader
            maxRows={PAGE_SIZE}
            onRowClick={(r) => setSelectedTraceId(r.trace_id)}
            selectedKey={selectedTraceId ?? undefined}
            aria-label="Traces"
          />
        )}

        {/* Pagination */}
        {!loading && traces.length > 0 && (
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--dsd-border-subtle)]">
            <span className="text-[11px] text-[var(--dsd-text-faint)]">
              Showing {offset + 1}–{Math.min(offset + traces.length, total)} of{" "}
              {total}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={!hasPrev}
                className="deck-btn-sm ghost disabled:opacity-40"
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                ← Prev
              </button>
              <button
                type="button"
                disabled={!hasNext}
                className="deck-btn-sm ghost disabled:opacity-40"
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Trace detail drawer */}
      <TraceDrawer
        traceId={selectedTraceId}
        onClose={() => setSelectedTraceId(null)}
      />
    </DeckPageShell>
  );
}
