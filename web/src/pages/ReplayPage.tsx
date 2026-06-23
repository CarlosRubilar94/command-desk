import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { TraceDetailResponse, SpanRow } from "@/lib/api";
import { DeckPageShell } from "@/components/DeckPageShell";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { SkeletonTable } from "@/components/ds/Skeleton";
import { PlaybackControls } from "./replay/PlaybackControls";
import { ReplayStepList } from "./replay/ReplayStepList";
import { StepInspector } from "./replay/StepInspector";
import { fmtMs, fmtTokens, fmtUsd } from "./replay/utils";

// ── Helpers ───────────────────────────────────────────────────────────────────

function speedToIntervalMs(speed: number): number {
  return Math.round(1000 / speed);
}

// ── Cross-link badge ─────────────────────────────────────────────────────────

function LinkChip({
  href,
  label,
  children,
}: {
  href: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={href}
      aria-label={label}
      className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono rounded-[var(--dsd-radius-sm)] bg-[var(--dsd-layer-raised)] border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-dim)] hover:text-[var(--dsd-text-base)] hover:border-[var(--dsd-border-default)] transition-colors duration-[var(--dsd-dur-fast)]"
    >
      {children}
    </Link>
  );
}

// ── Totals strip ─────────────────────────────────────────────────────────────

function TotalsStrip({ detail }: { detail: TraceDetailResponse }) {
  const { totals } = detail;
  return (
    <div className="flex flex-wrap gap-4 text-xs font-mono border-b border-[var(--dsd-border-subtle)] px-4 py-2 bg-[var(--dsd-layer-surface)]">
      <span>
        <span className="text-[var(--dsd-text-faint)]">spans </span>
        <span className="text-[var(--dsd-text-base)]">{totals.span_count}</span>
      </span>
      <span>
        <span className="text-[var(--dsd-text-faint)]">duration </span>
        <span className="text-[var(--dsd-text-base)]">{fmtMs(totals.duration_ms)}</span>
      </span>
      <span>
        <span className="text-[var(--dsd-text-faint)]">tokens </span>
        <span className="text-[var(--dsd-text-base)]">{fmtTokens(totals.total_tokens)}</span>
      </span>
      <span>
        <span className="text-[var(--dsd-text-faint)]">cost </span>
        <span className="text-[var(--dsd-cat-cost)]">{fmtUsd(totals.cost_usd)}</span>
      </span>
      {totals.error_count > 0 && (
        <span className="text-[var(--dsd-status-error)]">
          {totals.error_count} error{totals.error_count > 1 ? "s" : ""}
        </span>
      )}
    </div>
  );
}

// ── ReplayPage ────────────────────────────────────────────────────────────────

