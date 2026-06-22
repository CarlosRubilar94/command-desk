import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { RoutingStatusResponse } from "@/lib/api";
import { DeckCard, DeckToolbar, LayoutGrid, MetricRow } from "@/components/DeckOps";

export default function RoutingPage() {
  const [routing, setRouting] = useState<RoutingStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
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

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const { setEnd } = usePageHeader();
  useLayoutEffect(() => {
    setEnd(
      <button type="button" className="deck-btn-sm ghost" onClick={() => void refresh()}>
        <RefreshCw className="h-3.5 w-3.5" />
        Refresh
      </button>,
    );
    return () => setEnd(null);
  }, [refresh, setEnd]);

  if (loading && !routing) {
    return (
      <div className="flex items-center gap-2 py-8">
        <Spinner />
        <span className="text-sm text-muted-foreground">Loading routing…</span>
      </div>
    );
  }

  return (
    <div className="deck-dashboard">
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
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
              <p key={line} className="text-xs text-text-secondary">
                {line}
              </p>
            ))}
          </DeckCard>

          <DeckCard title="Economy tasks" subtitle="Cheap model for side work" colClass="col-6">
            <p className="text-xs leading-relaxed text-text-secondary">
              {routing.economy_tasks.join(", ")}
            </p>
          </DeckCard>

          <DeckCard title="Performance tasks" subtitle="Keep main chat model" colClass="col-12">
            <p className="text-xs leading-relaxed text-text-secondary">
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
  );
}
