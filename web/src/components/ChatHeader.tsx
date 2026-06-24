/**
 * ChatHeader — thin React chrome that sits above the embedded xterm.js
 * terminal on the dashboard Chat tab.
 *
 * Architectural note: the Hermes identity banner, the status line, and the
 * prompt input the user types into are all painted by the Ink TUI *inside*
 * the terminal (they arrive as PTY bytes, not React). We can't restyle that
 * content from the SPA without changing the TUI runtime, which is out of
 * scope here. Instead this header adds React-side affordances *around* the
 * terminal:
 *
 *   - a compact, always-visible product identity (so the page keeps its
 *     identity even after the TUI's big splash banner scrolls away);
 *   - a prominent model switcher (the right-rail picker is easy to miss).
 *     It reuses the exact REST path (`/api/model/set`) and dialogs the
 *     sidebar uses, so the two stay in sync on the same config.yaml model;
 *   - a help popover that decodes the TUI's cryptic status line and lists
 *     the keyboard / slash affordances;
 *   - the "copy last response" action, relocated out of a floating overlay
 *     into a clear, labelled toolbar button.
 */

import { Button } from "@nous-research/ui/ui/components/button";
import {
  ChevronDown,
  Copy,
  HelpCircle,
  IdCard,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ModelPickerDialog } from "@/components/ModelPickerDialog";
import { ModelReloadConfirm } from "@/components/ModelReloadConfirm";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChatHeaderProps {
  /** Management profile from the dashboard switcher (label only). */
  profile?: string;
  /** Sends `/copy` + Return to the PTY (provided by ChatPage). */
  onCopyLast: () => void;
  copyState: "idle" | "copied";
}

/** Legend for the TUI status line tokens (e.g. `ready · <model> · 6/1m …`). */
const STATUS_LEGEND: ReadonlyArray<{ token: string; meaning: string }> = [
  { token: "ready / working", meaning: "agent state — idle or running a turn" },
  { token: "<model>", meaning: "model answering this conversation" },
  { token: "6/1m", meaning: "requests used in the last minute" },
  { token: "[ ] 0%", meaning: "context window currently filled" },
  { token: "1m 26s", meaning: "time elapsed in this session" },
  { token: "voice off", meaning: "voice input toggle" },
  { token: "2 sessions", meaning: "active chat sessions" },
  { token: "<profile>", meaning: "management profile scoping this chat" },
];

const TIPS: ReadonlyArray<string> = [
  "Type / in the prompt to list slash commands (/help, /model, /new).",
  "Enter sends · Shift+Enter adds a newline.",
  "Ctrl+C interrupts the current turn.",
];

