import { useCallback, useEffect, useLayoutEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  Bot,
  ExternalLink,
  KeyRound,
  Play,
  RefreshCw,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { ActionResponse, DevssdStatusResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  computeOverallHealth,
  DeckBtn,
  DeckBtnLink,
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricRow,
  OperationalStatus,
  MetricTile,
  OpsSummaryGrid,
  ServiceCell,
} from "@/components/DeckOps";
import { FleetOpsPanel } from "@/components/FleetOpsPanel";
import { useI18n } from "@/i18n";

function useDevssdStatus() {
  const [status, setStatus] = useState<DevssdStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await api.getDevssdStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { status, loading, error, refresh };
}

function DevssdShell({
  title,
  description,
  children,
  onRefresh,
  loading,
  hideTitle,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onRefresh?: () => void;
  loading?: boolean;
  hideTitle?: boolean;
}) {
  const { setEnd } = usePageHeader();
  const { t } = useI18n();

  useLayoutEffect(() => {
    setEnd(
      onRefresh ? (
        <DeckBtn onClick={onRefresh} disabled={loading} ghost>
          {loading ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw className="h-3.5 w-3.5" />}
          {t.common.refresh}
        </DeckBtn>
      ) : null,
    );
    return () => setEnd(null);
  }, [loading, onRefresh, setEnd, t.common.refresh]);

  return (
    <div className="deck-content-shell flex min-w-0 flex-col gap-5 pb-8">
      {!hideTitle ? (
        <div className="flex flex-col gap-1 px-0">
          <p className="text-[var(--dsd-text-h2)] font-semibold tracking-[-0.01em] text-[var(--dsd-text-primary)]">
            {title}
          </p>
          <p className="max-w-3xl text-sm text-[var(--dsd-text-secondary)]">{description}</p>
        </div>
      ) : null}
      {children}
    </div>
  );
}

function LoadingOrError({
  loading,
  error,
}: {
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <DeckCard title="Command Desk">
        <div className="flex items-center gap-2 text-sm text-[var(--dsd-text-secondary)]">
          <Spinner className="h-4 w-4" />
          Loading Command Desk status...
        </div>
      </DeckCard>
    );
  }
  if (error) {
    return (
      <DeckCard title="Command Desk">
        <div className="text-sm text-[var(--dsd-sem-critical)]">{error}</div>
      </DeckCard>
    );
  }
  return null;
}

function ActionButton({
  label,
  action,
}: {
  label: string;
  action: () => Promise<ActionResponse>;
}) {
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const run = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const result = await action();
      setMessage(result.ok ? `Started: ${result.name}` : result.error || "Action failed");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <DeckBtn onClick={run} disabled={running}>
        {running ? <Spinner className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
        {label}
      </DeckBtn>
      {message ? <span className="text-xs text-[var(--dsd-text-muted)]">{message}</span> : null}
    </div>
  );
}

function CommandList({ commands }: { commands: Record<string, string> }) {
  return (
    <div className="deck-smoke-list">
      {Object.entries(commands).map(([name, command]) => (
        <div key={name} className="deck-smoke-row">
          <span className="deck-smoke-label">{name}</span>
          <pre className="deck-muted-pre">{command}</pre>
        </div>
      ))}
    </div>
  );
}

