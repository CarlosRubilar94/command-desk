import { useState, type ReactNode, type ChangeEvent } from "react";
import { cn } from "@/lib/utils";

/* ── Toolbar ──────────────────────────────────────────────────────── */

export interface ToolbarProps {
  left?: ReactNode;
  right?: ReactNode;
  children?: ReactNode;
  className?: string;
  dense?: boolean;
}

export function Toolbar({ left, right, children, className, dense = false }: ToolbarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Toolbar"
      className={cn(
        "flex items-center gap-2 flex-wrap",
        dense ? "px-3 py-1.5" : "px-4 py-2.5",
        "bg-[var(--dsd-layer-raised)] border-b border-[var(--dsd-border-subtle)]",
        className,
      )}
    >
      {left && <div className="flex items-center gap-2 shrink-0">{left}</div>}
      {children && <div className="flex items-center gap-2 flex-wrap flex-1">{children}</div>}
      {right && <div className="flex items-center gap-2 shrink-0 ml-auto">{right}</div>}
    </div>
  );
}

/* ── FilterBar ────────────────────────────────────────────────────── */

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export interface FilterBarProps {
  /** Current active filter value */
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  /** Optional search input */
  search?: {
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
  };
  right?: ReactNode;
  className?: string;
}

export function FilterBar({ value, onChange, options, search, right, className }: FilterBarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Filters"
      className={cn(
        "flex items-center gap-2 flex-wrap px-3 py-2",
        "bg-[var(--dsd-layer-surface)] border-b border-[var(--dsd-border-subtle)]",
        className,
      )}
    >
      {search && (
        <label className="sr-only" htmlFor="ds-filterbar-search">
          Search
        </label>
      )}
      {search && (
        <input
          id="ds-filterbar-search"
          type="search"
          role="searchbox"
          value={search.value}
          onChange={(e: ChangeEvent<HTMLInputElement>) => search.onChange(e.target.value)}
          placeholder={search.placeholder ?? "Search…"}
          className={cn(
            "rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)]",
            "bg-[var(--dsd-layer-raised)] text-[var(--dsd-text-base)]",
            "px-2.5 py-1 text-[var(--dsd-text-sm)] placeholder:text-[var(--dsd-text-faint)]",
            "focus:outline-none focus:border-[var(--dsd-border-focus)]",
            "transition-colors duration-[var(--dsd-dur-fast)]",
            "w-[180px]",
          )}
        />
      )}

      <div role="group" aria-label="Filter options" className="flex items-center gap-1 flex-wrap">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            aria-pressed={value === opt.value}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded-[var(--dsd-radius-sm)] px-2.5 py-0.5 text-[var(--dsd-text-xs)] font-[var(--dsd-fw-medium)]",
              "border transition-colors duration-[var(--dsd-dur-fast)]",
              "focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)]",
              value === opt.value
                ? "bg-[var(--dsd-accent-primary-bg)] border-[var(--dsd-accent-primary)]/40 text-[var(--dsd-accent-primary)]"
                : "bg-transparent border-[var(--dsd-border-subtle)] text-[var(--dsd-text-dim)] hover:border-[var(--dsd-border-emphasis)] hover:text-[var(--dsd-text-base)]",
            )}
          >
            {opt.label}
            {opt.count !== undefined && (
              <span className="ml-1 opacity-60 tabular-nums">{opt.count}</span>
            )}
          </button>
        ))}
      </div>

      {right && <div className="ml-auto flex items-center gap-2">{right}</div>}
    </div>
  );
}

/* ── useFilterBar convenience hook ────────────────────────────────── */

export function useFilterBar(defaultValue = "all") {
  const [filter, setFilter] = useState(defaultValue);
  const [search, setSearch] = useState("");
  return { filter, setFilter, search, setSearch };
}
