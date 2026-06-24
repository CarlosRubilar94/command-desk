/**
 * CommandDeckUX — Command Palette (Ctrl/Cmd+K) + Keyboard Shortcuts (? help overlay).
 *
 * Mount once inside App, inside the Router context:
 *   <CommandDeckUX />
 *
 * Keyboard contract:
 *   Ctrl/Cmd+K   → open palette
 *   ?            → open shortcut help (when not focused in input/textarea)
 *   Esc          → close active overlay
 *   g h          → navigate /agent   (Home)
 *   g m          → navigate /missions
 *   g o          → navigate /ops
 *   g c          → navigate /costs
 *   g t          → navigate /traces
 *   ↑ ↓ Enter    → palette navigation
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Static palette item list ─────────────────────────────────────────────────

interface PaletteItem {
  path: string;
  label: string;
  group: "Command Desk" | "Hermes";
  keywords?: string;
}

const PALETTE_ITEMS: PaletteItem[] = [
  // Command Desk section
  { path: "/agent",        label: "Home",          group: "Command Desk", keywords: "agent start" },
  { path: "/missions",     label: "Missions",      group: "Command Desk", keywords: "tasks objectives" },
  { path: "/missions/builder", label: "Mission Builder", group: "Command Desk", keywords: "create new mission build" },
  { path: "/replay",       label: "Replay",        group: "Command Desk", keywords: "trace replay debug" },
  { path: "/ops",          label: "Fleet",         group: "Command Desk", keywords: "operations ops" },
  { path: "/costs",        label: "Spend",         group: "Command Desk", keywords: "costs billing" },
  { path: "/traces",       label: "Runs",          group: "Command Desk", keywords: "traces logs runs" },
  { path: "/routing",      label: "Routing",       group: "Command Desk" },
  { path: "/doctor",       label: "Doctor",        group: "Command Desk", keywords: "health status check" },
  { path: "/gateway",      label: "Gateway",       group: "Command Desk", keywords: "network" },
  { path: "/command-deck", label: "Command Deck",  group: "Command Desk", keywords: "ops deck" },
  // Hermes section
  { path: "/sessions",     label: "Sessions",      group: "Hermes", keywords: "chat history" },
  { path: "/files",        label: "Files",         group: "Hermes" },
  { path: "/analytics",    label: "Analytics",     group: "Hermes", keywords: "tokens usage" },
  { path: "/models",       label: "Models",        group: "Hermes", keywords: "llm providers" },
  { path: "/logs",         label: "Logs",          group: "Hermes" },
  { path: "/cron",         label: "Cron",          group: "Hermes", keywords: "schedule" },
  { path: "/skills",       label: "Skills",        group: "Hermes" },
  { path: "/plugins",      label: "Plugins",       group: "Hermes", keywords: "extensions" },
  { path: "/mcp",          label: "MCP",           group: "Hermes", keywords: "model context protocol" },
  { path: "/channels",     label: "Channels",      group: "Hermes" },
  { path: "/webhooks",     label: "Webhooks",      group: "Hermes", keywords: "integrations" },
  { path: "/pairing",      label: "Pairing",       group: "Hermes", keywords: "connect" },
  { path: "/profiles",     label: "Profiles",      group: "Hermes", keywords: "accounts" },
  { path: "/config",       label: "Config",        group: "Hermes", keywords: "settings configuration" },
  { path: "/env",          label: "Keys",          group: "Hermes", keywords: "env environment secrets" },
  { path: "/system",       label: "System",        group: "Hermes", keywords: "system info" },
  { path: "/docs",         label: "Documentation", group: "Hermes", keywords: "help docs" },
];

// ─── Fuzzy match ──────────────────────────────────────────────────────────────

function fuzzyMatch(query: string, target: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  let qi = 0;
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) qi++;
  }
  return qi === q.length;
}

function matchesQuery(query: string, item: PaletteItem): boolean {
  return (
    fuzzyMatch(query, item.label) ||
    fuzzyMatch(query, item.path) ||
    (!!item.keywords && fuzzyMatch(query, item.keywords))
  );
}

// ─── Guard: skip shortcut when typing in editable element ────────────────────

function isEditableTarget(el: Element | null): boolean {
  if (!el) return false;
  const tag = (el as HTMLElement).tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return (el as HTMLElement).isContentEditable;
}

// ─── Command Palette Modal ────────────────────────────────────────────────────

interface CommandPaletteModalProps {
  open: boolean;
  onClose: () => void;
}

function CommandPaletteModal({ open, onClose }: CommandPaletteModalProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(
    () => PALETTE_ITEMS.filter((item) => matchesQuery(query, item)),
    [query],
  );

  // Reset + focus on open
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIdx(0);
    const raf = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(raf);
  }, [open]);

  // Clamp active index as filtered list changes
  useEffect(() => {
    if (filtered.length === 0) return;
    setActiveIdx((prev) => Math.min(prev, filtered.length - 1));
  }, [filtered.length]);

  const commit = useCallback(
    (item: PaletteItem) => {
      navigate(item.path);
      onClose();
    },
    [navigate, onClose],
  );

  // Key navigation while palette is open
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = filtered[activeIdx];
        if (item) commit(item);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, filtered, activeIdx, commit, onClose]);

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>("[data-active='true']");
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  if (!open) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className={cn(
          "fixed left-1/2 top-[15vh] z-[201] w-full max-w-lg -translate-x-1/2",
          "flex flex-col overflow-hidden",
          "rounded-[var(--dsd-radius-lg)]",
          "border border-[var(--dsd-border-subtle)]",
          "bg-[var(--dsd-layer-raised)] shadow-2xl",
        )}
      >
        {/* Search input */}
        <div className="flex items-center gap-2 border-b border-[var(--dsd-border-subtle)] px-3">
          <Search className="h-4 w-4 shrink-0 text-[var(--dsd-text-faint)]" aria-hidden />
          <input
            ref={inputRef}
            type="search"
            role="combobox"
            aria-expanded="true"
            aria-haspopup="listbox"
            aria-autocomplete="list"
            aria-controls="cmd-palette-list"
            aria-activedescendant={filtered[activeIdx] ? `cp-item-${activeIdx}` : undefined}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIdx(0);
            }}
            placeholder="Search pages…"
            autoComplete="off"
            className="flex-1 bg-transparent py-3 text-sm text-[var(--dsd-text-primary)] placeholder:text-[var(--dsd-text-faint)] outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close palette"
            className="shrink-0 text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-primary)] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results list */}
        <div
          id="cmd-palette-list"
          ref={listRef}
          role="listbox"
          aria-label="Navigation results"
          className="max-h-[360px] overflow-y-auto py-1"
        >
          {filtered.length === 0 ? (
            <p className="py-10 text-center text-sm text-[var(--dsd-text-faint)]">
              No results for &ldquo;{query}&rdquo;
            </p>
          ) : (
            filtered.map((item, idx) => (
              <div
                key={item.path}
                id={`cp-item-${idx}`}
                role="option"
                aria-selected={idx === activeIdx}
                data-active={idx === activeIdx ? "true" : "false"}
                onClick={() => commit(item)}
                onMouseEnter={() => setActiveIdx(idx)}
                className={cn(
                  "flex cursor-pointer items-center gap-3 px-3 py-2 text-sm transition-colors",
                  idx === activeIdx
                    ? "bg-[var(--dsd-layer-overlay)] text-[var(--dsd-text-primary)]"
                    : "text-[var(--dsd-text-secondary)] hover:bg-[var(--dsd-layer-overlay)]",
                )}
              >
                <span className="flex-1 min-w-0 truncate">{item.label}</span>
                <span className="shrink-0 text-[10px] text-[var(--dsd-text-faint)]">
                  {item.group}
                </span>
                {idx === activeIdx && (
                  <kbd
                    className="shrink-0 text-[10px] text-[var(--dsd-text-faint)]"
                    aria-hidden
                  >
                    ↵
                  </kbd>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer hints */}
        <div className="flex items-center gap-4 border-t border-[var(--dsd-border-subtle)] px-3 py-1.5 text-[10px] text-[var(--dsd-text-faint)]">
          <span>
            <kbd className="font-mono">↑↓</kbd> navigate
          </span>
          <span>
            <kbd className="font-mono">↵</kbd> open
          </span>
          <span>
            <kbd className="font-mono">Esc</kbd> close
          </span>
          <span className="ml-auto">
            <kbd className="font-mono">?</kbd> all shortcuts
          </span>
        </div>
      </div>
    </>,
    document.body,
  );
}

// ─── Shortcut Help Overlay ────────────────────────────────────────────────────

const SHORTCUT_ROWS: Array<{ keys: string; action: string }> = [
  { keys: "Ctrl / ⌘  K",   action: "Open command palette" },
  { keys: "?",              action: "Show this help" },
  { keys: "Esc",            action: "Close palette / help" },
  { keys: "g  h",           action: "Go → Home" },
  { keys: "g  m",           action: "Go → Missions" },
  { keys: "g  o",           action: "Go → Fleet (Ops)" },
  { keys: "g  c",           action: "Go → Spend (Costs)" },
  { keys: "g  t",           action: "Go → Runs (Traces)" },
  { keys: "↑ ↓",           action: "Navigate palette list" },
  { keys: "↵",             action: "Confirm selection" },
];

interface ShortcutHelpProps {
  open: boolean;
  onClose: () => void;
}

function ShortcutHelpOverlay({ open, onClose }: ShortcutHelpProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        className={cn(
          "fixed left-1/2 top-1/2 z-[201] w-full max-w-sm -translate-x-1/2 -translate-y-1/2",
          "flex flex-col overflow-hidden",
          "rounded-[var(--dsd-radius-lg)]",
          "border border-[var(--dsd-border-subtle)]",
          "bg-[var(--dsd-layer-raised)] shadow-2xl",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--dsd-border-subtle)] px-4 py-3">
          <span className="text-sm font-semibold text-[var(--dsd-text-primary)]">
            Keyboard Shortcuts
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close shortcuts"
            className="text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-primary)] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Shortcut list */}
        <div className="flex flex-col divide-y divide-[var(--dsd-border-subtle)]">
          {SHORTCUT_ROWS.map(({ keys, action }) => (
            <div
              key={keys}
              className="flex items-center justify-between gap-4 px-4 py-2"
            >
              <span className="text-xs text-[var(--dsd-text-secondary)]">{action}</span>
              <kbd className="shrink-0 font-mono text-[11px] text-[var(--dsd-text-faint)] tracking-wide whitespace-nowrap">
                {keys}
              </kbd>
            </div>
          ))}
        </div>

        <div className="border-t border-[var(--dsd-border-subtle)] px-4 py-2 text-[10px] text-[var(--dsd-text-faint)]">
          Shortcuts are inactive while focused in input fields.
        </div>
      </div>
    </>,
    document.body,
  );
}

// ─── Root UX component — mount once inside App ────────────────────────────────

/**
 * CommandDeckUX registers global keyboard shortcuts and renders overlays.
 * Must be mounted inside the Router context (uses useNavigate).
 */
export function CommandDeckUX() {
  const navigate = useNavigate();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const closePalette = useCallback(() => setPaletteOpen(false), []);
  const closeHelp = useCallback(() => setHelpOpen(false), []);

  // "g" then key sequence (500ms window)
  const pendingG = useRef(false);
  const pendingGTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearPendingG = useCallback(() => {
    pendingG.current = false;
    if (pendingGTimer.current) {
      clearTimeout(pendingGTimer.current);
      pendingGTimer.current = null;
    }
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // If either overlay is open, Esc handling is delegated to the overlay
      if (paletteOpen || helpOpen) return;

      // Ignore when focus is in an editable element
      const inEditable = isEditableTarget(document.activeElement);

      // Ctrl/Cmd+K always opens palette (regardless of focus)
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }

      if (inEditable) return;

      // "?" opens shortcut help
      if (e.key === "?") {
        e.preventDefault();
        setHelpOpen(true);
        return;
      }

      // "g" starts the go-to sequence
      if (e.key === "g") {
        e.preventDefault();
        pendingG.current = true;
        pendingGTimer.current = setTimeout(clearPendingG, 500);
        return;
      }

      // "g X" navigation sequences
      if (pendingG.current) {
        clearPendingG();
        const dest: Record<string, string> = {
          h: "/agent",
          m: "/missions",
          o: "/ops",
          c: "/costs",
          t: "/traces",
        };
        const path = dest[e.key];
        if (path) {
          e.preventDefault();
          navigate(path);
        }
        return;
      }
    };

    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      clearPendingG();
    };
  }, [paletteOpen, helpOpen, navigate, clearPendingG]);

  return (
    <>
      <CommandPaletteModal open={paletteOpen} onClose={closePalette} />
      <ShortcutHelpOverlay open={helpOpen} onClose={closeHelp} />
    </>
  );
}