function OpsPill({
  label,
  tone,
}: {
  label: string;
  tone: "ok" | "warn" | "bad";
}) {
  return (
    <span className={cn("deck-health-badge", tone)}>
      <span
        className={cn(
          "deck-status-dot",
          tone === "ok" ? "ok" : tone === "warn" ? "warning" : "critical",
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}

export function AgentHomePage() {
  const { t } = useI18n();
  const { status, loading, error, refresh } = useDevssdStatus();
  const bwOk = Boolean(status?.bitwarden.enabled && status.bitwarden.token_present && status.bitwarden.project_configured);
  const gatewayOk = Boolean(status?.gateway.running);
  const deckOk = Boolean(status?.command_deck.available);

  const overall = computeOverallHealth({
    critical: !gatewayOk && !deckOk,
    warning: !bwOk || !gatewayOk || !deckOk,
  });

  const opsTitle =
    gatewayOk && deckOk && bwOk
      ? t.ops?.statusOk ?? "Operacional"
      : t.ops?.statusWarn ?? "Atenção necessária";

  return (
    <DevssdShell
      title="Command Desk"
      description="Portal principal do Hermes Agent pessoal DevSSD."
      onRefresh={refresh}
      loading={loading}
      hideTitle
    >
      <LoadingOrError loading={loading} error={error} />
      {status ? (
        <div className="deck-dashboard">
          <div className="ops-first-fold">
            <div className="ops-hero">
              <OperationalStatus
                overall={overall}
                title={opsTitle}
                subtitle={t.ops?.homeSubtitle ?? "Dashboard local :9119 — integrado com Command Deck :8765."}
                label={t.ops?.operationalLabel ?? "Estado operacional"}
                chips={[
                  { label: "Gateway", value: gatewayOk ? "online" : "offline" },
                  { label: "Deck", value: deckOk ? "online" : "offline" },
                  { label: "Bitwarden", value: bwOk ? "ok" : "warn" },
                ]}
              />
              <div className="ops-hero-badges">
                <OpsPill
                  label={gatewayOk ? "Gateway online" : "Gateway offline"}
                  tone={gatewayOk ? "ok" : "warn"}
                />
                <OpsPill
                  label={deckOk ? "Deck online" : "Deck offline"}
                  tone={deckOk ? "ok" : "warn"}
                />
                {status.command_deck.app_url ? (
                  <a
                    href={status.command_deck.app_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="deck-btn-sm primary"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Command Deck
                  </a>
                ) : null}
              </div>
            </div>
          </div>

          <div className="metrics-strip col-12">
            <MetricTile
              label="Model"
              value={(status.agent.model || "—").split("/").pop() ?? "—"}
              context={status.agent.provider || undefined}
              state="ok"
            />
            <MetricTile
              label="Gateway"
              value={gatewayOk ? "online" : "offline"}
              state={gatewayOk ? "ok" : "warning"}
            />
            <MetricTile
              label="Command Deck"
              value={deckOk ? `${status.command_deck.latency_ms} ms` : "offline"}
              state={deckOk ? "ok" : "warning"}
            />
            <MetricTile
              label="Secrets"
              value={bwOk ? "configured" : "pending"}
              state={bwOk ? "ok" : "warning"}
            />
          </div>

          <div className="service-matrix col-12">
            <ServiceCell
              name="Hermes Agent"
              icon={<Bot className="h-4 w-4 text-[var(--dsd-sem-info)]" />}
              state={status.agent.model || "—"}
              stateTone="ok"
              meta={`${status.agent.provider || "provider"} / ${status.agent.model || "model"}`}
              hint={status.agent.home}
            />
            <ServiceCell
              name="Bitwarden SM"
              icon={<KeyRound className="h-4 w-4 text-[var(--dsd-sem-info)]" />}
              state={bwOk ? "Enabled and configured" : "Needs setup"}
              stateTone={bwOk ? "ok" : "warn"}
              warn={!bwOk}
            />
            <ServiceCell
              name="Command Deck Ops"
              icon={<Activity className="h-4 w-4 text-[var(--dsd-sem-info)]" />}
              state={deckOk ? `Online (${status.command_deck.latency_ms} ms)` : "Offline"}
              stateTone={deckOk ? "ok" : "warn"}
              warn={!deckOk}
              meta={deckOk ? status.command_deck.url : (status.command_deck.error ?? undefined)}
            />
          </div>

          <LayoutGrid>
            <DeckCard title="Run" colClass="col-4">
              <DeckToolbar>
                <Link to="/chat" className="deck-btn-sm primary">
                  <Terminal className="h-3.5 w-3.5" />
                  Chat / Run
                </Link>
                <Link to="/ops" className="deck-btn-sm ghost">
                  Fleet
                </Link>
                <Link to="/skills" className="deck-btn-sm ghost">
                  Skills DevSSD
                </Link>
                <Link to="/doctor" className="deck-btn-sm ghost">
                  Doctor
                </Link>
              </DeckToolbar>
            </DeckCard>

            <FleetOpsPanel compact />

            <DeckCard title="Smoke commands" colClass="col-8">
              <CommandList commands={status.agent.commands} />
            </DeckCard>

            <DeckCard
              title="Integração Command Deck"
              subtitle="Espelha renderCommandDesk() do Deck :8765"
              colClass="col-6"
            >
              <MetricRow label="Dashboard :9119" value="Online" tone="ok" />
              <MetricRow
                label="Gateway"
                value={gatewayOk ? "running" : "stopped"}
                tone={gatewayOk ? "ok" : "warn"}
              />
              <MetricRow
                label="Command Deck :8765"
                value={deckOk ? `Online (${status.command_deck.latency_ms} ms)` : "Offline"}
                tone={deckOk ? "ok" : "warn"}
              />
              <MetricRow
                label="Provider / Model"
                value={`${status.agent.provider} / ${status.agent.model}`}
                tone="ok"
              />
              <DeckToolbar>
                {status.command_deck.app_url ? (
                  <DeckBtnLink href={status.command_deck.app_url} target="_blank" rel="noopener noreferrer" primary>
                    <ExternalLink className="h-3.5 w-3.5" />
                    Command Deck
                  </DeckBtnLink>
                ) : null}
                <Link to="/command-deck" className="deck-btn-sm ghost">
                  Ops embed
                </Link>
              </DeckToolbar>
            </DeckCard>

            <DeckCard title="Resumo DevSSD" subtitle="Paths e runtime" colClass="col-6">
              <OpsSummaryGrid
                items={[
                  {
                    label: "Agent home",
                    value: status.agent.home.split("\\").pop() ?? status.agent.home,
                    hint: status.agent.home,
                  },
                  {
                    label: "DevSSD skill",
                    value: status.agent.devssd_skill_installed ? "Installed" : "Missing",
                    tone: status.agent.devssd_skill_installed ? "ok" : "warn",
                  },
                  {
                    label: "Config",
                    value: "YAML",
                    hint: status.agent.config_path,
                  },
                  {
                    label: "Secrets",
                    value: bwOk ? "Configured" : "Pending",
                    tone: bwOk ? "ok" : "warn",
                  },
                ]}
              />
            </DeckCard>
          </LayoutGrid>
        </div>
      ) : null}
    </DevssdShell>
  );
}

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
            {!bwOk ? (
              <div className="mt-3 flex items-center gap-2 text-sm text-[var(--dsd-sem-warning)]">
                <ShieldCheck className="h-4 w-4" />
                Needs attention
              </div>
            ) : null}
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

export function CommandDeckOpsPage() {
  const { status, loading, error, refresh } = useDevssdStatus();
  const deck = status?.command_deck;

  return (
    <DevssdShell
      title="Command Deck Ops"
      description="Command Deck continua separado em :8765, mas fica visível dentro do Command Desk."
      onRefresh={refresh}
      loading={loading}
    >
      <LoadingOrError loading={loading} error={error} />
      {deck ? (
        <div className="deck-dashboard gap-5">
          <FleetOpsPanel compact />

          <DeckCard title="Command Deck" colClass="col-12">
            <MetricRow
              label="Status"
              value={deck.available ? `Online (${deck.latency_ms} ms)` : "Offline"}
              tone={deck.available ? "ok" : "warn"}
            />
            <MetricRow label="URL" value={deck.url} tone="ok" />
            <DeckToolbar>
              <DeckBtnLink href={deck.app_url} target="_blank" rel="noopener noreferrer" primary>
                <ExternalLink className="h-3.5 w-3.5" />
                Open Deck :8765
              </DeckBtnLink>
            </DeckToolbar>
            {deck.error ? <div className="mt-3 text-xs text-[var(--dsd-sem-critical)]">{deck.error}</div> : null}
          </DeckCard>
          {deck.available ? (
            <iframe
              title="Command Deck"
              src={deck.app_url}
              className="col-12 min-h-[560px] w-full rounded-[var(--dsd-radius-lg)] border border-[var(--dsd-border-glow)] bg-[var(--dsd-surface-1-solid)] shadow-[var(--dsd-shadow-glow)]"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />
          ) : null}
        </div>
      ) : null}
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
