import { Link } from "react-router-dom";
import { Activity, Bot, ExternalLink, KeyRound, Terminal } from "lucide-react";
import {
  computeOverallHealth,
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricTile,
  OperationalStatus,
  ServiceCell,
} from "@/components/DeckOps";
import { MissionOverview } from "@/components/MissionOverview";
import { useI18n } from "@/i18n";
import {
  DevssdShell,
  LoadingOrError,
  OpsPill,
  useDevssdStatus,
} from "@/pages/DevssdPageShared";

export function AgentHomePage() {
  const { t } = useI18n();
  const { status, loading, error, refresh } = useDevssdStatus();
  const bwOk = Boolean(
    status?.bitwarden.enabled &&
      status.bitwarden.token_present &&
      status.bitwarden.project_configured,
  );
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
      <LoadingOrError loading={loading} error={error} onRetry={refresh} />
      {status ? (
        <div className="deck-dashboard deck-animate">
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
                <Link to="/command-deck" className="deck-btn-sm ghost">
                  Command Deck overview
                </Link>
                <Link to="/doctor" className="deck-btn-sm ghost">
                  CLI / Smoke + DevSSD info
                </Link>
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

          <MissionOverview />

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
          </LayoutGrid>
        </div>
      ) : null}
    </DevssdShell>
  );
}
