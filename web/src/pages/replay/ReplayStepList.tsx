import { useEffect, useMemo, useRef, useState } from "react";
import type { SpanRow } from "@/lib/api";
import { StatusPill } from "@/components/ds/StatusPill";
import { cn } from "@/lib/utils";
import { fmtMs, kindVariant, kindCatToken, spanStatusVariant, buildDepthMap } from "./utils";

export interface ReplayStepListProps {
  spans: SpanRow[];
  currentStep: number;
  traceStartSec: number;
  totalMs: number;
  onJumpTo: (index: number) => void;
}

export function ReplayStepList({
  spans,
  currentStep,
  traceStartSec,
  totalMs,
  onJumpTo,
}: ReplayStepListProps) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const activeRef = useRef<HTMLButtonElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const depthMap = buildDepthMap(spans);
  const ROW_ESTIMATE = 88;
  const OVERSCAN_ROWS = 8;

  useEffect(() => {
    const node = listRef.current;
    if (!node) return;
    const measure = () => setViewportHeight(node.clientHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [currentStep]);

  const { start, end, topPad, bottomPad } = useMemo(() => {
    const total = spans.length;
    const visibleCount = Math.max(1, Math.ceil(viewportHeight / ROW_ESTIMATE));
    let nextStart = Math.max(0, Math.floor(scrollTop / ROW_ESTIMATE) - OVERSCAN_ROWS);
    let nextEnd = Math.min(total, nextStart + visibleCount + OVERSCAN_ROWS * 2);

    if (currentStep < nextStart) {
      nextStart = Math.max(0, currentStep - OVERSCAN_ROWS);
      nextEnd = Math.min(total, nextStart + visibleCount + OVERSCAN_ROWS * 2);
    } else if (currentStep >= nextEnd) {
      nextEnd = Math.min(total, currentStep + OVERSCAN_ROWS + 1);
      nextStart = Math.max(0, nextEnd - visibleCount - OVERSCAN_ROWS * 2);
    }

    return {
      start: nextStart,
      end: nextEnd,
      topPad: nextStart * ROW_ESTIMATE,
      bottomPad: Math.max(0, (total - nextEnd) * ROW_ESTIMATE),
    };
  }, [currentStep, scrollTop, spans.length, viewportHeight]);

  const visible = spans.slice(start, end);

  if (spans.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-[var(--dsd-text-faint)]">
        No spans in this trace.
      </div>
    );
  }

  return (
    <div
      role="list"
      aria-label="Trace steps"
      className="flex flex-col overflow-y-auto"
      style={{ maxHeight: "100%" }}
      ref={listRef}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
    >
      {topPad > 0 ? <div aria-hidden style={{ height: topPad }} /> : null}
      {visible.map((span, idx) => {
        const i = start + idx;
        const isActive = i === currentStep;
        const isFuture = i > currentStep;
        const depth = depthMap.get(span.span_id) ?? 0;
        const spanOffsetMs = (span.started_at - traceStartSec) * 1000;
        const spanDurationMs = span.duration_ms ?? 0;
        const safeTotal = totalMs > 0 ? totalMs : 1;
        const leftPct = Math.max(0, Math.min(99, (spanOffsetMs / safeTotal) * 100));
        const widthPct = Math.max(0.5, Math.min(100 - leftPct, (spanDurationMs / safeTotal) * 100));
        const catToken = kindCatToken(span.kind);

        return (
          <button
            key={span.span_id}
            type="button"
            role="listitem"
            ref={isActive ? activeRef : null}
            aria-current={isActive ? "step" : undefined}
            aria-label={`Step ${i + 1}: ${span.name} (${span.kind})`}
            onClick={() => onJumpTo(i)}
            className={cn(
              "w-full text-left flex flex-col gap-1 py-2 px-3 border-b border-[var(--dsd-border-subtle)]/40 transition-colors duration-[var(--dsd-dur-fast)] focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)] focus-visible:outline-offset-[-2px]",
              isActive
                ? "bg-[var(--dsd-accent-primary-bg)] border-l-2 border-l-[var(--dsd-accent-primary)]"
                : isFuture
                  ? "bg-transparent opacity-50 hover:opacity-70 hover:bg-[var(--dsd-layer-overlay)]/20"
                  : "bg-transparent hover:bg-[var(--dsd-layer-overlay)]/30",
            )}
            style={{ minHeight: ROW_ESTIMATE, paddingLeft: `${depth * 12 + 12}px` }}
          >
            {/* Top row: step number + kind + name + status */}
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="shrink-0 text-[10px] font-mono text-[var(--dsd-text-faint)] w-6 text-right"
                aria-hidden
              >
                {i + 1}
              </span>
              <StatusPill variant={kindVariant(span.kind)} label={span.kind} size="sm" />
              <span
                className="text-[11px] font-mono truncate text-[var(--dsd-text-base)] flex-1 min-w-0"
                title={span.name}
              >
                {span.name}
              </span>
              <StatusPill
                variant={spanStatusVariant(span.status)}
                label={span.status}
                dot
                size="sm"
              />
            </div>

            {/* Sub-row: model/agent + duration */}
            {(span.model ?? span.agent) && (
              <div className="pl-8 text-[10px] font-mono text-[var(--dsd-text-faint)] truncate">
                {span.model ?? span.agent}
              </div>
            )}

            {/* Error message */}
            {span.error && (
              <div
                className="pl-8 text-[10px] font-mono text-[var(--dsd-status-error)] truncate"
                title={span.error}
              >
                {span.error}
              </div>
            )}

            {/* Duration bar */}
            <div className="pl-8 pr-2 flex items-center gap-2">
              <div
                className="flex-1 relative rounded-sm overflow-hidden"
                style={{ height: 5 }}
                aria-hidden
              >
                <div className="absolute inset-0 bg-[var(--dsd-layer-raised)]" />
                <div
                  className="absolute top-0 bottom-0 rounded-sm"
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    background: `var(--dsd-cat-${catToken})`,
                    opacity: span.status === "error" ? 0.9 : 0.6,
                  }}
                />
              </div>
              <span className="shrink-0 text-[10px] font-mono text-[var(--dsd-text-faint)]">
                {fmtMs(spanDurationMs)}
              </span>
            </div>
          </button>
        );
      })}
      {bottomPad > 0 ? <div aria-hidden style={{ height: bottomPad }} /> : null}
    </div>
  );
}
