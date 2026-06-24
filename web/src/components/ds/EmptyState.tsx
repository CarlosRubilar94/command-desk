import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      role="status"
      aria-label={title}
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2 py-8 px-4" : "gap-3 py-16 px-6",
        className,
      )}
    >
      {icon && (
        <div
          aria-hidden
          className={cn(
            "flex items-center justify-center rounded-full",
            "bg-[var(--dsd-layer-raised)] text-[var(--dsd-text-faint)]",
            compact ? "w-10 h-10 text-xl" : "w-14 h-14 text-2xl",
          )}
        >
          {icon}
        </div>
      )}
      <p
        className={cn(
          "font-[var(--dsd-fw-semibold)] text-[var(--dsd-text-base)]",
          compact ? "text-[var(--dsd-text-sm)]" : "text-[var(--dsd-text-xl)]",
        )}
      >
        {title}
      </p>
      {description && (
        <p className="max-w-xs text-[var(--dsd-text-sm)] text-[var(--dsd-text-faint)] leading-[var(--dsd-lh-normal)]">
          {description}
        </p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
