import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  Key,
  Lock,
  RefreshCw,
  Server,
  ShieldOff,
  WifiOff,
  Wrench,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type {
  SetupHealthResponse,
  SetupProviderEntry,
  SetupStatusChip,
} from "@/lib/api";
import { DeckBtn, DeckCard, DeckBtnLink } from "@/components/DeckOps";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Status chip helpers — mirror McpPage patterns
// ---------------------------------------------------------------------------

const STATUS_TONE: Record<
  SetupStatusChip | string,
  "success" | "warning" | "destructive" | "outline" | "secondary"
> = {
  READY: "success",
  WAITING_CREDENTIAL: "warning",
  WAITING_SERVICE: "warning",
  LOCKED: "warning",
  FAILED: "destructive",
  DISABLED: "outline",
};

const STATUS_LABEL: Record<SetupStatusChip | string, string> = {
  READY: "Ready",
  WAITING_CREDENTIAL: "Waiting credential",
  WAITING_SERVICE: "Waiting service",
  LOCKED: "Locked",
  FAILED: "Failed",
  DISABLED: "Disabled",
};

const STATUS_ICON: Record<SetupStatusChip | string, React.ReactNode> = {
  READY: <CheckCircle className="h-3 w-3" />,
  WAITING_CREDENTIAL: <Key className="h-3 w-3" />,
  WAITING_SERVICE: <Clock className="h-3 w-3" />,
  LOCKED: <Lock className="h-3 w-3" />,
  FAILED: <AlertTriangle className="h-3 w-3" />,
  DISABLED: <ShieldOff className="h-3 w-3" />,
};

