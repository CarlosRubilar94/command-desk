import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { DeckPageShell } from "@/components/DeckPageShell";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { DelegationStatusResponse, FleetStatusResponse } from "@/lib/api";
import {
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricRow,
  MetricTile,
} from "@/components/DeckOps";
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

export default function OpsFleetPage() {
  const [fleet, setFleet] = useState<FleetStatusResponse | null>(null);
  const [delegation, setDelegation] = useState<DelegationStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [fleetData, delegationData] = await Promise.all([
        api.getFleetStatus(),
        api.getDelegationStatus(),
      ]);
      setFleet(fleetData);
      setDelegation(delegationData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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
          </>
        ) : null}
      </div>
    </DeckPageShell>
  );
}
