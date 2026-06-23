import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { DeckPageShell } from "@/components/DeckPageShell";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type {
  AutopilotDiagnoseResponse,
  AutopilotIncident,
  DelegationStatusResponse,
  FleetMetricsResponse,
  FleetStatusResponse,
} from "@/lib/api";
import {
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricRow,
  MetricTile,
} from "@/components/DeckOps";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { StatusPill } from "@/components/ds/StatusPill";
import { DataTable } from "@/components/ds/DataTable";
import type { ColDef } from "@/components/ds/DataTable";
import { cn } from "@/lib/utils";

function countStatus(stats: FleetStatusResponse["kanban"]["stats"], key: string): number {
  return stats?.by_status?.[key] ?? 0;
}

function delegationPillClass(status?: string): string {
  const s = (status ?? "").toLowerCase();
  if (s === "running" || s === "pending") return "running";
  if (s === "error" || s === "failed") return "error";
  if (s === "done" || s === "completed") return "done";
  return "";
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  if (n < 0.0001) return "<$0.0001";
  return `$${n.toFixed(4)}`;
}

function fmtMs(ms: number): string {
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`;
  if (ms >= 1_000) return `${(ms / 1_000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

function severityVariant(severity: string): "error" | "warning" | "info" | "neutral" {
  const normalized = severity.toLowerCase();
  if (normalized === "critical") return "error";
  if (normalized === "warning") return "warning";
  if (normalized === "info") return "info";
  return "neutral";
}

const BOTTLENECK_COLS: ColDef<FleetMetricsResponse["bottlenecks"][number]>[] = [
  {
    key: "name",
    header: "Span",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-base)]">{r.name}</span>
    ),
  },
  {
    key: "kind",
    header: "Kind",
    width: 100,
    cell: (r) => (
      <StatusPill variant="trace" label={r.kind} size="sm" />
    ),
  },
  {
    key: "avg_duration_ms",
    header: "Avg duration",
    width: 110,
    align: "right",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-dim)]">
        {fmtMs(r.avg_duration_ms)}
      </span>
    ),
  },
  {
    key: "count",
    header: "Count",
    width: 70,
    align: "right",
    cell: (r) => (
      <span className="text-xs font-mono text-[var(--dsd-text-faint)]">{r.count}</span>
    ),
  },
];

