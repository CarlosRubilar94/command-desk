import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type DrawerSide = "right" | "left";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  width?: string | number;
  side?: DrawerSide;
  footer?: ReactNode;
  className?: string;
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  width = 400,
  side = "right",
  footer,
  className,
}: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  /* Focus trap — move focus into panel on open */
  useEffect(() => {
    if (open) {
      panelRef.current?.focus();
    }
  }, [open]);

  /* Close on Escape */
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/50 backdrop-blur-sm",
          "transition-opacity duration-[var(--dsd-dur-normal)]",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        )}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ?? "Side panel"}
        tabIndex={-1}
        style={{
          width,
          [side]: 0,
          transitionDuration: "var(--dsd-dur-normal)",
          transitionTimingFunction: "var(--dsd-ease-out)",
        }}
        className={cn(
          "fixed top-0 bottom-0 z-50 flex flex-col",
          "bg-[var(--dsd-layer-raised)] border-[var(--dsd-border-subtle)]",
          side === "right" ? "border-l" : "border-r",
          "shadow-[var(--dsd-elev-4)]",
          "transition-transform",
          open
            ? "translate-x-0"
            : side === "right"
              ? "translate-x-full"
              : "-translate-x-full",
          "outline-none",
          className,
        )}
      >
        {/* Header */}
        {title && (
          <div className="flex items-center justify-between shrink-0 px-5 py-3.5 border-b border-[var(--dsd-border-subtle)]">
            <h2 className="text-[var(--dsd-text-xl)] font-[var(--dsd-fw-semibold)] text-[var(--dsd-text-base)]">
              {title}
            </h2>
            <button
              type="button"
              aria-label="Close panel"
              onClick={onClose}
              className={cn(
                "rounded-[var(--dsd-radius-sm)] p-1 text-[var(--dsd-text-faint)]",
                "hover:bg-[var(--dsd-layer-overlay)] hover:text-[var(--dsd-text-base)]",
                "transition-colors duration-[var(--dsd-dur-fast)]",
                "focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)]",
              )}
            >
              ✕
            </button>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="shrink-0 px-5 py-3.5 border-t border-[var(--dsd-border-subtle)]">
            {footer}
          </div>
        )}
      </div>
    </>
  );
}
