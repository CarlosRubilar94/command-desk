import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

/** Route-to-label map mirroring COMMAND_DESK_NAV + BUILTIN_NAV_REST. */
const PATH_LABELS: Record<string, string> = {
  "/agent":        "Home",
  "/missions":     "Missions",
  "/missions/builder": "Mission Builder",
  "/ops":          "Fleet",
  "/costs":        "Spend",
  "/traces":       "Runs",
  "/routing":      "Routing",
  "/doctor":       "Doctor",
  "/bitwarden":    "Bitwarden",
  "/gateway":      "Gateway",
  "/command-deck": "Command Deck",
  "/sessions":     "Sessions",
  "/files":        "Files",
  "/analytics":    "Analytics",
  "/models":       "Models",
  "/logs":         "Logs",
  "/cron":         "Cron",
  "/skills":       "Skills",
  "/plugins":      "Plugins",
  "/mcp":          "MCP",
  "/channels":     "Channels",
  "/webhooks":     "Webhooks",
  "/pairing":      "Pairing",
  "/profiles":     "Profiles",
  "/config":       "Config",
  "/env":          "Keys",
  "/system":       "System",
  "/docs":         "Documentation",
  "/replay":       "Replay",
};

/** Derive breadcrumb segments from a pathname. */
function buildCrumbs(pathname: string): Array<{ label: string; path: string }> {
  const normalized = pathname.replace(/\/$/, "") || "/agent";

  // For /agent (root redirect), no breadcrumbs needed
  if (normalized === "/agent" || normalized === "/") return [];

  const crumbs: Array<{ label: string; path: string }> = [
    { label: "Home", path: "/agent" },
  ];

  // Walk each prefix segment
  const parts = normalized.split("/").filter(Boolean);
  let accumulated = "";
  for (const part of parts) {
    accumulated += `/${part}`;
    const label = PATH_LABELS[accumulated] ?? part.charAt(0).toUpperCase() + part.slice(1);
    crumbs.push({ label, path: accumulated });
  }

  return crumbs;
}

function DeckBreadcrumbs() {
  const { pathname } = useLocation();
  const crumbs = buildCrumbs(pathname);

  if (crumbs.length <= 1) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1 text-[11px] text-[var(--dsd-text-faint)] px-5 pt-3 pb-1 select-none"
    >
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={crumb.path} className="flex items-center gap-1">
            {i > 0 && (
              <span aria-hidden className="opacity-40">
                /
              </span>
            )}
            {isLast ? (
              <span
                className="text-[var(--dsd-text-secondary)] font-medium"
                aria-current="page"
              >
                {crumb.label}
              </span>
            ) : (
              <Link
                to={crumb.path}
                className="hover:text-[var(--dsd-text-secondary)] transition-colors"
              >
                {crumb.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}

/**
 * Shared padding + vertical rhythm for Command Desk ops pages.
 */
export function DeckPageShell({
  children,
  className,
  intro,
}: {
  children: ReactNode;
  className?: string;
  intro?: ReactNode;
}) {
  return (
    <div className={cn("deck-page-shell", className)}>
      <DeckBreadcrumbs />
      {intro ? <div className="deck-page-intro">{intro}</div> : null}
      {children}
    </div>
  );
}
