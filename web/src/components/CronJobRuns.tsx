import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { SessionTranscript } from "@/components/SessionTranscript";
import { api } from "@/lib/api";
import type { SessionInfo } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

function formatRunTime(epoch?: number): string {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleString();
}

function CronRunRow({
  run,
  profile,
}: {
  run: SessionInfo;
  profile: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={cn("deck-list-row", expanded && "deck-list-row--open")}>
      <button
        type="button"
        className="flex w-full flex-wrap items-center gap-2 text-left text-xs text-[var(--dsd-text-secondary)]"
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-[var(--dsd-sem-info)]" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" />
        )}
        <span className="font-mono text-[var(--dsd-sem-info)]" title={run.id} onClick={(e) => e.stopPropagation()}>
          {run.id.slice(-12)}
        </span>
        <span>{formatRunTime(run.started_at)}</span>
        <span>{timeAgo(run.last_active)}</span>
        <span>{run.message_count} msgs</span>
        {run.is_active ? (
          <span className="deck-status-pill running">active</span>
        ) : null}
        <Link
          to={`/sessions?focus=${encodeURIComponent(run.id)}`}
          className="ml-auto text-[var(--dsd-sem-info)] hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          open session
        </Link>
      </button>
      {expanded ? (
        <SessionTranscript sessionId={run.id} profile={profile} maxHeight="320px" />
      ) : null}
    </div>
  );
}

export function CronJobRuns({
  jobId,
  profile,
}: {
  jobId: string;
  profile: string;
}) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<SessionInfo[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || runs !== null) return;
    setLoading(true);
    setError(null);
    void api
      .getCronJobRuns(jobId, profile, 8)
      .then((resp) => setRuns(resp.runs))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [open, jobId, profile, runs]);

  return (
    <div className="mt-3 border-t border-[var(--dsd-border-subtle)] pt-3">
      <Button
        ghost
        size="sm"
        className="h-7 px-2 text-xs text-[var(--dsd-text-secondary)]"
        onClick={() => setOpen((v) => !v)}
        prefix={open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      >
        <History className="h-3 w-3" />
        Run history
      </Button>

      {open ? (
        <div className="mt-2 space-y-2">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-[var(--dsd-text-secondary)]">
              <Spinner />
              Loading runs…
            </div>
          ) : null}
          {error ? <p className="text-xs text-[var(--dsd-sem-critical)]">{error}</p> : null}
          {runs && runs.length === 0 ? (
            <p className="text-xs text-[var(--dsd-text-muted)]">No runs yet.</p>
          ) : null}
          {runs?.map((run) => (
            <CronRunRow key={run.id} run={run} profile={profile} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
