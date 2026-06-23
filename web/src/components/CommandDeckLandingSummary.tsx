import { Link } from "react-router-dom";
import { Compass, Route } from "lucide-react";
import { DeckCard, DeckToolbar, MetricRow, MetricTile } from "@/components/DeckOps";

type CommandDeckLandingSummaryProps = {
  deck: {
    available: boolean;
    status: string;
  };
};

function parseLatency(status: string): string {
  const m = status.match(/(\d+(?:\.\d+)?)\s*ms/i);
  return m ? `${m[1]} ms` : "—";
}

export function CommandDeckLandingSummary({ deck }: CommandDeckLandingSummaryProps) {
  return (
    <DeckCard
      title="Command Deck landing"
      subtitle="Availability and quick actions"
      colClass="col-12"
    >
      <div className="mb-3 flex flex-wrap gap-3">
        <MetricTile
          label="Deck"
          value={deck.available ? "Online" : "Offline"}
          context={deck.status || "No status message"}
          state={deck.available ? "ok" : "critical"}
        />
        <MetricTile
          label="Latency"
          value={parseLatency(deck.status)}
          context="parsed from status"
          state={deck.available ? "ok" : "degraded"}
        />
      </div>

      <MetricRow label="Deck status" value={deck.status || "Unavailable"} tone={deck.available ? "ok" : "bad"} />

      <DeckToolbar>
        <Link to="/ops?source=command-deck" className="deck-btn-sm">
          <Compass className="h-3.5 w-3.5" />
          Open Ops
        </Link>
        <Link to="/routing?source=command-deck" className="deck-btn-sm ghost">
          <Route className="h-3.5 w-3.5" />
          Open Routing
        </Link>
      </DeckToolbar>
    </DeckCard>
  );
}