export function ChatHeader({ profile, onCopyLast, copyState }: ChatHeaderProps) {
  const [effectiveModel, setEffectiveModel] = useState("");
  const [modelOpen, setModelOpen] = useState(false);
  const [pendingReloadModel, setPendingReloadModel] = useState<string | null>(
    null,
  );
  const [helpOpen, setHelpOpen] = useState(false);
  const helpRef = useRef<HTMLDivElement | null>(null);

  const refreshEffectiveModel = useCallback(() => {
    void api
      .getModelInfo()
      .then((r) => {
        if (r?.model) setEffectiveModel(String(r.model));
      })
      .catch(() => {
        /* best-effort: keep the last known label rather than blanking it */
      });
  }, []);

  // `/api/model/info` is profile-scoped by fetchJSON, so re-read it whenever
  // the dashboard profile changes (matches the sidebar badge's behaviour).
  useEffect(() => {
    refreshEffectiveModel();
  }, [refreshEffectiveModel, profile]);

  // Dismiss the help popover on outside-click / Escape.
  useEffect(() => {
    if (!helpOpen) return;
    const onPointer = (e: MouseEvent) => {
      if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
        setHelpOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHelpOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [helpOpen]);

  const modelName = effectiveModel || "—";
  const modelLabel = modelName.split("/").slice(-1)[0] ?? "—";

  return (
    <div
      className={cn(
        "flex items-center gap-2 border-b border-current/15 px-1 pb-2",
        "min-w-0",
      )}
    >
      {/* Product identity — compact, survives the TUI splash scrolling off. */}
      <div className="flex min-w-0 shrink items-center gap-2">
        <span
          aria-hidden
          className="size-1.5 shrink-0 rounded-full bg-primary shadow-[0_0_8px_var(--color-primary,#7dd3fc)]"
        />
        <span className="text-display hidden text-xs font-semibold tracking-[0.18em] text-text-secondary sm:inline">
          HERMES
        </span>
      </div>

      <span aria-hidden className="text-text-tertiary/50">
        ·
      </span>

      {/* Prominent model switcher. */}
      <Button
        ghost
        size="sm"
        onClick={() => setModelOpen(true)}
        title={modelName === "—" ? "Switch model" : `Model: ${modelName}`}
        aria-label={`Switch model (current: ${modelName})`}
        className={cn(
          "min-w-0 max-w-[10rem] px-1.5 py-0.5 sm:max-w-[16rem]",
          "normal-case tracking-normal text-sm font-medium",
        )}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <Sparkles className="size-3.5 shrink-0 text-text-secondary" />
          <span className="text-[0.625rem] uppercase tracking-wider text-text-tertiary">
            model
          </span>
          <span className="truncate">{modelLabel}</span>
          <ChevronDown className="size-3.5 shrink-0 text-text-secondary" />
        </span>
      </Button>

      {profile && (
        <span
          title={`Management profile: ${profile}`}
          className={cn(
            "hidden min-w-0 items-center gap-1 rounded border border-current/15 px-1.5 py-0.5",
            "text-[0.6875rem] text-text-secondary md:inline-flex",
          )}
        >
          <IdCard className="size-3 shrink-0 text-text-tertiary" />
          <span className="truncate">{profile}</span>
        </span>
      )}

      {/* Right-aligned actions. */}
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <div ref={helpRef} className="relative">
          <Button
            ghost
            size="icon"
            onClick={() => setHelpOpen((v) => !v)}
            aria-expanded={helpOpen}
            aria-label="Chat help — status line legend and shortcuts"
            title="Status line legend & shortcuts"
            className="text-text-secondary hover:text-foreground"
          >
            <HelpCircle className="size-4" />
          </Button>

          {helpOpen && (
            <div
              role="dialog"
              aria-label="Chat help"
              className={cn(
                "absolute right-0 top-full z-30 mt-1 w-72 max-w-[80vw]",
                "rounded border border-current/20 bg-background-base/95 p-3 shadow-lg backdrop-blur-sm",
                "text-left",
              )}
            >
              <div className="text-display pb-1.5 text-[0.625rem] uppercase tracking-wider text-text-tertiary">
                status line
              </div>
              <dl className="flex flex-col gap-1">
                {STATUS_LEGEND.map((row) => (
                  <div key={row.token} className="flex gap-2 text-xs">
                    <dt className="shrink-0 font-mono text-text-secondary">
                      {row.token}
                    </dt>
                    <dd className="min-w-0 flex-1 text-text-tertiary">
                      {row.meaning}
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="text-display pb-1.5 pt-3 text-[0.625rem] uppercase tracking-wider text-text-tertiary">
                tips
              </div>
              <ul className="flex flex-col gap-1 text-xs text-text-tertiary">
                {TIPS.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <Button
          ghost
          size="sm"
          onClick={onCopyLast}
          title="Copy last assistant response as raw markdown"
          aria-label="Copy last assistant response"
          className="normal-case tracking-normal text-text-secondary hover:text-foreground"
        >
          <span className="inline-flex items-center gap-1.5 text-xs">
            <Copy className="size-3.5 shrink-0" />
            <span className="hidden min-[420px]:inline">
              {copyState === "copied" ? "copied" : "copy last"}
            </span>
          </span>
        </Button>
      </div>

      {modelOpen && (
        <ModelPickerDialog
          loader={api.getModelOptions}
          alwaysGlobal
          onApply={async ({ provider, model, confirmExpensiveModel }) => {
            const result = await api.setModelAssignment({
              confirm_expensive_model: confirmExpensiveModel,
              scope: "main",
              provider,
              model,
            });
            if (!result.confirm_required) {
              refreshEffectiveModel();
              setPendingReloadModel(model.split("/").slice(-1)[0]);
            }
            return result;
          }}
          onClose={() => {
            setModelOpen(false);
            refreshEffectiveModel();
          }}
        />
      )}

      <ModelReloadConfirm
        model={pendingReloadModel}
        onCancel={() => setPendingReloadModel(null)}
      />
    </div>
  );
}