export default function ReplayPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const traceParam = searchParams.get("trace");
  const sessionParam = searchParams.get("session");

  const [traceId, setTraceId] = useState<string | null>(traceParam);
  const [detail, setDetail] = useState<TraceDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Playback state
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Derived spans (memoised)
  const spans = useMemo<SpanRow[]>(() => detail?.spans ?? [], [detail]);
  const totalSteps = spans.length;

  const traceStartSec = useMemo(
    () => (spans.length > 0 ? Math.min(...spans.map((s) => s.started_at)) : 0),
    [spans],
  );
  const totalMs = useMemo(
    () => (detail ? Math.max(detail.totals.duration_ms, 1) : 1),
    [detail],
  );

  // Session id: prefer query param, fall back to span session_id
  const sessionId = useMemo(() => {
    if (sessionParam) return sessionParam;
    return spans.find((s) => s.session_id)?.session_id ?? null;
  }, [sessionParam, spans]);

  // ── Data loading ───────────────────────────────────────────────────────────

  const loadTrace = useCallback(async (id: string) => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getTrace(id);
      setDetail(data);
      setCurrentStep(0);
      setIsPlaying(false);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const resolveAndLoad = useCallback(async () => {
    // Priority: trace param > resolve from session param
    if (traceParam) {
      setTraceId(traceParam);
      await loadTrace(traceParam);
      return;
    }
    if (sessionParam) {
      setLoading(true);
      setLoadError(null);
      try {
        const r = await api.getTracesBySession(sessionParam);
        if (r.traces.length === 0) {
          setLoadError("No trace found for this session.");
          setLoading(false);
          return;
        }
        const resolved = r.traces[0].trace_id;
        setTraceId(resolved);
        await loadTrace(resolved);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      }
      return;
    }
    setLoadError("No trace or session ID provided. Add ?trace=<id> or ?session=<id> to the URL.");
  }, [traceParam, sessionParam, loadTrace]);

  useEffect(() => {
    void resolveAndLoad();
  }, [resolveAndLoad]);

  // ── Playback engine ────────────────────────────────────────────────────────

  const stepForward = useCallback(() => {
    setCurrentStep((s) => {
      if (s >= totalSteps - 1) {
        setIsPlaying(false);
        return s;
      }
      return s + 1;
    });
  }, [totalSteps]);

  const stepBack = useCallback(() => {
    setCurrentStep((s) => Math.max(0, s - 1));
  }, []);

  const jumpTo = useCallback((index: number) => {
    setCurrentStep(Math.max(0, Math.min(index, totalSteps - 1)));
  }, [totalSteps]);

  // Auto-advance interval
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (!isPlaying || totalSteps === 0) return;

    intervalRef.current = setInterval(() => {
      setCurrentStep((s) => {
        if (s >= totalSteps - 1) {
          setIsPlaying(false);
          return s;
        }
        return s + 1;
      });
    }, speedToIntervalMs(speed));

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, speed, totalSteps]);

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't intercept when focus is on an input/textarea/select
      const tag = (e.target as Element)?.tagName ?? "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.code === "Space") {
        e.preventDefault();
        setIsPlaying((p) => !p);
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        stepForward();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        stepBack();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [stepForward, stepBack]);

  // ── Render ─────────────────────────────────────────────────────────────────

  const currentSpan = spans[currentStep] ?? null;
  const shortTraceId = traceId ? traceId.slice(0, 12) : null;

  return (
    <DeckPageShell>
      {/* Page header */}
      <div className="flex flex-wrap items-center gap-3 px-1 mb-3">
        <button
          type="button"
          aria-label="Go back"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1 text-[11px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-base)] transition-colors duration-[var(--dsd-dur-fast)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        <h1 className="text-[var(--dsd-text-h2)] font-semibold text-[var(--dsd-text-base)]">
          Replay
          {shortTraceId && (
            <span className="font-mono text-[var(--dsd-text-faint)] ml-2 text-[13px]">
              {shortTraceId}…
            </span>
          )}
        </h1>

        {/* Cross-links */}
        <div className="flex items-center gap-2 ml-auto flex-wrap">
          {sessionId && (
            <LinkChip href={`/sessions`} label="Go to Sessions">
              session: {sessionId.slice(0, 10)}…
            </LinkChip>
          )}
          {traceId && (
            <LinkChip href={`/traces`} label="Go to Traces list">
              traces list
            </LinkChip>
          )}

          <button
            type="button"
            aria-label="Reload trace"
            onClick={() => void resolveAndLoad()}
            className="inline-flex items-center gap-1 text-[11px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-base)] transition-colors"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
            Reload
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && !detail && (
        <SkeletonTable rows={8} cols={4} />
      )}

      {/* Error */}
      {loadError && !loading && (
        <ErrorState
          title="Failed to load trace"
          message={loadError}
          onRetry={() => void resolveAndLoad()}
          compact
        />
      )}

      {/* No params */}
      {!loading && !loadError && !traceId && (
        <EmptyState
          icon="🎬"
          title="No trace selected"
          description="Open Replay from the Traces or Sessions page to step through an agent run."
          compact
        />
      )}

      {/* Main replay UI */}
      {detail && !loading && (
        <div
          className="flex flex-col rounded-[var(--dsd-radius-md)] border border-[var(--dsd-border-subtle)] overflow-hidden bg-[var(--dsd-surface-1-solid)]"
          style={{ minHeight: 480 }}
        >
          {/* Trace totals */}
          <TotalsStrip detail={detail} />

          {/* Playback controls */}
          <PlaybackControls
            currentStep={currentStep}
            totalSteps={totalSteps}
            isPlaying={isPlaying}
            speed={speed}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onStepBack={stepBack}
            onStepForward={stepForward}
            onJumpTo={jumpTo}
            onSpeedChange={(s) => setSpeed(s)}
          />

          {/* Zero-span edge case */}
          {totalSteps === 0 ? (
            <EmptyState
              icon="🔭"
              title="No spans recorded"
              description="This trace has no spans yet. It may still be running or was not instrumented."
              compact
            />
          ) : (
            /* Split pane: step list | inspector */
            <div className="flex flex-col lg:flex-row flex-1 overflow-hidden" style={{ minHeight: 360 }}>
              {/* Left: step list */}
              <div
                className="lg:w-[420px] shrink-0 border-b lg:border-b-0 lg:border-r border-[var(--dsd-border-subtle)] overflow-y-auto"
                style={{ maxHeight: "70vh" }}
                aria-label="Step timeline"
              >
                <div className="sticky top-0 z-10 px-3 py-1.5 bg-[var(--dsd-layer-surface)] border-b border-[var(--dsd-border-subtle)]/50">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--dsd-text-faint)]">
                    Timeline — {totalSteps} step{totalSteps !== 1 ? "s" : ""}
                  </span>
                </div>
                <ReplayStepList
                  spans={spans}
                  currentStep={currentStep}
                  traceStartSec={traceStartSec}
                  totalMs={totalMs}
                  onJumpTo={jumpTo}
                />
              </div>

              {/* Right: inspector */}
              <div
                className="flex-1 min-w-0 overflow-y-auto"
                style={{ maxHeight: "70vh" }}
                aria-label="Step inspector"
              >
                <div className="sticky top-0 z-10 px-3 py-1.5 bg-[var(--dsd-layer-surface)] border-b border-[var(--dsd-border-subtle)]/50">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--dsd-text-faint)]">
                    Inspector
                  </span>
                </div>
                <StepInspector
                  span={currentSpan}
                  stepIndex={currentStep}
                  totalSteps={totalSteps}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </DeckPageShell>
  );
}
