import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type DeckTone = "ok" | "warn" | "bad";

export type OverallHealth =
  | "overall-ok"
  | "overall-warning"
  | "overall-degraded"
  | "overall-critical"
  | "overall-unknown";

export function statusDotInline(tone: DeckTone) {
  return <span className={cn("status-dot-inline", tone)} aria-hidden />;
}

export function MetricRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: ReactNode;
  tone?: DeckTone;
}) {
  return (
    <div className="metric-row">
      <span className="label">{label}</span>
      <strong className="value">
        {tone ? statusDotInline(tone) : null}
        {value}
      </strong>
    </div>
  );
}

export function MetricTile({
  label,
  value,
  context,
  state,
}: {
  label: string;
  value: ReactNode;
  context?: string;
  state?: "ok" | "warning" | "critical" | "degraded";
}) {
  return (
    <article
      className={cn(
        "metric-tile",
        state === "ok" && "state-ok",
        state === "warning" && "state-warning",
        state === "critical" && "state-critical",
        state === "degraded" && "state-degraded",
      )}
    >
      <div className="mt-label">{label}</div>
      <div className="mt-value">{value}</div>
      {context ? <div className="mt-context">{context}</div> : null}
    </article>
  );
}

export function OpsSummaryGrid({
  items,
}: {
  items: Array<{ label: string; value: ReactNode; hint?: string; tone?: DeckTone }>;
}) {
  return (
    <div className="ops-summary-grid">
      {items.map((item) => (
        <div key={item.label} className="ops-summary-item">
          <span className="osi-label">{item.label}</span>
          <span className="osi-value">
            {item.tone ? statusDotInline(item.tone) : null}
            {item.value}
          </span>
          {item.hint ? <span className="osi-hint">{item.hint}</span> : null}
        </div>
      ))}
    </div>
  );
}

export function DeckCard({
  title,
  subtitle,
  actions,
  children,
  colClass = "col-12",
  id,
  badge,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  badge?: { label: string; tone: DeckTone };
  children: ReactNode;
  colClass?: string;
  id?: string;
}) {
  const headerActions = badge ? (
    <span className={cn("deck-card-badge", badge.tone)}>{badge.label}</span>
  ) : (
    actions
  );

  return (
    <section className={cn("deck-card", colClass)} id={id}>
      <div className="deck-card-header">
        <div className="min-w-0">
          <h2>{title}</h2>
          {subtitle ? <div className="deck-card-sub">{subtitle}</div> : null}
        </div>
        {headerActions ? <div className="deck-card-actions shrink-0">{headerActions}</div> : null}
      </div>
      <div className="deck-card-body">{children}</div>
    </section>
  );
}

export function ServiceCell({
  name,
  icon,
  state,
  stateTone,
  meta,
  hint,
  warn,
}: {
  name: string;
  icon?: ReactNode;
  state: ReactNode;
  stateTone?: "ok" | "warn" | "bad";
  meta?: string;
  hint?: string;
  warn?: boolean;
}) {
  return (
    <article className={cn("service-cell", warn && "service-cell--warn")}>
      <div className="sc-head">
        <div className="sc-name">
          {icon}
          {name}
        </div>
        {stateTone ? (
          <span className={cn("deck-card-badge", stateTone)}>
            {stateTone === "ok" ? "OK" : stateTone === "warn" ? "WARN" : "ERR"}
          </span>
        ) : null}
      </div>
      <div className={cn("sc-state", stateTone)}>{state}</div>
      {meta ? <div className="sc-meta">{meta}</div> : null}
      {hint ? <div className="sc-hint">{hint}</div> : null}
    </article>
  );
}

export function OperationalStatus({
  overall,
  title,
  subtitle,
  chips,
  label = "Estado operacional",
}: {
  overall: OverallHealth;
  title: string;
  subtitle: string;
  chips: Array<{ label: string; value: string | number }>;
  label?: string;
}) {
  return (
    <div className={cn("operational-status", overall)}>
      <div className="os-label">{label}</div>
      <div className="os-title">{title}</div>
      <div className="os-sub">{subtitle}</div>
      <div className="breakdown-chips">
        {chips.map((chip) => (
          <span key={chip.label} className="breakdown-chip">
            {chip.label}: <strong>{chip.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export function LayoutGrid({ children }: { children: ReactNode }) {
  return <div className="layout-grid">{children}</div>;
}

export function DeckToolbar({ children }: { children: ReactNode }) {
  return <div className="deck-toolbar">{children}</div>;
}

export function DeckBtn({
  children,
  className,
  ghost,
  primary,
  ...props
}: React.ComponentProps<"button"> & { ghost?: boolean; primary?: boolean }) {
  return (
    <button
      type="button"
      className={cn("deck-btn-sm", ghost && "ghost", primary && "primary", className)}
      {...props}
    >
      {children}
    </button>
  );
}

export function DeckBtnLink({
  children,
  className,
  ghost,
  primary,
  href,
  ...props
}: React.ComponentProps<"a"> & { ghost?: boolean; primary?: boolean }) {
  return (
    <a
      href={href}
      className={cn("deck-btn-sm", ghost && "ghost", primary && "primary", className)}
      {...props}
    >
      {children}
    </a>
  );
}

export function computeOverallHealth(flags: {
  critical?: boolean;
  degraded?: boolean;
  warning?: boolean;
}): OverallHealth {
  if (flags.critical) return "overall-critical";
  if (flags.degraded) return "overall-degraded";
  if (flags.warning) return "overall-warning";
  if (!flags.critical && !flags.degraded && !flags.warning) return "overall-ok";
  return "overall-unknown";
}
