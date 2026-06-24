import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface KVEntry {
  key: string;
  value: ReactNode;
  /** Optional copy-to-clipboard string */
  copyText?: string;
  mono?: boolean;
}

export interface KeyValueGridProps {
  entries: KVEntry[];
  cols?: 1 | 2 | 3;
  compact?: boolean;
  className?: string;
}

export function KeyValueGrid({ entries, cols = 2, compact = false, className }: KeyValueGridProps) {
  const colClass =
    cols === 1 ? "grid-cols-1" : cols === 3 ? "grid-cols-3" : "grid-cols-2";

  return (
    <dl
      className={cn(
        "grid gap-x-4",
        compact ? "gap-y-2" : "gap-y-3",
        colClass,
        className,
      )}
    >
      {entries.map((e) => (
        <div key={e.key} className="min-w-0">
          <dt className="text-[var(--dsd-text-xs)] font-[var(--dsd-fw-medium)] uppercase tracking-wider text-[var(--dsd-text-faint)] mb-0.5">
            {e.key}
          </dt>
          <dd
            className={cn(
              "text-[var(--dsd-text-sm)] text-[var(--dsd-text-base)] truncate",
              e.mono && "font-mono text-[var(--dsd-text-xs)]",
            )}
            title={typeof e.value === "string" ? e.value : undefined}
          >
            {e.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
