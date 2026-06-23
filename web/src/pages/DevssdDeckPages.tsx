import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, DollarSign, Radio, Terminal, Zap } from "lucide-react";
import { SkeletonCard } from "@/components/ds/Skeleton";
import { ErrorState } from "@/components/ds/ErrorState";
import { EmptyState } from "@/components/ds/EmptyState";
import {
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricRow,
  MetricTile,
} from "@/components/DeckOps";
import { FleetOpsPanel } from "@/components/FleetOpsPanel";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import type { CommandDeckOverviewResponse } from "@/lib/api";
import {
  ActionButton,
  DevssdShell,
  LoadingOrError,
  useDevssdStatus,
} from "@/pages/DevssdPageShared";

export function DevssdDoctorPage() {
  const { status, loading, error, refresh } = useDevssdStatus();
  return (
    <DevssdShell
      title="Config / Doctor"
      description="Validação operacional do Command Desk, Bitwarden, gateway e runtime local."
      onRefresh={refresh}
      loading={loading}
    >
      <LoadingOrError loading={loading} error={error} />
      <LayoutGrid>
        <DeckCard title="Ações" colClass="col-12">
          <DeckToolbar>
            <ActionButton label="Run command-desk doctor" action={api.runDoctor} />
            <Link to="/config" className="deck-btn-sm ghost">
              Open Config
            </Link>
            <Link to="/system" className="deck-btn-sm ghost">
              System tools
            </Link>
          </DeckToolbar>
        </DeckCard>
        {status ? (
          <DeckCard title="Resolved paths" colClass="col-12">
            <div className="grid gap-2 font-mono text-xs text-[var(--dsd-text-secondary)]">
              <code>{status.agent.config_path}</code>
              <code>{status.agent.env_path}</code>
              <code>{status.agent.skills_dir}</code>
            </div>
          </DeckCard>
        ) : null}
      </LayoutGrid>
    </DevssdShell>
  );
}

export function BitwardenStatusPage() {
  const { status, loading, error, refresh } = useDevssdStatus();
  const bw = status?.bitwarden;
  const bwOk = Boolean(bw?.enabled && bw.token_present && bw.project_configured);

  return (
    <DevssdShell
      title="Secrets / Bitwarden"
      description="Bitwarden Secrets Manager e o bootstrap local BWS_ACCESS_TOKEN."
      onRefresh={refresh}
      loading={loading}
    >
      <LoadingOrError loading={loading} error={error} />
      {bw ? (
        <LayoutGrid>
          <DeckCard title="Bitwarden SM" colClass="col-6">
            <MetricRow label="Enabled" value={bw.enabled ? "Yes" : "No"} tone={bw.enabled ? "ok" : "warn"} />
            <MetricRow label="Token env" value={bw.token_present ? "present" : "missing"} tone={bw.token_present ? "ok" : "bad"} />
            <MetricRow label="Project" value={bw.project_configured ? "configured" : "missing"} tone={bw.project_configured ? "ok" : "warn"} />
            <MetricRow label="Server" value={bw.server_url} tone="ok" />
            <MetricRow label="bws CLI" value={bw.bws_found ? bw.bws_path ?? "found" : "not found"} tone={bw.bws_found ? "ok" : "warn"} />
            <MetricRow label="Secrets fetched" value={String(bw.secret_count ?? "not checked")} tone="ok" />
          </DeckCard>
          <DeckCard title="Actions" colClass="col-6">
            <DeckToolbar>
              <Link to="/env" className="deck-btn-sm">
                Open Keys page
              </Link>
            </DeckToolbar>
            <div className="mt-4 grid gap-2 font-mono text-xs text-[var(--dsd-text-secondary)]">
              <code>command-desk secrets bitwarden status</code>
              <code>command-desk secrets bitwarden sync</code>
            </div>
            {bw.error ? <div className="mt-3 text-xs text-[var(--dsd-sem-critical)]">{bw.error}</div> : null}
            {bw.warnings.map((warning) => (
              <div key={warning} className="mt-1 text-xs text-[var(--dsd-sem-warning)]">
                {warning}
              </div>
            ))}
          </DeckCard>
        </LayoutGrid>
      ) : null}
    </DevssdShell>
  );
}

export function GatewayStatusPage() {
  const { status, loading, error, refresh } = useDevssdStatus();
  const gateway = status?.gateway;

  return (
    <DevssdShell
      title="Gateway / API"
      description="Estado e controles do gateway local do Hermes Agent."
      onRefresh={refresh}
      loading={loading}
    >
      <LoadingOrError loading={loading} error={error} />
      {gateway ? (
        <LayoutGrid>
          <DeckCard title="Gateway" colClass="col-6">
            <MetricRow
              label="State"
              value={gateway.running ? "Running" : "Stopped"}
              tone={gateway.running ? "ok" : "warn"}
            />
            <MetricRow
              label="Health URL"
              value={gateway.health_url || "local PID/runtime"}
              tone="ok"
            />
          </DeckCard>
          <DeckCard title="Controls" colClass="col-6">
            <DeckToolbar>
              <ActionButton label="Start gateway" action={api.startGateway} />
              <ActionButton label="Restart gateway" action={api.restartGateway} />
              <ActionButton label="Stop gateway" action={api.stopGateway} />
            </DeckToolbar>
          </DeckCard>
        </LayoutGrid>
      ) : null}
    </DevssdShell>
  );
}

