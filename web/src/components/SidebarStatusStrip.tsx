import { Link } from "react-router-dom";
import type { StatusResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";

/** Gateway + session + multi-agent summary for the sidebar. */
export function SidebarStatusStrip({ status }: SidebarStatusStripProps) {
  const { t } = useI18n();

  if (status === null) {
    return (
      <div className="deck-sidebar-status deck-sidebar-status--loading" aria-hidden>
        <div className="h-8 w-full animate-pulse rounded-md bg-[var(--dsd-surface-3-solid)]" />
      </div>
    );
  }

  const gw = gatewayLine(status, t);
  const { activeSessionsLabel, gatewayStatusLabel } = t.app;
  const busyAgents = status.active_agents ?? 0;

  return (
    <Link
      to="/ops"
      title={t.app.statusOverview}
      className={cn("deck-sidebar-status deck-sidebar-status-link")}
    >
      <div className="status-line">
        <span className={cn("deck-status-dot", gw.tone.includes("success") ? "ok" : gw.tone.includes("warning") ? "warning" : "critical")} aria-hidden />
        <span className="truncate">
          <span className="text-[var(--dsd-text-muted)]">{gatewayStatusLabel}</span>{" "}
          <span className={cn("font-semibold", gw.tone)}>{gw.label}</span>
        </span>
      </div>
      <div className="status-sub">
        <span>{activeSessionsLabel}</span>{" "}
        <span className="tabular-nums font-medium text-[var(--dsd-text-primary)]">
          {status.active_sessions}
        </span>
        {busyAgents > 0 ? (
          <>
            {" · "}
            <span className="text-[var(--dsd-text-muted)]">agents</span>{" "}
            <span className="tabular-nums font-semibold text-[var(--dsd-sem-warning)]">
              {busyAgents}
            </span>
          </>
        ) : null}
      </div>
    </Link>
  );
}

interface SidebarStatusStripProps {
  status: StatusResponse | null;
}

export function gatewayLine(
  status: StatusResponse,
  t: ReturnType<typeof useI18n>["t"],
): { label: string; tone: string } {
  const g = t.app.gatewayStrip;
  const byState: Record<string, { label: string; tone: string }> = {
    running: { label: g.running, tone: "text-success" },
    starting: { label: g.starting, tone: "text-warning" },
    startup_failed: { label: g.failed, tone: "text-destructive" },
    stopped: { label: g.stopped, tone: "text-muted-foreground" },
  };
  if (status.gateway_state && byState[status.gateway_state]) {
    return byState[status.gateway_state];
  }
  return status.gateway_running
    ? { label: g.running, tone: "text-success" }
    : { label: g.off, tone: "text-muted-foreground" };
}