export default function OpsFleetPage() {
  const [fleet, setFleet] = useState<FleetStatusResponse | null>(null);
  const [delegation, setDelegation] = useState<DelegationStatusResponse | null>(null);
  const [metrics, setMetrics] = useState<FleetMetricsResponse | null>(null);
  const [incidents, setIncidents] = useState<AutopilotIncident[]>([]);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const [diagnosingId, setDiagnosingId] = useState<string | null>(null);
  const [diagnoseResultByIncident, setDiagnoseResultByIncident] = useState<
    Record<string, AutopilotDiagnoseResponse>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIncidentsError(null);
    try {
      const [fleetData, delegationData, metricsData, incidentsData] = await Promise.all([
        api.getFleetStatus(),
        api.getDelegationStatus(),
        api.getFleetMetrics().catch(() => null),
        api.getAutopilotIncidents().catch((err: unknown) => {
          setIncidentsError(err instanceof Error ? err.message : String(err));
          return { incidents: [] };
        }),
      ]);
      setFleet(fleetData);
      setDelegation(delegationData);
      setMetrics(metricsData);
      setIncidents(incidentsData.incidents ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createDiagnostic = useCallback(
    async (incident: AutopilotIncident) => {
      setDiagnosingId(incident.id);
      try {
        const response = await api.createAutopilotDiagnostic({ incident_id: incident.id });
        setDiagnoseResultByIncident((prev) => ({ ...prev, [incident.id]: response }));
      } catch (err) {
        setIncidentsError(err instanceof Error ? err.message : String(err));
      } finally {
        setDiagnosingId(null);
      }
    },
    [],
  );

  const { setEnd } = usePageHeader();
  useLayoutEffect(() => {
    setEnd(
      <button type="button" className="deck-btn-sm ghost" onClick={() => void refresh()}>
        <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
        Refresh
      </button>,
    );
    return () => setEnd(null);
  }, [refresh, setEnd, loading]);

  if (loading && !fleet) {
    return (
      <DeckPageShell>
        <div className="flex items-center gap-2 py-8">
          <Spinner />
          <span className="text-sm text-[var(--dsd-text-secondary)]">Loading fleet…</span>
        </div>
      </DeckPageShell>
    );
  }

  const running = fleet ? countStatus(fleet.kanban.stats, "running") : 0;
  const ready = fleet ? countStatus(fleet.kanban.stats, "ready") : 0;

  return (
    <DeckPageShell>
      <div className="deck-dashboard deck-animate">
        {error ? (
          <p className="mb-4 text-sm text-[var(--dsd-sem-critical)]">{error}</p>
        ) : null}
        {fleet ? (
          <>
            <div className="metrics-strip">
              <MetricTile
                label="Active agents"
                value={fleet.active_agents}
                state={fleet.active_agents > 0 ? "warning" : "ok"}
              />
              <MetricTile
                label="Kanban ready"
                value={ready}
                context={`${running} running`}
                state={ready > 0 && !fleet.kanban.dispatcher.running ? "warning" : "ok"}
              />
              <MetricTile
                label="Delegations"
                value={fleet.async_delegations_running}
                state={fleet.async_delegations_running > 0 ? "warning" : "ok"}
              />
              <MetricTile
                label="Cron due"
                value={`${fleet.cron.due_now} / ${fleet.cron.enabled_jobs}`}
                state="ok"
              />
            </div>

            <LayoutGrid>
              <DeckCard title="Gateway" colClass="col-4">
                <MetricRow label="State" value={fleet.gateway_state ?? "—"} tone="ok" />
                <MetricRow
                  label="Active agents"
                  value={String(fleet.active_agents)}
                  tone={fleet.active_agents > 0 ? "warn" : "ok"}
                />
                <MetricRow
                  label="Busy / drainable"
                  value={`${fleet.gateway_busy} / ${fleet.gateway_drainable}`}
                  tone="ok"
                />
              </DeckCard>

              <DeckCard title="Delegation" colClass="col-4">
                <MetricRow
                  label="Async running"
                  value={String(fleet.async_delegations_running)}
                  tone="ok"
                />
                <MetricRow
                  label="Max concurrent"
                  value={String(fleet.delegation.max_concurrent_children)}
                  tone="ok"
                />
                <MetricRow
                  label="Spawn depth"
                  value={String(fleet.delegation.max_spawn_depth)}
                  tone="ok"
                />
                <MetricRow
                  label="Subagent model"
                  value={fleet.delegation.model ?? "(routing / inherit)"}
                  tone="ok"
                />
              </DeckCard>

              <DeckCard title="Cron" colClass="col-4">
                <MetricRow label="Enabled jobs" value={String(fleet.cron.enabled_jobs)} tone="ok" />
                <MetricRow label="Paused" value={String(fleet.cron.paused_jobs)} tone="ok" />
                <MetricRow label="Due now" value={String(fleet.cron.due_now)} tone="ok" />
              </DeckCard>

              <DeckCard title="Kanban board" colClass="col-6">
                {fleet.kanban.stats ? (
                  <>
                    {Object.entries(fleet.kanban.stats.by_status).map(([status, n]) => (
                      <MetricRow key={status} label={status} value={String(n)} tone="ok" />
                    ))}
                    {fleet.kanban.stats.oldest_ready_age_seconds != null ? (
                      <MetricRow
                        label="Oldest ready (s)"
                        value={String(fleet.kanban.stats.oldest_ready_age_seconds)}
                        tone={
                          (fleet.kanban.stats.oldest_ready_age_seconds ?? 0) > 120 ? "warn" : "ok"
                        }
                      />
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-[var(--dsd-text-secondary)]">
                    No kanban board initialized.
                  </p>
                )}
              </DeckCard>

              <DeckCard title="Smart model routing" colClass="col-6">
                {fleet.smart_model_routing.lines.map((line) => (
                  <p key={line} className="text-xs text-[var(--dsd-text-secondary)]">
                    {line}
                  </p>
                ))}
                <DeckToolbar>
                  <Link to="/routing" className="deck-btn-sm primary">
                    Routing settings
                  </Link>
                  <Link to="/config" className="deck-btn-sm ghost">
                    Config YAML
                  </Link>
                </DeckToolbar>
              </DeckCard>

              <DeckCard title="Background delegations" colClass="col-12">
                {delegation && delegation.items.length > 0 ? (
                  <div>
                    {delegation.items.map((item) => (
                      <div
                        key={item.delegation_id ?? item.goal}
                        className="deck-list-row"
                      >
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span
                            className={cn(
                              "deck-status-pill",
                              delegationPillClass(item.status),
                            )}
                          >
                            {item.status ?? "unknown"}
                          </span>
                          {item.model ? (
                            <span className="font-mono text-[var(--dsd-text-secondary)]">
                              {item.model}
                            </span>
                          ) : null}
                        </div>
                        {item.goal ? (
                          <p className="mt-2 text-sm text-[var(--dsd-text-secondary)]">
                            {item.goal}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--dsd-text-secondary)]">
                    No background delegations in this process.
                  </p>
                )}
                <DeckToolbar>
                  <Link to="/sessions?kind=delegation" className="deck-btn-sm ghost">
                    Delegation sessions
                  </Link>
                </DeckToolbar>
              </DeckCard>
            </LayoutGrid>

            {/* ── Fleet Metrics / Incident Console ────────────────────────── */}
            {metrics ? (
              <>
                <h2 className="mt-6 mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--dsd-text-faint)]">
                  Fleet Metrics / Incident
                </h2>

                {/* Tracer health warning */}
                {(!metrics.tracer.healthy || metrics.tracer.dropped_spans > 0) && (
                  <div
                    role="alert"
                    className="mb-3 flex items-center gap-2 px-3 py-2 rounded-[var(--dsd-radius-sm)] bg-[var(--dsd-status-warning-bg)] border border-[var(--dsd-status-warning)]/30 text-[var(--dsd-status-warning)] text-xs"
                  >
                    <span aria-hidden className="text-base">⚠</span>
                    <span>
                      Tracer{" "}
                      {!metrics.tracer.healthy ? "unhealthy" : "running"}
                      {metrics.tracer.dropped_spans > 0
                        ? ` — ${metrics.tracer.dropped_spans} dropped spans`
                        : ""}
                      {metrics.tracer.queue_size > 0
                        ? `, queue: ${metrics.tracer.queue_size}`
                        : ""}
                    </span>
                    <Link to="/traces" className="ml-auto underline hover:no-underline text-[var(--dsd-status-warning)]">
                      View traces →
                    </Link>
                  </div>
                )}

                <div className="metrics-strip mb-4">
                  <MetricTile
                    label="Queue ready"
                    value={metrics.queue.ready}
                    state={metrics.queue.ready > 0 ? "warning" : "ok"}
                  />
                  <MetricTile
                    label="In progress"
                    value={metrics.queue.in_progress}
                    state={metrics.queue.in_progress > 0 ? "warning" : "ok"}
                  />
                  <MetricTile
                    label="Blocked"
                    value={metrics.queue.blocked}
                    state={metrics.queue.blocked > 0 ? "warning" : "ok"}
                  />
                  <MetricTile
                    label="Spans / min"
                    value={metrics.throughput.spans_per_min}
                    state="ok"
                  />
                  <MetricTile
                    label="Traces today"
                    value={metrics.throughput.traces_today}
                    state="ok"
                  />
                  <MetricTile
                    label="Cost today"
                    value={fmtUsd(metrics.cost_today_usd)}
                    state="ok"
                  />
                </div>

                <LayoutGrid>
                  {/* Bottlenecks */}
                  <DeckCard title="Bottlenecks (slowest spans)" colClass="col-6">
                    {metrics.bottlenecks.length > 0 ? (
                      <DataTable
                        cols={BOTTLENECK_COLS}
                        rows={metrics.bottlenecks}
                        rowKey={(r) => r.name}
                        dense
                        stickyHeader={false}
                        onRowClick={(r) => {
                          window.location.href = `/traces?agent=${encodeURIComponent(r.name)}`;
                        }}
                        aria-label="Bottleneck spans"
                      />
                    ) : (
                      <p className="text-sm text-[var(--dsd-text-secondary)]">
                        No bottleneck data available.
                      </p>
                    )}
                    <DeckToolbar>
                      <Link to="/traces" className="deck-btn-sm ghost">
                        All traces →
                      </Link>
                    </DeckToolbar>
                  </DeckCard>

                  {/* Recurring errors */}
                  <DeckCard title="Recurring errors" colClass="col-6">
                    {metrics.recurring_errors.length > 0 ? (
                      <div className="space-y-1">
                        {metrics.recurring_errors.map((e) => (
                          <div
                            key={e.error}
                            className="deck-list-row flex items-start justify-between gap-3"
                          >
                            <div className="min-w-0">
                              <p
                                className="text-xs font-mono text-[var(--dsd-status-error)] truncate"
                                title={e.error}
                              >
                                {e.error}
                              </p>
                              <p className="text-[10px] text-[var(--dsd-text-faint)] font-mono">
                                last seen {e.last_seen}
                              </p>
                            </div>
                            <div className="shrink-0 flex flex-col items-end gap-1">
                              <span className="text-xs font-mono text-[var(--dsd-status-error)]">
                                ×{e.count}
                              </span>
                              <Link
                                to="/traces?status=error"
                                className="text-[10px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-accent-primary)] transition-colors"
                              >
                                traces →
                              </Link>
                              <Link
                                to="/sessions"
                                className="text-[10px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-accent-primary)] transition-colors"
                              >
                                sessions →
                              </Link>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-[var(--dsd-text-secondary)]">
                        No recurring errors recorded.
                      </p>
                    )}
                    <DeckToolbar>
                      <Link to="/traces?status=error" className="deck-btn-sm ghost">
                        Error traces →
                      </Link>
                      <Link to="/sessions" className="deck-btn-sm ghost">
                        Sessions →
                      </Link>
                    </DeckToolbar>
                  </DeckCard>
                </LayoutGrid>

                <LayoutGrid>
                  <DeckCard title="Ops Autopilot (operator-triggered)" colClass="col-12">
                    <p className="mb-3 text-xs text-[var(--dsd-text-faint)]">
                      Detection is read-only. Diagnostics are created only when you click
                      <span className="mx-1 font-semibold">Create diagnostic</span>
                      for an incident.
                    </p>

                    {incidentsError ? (
                      <ErrorState
                        compact
                        title="Autopilot unavailable"
                        message={incidentsError}
                        onRetry={() => void refresh()}
                      />
                    ) : incidents.length === 0 ? (
                      <EmptyState
                        compact
                        icon={<AlertTriangle className="h-4 w-4" />}
                        title="No incidents detected"
                        description="Current telemetry is healthy for configured thresholds."
                      />
                    ) : (
                      <div className="space-y-2">
                        {incidents.map((incident) => {
                          const result = diagnoseResultByIncident[incident.id];
                          const isRunning = diagnosingId === incident.id;
                          return (
                            <div key={incident.id} className="deck-list-row">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <StatusPill
                                    variant={severityVariant(incident.severity)}
                                    label={incident.severity}
                                  />
                                  <StatusPill variant="fleet" label={incident.kind} />
                                </div>
                                <button
                                  type="button"
                                  className="deck-btn-sm primary"
                                  onClick={() => void createDiagnostic(incident)}
                                  disabled={isRunning}
                                  aria-label={`Create diagnostic for ${incident.title}`}
                                >
                                  {isRunning ? "Creating…" : "Create diagnostic"}
                                </button>
                              </div>
                              <p className="mt-2 text-sm text-[var(--dsd-text-base)]">{incident.title}</p>
                              <p className="mt-1 text-xs text-[var(--dsd-text-secondary)]">{incident.detail}</p>
                              <p className="mt-1 text-xs text-[var(--dsd-text-faint)]">
                                Suggested action: {incident.suggested_action}
                              </p>

                              {result ? (
                                <div className="mt-3 rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] p-3">
                                  <div className="flex flex-wrap items-center gap-3 text-xs">
                                    <Link to="/missions" className="deck-btn-sm ghost">
                                      Mission {result.mission_id}
                                    </Link>
                                    <span className="font-mono text-[var(--dsd-text-faint)]">
                                      Kanban task: {result.kanban_task_id ?? "not created"}
                                    </span>
                                  </div>
                                  <div className="mt-2 space-y-1 text-xs">
                                    <p>
                                      <span className="font-semibold">Summary:</span>{" "}
                                      {result.report.summary}
                                    </p>
                                    <p>
                                      <span className="font-semibold">Suspected cause:</span>{" "}
                                      {result.report.suspected_cause}
                                    </p>
                                    <p>
                                      <span className="font-semibold">Suggested fix:</span>{" "}
                                      {result.report.suggested_fix}
                                    </p>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </DeckCard>
                </LayoutGrid>
              </>
            ) : null}
          </>
        ) : null}
      </div>
    </DeckPageShell>
  );
}
