import { cn } from "@/lib/utils";

export type StatusVariant =
  | "success"
  | "warning"
  | "error"
  | "info"
  | "neutral"
  | "degraded"
  | "agent"
  | "mission"
  | "tool"
  | "model"
  | "cost"
  | "fleet"
  | "trace";

const VARIANT_STYLES: Record<StatusVariant, string> = {
  success:  "bg-[var(--dsd-status-success-bg)]  text-[var(--dsd-status-success)]  border-[var(--dsd-status-success)]/30",
  warning:  "bg-[var(--dsd-status-warning-bg)]  text-[var(--dsd-status-warning)]  border-[var(--dsd-status-warning)]/30",
  error:    "bg-[var(--dsd-status-error-bg)]    text-[var(--dsd-status-error)]    border-[var(--dsd-status-error)]/30",
  info:     "bg-[var(--dsd-status-info-bg)]     text-[var(--dsd-status-info)]     border-[var(--dsd-status-info)]/30",
  neutral:  "bg-[var(--dsd-status-neutral-bg)]  text-[var(--dsd-status-neutral)]  border-[var(--dsd-status-neutral)]/30",
  degraded: "bg-[var(--dsd-status-degraded-bg)] text-[var(--dsd-status-degraded)] border-[var(--dsd-status-degraded)]/30",
  agent:    "bg-[var(--dsd-accent-primary-bg)]  text-[var(--dsd-cat-agent)]       border-[var(--dsd-cat-agent)]/30",
  mission:  "bg-[rgba(167,139,250,0.10)]         text-[var(--dsd-cat-mission)]     border-[var(--dsd-cat-mission)]/30",
  tool:     "bg-[rgba(52,211,153,0.10)]          text-[var(--dsd-cat-tool)]        border-[var(--dsd-cat-tool)]/30",
  model:    "bg-[rgba(249,168,212,0.10)]         text-[var(--dsd-cat-model)]       border-[var(--dsd-cat-model)]/30",
  cost:     "bg-[rgba(251,191,36,0.10)]          text-[var(--dsd-cat-cost)]        border-[var(--dsd-cat-cost)]/30",
  fleet:    "bg-[rgba(251,146,60,0.10)]          text-[var(--dsd-cat-fleet)]       border-[var(--dsd-cat-fleet)]/30",
  trace:    "bg-[rgba(147,197,253,0.10)]         text-[var(--dsd-cat-trace)]       border-[var(--dsd-cat-trace)]/30",
};

const DOT_VARIANTS = new Set<StatusVariant>(["success", "warning", "error", "info", "neutral", "degraded"]);

export interface StatusPillProps {
  variant?: StatusVariant;
  label: string;
  /** Show a filled dot indicator to the left */
  dot?: boolean;
  className?: string;
  size?: "sm" | "md";
}

export function StatusPill({
  variant = "neutral",
  label,
  dot,
  className,
  size = "sm",
}: StatusPillProps) {
  const showDot = dot ?? DOT_VARIANTS.has(variant);

  return (
    <span
      role="status"
      aria-label={`Status: ${label}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium tracking-wide uppercase",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
        VARIANT_STYLES[variant],
        className,
      )}
    >
      {showDot && (
        <span
          aria-hidden
          className="inline-block shrink-0 rounded-full"
          style={{
            width: size === "sm" ? 5 : 6,
            height: size === "sm" ? 5 : 6,
            background: "currentColor",
            boxShadow: "0 0 4px currentColor",
          }}
        />
      )}
      {label}
    </span>
  );
}
