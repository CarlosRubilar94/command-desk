import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
  title?: string;
  message?: string;
  /** Error object — message extracted automatically if `message` not set */
  error?: Error | unknown;
  onRetry?: () => void;
  retryLabel?: string;
  icon?: ReactNode;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  error,
  onRetry,
  retryLabel = "Retry",
  icon,
  className,
  compact = false,
}: ErrorStateProps) {
  const errMsg =
    message ??
    (error instanceof Error ? error.message : error ? String(error) : undefined);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2 py-8 px-4" : "gap-3 py-16 px-6",
        className,
      )}
    >
      <div
        aria-hidden
        className={cn(
          "flex items-center justify-center rounded-full",
          "bg-[var(--dsd-status-error-bg)] text-[var(--dsd-status-error)]",
          compact ? "w-10 h-10 text-xl" : "w-14 h-14 text-2xl",
        )}
      >
        {icon ?? "⚠"}
      </div>

      <p
        className={cn(
          "font-[var(--dsd-fw-semibold)] text-[var(--dsd-status-error)]",
          compact ? "text-[var(--dsd-text-sm)]" : "text-[var(--dsd-text-xl)]",
        )}
      >
        {title}
      </p>

      {errMsg && (
        <p className="max-w-xs text-[var(--dsd-text-sm)] text-[var(--dsd-text-faint)] leading-[var(--dsd-lh-normal)] font-mono">
          {errMsg}
        </p>
      )}

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className={cn(
            "mt-1 rounded-[var(--dsd-radius-sm)] px-4 py-1.5",
            "text-[var(--dsd-text-sm)] font-[var(--dsd-fw-medium)]",
            "bg-[var(--dsd-status-error-bg)] text-[var(--dsd-status-error)]",
            "border border-[var(--dsd-status-error)]/30",
            "hover:bg-[var(--dsd-status-error)]/20",
            "transition-colors duration-[var(--dsd-dur-fast)]",
            "focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)]",
          )}
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}
