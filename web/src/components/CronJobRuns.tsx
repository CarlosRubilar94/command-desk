import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type { SessionInfo } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

function formatRunTime(epoch?: number): string {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleString();
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
    <div className="mt-2 border-t border-border pt-2">
      <Button
        ghost
        size="sm"
        className="h-7 px-2 text-xs text-muted-foreground"
        onClick={() => setOpen((v) => !v)}
        prefix={open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      >
        <History className="h-3 w-3" />
        Run history
      </Button>

      {open ? (
        <div className="mt-2 space-y-1">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Spinner />
              Loading runs…
            </div>
          ) : null}
          {error ? <p className="text-xs text-destructive">{error}</p> : null}
          {runs && runs.length === 0 ? (
            <p className="text-xs text-muted-foreground">No runs yet.</p>
          ) : null}
          {runs?.map((run) => (
            <div
              key={run.id}
              className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
            >
              <Link
                to={`/sessions?focus=${encodeURIComponent(run.id)}`}
                className="font-mono-ui text-primary hover:underline"
                title={run.id}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                {run.id.slice(-12)}
              </Link>
              <span>{formatRunTime(run.started_at)}</span>
              <span>{timeAgo(run.last_active)}</span>
              <span>{run.message_count} msgs</span>
              {run.is_active ? (
                <span className="text-warning">active</span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
