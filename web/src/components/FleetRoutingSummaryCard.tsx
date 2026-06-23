import { Link } from "react-router-dom";
import { Activity, Route, Radio, Zap } from "lucide-react";
import { DeckCard, DeckToolbar, MetricRow, MetricTile } from "@/components/DeckOps";

type FleetRoutingSummaryCardProps = {
  fleet: {
    queue: number;
    throughput: number;
    costTodayUsd: number | null;
    bottlenecks: string[];
    recurringErrors: string[];
  };
  routing: {
    tracerHealthy: boolean;
    droppedSpans: number;
    missionsCount: number;
  };
};

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  return `$${n.toFixed(2)}`;
}

export function FleetRoutingSummaryCard({ fleet, routing }: FleetRoutingSummaryCardProps) {
  return (
    <DeckCard title="Fleet + Routing summary" subtitle="Read-only snapshot" colClass="col-12">
      <div className="mb-3 flex flex-wrap gap-3">
        <MetricTile
          label="Queue"
          value={fleet.queue}
          context="pending runs"
          state={fleet.queue > 10 ? "warning" : "ok"}
        />
        <MetricTile
          label="Throughput"
          value={fleet.throughput}
          context="runs/min"
          state={fleet.throughput > 0 ? "ok" : "degraded"}
        />
        <MetricTile
          label="Tracer"
          value={routing.tracerHealthy ? "Healthy" : "Degraded"}
          context={`${routing.droppedSpans} dropped spans`}
          state={routing.tracerHealthy ? "ok" : "degraded"}
        />
      </div>

      <MetricRow
        label="Spend today"
        value={fmtUsd(fleet.costTodayUsd)}
        tone={fleet.costTodayUsd != null && fleet.costTodayUsd > 10 ? "warn" : "ok"}
      />
      <MetricRow
        label="Bottlenecks"
        value={fleet.bottlenecks.length > 0 ? fleet.bottlenecks.join(" | ") : "None"}
        tone={fleet.bottlenecks.length > 0 ? "warn" : "ok"}
      />
      <MetricRow
        label="Recurring errors"
        value={fleet.recurringErrors.length > 0 ? fleet.recurringErrors.join(" | ") : "None"}
        tone={fleet.recurringErrors.length > 0 ? "bad" : "ok"}
      />
      <MetricRow label="Missions" value={String(routing.missionsCount)} tone="ok" />

      <DeckToolbar>
        <Link to="/ops?source=command-deck" className="deck-btn-sm">
          <Activity className="h-3.5 w-3.5" />
          Ops detail
        </Link>
        <Link to="/routing?source=command-deck" className="deck-btn-sm ghost">
          <Route className="h-3.5 w-3.5" />
          Routing detail
        </Link>
        <Link to="/traces" className="deck-btn-sm ghost">
          <Radio className="h-3.5 w-3.5" />
          Traces
        </Link>
        <Link to="/missions" className="deck-btn-sm ghost">
          <Zap className="h-3.5 w-3.5" />
          Missions
        </Link>
      </DeckToolbar>
    </DeckCard>
  );
}