function StatusChip({ status }: { status: SetupStatusChip | string }) {
  const tone = STATUS_TONE[status] ?? "secondary";
  const label = STATUS_LABEL[status] ?? status;
  const icon = STATUS_ICON[status] ?? null;
  return (
    <Badge variant={tone} className="flex items-center gap-1 font-mono text-[11px]">
      {icon}
      {label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Hint box
// ---------------------------------------------------------------------------

function HintBox({ hint }: { hint: string }) {
  return (
    <div className="mt-2 rounded border border-[var(--dsd-border-subtle)] bg-[var(--dsd-surface-sunken)] px-3 py-2 font-mono text-xs text-[var(--dsd-text-secondary)]">
      <span className="text-[var(--dsd-text-muted)] mr-1">Next step:</span>
      {hint}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section row — a single item with name + chip + optional hint
// ---------------------------------------------------------------------------

function SectionRow({
  label,
  status,
  meta,
  hint,
}: {
  label: string;
  status: SetupStatusChip | string;
  meta?: string;
  hint?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const needsHint =
    status !== "READY" && status !== "DISABLED" && hint;
  return (
    <div className="flex flex-col gap-1 py-2 border-b border-[var(--dsd-border-subtle)] last:border-0">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-sm font-medium text-[var(--dsd-text-primary)] truncate">
            {label}
          </span>
          {meta && (
            <span className="text-xs text-[var(--dsd-text-muted)] font-mono truncate">
              {meta}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusChip status={status} />
          {needsHint && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="text-[var(--dsd-text-muted)] hover:text-[var(--dsd-text-secondary)] transition-colors"
              aria-label={open ? "Hide hint" : "Show fix hint"}
            >
              {open ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>
      </div>
      {open && hint && <HintBox hint={hint} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary bar
// ---------------------------------------------------------------------------

function ReadinessSummary({ data }: { data: SetupHealthResponse }) {
  const { summary } = data;
  const pct = summary.readiness_pct;
  const tone =
    pct >= 80 ? "ok" : pct >= 50 ? "warn" : "bad";

  return (
    <div
      className={cn(
        "rounded-lg border px-5 py-4 flex flex-col gap-3",
        tone === "ok" && "border-[var(--dsd-sem-ok)] bg-[var(--dsd-sem-ok)]/5",
        tone === "warn" && "border-[var(--dsd-sem-warning)] bg-[var(--dsd-sem-warning)]/5",
        tone === "bad" && "border-[var(--dsd-sem-error)] bg-[var(--dsd-sem-error)]/5",
      )}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[var(--dsd-text-primary)]">
            Integration Readiness
          </p>
          <p className="text-xs text-[var(--dsd-text-secondary)] mt-0.5">
            {summary.ready}/{summary.total} components ready
          </p>
        </div>
        <span
          className={cn(
            "text-2xl font-bold tabular-nums",
            tone === "ok" && "text-[var(--dsd-sem-ok)]",
            tone === "warn" && "text-[var(--dsd-sem-warning)]",
            tone === "bad" && "text-[var(--dsd-sem-error)]",
          )}
        >
          {pct}%
        </span>
      </div>

      <div className="h-2 w-full rounded-full bg-[var(--dsd-border-subtle)] overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            tone === "ok" && "bg-[var(--dsd-sem-ok)]",
            tone === "warn" && "bg-[var(--dsd-sem-warning)]",
            tone === "bad" && "bg-[var(--dsd-sem-error)]",
          )}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Integration readiness: ${pct}%`}
        />
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-[var(--dsd-text-secondary)]">
        {summary.ready > 0 && (
          <span className="flex items-center gap-1">
            <CheckCircle className="h-3 w-3 text-[var(--dsd-sem-ok)]" aria-hidden />
            {summary.ready} ready
          </span>
        )}
        {summary.waiting_credential > 0 && (
          <span className="flex items-center gap-1">
            <Key className="h-3 w-3 text-[var(--dsd-sem-warning)]" aria-hidden />
            {summary.waiting_credential} waiting credential
          </span>
        )}
        {summary.waiting_service > 0 && (
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3 text-[var(--dsd-sem-warning)]" aria-hidden />
            {summary.waiting_service} waiting service
          </span>
        )}
        {summary.failed > 0 && (
          <span className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-[var(--dsd-sem-error)]" aria-hidden />
            {summary.failed} failed
          </span>
        )}
        {summary.disabled > 0 && (
          <span className="flex items-center gap-1">
            <ShieldOff className="h-3 w-3 text-[var(--dsd-text-muted)]" aria-hidden />
            {summary.disabled} disabled
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Secrets Provider
// ---------------------------------------------------------------------------

function SecretsSection({ data }: { data: SetupHealthResponse }) {
  const { secrets } = data;
  return (
    <DeckCard title="Secrets Provider" subtitle="Bitwarden CLI, bws token, .env fallback">
      <SectionRow
        label="Bitwarden CLI (bw)"
        status={
          !secrets.bw_cli_available && !secrets.bw_locked
            ? "DISABLED"
            : secrets.bw_locked
              ? "LOCKED"
              : "READY"
        }
        meta={
          secrets.bw_locked
            ? "Status: locked / unauthenticated"
            : "Status: unlocked"
        }
        hint={
          secrets.bw_locked
            ? "Run `bw login` then `bw unlock` in your terminal, then refresh."
            : null
        }
      />
      <SectionRow
        label={`Bitwarden Secrets (${secrets.bws_token_env})`}
        status={secrets.bws_token_present ? "READY" : "WAITING_CREDENTIAL"}
        meta={`env: ${secrets.bws_token_env}`}
        hint={
          secrets.bws_token_present
            ? null
            : `Set ${secrets.bws_token_env} in ~/.hermes/.env or your shell environment.`
        }
      />
      <SectionRow
        label=".env fallback (~/.hermes/.env)"
        status={secrets.env_fallback_exists ? "READY" : "DISABLED"}
        meta={secrets.env_fallback_exists ? "File found" : "File not found"}
        hint={
          secrets.env_fallback_exists
            ? null
            : "Create ~/.hermes/.env to store credentials as a fallback."
        }
      />
    </DeckCard>
  );
}

// ---------------------------------------------------------------------------
// Section: Model Providers
// ---------------------------------------------------------------------------

function ProvidersSection({ data }: { data: SetupHealthResponse }) {
  const { providers } = data;
  return (
    <DeckCard title="Model Providers" subtitle="API keys (name/boolean only — values never shown)">
      {providers.map((p: SetupProviderEntry) => (
        <SectionRow
          key={p.name}
          label={p.name}
          status={p.status}
          meta={
            p.key_env
              ? `env: ${p.key_env} ${p.key_present ? "✓ present" : "✗ missing"}`
              : p.fallback_active
                ? "Responses-API fallback active"
                : undefined
          }
          hint={p.hint}
        />
      ))}
    </DeckCard>
  );
}

// ---------------------------------------------------------------------------
// Section: MCP Servers
// ---------------------------------------------------------------------------

function McpSection({ data }: { data: SetupHealthResponse }) {
  const { mcp } = data;
  return (
    <DeckCard
      title="MCP Servers"
      subtitle="Aggregated from /mcp control-center"
      actions={
        <Link to="/mcp" className="flex items-center gap-1 text-xs text-[var(--dsd-accent-primary)] hover:underline">
          <ExternalLink className="h-3 w-3" />
          Open MCP page
        </Link>
      }
    >
      <div className="flex items-center justify-between py-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-[var(--dsd-text-primary)]">
            Overall status
          </span>
          <span className="text-xs text-[var(--dsd-text-muted)]">
            {mcp.total} servers configured · {mcp.ready} ready · {mcp.waiting} waiting · {mcp.disabled} disabled
            {mcp.failed > 0 && ` · ${mcp.failed} failed`}
          </span>
        </div>
        <StatusChip status={mcp.status} />
      </div>
      {mcp.hint && <HintBox hint={mcp.hint} />}
    </DeckCard>
  );
}

// ---------------------------------------------------------------------------
// Section: Skills
// ---------------------------------------------------------------------------

function SkillsSection({ data }: { data: SetupHealthResponse }) {
  const { skills } = data;
  return (
    <DeckCard
      title="Skills"
      subtitle="Wave 19 active / disabled counts"
      actions={
        <Link to="/skills" className="flex items-center gap-1 text-xs text-[var(--dsd-accent-primary)] hover:underline">
          <ExternalLink className="h-3 w-3" />
          Open Skills page
        </Link>
      }
    >
      <div className="flex items-center justify-between py-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-[var(--dsd-text-primary)]">
            Skill governance
          </span>
          <span className="text-xs text-[var(--dsd-text-muted)]">
            {skills.active} active · {skills.disabled} disabled · {skills.total} total
          </span>
        </div>
        <StatusChip status={skills.status} />
      </div>
      {skills.hint && <HintBox hint={skills.hint} />}
    </DeckCard>
  );
}

// ---------------------------------------------------------------------------
// Section: Gateway
// ---------------------------------------------------------------------------

function GatewaySection({ data }: { data: SetupHealthResponse }) {
  const { gateway } = data;
  return (
    <DeckCard
      title="Gateway"
      subtitle="Hermes gateway process health"
      actions={
        <Link to="/gateway" className="flex items-center gap-1 text-xs text-[var(--dsd-accent-primary)] hover:underline">
          <ExternalLink className="h-3 w-3" />
          Open Gateway page
        </Link>
      }
    >
      <div className="flex items-center justify-between py-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-[var(--dsd-text-primary)]">
            Process state
          </span>
          <span className="text-xs text-[var(--dsd-text-muted)]">
            {gateway.state ?? (gateway.running ? "running" : "stopped")}
          </span>
        </div>
        <StatusChip status={gateway.status} />
      </div>
      {!gateway.running && (
        <div className="flex flex-wrap gap-2 pt-1">
          <DeckBtn
            onClick={() => {
              void api.startGateway().catch(() => {});
            }}
            ghost
          >
            <Server className="h-3.5 w-3.5" />
            Restart Gateway
          </DeckBtn>
          <Link to="/doctor" className="deck-btn-sm ghost flex items-center gap-1.5">
            <Wrench className="h-3.5 w-3.5" />
            Doctor
          </Link>
        </div>
      )}
      {gateway.hint && <HintBox hint={gateway.hint} />}
    </DeckCard>
  );
}

// ---------------------------------------------------------------------------
// Section: Observability
// ---------------------------------------------------------------------------

function ObservabilitySection({ data }: { data: SetupHealthResponse }) {
  const { observability } = data;
  return (
    <DeckCard title="Observability" subtitle="OTEL exporter + Obsidian bridge">
      <SectionRow
        label={`OTEL Exporter (${observability.otel_env})`}
        status={observability.otel_enabled ? "READY" : "DISABLED"}
        meta={`env: ${observability.otel_env} = ${observability.otel_enabled ? "1 (enabled)" : "0 (off)"}`}
        hint={observability.hint}
      />
      <SectionRow
        label="Obsidian Bridge"
        status={observability.obsidian_bridge_status}
        meta="env: OBSIDIAN_VAULT_PATH"
        hint={
          observability.obsidian_bridge_status !== "READY"
            ? "Set OBSIDIAN_VAULT_PATH in ~/.hermes/.env to enable the Obsidian bridge."
            : null
        }
      />
    </DeckCard>
  );
}

// ---------------------------------------------------------------------------
// Degraded state (gateway OFF / fetch error) — mirrors PR#23 pattern
// ---------------------------------------------------------------------------

function DegradedState({
  error,
  onRetry,
}: {
  error: string;
  onRetry?: () => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  return (
    <DeckCard title="Integration Health">
      <div className="flex flex-col gap-3">
        <div className="flex items-start gap-2">
          <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-[var(--dsd-sem-warning)]" aria-hidden />
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-medium text-[var(--dsd-text-primary)]">
              Integration Health unavailable
            </span>
            <span className="text-xs text-[var(--dsd-text-secondary)]">
              Backend is running but{" "}
              <span className="font-mono">/api/setup/health</span> could not be
              reached. Gateway may be offline.
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
              void api.startGateway().catch(() => {}).then(() => onRetry?.());
            }}
            ghost
          >
            <Server className="h-3.5 w-3.5" />
            Restart Gateway
          </DeckBtn>
          <Link to="/doctor" className="deck-btn-sm ghost flex items-center gap-1.5">
            <Wrench className="h-3.5 w-3.5" />
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
              <span>/api/setup/health</span>
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

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const FETCH_TIMEOUT_MS = 6_000;

export function SetupPage() {
  const { setEnd } = usePageHeader();
  const [data, setData] = useState<SetupHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(
        () =>
          reject(
            new Error(`Setup health check timed out after ${FETCH_TIMEOUT_MS / 1000} s`),
          ),
        FETCH_TIMEOUT_MS,
      ),
    );
    try {
      setData(await Promise.race([api.getSetupHealth(), timeout]));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useLayoutEffect(() => {
    setEnd(
      <DeckBtn onClick={refresh} disabled={loading} ghost>
        {loading ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw className="h-3.5 w-3.5" />}
        Refresh
      </DeckBtn>,
    );
    return () => setEnd(null);
  }, [loading, refresh, setEnd]);

  return (
    <div className="deck-content-shell flex min-w-0 flex-col gap-5 pb-8">
      <div className="flex flex-col gap-1 px-0">
        <p className="text-[var(--dsd-text-h2)] font-semibold tracking-[-0.01em] text-[var(--dsd-text-primary)]">
          Integration Health
        </p>
        <p className="max-w-3xl text-sm text-[var(--dsd-text-secondary)]">
          Read-only status of every Hermes integration. Each item shows its current state
          and a safe next step. Secret values are never displayed.
        </p>
      </div>

      {loading && (
        <DeckCard title="Integration Health">
          <div className="flex items-center gap-2 text-sm text-[var(--dsd-text-secondary)]">
            <Spinner className="h-4 w-4" />
            Loading integration health...
          </div>
        </DeckCard>
      )}

      {!loading && error && <DegradedState error={error} onRetry={refresh} />}

      {!loading && data && (
        <>
          <ReadinessSummary data={data} />
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <SecretsSection data={data} />
            <ProvidersSection data={data} />
            <McpSection data={data} />
            <SkillsSection data={data} />
            <GatewaySection data={data} />
            <ObservabilitySection data={data} />
          </div>
        </>
      )}
    </div>
  );
}

export default SetupPage;
