import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { AlertTriangle, Plus, RefreshCw, Save, TrendingDown, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type {
  CostGuardrailsConfig,
  CostGuardrailsMissionBudgetStatus,
  CostsGuardrailsResponse,
  CostsSummaryResponse,
  CostsModelEntry,
  CostsDayEntry,
  CostsSavingsResponse,
  MissionCostRow,
} from "@/lib/api";
import { DeckPageShell } from "@/components/DeckPageShell";
import {
  DeckCard,
  LayoutGrid,
  MetricTile,
} from "@/components/DeckOps";
import { DataTable, EmptyState, ErrorState, SkeletonTable, StatusPill } from "@/components/ds";
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
      <div className="flex flex-col gap-4 py-4">
        <div className="grid grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="rounded-[var(--dsd-radius-md)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] p-4">
              <div className="h-3 w-16 rounded bg-[var(--dsd-layer-overlay)] mb-2 animate-pulse" />
              <div className="h-6 w-24 rounded bg-[var(--dsd-layer-overlay)] animate-pulse" />
            </div>
          ))}
        </div>
        <SkeletonTable rows={8} cols={5} />
      </div>
    </DeckPageShell>
  );
}

function CostsError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <DeckPageShell>
      <ErrorState
        title="Failed to load costs"
        message={message}
        icon={<AlertTriangle className="h-5 w-5" />}
        onRetry={onRetry}
      />
    </DeckPageShell>
  );
}

function CostsEmpty() {
  return (
    <DeckPageShell>
      <EmptyState
        title="No cost data yet"
        description="Run an agent session to start tracking spend."
        icon={<span aria-hidden>💰</span>}
        compact
      />
    </DeckPageShell>
  );
}

/** Mini bar-chart sparkline rendered via CSS — no chart dependency. */
const MiniBarChart = memo(function MiniBarChart({ data, valueKey }: { data: CostsDayEntry[]; valueKey: keyof CostsDayEntry }) {
  const max = useMemo(
    () => Math.max(...data.map((d) => Number(d[valueKey]) || 0), 0),
    [data, valueKey],
  );
  if (!data.length) {
    return <p className="text-xs text-[var(--dsd-text-secondary)] py-2">No trend data for this period.</p>;
  }
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
});

/** Per-model cost table */
const ModelTable = memo(function ModelTable({ rows }: { rows: CostsModelEntry[] }) {
  if (!rows.length) {
    return <p className="text-xs text-[var(--dsd-text-secondary)]">No model data.</p>;
  }
  const columns = [
    {
      key: "model",
      header: "Model",
      sortKey: "model" as const,
      cell: (row: CostsModelEntry) => (
        <span className="font-mono-ui truncate max-w-[220px]" title={row.model}>
          {row.model}
        </span>
      ),
    },
    {
      key: "estimated_cost",
      header: "Cost (est.)",
      sortKey: "estimated_cost" as const,
      align: "right" as const,
      cell: (row: CostsModelEntry) => <span className="tabular-nums">{fmtUsd(row.estimated_cost)}</span>,
    },
    {
      key: "input_tokens",
      header: "Input",
      sortKey: "input_tokens" as const,
      align: "right" as const,
      cell: (row: CostsModelEntry) => <span className="tabular-nums">{fmtTokens(row.input_tokens)}</span>,
    },
    {
      key: "output_tokens",
      header: "Output",
      sortKey: "output_tokens" as const,
      align: "right" as const,
      cell: (row: CostsModelEntry) => <span className="tabular-nums">{fmtTokens(row.output_tokens)}</span>,
    },
    {
      key: "runs",
      header: "Runs",
      sortKey: "runs" as const,
      align: "right" as const,
      cell: (row: CostsModelEntry) => <span className="tabular-nums">{row.runs}</span>,
    },
  ];
  return (
    <DataTable
      rows={rows}
      rowKey={(row) => row.model}
      cols={columns}
      dense
      maxRows={12}
      quickFilter
      filterPlaceholder="Filter models…"
      aria-label="Cost by model"
    />
  );
});

