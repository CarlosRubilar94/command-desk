import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type {
  MissionRow,
  FleetMetricsResponse,
  CostsSummaryResponse,
} from "@/lib/api";
import { MetricTile } from "@/components/DeckOps";
import { StatusPill } from "@/components/ds/StatusPill";
import type { StatusVariant } from "@/components/ds/StatusPill";
import { Spinner } from "@nous-research/ui/ui/components/spinner";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  if (n < 0.0001) return "<$0.0001";
  return `$${n.toFixed(4)}`;
}

function missionStatusVariant(status: string): StatusVariant {
  const s = status.toLowerCase();
  if (s === "done" || s === "completed" || s === "closed") return "success";
  if (s === "in_progress" || s === "active" || s === "running") return "info";
  if (s === "blocked" || s === "error" || s === "failed") return "error";
  if (s === "paused" || s === "waiting") return "warning";
  return "neutral";
}

// ── Mission Overview panel ─────────────────────────────────────────────────────

export function MissionOverview() {
  const [missions, setMissions] = useState<MissionRow[]>([]);
  const [fleet, setFleet] = useState<FleetMetricsResponse | null>(null);
  const [costSummary, setCostSummary] = useState<CostsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [missionsResp, fleetResp, costsResp] = await Promise.allSettled([
        api.getMissions({ limit: 5 }),
        api.getFleetMetrics(),
        api.getCostsSummary(),
      ]);
      if (missionsResp.status === "fulfilled") setMissions(missionsResp.value.missions);
      if (fleetResp.status === "fulfilled") setFleet(fleetResp.value);
      if (costsResp.status === "fulfilled") setCostSummary(costsResp.value);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const activeMissions = missions.filter(
    (m) =>
      m.status.toLowerCase() === "in_progress" ||
      m.status.toLowerCase() === "active" ||
      m.status.toLowerCase() === "running",
  );
  const topBySpend = [...missions].sort((a, b) => b.cost_usd - a.cost_usd).slice(0, 3);

  // Overall health from fleet
  const tracerHealthy = fleet?.tracer.healthy !== false;
  const errorRate = fleet?.recurring_errors.length ?? 0;
  const healthState: StatusVariant =
    !tracerHealthy ? "error" : errorRate > 0 ? "warning" : "success";
  const healthLabel = !tracerHealthy ? "degraded" : errorRate > 0 ? "errors" : "healthy";

  if (loading && !missions.length) {
    return (
      <div className="deck-card col-12 rounded-[var(--dsd-radius-lg)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-base)] p-4">
        <div className="flex items-center gap-2 text-sm text-[var(--dsd-text-secondary)]">
          <Spinner className="h-3.5 w-3.5" />
          Loading mission overview…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="deck-card col-12 rounded-[var(--dsd-radius-lg)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-base)] p-4">
        <p className="text-xs text-[var(--dsd-sem-critical)]">{error}</p>
      </div>
    );
  }

  return (
    <div className="col-12 flex flex-col gap-3 rounded-[var(--dsd-radius-lg)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-base)] p-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-1.5 h-3.5 rounded-sm bg-[var(--dsd-cat-mission)] opacity-80"
            aria-hidden
          />
          <span className="text-xs font-semibold tracking-wider uppercase text-[var(--dsd-text-primary)]">
            Mission Overview
          </span>
        </div>
        <Link
          to="/missions"
          className="text-[10px] text-[var(--dsd-cat-mission)] hover:underline shrink-0"
        >
          View all →
        </Link>
      </div>

      {/* Metric tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <MetricTile
          label="Active Missions"
          value={String(activeMissions.length)}
          state={activeMissions.length > 0 ? "ok" : "neutral"}
        />
        <MetricTile
          label="Spend Today"
          value={fmtUsd(costSummary?.spend_today)}
          state="ok"
          context={`${costSummary?.runs_today ?? "—"} runs`}
        />
        <MetricTile
          label="Agents Running"
          value={
            fleet
              ? String(fleet.queue.in_progress)
              : "—"
          }
          state="ok"
          context={
            fleet
              ? `${fleet.queue.ready} queued`
              : undefined
          }
        />
        <MetricTile
          label="Fleet Health"
          value={healthLabel}
          state={healthState === "success" ? "ok" : healthState === "warning" ? "warning" : "critical"}
        />
      </div>

      {/* Top missions by spend */}
      {topBySpend.length > 0 && (
        <div className="flex flex-col gap-0">
          <div className="text-[10px] font-semibold tracking-widest uppercase text-[var(--dsd-text-faint)] mb-1">
            Top Missions by Spend
          </div>
          <div className="flex flex-col gap-0.5">
            {topBySpend.map((m) => (
              <Link
                key={m.mission_id}
                to="/missions"
                className="flex items-center gap-2 rounded px-1.5 py-1 hover:bg-[var(--dsd-layer-overlay)] transition-colors text-xs group"
              >
                <StatusPill
                  variant={missionStatusVariant(m.status)}
                  label={m.status}
                  dot
                  size="sm"
                />
                <span className="flex-1 min-w-0 text-[var(--dsd-text-secondary)] truncate">
                  {m.title}
                </span>
                <span className="tabular-nums text-[var(--dsd-cat-cost)] shrink-0">
                  {fmtUsd(m.cost_usd)}
                </span>
                <span className="text-[10px] text-[var(--dsd-text-faint)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  {Math.round(m.progress.pct)}%
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {missions.length === 0 && (
        <p className="text-xs text-[var(--dsd-text-faint)] text-center py-2">
          No missions yet.{" "}
          <Link to="/missions" className="text-[var(--dsd-cat-mission)] hover:underline">
            Create one →
          </Link>
        </p>
      )}
    </div>
  );
}
