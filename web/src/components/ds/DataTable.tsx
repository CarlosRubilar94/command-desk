import { useState, useMemo, useRef, type ChangeEvent, type ReactNode, type CSSProperties } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Types ────────────────────────────────────────────────────────── */

export type SortDir = "asc" | "desc" | null;

export interface ColDef<T> {
  key: string;
  header: ReactNode;
  /** Render cell. Receives the row datum. */
  cell: (row: T) => ReactNode;
  /** If provided, column is sortable using this comparator key */
  sortKey?: keyof T;
  width?: CSSProperties["width"];
  align?: "left" | "right" | "center";
}

export interface DataTableProps<T> {
  cols: ColDef<T>[];
  rows: T[];
  /** Unique row identifier (for keying) */
  rowKey: (row: T) => string | number;
  /** Max visible rows before scrolling (virtualization-ready; no dep) */
  maxRows?: number;
  dense?: boolean;
  stickyHeader?: boolean;
  onRowClick?: (row: T) => void;
  selectedKey?: string | number;
  emptyLabel?: string;
  className?: string;
  "aria-label"?: string;
  /**
   * When true, renders a search input above the table that filters rows
   * by matching any string value in any column's cell output.
   * The filter is applied client-side via `filterField` or falls back to
   * JSON-stringifying each row.
   */
  quickFilter?: boolean;
  /** Placeholder text for the quick-filter input. */
  filterPlaceholder?: string;
  /**
   * Optional function that returns a searchable string for a row.
   * If omitted, `JSON.stringify(row).toLowerCase()` is used.
   */
  filterFn?: (row: T, query: string) => boolean;
}

/* ── Component ────────────────────────────────────────────────────── */

export function DataTable<T>({
  cols,
  rows,
  rowKey,
  maxRows,
  dense = false,
  stickyHeader = true,
  onRowClick,
  selectedKey,
  emptyLabel = "No data",
  className,
  "aria-label": ariaLabel,
  quickFilter = false,
  filterPlaceholder = "Filter…",
  filterFn,
}: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [filterQuery, setFilterQuery] = useState("");
  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  const filtered = useMemo(() => {
    if (!quickFilter || !filterQuery.trim()) return rows;
    const q = filterQuery.toLowerCase();
    if (filterFn) return rows.filter((r) => filterFn(r, q));
    return rows.filter((r) => {
      try {
        return JSON.stringify(r).toLowerCase().includes(q);
      } catch {
        return true;
      }
    });
  }, [rows, quickFilter, filterQuery, filterFn]);

  const sorted = useMemo(() => {
    if (!sortCol || !sortDir) return filtered;
    const col = cols.find((c) => c.key === sortCol);
    if (!col?.sortKey) return filtered;
    const sk = col.sortKey;
    return [...filtered].sort((a, b) => {
      const av = a[sk];
      const bv = b[sk];
      const cmp =
        typeof av === "string" && typeof bv === "string"
          ? av.localeCompare(bv)
          : Number(av) - Number(bv);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortCol, sortDir, cols]);

  function handleSort(col: ColDef<T>) {
    if (!col.sortKey) return;
    if (sortCol !== col.key) {
      setSortCol(col.key);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol(null);
      setSortDir(null);
    }
  }

  const rowH = dense ? 28 : 36;
  const containerStyle: CSSProperties = maxRows
    ? { maxHeight: maxRows * rowH + 32, overflowY: "auto" }
    : {};

  return (
    <div className={cn("ds-data-table-wrapper flex flex-col gap-2", className)}>
      {quickFilter && (
        <div className="relative flex items-center">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--dsd-text-faint)]"
          />
          <input
            type="search"
            value={filterQuery}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setFilterQuery(e.target.value)}
            placeholder={filterPlaceholder}
            aria-label={filterPlaceholder}
            className={cn(
              "w-full rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)]",
              "bg-[var(--dsd-layer-surface)] pl-8 pr-3 text-[var(--dsd-text-sm)] text-[var(--dsd-text-base)]",
              "placeholder:text-[var(--dsd-text-faint)] outline-none",
              "focus-visible:border-[var(--dsd-accent-primary)] focus-visible:ring-1 focus-visible:ring-[var(--dsd-border-focus)]",
              dense ? "py-1" : "py-1.5",
            )}
          />
        </div>
      )}
    <div
      className="ds-data-table relative overflow-auto rounded-[var(--dsd-radius-md)]"
      style={containerStyle}
    >
      <table
        role="grid"
        aria-label={ariaLabel}
        className="w-full border-separate border-spacing-0 text-[var(--dsd-text-md)]"
      >
        <thead
          className={cn(
            stickyHeader && "sticky top-0 z-10",
            "bg-[var(--dsd-layer-raised)]",
          )}
        >
          <tr>
            {cols.map((col) => {
              const isSorted = sortCol === col.key;
              const sortable = !!col.sortKey;
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={isSorted ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  onClick={sortable ? () => handleSort(col) : undefined}
                  onKeyDown={
                    sortable
                      ? (e) => e.key === "Enter" || e.key === " " ? handleSort(col) : undefined
                      : undefined
                  }
                  tabIndex={sortable ? 0 : undefined}
                  style={{ width: col.width, textAlign: col.align ?? "left" }}
                  className={cn(
                    "border-b border-[var(--dsd-table-border)] px-3 font-[var(--dsd-fw-semibold)] text-[var(--dsd-text-xs)] tracking-wider uppercase text-[var(--dsd-text-dim)]",
                    dense ? "py-1" : "py-2",
                    sortable && "cursor-pointer select-none hover:text-[var(--dsd-text-base)] focus-visible:outline-[var(--dsd-border-focus)] focus-visible:outline-2",
                  )}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {sortable && (
                      <span aria-hidden className="opacity-60 text-[9px]">
                        {isSorted ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody ref={tbodyRef}>
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={cols.length}
                className="py-10 text-center text-[var(--dsd-text-faint)] text-[var(--dsd-text-sm)]"
              >
                {emptyLabel}
              </td>
            </tr>
          ) : (
            sorted.map((row) => {
              const key = rowKey(row);
              const isSelected = selectedKey !== undefined && key === selectedKey;
              return (
                <tr
                  key={key}
                  role={onRowClick ? "button" : "row"}
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-selected={isSelected || undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => { if (e.key === "Enter" || e.key === " ") onRowClick(row); }
                      : undefined
                  }
                  className={cn(
                    "transition-colors duration-[var(--dsd-dur-fast)]",
                    "border-b border-[var(--dsd-table-border)] last:border-b-0",
                    onRowClick && "cursor-pointer hover:bg-[var(--dsd-table-row-hover)]",
                    isSelected && "bg-[var(--dsd-table-row-selected)]",
                    onRowClick && "focus-visible:outline-[var(--dsd-border-focus)] focus-visible:outline-2 focus-visible:outline-offset-[-2px]",
                  )}
                >
                  {cols.map((col) => (
                    <td
                      key={col.key}
                      style={{ textAlign: col.align ?? "left" }}
                      className={cn(
                        "px-3 text-[var(--dsd-text-base)]",
                        dense ? "py-1" : "py-2",
                      )}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
    </div>
  );
}