function BudgetBar({
  spend,
  budget,
  label,
}: {
  spend: number;
  budget: number | null;
  label: string;
}) {
  const pct = budget && budget > 0 ? Math.min(100, (spend / budget) * 100) : 0;
  const over = budget !== null && spend > budget;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--dsd-text-secondary)]">{label}</span>
        <span className="tabular-nums text-[var(--dsd-text-primary)]">
          {fmtUsd(spend)} {budget !== null ? ` / ${fmtUsd(budget)}` : ""}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-[var(--dsd-layer-surface)]" aria-hidden>
        <div
          className={cn("h-full rounded-full transition-all", over ? "bg-[var(--dsd-sem-critical)]" : "bg-[var(--dsd-accent-primary)]")}
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
    </div>
  );
}

function SavingsPanel({ savings }: { savings: CostsSavingsResponse }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <TrendingDown className="h-4 w-4 text-[var(--dsd-sem-success)]" />
        <span className="text-sm font-medium">
          {fmtUsd(savings.estimated_savings_usd, 4)} saved
        </span>
        <StatusPill
          variant={savings.is_estimate ? "warning" : "success"}
          label={savings.is_estimate ? "estimated" : "actual"}
        />
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

const MissionCostTable = memo(function MissionCostTable({ rows }: { rows: MissionCostRow[] }) {
  if (!rows.length) {
    return <p className="text-xs text-[var(--dsd-text-secondary)]">No mission cost data.</p>;
  }
  const columns = [
    {
      key: "title",
      header: "Mission",
      sortKey: "title" as const,
      cell: (row: MissionCostRow) => (
        <div className="flex items-center gap-2">
          <span className="truncate max-w-[240px]" title={row.title}>
            {row.title}
          </span>
          <StatusPill
            variant={row.is_estimate ? "warning" : "success"}
            label={row.is_estimate ? "estimated" : "actual"}
          />
        </div>
      ),
    },
    {
      key: "cost_usd",
      header: "Cost",
      sortKey: "cost_usd" as const,
      align: "right" as const,
      cell: (row: MissionCostRow) => <span className="tabular-nums">{fmtUsd(row.cost_usd)}</span>,
    },
    {
      key: "total_tokens",
      header: "Tokens",
      sortKey: "total_tokens" as const,
      align: "right" as const,
      cell: (row: MissionCostRow) => <span className="tabular-nums">{fmtTokens(row.total_tokens)}</span>,
    },
    {
      key: "run_count",
      header: "Runs",
      sortKey: "run_count" as const,
      align: "right" as const,
      cell: (row: MissionCostRow) => <span className="tabular-nums">{row.run_count}</span>,
    },
  ];
  return (
    <DataTable
      rows={rows}
      rowKey={(row) => row.mission_id}
      cols={columns}
      dense
      maxRows={8}
      quickFilter
      filterPlaceholder="Filter missions…"
      aria-label="Cost by mission"
    />
  );
});

function GuardrailsPanel({
  payload,
  saving,
  onSave,
}: {
  payload: CostsGuardrailsResponse;
  saving: boolean;
  onSave: (cfg: CostGuardrailsConfig) => Promise<void>;
}) {
  const [config, setConfig] = useState<CostGuardrailsConfig>(payload.cost_guardrails);
  const [newMissionId, setNewMissionId] = useState("");
  const [newMissionBudget, setNewMissionBudget] = useState("");

  useEffect(() => setConfig(payload.cost_guardrails), [payload.cost_guardrails]);

  const missionEntries = useMemo(
    () => Object.entries(config.mission_budgets_usd).sort((a, b) => a[0].localeCompare(b[0])),
    [config.mission_budgets_usd],
  );

  const actionVariant = payload.status.current_decision.action === "fallback"
    ? "warning"
    : payload.status.current_decision.action === "block"
      ? "error"
      : payload.status.current_decision.action === "warn"
        ? "warning"
        : "success";

  const save = async () => {
    await onSave(config);
  };

  return (
    <DeckCard title="Guardrails" subtitle="Budget, premium alert, and fallback controls" colClass="col-12">
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={(e) => setConfig((prev) => ({ ...prev, enabled: e.target.checked }))}
            />
            <span>Enable cost guardrails</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={config.premium_alert}
              onChange={(e) => setConfig((prev) => ({ ...prev, premium_alert: e.target.checked }))}
            />
            <span>Alert on premium model usage</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={config.block_expensive}
              onChange={(e) => setConfig((prev) => ({ ...prev, block_expensive: e.target.checked }))}
            />
            <span>Block expensive models</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={config.auto_fallback}
              onChange={(e) => setConfig((prev) => ({ ...prev, auto_fallback: e.target.checked }))}
            />
            <span>Auto-fallback when blocked/over budget</span>
          </label>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="text-xs text-[var(--dsd-text-secondary)]">
            Daily budget (USD)
            <input
              type="number"
              min={0}
              step="0.01"
              value={config.daily_budget_usd ?? ""}
              onChange={(e) => {
                const value = e.target.value.trim();
                setConfig((prev) => ({ ...prev, daily_budget_usd: value ? Number(value) : null }));
              }}
              className="mt-1 w-full rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-[var(--dsd-text-secondary)]">
            Fallback model
            <input
              type="text"
              value={config.fallback_model}
              onChange={(e) => setConfig((prev) => ({ ...prev, fallback_model: e.target.value }))}
              className="mt-1 w-full rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-[var(--dsd-text-secondary)]">
            Fallback provider (optional)
            <input
              type="text"
              value={config.fallback_provider}
              onChange={(e) => setConfig((prev) => ({ ...prev, fallback_provider: e.target.value }))}
              className="mt-1 w-full rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="space-y-2">
          <div className="text-xs text-[var(--dsd-text-secondary)]">Per-mission budgets</div>
          {missionEntries.length === 0 ? (
            <div className="text-xs text-[var(--dsd-text-faint)]">No mission budgets configured.</div>
          ) : (
            <div className="space-y-2">
              {missionEntries.map(([missionId, budget]) => (
                <div key={missionId} className="flex items-center gap-2">
                  <code className="min-w-[220px] truncate rounded bg-[var(--dsd-layer-surface)] px-2 py-1 text-xs">{missionId}</code>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={budget}
                    onChange={(e) => {
                      const val = Number(e.target.value || 0);
                      setConfig((prev) => ({
                        ...prev,
                        mission_budgets_usd: {
                          ...prev.mission_budgets_usd,
                          [missionId]: val,
                        },
                      }));
                    }}
                    className="w-28 rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] px-2 py-1 text-sm"
                  />
                  <button
                    type="button"
                    className="deck-btn-sm ghost"
                    onClick={() =>
                      setConfig((prev) => {
                        const next = { ...prev.mission_budgets_usd };
                        delete next[missionId];
                        return { ...prev, mission_budgets_usd: next };
                      })
                    }
                    aria-label={`Remove mission budget ${missionId}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              placeholder="mission_id"
              value={newMissionId}
              onChange={(e) => setNewMissionId(e.target.value)}
              className="rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] px-2 py-1 text-sm"
            />
            <input
              type="number"
              min={0}
              step="0.01"
              placeholder="budget"
              value={newMissionBudget}
              onChange={(e) => setNewMissionBudget(e.target.value)}
              className="w-28 rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] px-2 py-1 text-sm"
            />
            <button
              type="button"
              className="deck-btn-sm ghost"
              onClick={() => {
                const key = newMissionId.trim();
                const val = Number(newMissionBudget || 0);
                if (!key || !Number.isFinite(val) || val <= 0) return;
                setConfig((prev) => ({
                  ...prev,
                  mission_budgets_usd: { ...prev.mission_budgets_usd, [key]: val },
                }));
                setNewMissionId("");
                setNewMissionBudget("");
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              Add mission
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusPill
            variant={actionVariant}
            label={`Current action: ${payload.status.current_decision.action}`}
          />
          <span className="text-xs text-[var(--dsd-text-secondary)]">
            {payload.status.current_decision.reason || "No active guardrail reason."}
          </span>
          <button type="button" className="deck-btn-sm primary ml-auto" onClick={() => void save()} disabled={saving}>
            <Save className="h-3.5 w-3.5" />
            {saving ? "Saving..." : "Save guardrails"}
          </button>
        </div>

        <BudgetBar
          spend={payload.status.spend_today_usd}
          budget={payload.status.daily_budget_usd}
          label="Daily budget usage"
        />

        {payload.status.mission_budgets.length > 0 && (
          <div className="space-y-2">
            {payload.status.mission_budgets.map((item: CostGuardrailsMissionBudgetStatus) => (
              <BudgetBar
                key={item.mission_id}
                spend={item.spend_usd}
                budget={item.budget_usd}
                label={`${item.title} (${item.mission_id})`}
              />
            ))}
          </div>
        )}

        <div className="text-xs text-[var(--dsd-text-secondary)]">
          Premium today: {payload.status.premium_usage_today.runs} runs, {fmtUsd(payload.status.premium_usage_today.spend_usd)} spend, projected day-end {fmtUsd(payload.status.projected_spend_today_usd)}.
        </div>
      </div>
    </DeckCard>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function CostsPage() {
  const [days, setDays] = useState<number>(30);
  const [summary, setSummary] = useState<CostsSummaryResponse | null>(null);
  const [byModel, setByModel] = useState<CostsModelEntry[]>([]);
  const [byDay, setByDay] = useState<CostsDayEntry[]>([]);
  const [savings, setSavings] = useState<CostsSavingsResponse | null>(null);
  const [byMission, setByMission] = useState<MissionCostRow[]>([]);
  const [byMissionEstimate, setByMissionEstimate] = useState(true);
  const [guardrails, setGuardrails] = useState<CostsGuardrailsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingGuardrails, setSavingGuardrails] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, byModelData, byDayData, savingsData, guardrailsData, byMissionData] = await Promise.all([
        api.getCostsSummary(),
        api.getCostsByModel(days),
        api.getCostsByDay(days),
        api.getCostsSavings(days),
        api.getCostsGuardrails(),
        api.getCostsByMission(days),
      ]);
      setSummary(summaryData);
      setByModel(byModelData.by_model);
      setByDay(byDayData.by_day);
      setSavings(savingsData);
      setGuardrails(guardrailsData);
      setByMission(byMissionData.missions || []);
      setByMissionEstimate(Boolean(byMissionData.is_estimate));
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
  const saveGuardrails = async (cfg: CostGuardrailsConfig) => {
    setSavingGuardrails(true);
    try {
      await api.updateCostsGuardrails({
        enabled: cfg.enabled,
        daily_budget_usd: cfg.daily_budget_usd,
        mission_budgets_usd: cfg.mission_budgets_usd,
        premium_alert: cfg.premium_alert,
        block_expensive: cfg.block_expensive,
        auto_fallback: cfg.auto_fallback,
        fallback_model: cfg.fallback_model,
        fallback_provider: cfg.fallback_provider,
        premium_model_prefixes: cfg.premium_model_prefixes,
      });
      await refresh();
    } finally {
      setSavingGuardrails(false);
    }
  };

  return (
    <DeckPageShell>
      <h1 className="sr-only">Spend</h1>
      {/* Threshold alert banner */}
      {showAlert && (
        <div role="alert" className="flex items-center gap-2 mb-4 px-3 py-2 rounded-md bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 text-[var(--color-warning)] text-xs">
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

      {/* Guardrails controls + live status */}
      {guardrails && (
        <GuardrailsPanel payload={guardrails} saving={savingGuardrails} onSave={saveGuardrails} />
      )}

      {/* Savings */}
      {savings && (
        <DeckCard title="Savings" subtitle="Estimated savings from routing and model mix" colClass="col-12">
          <SavingsPanel savings={savings} />
        </DeckCard>
      )}

      <DeckCard
        title="Cost by Mission"
        subtitle={byMissionEstimate ? "Estimated where span data is missing" : "Using recorded span costs"}
        colClass="col-12"
      >
        <MissionCostTable rows={byMission} />
      </DeckCard>
    </DeckPageShell>
  );
}
