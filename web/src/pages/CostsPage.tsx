import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { AlertTriangle, RefreshCw, TrendingDown } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type {
  CostsSummaryResponse,
  CostsModelEntry,
  CostsDayEntry,
  CostsSavingsResponse,
} from "@/lib/api";
import { DeckPageShell } from "@/components/DeckPageShell";
import {
  DeckCard,
  LayoutGrid,
  MetricTile,
} from "@/components/DeckOps";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";

// ── Constants ────────────────────────────────────────────────────────────────

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
] as const;

/** Daily spend alert threshold (USD). Hardcoded default; Wave 2 will make this configurable. */
const DEFAULT_ALERT_THRESHOLD_USD = 5.0;

// ── Formatters ───────────────────────────────────────────────────────────────

function fmtUsd(n: number | null | undefined, decimals = 4): string {
  if (n === null || n === undefined) return "—";
  if (n === 0) return "$0.00";
  if (n < 0.0001) return "<$0.0001";
  return `$${n.toFixed(decimals)}`;
}

function fmtTokens(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtDate(day: string): string {
  try {
    const d = new Date(day + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return day;
  }
}

// ── Sub-components ───────────────────────────────────────────────────────────

function CostsSkeleton() {
  return (
    <DeckPageShell>
      <div className="flex items-center gap-2 py-8">
        <Spinner />
        <span className="text-sm text-[var(--dsd-text-secondary)]">Loading cost data…</span>
      </div>
    </DeckPageShell>
  );
}

function CostsError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <DeckPageShell>
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <AlertTriangle className="h-6 w-6 text-[var(--color-warning)]" />
        <p className="text-sm text-[var(--dsd-text-secondary)]">{message}</p>
        <button type="button" className="deck-btn-sm ghost" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </button>
      </div>
    </DeckPageShell>
  );
}

function CostsEmpty() {
  return (
    <DeckPageShell>
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <span className="text-2xl opacity-40">💰</span>
        <p className="text-sm text-[var(--dsd-text-secondary)]">No cost data yet — run an agent session to start tracking spend.</p>
      </div>
    </DeckPageShell>
  );
}

/** Mini bar-chart sparkline rendered via CSS — no chart dependency. */
function MiniBarChart({ data, valueKey }: { data: CostsDayEntry[]; valueKey: keyof CostsDayEntry }) {
  if (!data.length) {
    return <p className="text-xs text-[var(--dsd-text-secondary)] py-2">No trend data for this period.</p>;
  }
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0));
  return (
    <div className="flex items-end gap-px h-16 w-full overflow-hidden" aria-label="Daily cost sparkline">
      {data.map((entry) => {
        const val = Number(entry[valueKey]) || 0;
        const pct = max > 0 ? (val / max) * 100 : 0;
        return (
          <div
            key={entry.day}
            title={`${fmtDate(entry.day)}: ${fmtUsd(val)}`}
            className="flex-1 min-w-0 rounded-sm bg-[var(--color-primary)] opacity-70 hover:opacity-100 transition-opacity"
            style={{ height: `${Math.max(pct, 2)}%` }}
          />
        );
      })}
    </div>
  );
}

/** Per-model cost table */
function ModelTable({ rows }: { rows: CostsModelEntry[] }) {
  if (!rows.length) {
    return <p className="text-xs text-[var(--dsd-text-secondary)]">No model data.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="text-left text-[var(--dsd-text-secondary)] border-b border-[var(--color-border)]">
            <th className="py-1.5 pr-4 font-medium">Model</th>
            <th className="py-1.5 pr-4 font-medium text-right">Cost (est.)</th>
            <th className="py-1.5 pr-4 font-medium text-right">Input tok</th>
            <th className="py-1.5 pr-4 font-medium text-right">Output tok</th>
            <th className="py-1.5 pr-4 font-medium text-right">Runs</th>
            <th className="py-1.5 font-medium text-right">API calls</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.model}
              className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-muted)] transition-colors"
            >
              <td className="py-1.5 pr-4 font-mono-ui truncate max-w-[200px]" title={row.model}>
                {row.model}
              </td>
              <td className="py-1.5 pr-4 text-right tabular-nums">{fmtUsd(row.estimated_cost)}</td>
              <td className="py-1.5 pr-4 text-right tabular-nums">{fmtTokens(row.input_tokens)}</td>
              <td className="py-1.5 pr-4 text-right tabular-nums">{fmtTokens(row.output_tokens)}</td>
              <td className="py-1.5 pr-4 text-right tabular-nums">{row.runs}</td>
              <td className="py-1.5 text-right tabular-nums">{row.api_calls}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Routing savings card */
