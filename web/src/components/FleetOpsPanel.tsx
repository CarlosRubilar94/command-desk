import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Clock, GitBranch, Layers, Radio, Zap } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type { FleetStatusResponse } from "@/lib/api";
import {
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricRow,
} from "@/components/DeckOps";
import { cn } from "@/lib/utils";

function countStatus(stats: FleetStatusResponse["kanban"]["stats"], key: string): number {
  return stats?.by_status?.[key] ?? 0;
}

export function FleetOpsPanel({ compact = false }: { compact?: boolean }) {
  const [fleet, setFleet] = useState<FleetStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nudging, setNudging] = useState(false);
  const [nudgeMsg, setNudgeMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setFleet(await api.getFleetStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  if (loading && !fleet) {
    return (
      <DeckCard title="Multi-agent fleet" colClass={compact ? "col-12" : "col-6"}>
        <div className="flex items-center gap-2 py-4 text-sm text-[var(--dsd-text-secondary)]">
          <Spinner />
          Loading fleet status…
        </div>
      </DeckCard>
    );
  }

  if (error && !fleet) {
    return (
      <DeckCard title="Multi-agent fleet" colClass={compact ? "col-12" : "col-6"}>
        <p className="text-sm text-[var(--dsd-sem-critical)]">{error}</p>
      </DeckCard>
    );
  }

  if (!fleet) return null;

  const running = countStatus(fleet.kanban.stats, "running");
  const ready = countStatus(fleet.kanban.stats, "ready");
  const blocked = countStatus(fleet.kanban.stats, "blocked");
  const routingOn = fleet.smart_model_routing.enabled;

  const handleNudgeDispatch = async () => {
    setNudging(true);
    setNudgeMsg(null);
    try {
      await api.nudgeKanbanDispatch(4);
      setNudgeMsg("Dispatcher nudged");
      await refresh();
    } catch (err) {
      setNudgeMsg(err instanceof Error ? err.message : "Dispatch failed");
    } finally {
      setNudging(false);
    }
  };

  return (
    <DeckCard
      title="Multi-agent fleet"
      subtitle="Gateway, kanban, cron, delegation"
      colClass={compact ? "col-12" : "col-6"}
    >
      <LayoutGrid>
        <MetricRow
          label="Gateway agents (busy)"
          value={String(fleet.active_agents)}
          tone={fleet.active_agents > 0 ? "warn" : "ok"}
        />
        <MetricRow
          label="Kanban workers"
          value={`${running} running · ${ready} ready · ${blocked} blocked`}
          tone={ready > 0 && !fleet.kanban.dispatcher.running ? "warn" : "ok"}
        />
        <MetricRow
          label="Background delegations"
          value={String(fleet.async_delegations_running)}
          tone={fleet.async_delegations_running > 0 ? "warn" : "ok"}
        />
        <MetricRow
          label="Cron (due / enabled)"
          value={`${fleet.cron.due_now} / ${fleet.cron.enabled_jobs}`}
          tone="ok"
        />
        <MetricRow
          label="Smart routing"
          value={routingOn ? `on (${fleet.smart_model_routing.delegation_tier})` : "off"}
          tone={routingOn ? "ok" : "warn"}
        />
        <MetricRow
          label="Kanban dispatcher"
          value={fleet.kanban.dispatcher.running ? "active" : "inactive"}
          tone={fleet.kanban.dispatcher.running ? "ok" : "warn"}
        />
      </LayoutGrid>

      {!compact && fleet.kanban.dispatcher.message ? (
        <p className="mt-2 text-xs text-[var(--dsd-text-muted)]">{fleet.kanban.dispatcher.message}</p>
      ) : null}
      {nudgeMsg ? <p className="mt-1 text-xs text-[var(--dsd-text-secondary)]">{nudgeMsg}</p> : null}

      <DeckToolbar>
        {ready > 0 ? (
          <button
            type="button"
            className="deck-btn-sm primary"
            disabled={nudging}
            onClick={() => void handleNudgeDispatch()}
          >
            <GitBranch className={cn("h-3.5 w-3.5", nudging && "animate-spin")} />
            Dispatch now
          </button>
        ) : null}
        <Link to="/ops" className="deck-btn-sm ghost">
          <Layers className="h-3.5 w-3.5" />
          Fleet detail
        </Link>
        <Link to="/routing" className="deck-btn-sm ghost">
          <Zap className="h-3.5 w-3.5" />
          Routing
        </Link>
        <Link to="/kanban" className="deck-btn-sm ghost">
          <GitBranch className="h-3.5 w-3.5" />
          Kanban
        </Link>
        <Link to="/cron" className="deck-btn-sm ghost">
          <Clock className="h-3.5 w-3.5" />
          Cron
        </Link>
        <button type="button" className="deck-btn-sm ghost" onClick={() => void refresh()}>
          <Radio className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </button>
      </DeckToolbar>
    </DeckCard>
  );
}
