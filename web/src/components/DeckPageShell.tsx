import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

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
      {intro ? <div className="deck-page-intro">{intro}</div> : null}
      {children}
    </div>
  );
}
