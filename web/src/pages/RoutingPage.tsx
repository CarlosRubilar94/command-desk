import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Power, RefreshCw } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { DeckPageShell } from "@/components/DeckPageShell";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { RoutingStatusResponse } from "@/lib/api";
import { DeckCard, DeckToolbar, LayoutGrid, MetricRow } from "@/components/DeckOps";
import { cn } from "@/lib/utils";

const DELEGATION_TIERS = ["economy", "inherit", "performance"] as const;

export default function RoutingPage() {
  const [routing, setRouting] = useState<RoutingStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRouting(await api.getRoutingStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const applyUpdate = useCallback(
    async (patch: { enabled?: boolean; delegation_tier?: (typeof DELEGATION_TIERS)[number] }) => {
      setSaving(true);
      setError(null);
      try {
        await api.updateRoutingStatus(patch);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

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

  if (loading && !routing) {
    return (
      <DeckPageShell>
        <div className="flex items-center gap-2 py-8">
          <Spinner />
          <span className="text-sm text-[var(--dsd-text-secondary)]">Loading routing…</span>
        </div>
      </DeckPageShell>
    );
  }

  return (
    <DeckPageShell>
      <div className="deck-dashboard deck-animate">
        {error ? <p className="mb-4 text-sm text-[var(--dsd-sem-critical)]">{error}</p> : null}
      {routing ? (
        <LayoutGrid>
          <DeckCard title="Status" colClass="col-6">
            <MetricRow
              label="Enabled"
              value={routing.enabled ? "yes" : "no"}
              tone={routing.enabled ? "ok" : "warn"}
            />
            <MetricRow label="Delegation tier" value={routing.delegation_tier} tone="ok" />
            <MetricRow
              label="Economy model"
              value={routing.economy_model ?? "auto (provider default)"}
              tone="ok"
            />
            {routing.lines.map((line) => (
              <p key={line} className="text-xs text-[var(--dsd-text-secondary)]">
                {line}
              </p>
            ))}
            <DeckToolbar>
              <button
                type="button"
                className="deck-btn-sm primary"
                disabled={saving || routing.enabled}
                onClick={() => void applyUpdate({ enabled: true })}
              >
                <Power className="h-3.5 w-3.5" />
                Enable routing
              </button>
              <button
                type="button"
                className="deck-btn-sm ghost"
                disabled={saving || !routing.enabled}
                onClick={() => void applyUpdate({ enabled: false })}
              >
                Disable routing
              </button>
            </DeckToolbar>
          </DeckCard>

          <DeckCard title="Delegation tier" subtitle="When delegation.model is unset" colClass="col-6">
            <div className="flex flex-wrap gap-2">
              {DELEGATION_TIERS.map((tier) => (
                <button
                  key={tier}
                  type="button"
                  className={cn(
                    "deck-btn-sm",
                    routing.delegation_tier === tier ? "primary" : "ghost",
                  )}
                  disabled={saving}
                  onClick={() => void applyUpdate({ delegation_tier: tier })}
                >
                  {tier}
                </button>
              ))}
            </div>
          </DeckCard>

          <DeckCard title="Economy tasks" subtitle="Cheap model for side work" colClass="col-6">
            <p className="text-xs leading-relaxed text-[var(--dsd-text-secondary)]">
              {routing.economy_tasks.join(", ")}
            </p>
          </DeckCard>

          <DeckCard title="Performance tasks" subtitle="Keep main chat model" colClass="col-6">
            <p className="text-xs leading-relaxed text-[var(--dsd-text-secondary)]">
              {routing.performance_tasks.join(", ")}
            </p>
            <DeckToolbar>
              <Link to="/config" className="deck-btn-sm ghost">
                Edit config.yaml
              </Link>
              <Link to="/models" className="deck-btn-sm ghost">
                Auxiliary models
              </Link>
              <Link to="/ops" className="deck-btn-sm ghost">
                Fleet overview
              </Link>
            </DeckToolbar>
          </DeckCard>
        </LayoutGrid>
      ) : null}
      </div>
    </DeckPageShell>
  );
}