function useCommandDeckOverview() {
  const [overview, setOverview] = useState<CommandDeckOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setOverview(await api.getCommandDeckOverview());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { overview, loading, error, refresh };
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  return `$${n.toFixed(2)}`;
}

export function CommandDeckOpsPage() {
  const { overview, loading, error, refresh } = useCommandDeckOverview();

  return (
    <DevssdShell
      title="Command Deck"
      description="Operational overview — fleet, spend, missions, and tracer health."
      onRefresh={refresh}
      loading={loading}
    >
      {loading ? (
        <div className="deck-dashboard deck-animate gap-5">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : error ? (
        <ErrorState
          title="Failed to load overview"
          message={error}
          onRetry={refresh}
          compact
        />
      ) : !overview ? (
        <EmptyState
          icon={<Radio className="h-6 w-6" />}
          title="No data yet"
          description="The overview endpoint returned no data."
          compact
        />
      ) : (
        <div className="deck-dashboard deck-animate gap-5">
          <DeckCard title="Deck Status" colClass="col-12">
            <div className="flex flex-wrap gap-3">
              <MetricTile
                label="Deck"
                value={overview.deck.available ? "Online" : "Offline"}
                context={overview.deck.status}
                state={overview.deck.available ? "ok" : "critical"}
              />
              <MetricTile
                label="Queue"
                value={overview.fleet.queue}
                context="pending runs"
                state={overview.fleet.queue > 10 ? "warning" : "ok"}
              />
              <MetricTile
                label="Throughput"
                value={overview.fleet.throughput}
                context="runs/min"
              />
              <MetricTile
                label="Spend Today"
                value={fmtUsd(overview.fleet.cost_today_usd)}
                context="USD"
                state={overview.fleet.cost_today_usd > 10 ? "warning" : "ok"}
              />
              <MetricTile
                label="Missions"
                value={overview.missions.count}
                context="total"
              />
              <MetricTile
                label="Tracer"
                value={overview.tracer.healthy ? "Healthy" : "Degraded"}
                context={`${overview.tracer.dropped_spans} dropped spans`}
                state={overview.tracer.healthy ? "ok" : "degraded"}
              />
            </div>
          </DeckCard>

          {(overview.fleet.bottlenecks.length > 0 ||
            overview.fleet.recurring_errors.length > 0) && (
            <DeckCard title="Alerts" colClass="col-12">
              {overview.fleet.bottlenecks.length > 0 && (
                <div className="mb-3">
                  <div className="flex items-center gap-1.5 mb-1.5 text-xs font-medium text-[var(--dsd-text-secondary)] uppercase tracking-wide">
                    <Zap className="h-3 w-3" />
                    Bottlenecks
                  </div>
                  <ul className="flex flex-col gap-1">
                    {overview.fleet.bottlenecks.map((b, i) => (
                      <li key={i} className="text-xs font-mono text-[var(--dsd-status-warning)]">
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {overview.fleet.recurring_errors.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5 text-xs font-medium text-[var(--dsd-text-secondary)] uppercase tracking-wide">
                    <AlertTriangle className="h-3 w-3" />
                    Recurring Errors
                  </div>
                  <ul className="flex flex-col gap-1">
                    {overview.fleet.recurring_errors.map((e, i) => (
                      <li key={i} className="text-xs font-mono text-[var(--dsd-status-error)]">
                        {e}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </DeckCard>
          )}

          <DeckCard title="Navigate" colClass="col-12">
            <DeckToolbar>
              <Link to="/ops" className="deck-btn-sm">
                <Activity className="h-3.5 w-3.5" />
                Ops
              </Link>
              <Link to="/traces" className="deck-btn-sm">
                <Radio className="h-3.5 w-3.5" />
                Traces
              </Link>
              <Link to="/costs" className="deck-btn-sm">
                <DollarSign className="h-3.5 w-3.5" />
                Spend
              </Link>
              <Link to="/missions" className="deck-btn-sm">
                <Zap className="h-3.5 w-3.5" />
                Missions
              </Link>
            </DeckToolbar>
          </DeckCard>

          <FleetOpsPanel compact />
        </div>
      )}
    </DevssdShell>
  );
}

export function ChatRunLandingPage() {
  const { t } = useI18n();
  return (
    <DevssdShell
      title="Chat / Run"
      description="A página de chat nativa permanece persistente em /chat para não reiniciar o terminal do agente."
    >
      <DeckCard title="Terminal persistente">
        <div className="mb-4 flex items-center gap-2 text-sm text-[var(--dsd-text-secondary)]">
          <Terminal className="h-4 w-4" />
          {t.ops?.chatHint ?? "Abra o chat persistente para rodar o Hermes Agent."}
        </div>
        <Link to="/chat" className="deck-btn-sm primary">
          Open persistent chat
        </Link>
      </DeckCard>
    </DevssdShell>
  );
}
