import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { StatusVariant } from "./StatusPill";

/* Dot colors derived from status variant */
const STATUS_DOT: Partial<Record<StatusVariant, string>> = {
  success:  "bg-[var(--dsd-status-success)]  shadow-[0_0_6px_var(--dsd-status-success)]",
  warning:  "bg-[var(--dsd-status-warning)]  shadow-[0_0_6px_var(--dsd-status-warning)]",
  error:    "bg-[var(--dsd-status-error)]    shadow-[0_0_6px_var(--dsd-status-error)]",
  info:     "bg-[var(--dsd-status-info)]     shadow-[0_0_6px_var(--dsd-status-info)]",
  neutral:  "bg-[var(--dsd-status-neutral)]",
  degraded: "bg-[var(--dsd-status-degraded)] shadow-[0_0_6px_var(--dsd-status-degraded)]",
};

export interface TimelineEvent {
  id: string | number;
  timestamp?: string;
  title: ReactNode;
  description?: ReactNode;
  status?: StatusVariant;
  icon?: ReactNode;
  meta?: string;
}

export interface TimelineProps {
  events: TimelineEvent[];
  className?: string;
  compact?: boolean;
}

export function Timeline({ events, className, compact = false }: TimelineProps) {
  return (
    <ol
      aria-label="Event timeline"
      className={cn("relative", className)}
    >
      {events.map((ev, idx) => {
        const isLast = idx === events.length - 1;
        const dotClass = (ev.status && STATUS_DOT[ev.status]) ?? STATUS_DOT.neutral ?? "bg-[var(--dsd-text-faint)]";

        return (
          <li
            key={ev.id}
            className={cn(
              "relative flex gap-3",
              compact ? "pb-3" : "pb-5",
            )}
          >
            {/* Vertical connector */}
            {!isLast && (
              <div
                aria-hidden
                className="absolute left-[7px] top-4 bottom-0 w-px bg-[var(--dsd-border-subtle)]"
              />
            )}

            {/* Dot / Icon */}
            <div className="shrink-0 flex items-start pt-0.5">
              {ev.icon ? (
                <div className="w-4 h-4 flex items-center justify-center text-[10px] text-[var(--dsd-text-faint)]">
                  {ev.icon}
                </div>
              ) : (
                <div
                  aria-hidden
                  className={cn(
                    "w-3.5 h-3.5 rounded-full ring-2 ring-[var(--dsd-layer-raised)]",
                    dotClass,
                  )}
                />
              )}
            </div>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className={cn(
                  "font-[var(--dsd-fw-medium)] text-[var(--dsd-text-base)]",
                  compact ? "text-[var(--dsd-text-sm)]" : "text-[var(--dsd-text-md)]",
                )}>
                  {ev.title}
                </span>
                {ev.timestamp && (
                  <time className="text-[var(--dsd-text-xs)] text-[var(--dsd-text-faint)] shrink-0 tabular-nums">
                    {ev.timestamp}
                  </time>
                )}
              </div>
              {ev.description && (
                <div className="mt-0.5 text-[var(--dsd-text-sm)] text-[var(--dsd-text-dim)] leading-[var(--dsd-lh-normal)]">
                  {ev.description}
                </div>
              )}
              {ev.meta && (
                <div className="mt-0.5 text-[var(--dsd-text-xs)] text-[var(--dsd-text-faint)] font-mono">
                  {ev.meta}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
