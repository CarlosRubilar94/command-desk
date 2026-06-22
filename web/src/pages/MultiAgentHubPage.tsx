import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Cpu, Layers, RefreshCw, Terminal, Zap } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { DeckPageShell } from "@/components/DeckPageShell";
import { FleetOpsPanel } from "@/components/FleetOpsPanel";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { MultiAgentHubResponse } from "@/lib/api";
import {
  DeckCard,
  DeckToolbar,
  LayoutGrid,
  MetricRow,
} from "@/components/DeckOps";
import { cn } from "@/lib/utils";

const LAYER_LABEL: Record<string, string> = {
  cursor: "Cursor (local)",
  hermes: "Hermes (runtime)",
};

export default function MultiAgentHubPage() {
  const [hub, setHub] = useState<MultiAgentHubResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHub(await api.getMultiAgentHub());
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

  if (loading && !hub) {
    return (
      <DeckPageShell>
        <div className="flex items-center gap-2 py-8">
          <Spinner />
          <span className="text-sm text-[var(--dsd-text-secondary)]">Loading multi-agent hub…</span>
        </div>
      </DeckPageShell>
    );
  }

  const routingOn = hub?.fleet.smart_model_routing.enabled ?? false;

  return (
    <DeckPageShell>
      <div className="deck-dashboard deck-animate">
        <p className="mb-4 max-w-3xl text-sm text-[var(--dsd-text-secondary)]">
          Duas camadas: <strong className="text-[var(--dsd-text-primary)]">Cursor</strong> para
          desenvolver este repo no IDE; <strong className="text-[var(--dsd-text-primary)]">Hermes</strong>{" "}
          para delegate_task, Kanban e Cron em runtime.
        </p>

        {error ? <p className="mb-4 text-sm text-[var(--dsd-sem-critical)]">{error}</p> : null}

        {hub ? (
          <LayoutGrid>
            <DeckCard title="Quick status" colClass="col-12">
              <div className="metrics-strip">
                <div className="deck-metric-tile">
                  <span className="deck-metric-label">Smart routing</span>
                  <span
                    className={cn(
                      "deck-metric-value",
                      routingOn ? "text-[var(--dsd-sem-ok)]" : "text-[var(--dsd-text-secondary)]",
                    )}
                  >
                    {routingOn ? "ON" : "OFF"}
                  </span>
                </div>
                <div className="deck-metric-tile">
                  <span className="deck-metric-label">Active agents</span>
                  <span className="deck-metric-value">{hub.fleet.active_agents}</span>
                </div>
                <div className="deck-metric-tile">
                  <span className="deck-metric-label">Delegations</span>
                  <span className="deck-metric-value">{hub.fleet.async_delegations_running}</span>
                </div>
                <div className="deck-metric-tile">
                  <span className="deck-metric-label">Cursor subagents</span>
                  <span className="deck-metric-value">{hub.cursor_agents.length}</span>
                </div>
              </div>
              <DeckToolbar>
                <Link to="/routing" className="deck-btn-sm primary">
                  <Zap className="h-3.5 w-3.5" />
                  Routing
                </Link>
                <Link to="/ops" className="deck-btn-sm ghost">
                  <Layers className="h-3.5 w-3.5" />
                  Fleet detail
                </Link>
                <Link to="/docs" className="deck-btn-sm ghost">
                  Docs
                </Link>
              </DeckToolbar>
            </DeckCard>

            <DeckCard title="Cursor subagents (local dev)" colClass="col-6">
              <p className="mb-3 text-xs text-[var(--dsd-text-secondary)]">
                Versionados em <code className="font-mono">.cursor/agents/</code>. Invocar com @ no
                Cursor ou Task tool.
              </p>
              <div className="flex flex-col gap-2">
                {hub.cursor_agents.map((agent) => (
                  <div key={agent.id} className="deck-list-row">
                    <div className="flex items-center gap-2">
                      <Terminal className="h-3.5 w-3.5 text-[var(--dsd-accent)]" />
                      <span className="font-mono text-sm text-[var(--dsd-text-primary)]">
                        @{agent.id}
                      </span>
                    </div>
                    {agent.description ? (
                      <p className="mt-1 text-xs text-[var(--dsd-text-secondary)]">
                        {agent.description}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
              <MetricRow
                label="Flow"
                value="analyst → planner → implementer → spec-reviewer → verifier"
                tone="ok"
              />
            </DeckCard>

            <DeckCard title="Hermes playbooks (runtime)" colClass="col-6">
              {hub.playbooks.map((pb) => (
                <div key={pb.id} className="deck-list-row">
                  <div className="flex flex-wrap items-center gap-2">
                    <Bot className="h-3.5 w-3.5 text-[var(--dsd-accent)]" />
                    <span className="text-sm font-medium text-[var(--dsd-text-primary)]">
                      {pb.title}
                    </span>
                    <span className="deck-status-pill">{LAYER_LABEL[pb.layer] ?? pb.layer}</span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--dsd-text-secondary)]">{pb.summary}</p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--dsd-text-tertiary)]">
                    {pb.invoke}
                  </p>
                </div>
              ))}
            </DeckCard>

            <FleetOpsPanel compact />
          </LayoutGrid>
        ) : null}

        <DeckCard title="Reference paths" colClass="col-12">
          <MetricRow label="Full guide" value="docs/CURSOR-LOCAL-MULTI-AGENT.md" tone="ok" />
          <MetricRow label="Skill" value="skills/devssd-ops/multi-agent-playbook/SKILL.md" tone="ok" />
          <MetricRow
            label="Profile template"
            value="integrations/command-deck/templates/multiagent-profiles.example.yaml"
            tone="ok"
          />
          <DeckToolbar>
            <span className="inline-flex items-center gap-1 text-xs text-[var(--dsd-text-secondary)]">
              <Cpu className="h-3 w-3" />
              CLI: command-desk routing · command-desk kanban init
            </span>
          </DeckToolbar>
        </DeckCard>
      </div>
    </DeckPageShell>
  );
}
