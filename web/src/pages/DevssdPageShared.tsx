import { useCallback, useEffect, useLayoutEffect, useState, type ReactNode } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Play, RefreshCw, Stethoscope, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { ActionResponse, DevssdStatusResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DeckBtn, DeckCard } from "@/components/DeckOps";
import { useI18n } from "@/i18n";

const STATUS_FETCH_TIMEOUT_MS = 6_000;

export function useDevssdStatus() {
  const [status, setStatus] = useState<DevssdStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    // Guard against: (a) backend hang with no response, (b) fetchJSON returning a
    // never-resolving promise when 401 triggers a page-redirect (gated mode) or a
    // stale-token reload — both paths return `new Promise(() => {})`. Racing against
    // a timed rejection guarantees the finally block always runs.
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(
        () => reject(new Error(`Status check timed out after ${STATUS_FETCH_TIMEOUT_MS / 1000} s`)),
        STATUS_FETCH_TIMEOUT_MS,
      ),
    );
    try {
      setStatus(await Promise.race([api.getDevssdStatus(), timeoutPromise]));
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

export function DevssdShell({
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

export function LoadingOrError({
  loading,
  error,
  onRetry,
}: {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);

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
        <div className="flex flex-col gap-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--dsd-sem-warning)]" aria-hidden />
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-medium text-[var(--dsd-text-primary)]">
                Command Desk status unavailable
              </span>
              <span className="text-xs text-[var(--dsd-text-secondary)]">
                Backend is running, but the gateway or status probe failed.{" "}
                <span className="text-[var(--dsd-text-muted)]">
                  Probable cause: gateway is offline, restarting, or the /api/devssd/status probe
                  timed out. Use the actions below to diagnose or recover.
                </span>
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {onRetry && (
              <DeckBtn onClick={onRetry} ghost>
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </DeckBtn>
            )}
            <DeckBtn
              onClick={() => {
                void api.restartGateway().catch(() => {}).then(() => onRetry?.());
              }}
              ghost
            >
              <Wrench className="h-3.5 w-3.5" />
              Restart Gateway
            </DeckBtn>
            <Link to="/gateway" className="deck-btn-sm ghost">
              <Wrench className="h-3.5 w-3.5" />
              Gateway page
            </Link>
            <Link to="/doctor" className="deck-btn-sm ghost">
              <Stethoscope className="h-3.5 w-3.5" />
              Doctor
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setDetailsOpen((v) => !v)}
            className="flex items-center gap-1 self-start text-xs text-[var(--dsd-text-muted)] hover:text-[var(--dsd-text-secondary)] transition-colors"
          >
            {detailsOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            {detailsOpen ? "Hide details" : "Show details"}
          </button>

          {detailsOpen && (
            <div className="rounded border border-[var(--dsd-border-subtle)] bg-[var(--dsd-surface-sunken)] p-3 font-mono text-xs text-[var(--dsd-text-secondary)]">
              <div className="flex gap-2">
                <span className="text-[var(--dsd-text-muted)]">endpoint:</span>
                <span>/api/devssd/status</span>
              </div>
              <div className="flex gap-2">
                <span className="text-[var(--dsd-text-muted)]">error:</span>
                <span className="break-all">{error}</span>
              </div>
              <div className="mt-1 text-[var(--dsd-text-muted)]">
                Next step: run &quot;hermes gateway start&quot; in a terminal, then click Retry.
              </div>
            </div>
          )}
        </div>
      </DeckCard>
    );
  }
  return null;
}

export function ActionButton({
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

export function CommandList({ commands }: { commands: Record<string, string> }) {
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

export function OpsPill({
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
