import { useCallback, useEffect, useLayoutEffect, useState, type ReactNode } from "react";
import { Play, RefreshCw } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { ActionResponse, DevssdStatusResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DeckBtn, DeckCard } from "@/components/DeckOps";
import { useI18n } from "@/i18n";

export function useDevssdStatus() {
  const [status, setStatus] = useState<DevssdStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await api.getDevssdStatus());
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
}: {
  loading: boolean;
  error: string | null;
}) {
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
        <div className="text-sm text-[var(--dsd-sem-critical)]">{error}</div>
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