function SavingsCard({ savings }: { savings: CostsSavingsResponse }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <TrendingDown className="h-4 w-4 text-[var(--color-success)]" />
        <span className="text-sm font-medium">
          {fmtUsd(savings.estimated_savings_usd, 4)} estimated saved
          {savings.is_estimate && (
            <span className="ml-1 text-xs text-[var(--dsd-text-secondary)]">(estimate)</span>
          )}
        </span>
      </div>
      <div className="text-xs text-[var(--dsd-text-secondary)] space-y-0.5">
        <div>Premium-tier spend: {fmtUsd(savings.premium_spend_usd)} across {savings.premium_runs} runs</div>
        <div>Mid-tier cost ratio: {Math.round(savings.mid_cost_factor * 100)}%</div>
        {savings.is_estimate && (
          <div className="italic opacity-70 mt-1">{savings.note}</div>
        )}
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function CostsPage() {
  const [days, setDays] = useState<number>(30);
  const [summary, setSummary] = useState<CostsSummaryResponse | null>(null);
  const [byModel, setByModel] = useState<CostsModelEntry[]>([]);
  const [byDay, setByDay] = useState<CostsDayEntry[]>([]);
  const [savings, setSavings] = useState<CostsSavingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, byModelData, byDayData, savingsData] = await Promise.all([
        api.getCostsSummary(),
        api.getCostsByModel(days),
        api.getCostsByDay(days),
        api.getCostsSavings(days),
      ]);
      setSummary(summaryData);
      setByModel(byModelData.by_model);
      setByDay(byDayData.by_day);
      setSavings(savingsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const { setEnd } = usePageHeader();
  useLayoutEffect(() => {
    setEnd(
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          {PERIODS.map(({ label, days: d }) => (
            <button
              key={label}
              type="button"
              className={cn("deck-btn-sm", days === d ? "primary" : "ghost")}
              onClick={() => setDays(d)}
            >
              {label}
            </button>
          ))}
        </div>
        <button type="button" className="deck-btn-sm ghost" onClick={() => void refresh()}>
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </button>
      </div>,
    );
    return () => setEnd(null);
  }, [refresh, setEnd, loading, days]);

  if (loading && !summary) return <CostsSkeleton />;
  if (error) return <CostsError message={error} onRetry={() => void refresh()} />;
  if (!summary) return <CostsEmpty />;

  const noData = summary.runs_total === 0;
  if (noData) return <CostsEmpty />;

  // Alert banner: fire when today's spend exceeds threshold
  const showAlert = (summary.spend_today ?? 0) >= DEFAULT_ALERT_THRESHOLD_USD;

  return (
    <DeckPageShell>
      {/* Threshold alert banner */}
      {showAlert && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-md bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 text-[var(--color-warning)] text-xs">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span>
            Daily spend alert: today's cost ({fmtUsd(summary.spend_today)}) exceeded the{" "}
            {fmtUsd(DEFAULT_ALERT_THRESHOLD_USD)} threshold.
          </span>
        </div>
      )}

      {/* KPI tiles */}
      <LayoutGrid>
        <MetricTile
          label="Spend Today"
          value={fmtUsd(summary.spend_today)}
          context={`${summary.runs_today} run${summary.runs_today !== 1 ? "s" : ""} today`}
        />
        <MetricTile
          label="Total Spend"
          value={fmtUsd(summary.spend_total, 4)}
          context={`${summary.runs_total} runs all-time`}
        />
        <MetricTile
          label="Tokens (period)"
          value={fmtTokens(summary.tokens_total)}
          context={`${days}d window`}
        />
        <MetricTile
          label="Runs (all-time)"
          value={String(summary.runs_total)}
        />
      </LayoutGrid>

      {/* Daily trend sparkline */}
      <DeckCard title="Daily Cost Trend" subtitle={`Last ${days} days`} colClass="col-12">
        <MiniBarChart data={byDay} valueKey="estimated_cost" />
      </DeckCard>

      {/* By-model table */}
      <DeckCard
        title="Cost by Model"
        subtitle={`Top models by estimated spend — last ${days} days`}
        colClass="col-12"
      >
        <ModelTable rows={byModel} />
      </DeckCard>

      {/* Routing savings */}
      {savings && (
        <DeckCard
          title="Routing Savings"
          subtitle="Estimated downgrade savings from smart model routing"
          colClass="col-12"
        >
          <SavingsCard savings={savings} />
        </DeckCard>
      )}
    </DeckPageShell>
  );
}
