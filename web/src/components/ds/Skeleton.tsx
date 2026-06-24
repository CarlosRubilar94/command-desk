import { cn } from "@/lib/utils";

const PULSE =
  "animate-pulse bg-gradient-to-r from-[var(--dsd-layer-raised)] via-[var(--dsd-layer-overlay)] to-[var(--dsd-layer-raised)] bg-[length:200%_100%]";

/* ── Shared pulse animation (uses Tailwind animate-pulse or CSS) ── */

function SkeletonBase({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <span
      aria-hidden
      role="presentation"
      className={cn("block rounded-[var(--dsd-radius-xs)]", PULSE, className)}
      style={style}
    />
  );
}

/* ── Line skeleton ─────────────────────────────────────────────── */

export interface SkeletonLineProps {
  /** Width as CSS value. Defaults to 100% */
  width?: string | number;
  /** Height as CSS value. Defaults to 14px */
  height?: string | number;
  className?: string;
}

export function SkeletonLine({ width = "100%", height = 14, className }: SkeletonLineProps) {
  return (
    <SkeletonBase
      className={className}
      style={{ width, height }}
    />
  );
}

/* ── Block skeleton ────────────────────────────────────────────── */

export interface SkeletonBlockProps {
  width?: string | number;
  height?: string | number;
  className?: string;
}

export function SkeletonBlock({ width = "100%", height = 80, className }: SkeletonBlockProps) {
  return (
    <SkeletonBase
      className={cn("rounded-[var(--dsd-radius-md)]", className)}
      style={{ width, height }}
    />
  );
}

/* ── Table skeleton ────────────────────────────────────────────── */

export interface SkeletonTableProps {
  rows?: number;
  cols?: number;
  className?: string;
}

export function SkeletonTable({ rows = 5, cols = 4, className }: SkeletonTableProps) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading table…"
      className={cn("space-y-1", className)}
    >
      {/* header row */}
      <div className="flex gap-2 px-3 py-2 border-b border-[var(--dsd-border-subtle)]">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={i} height={10} width={`${60 + (i % 3) * 20}px`} className="opacity-50" />
        ))}
      </div>
      {/* data rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-2 px-3 py-2 border-b border-[var(--dsd-border-subtle)] last:border-0">
          {Array.from({ length: cols }).map((_, c) => (
            <SkeletonLine
              key={c}
              height={12}
              width={`${50 + ((r + c) % 4) * 15}%`}
              className="opacity-70"
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/* ── Card skeleton ─────────────────────────────────────────────── */

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading…"
      className={cn(
        "rounded-[var(--dsd-radius-md)] border border-[var(--dsd-border-subtle)] p-4 space-y-3",
        className,
      )}
    >
      <SkeletonLine height={16} width="55%" />
      <SkeletonLine height={12} width="80%" />
      <SkeletonLine height={12} width="65%" />
      <SkeletonBlock height={60} />
    </div>
  );
}
