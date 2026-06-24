/**
 * ChatQuickStart — empty-state suggestion chips shown above the terminal
 * before the user has typed anything.
 *
 * The real composer is the prompt line the Ink TUI renders inside the
 * terminal; we don't replace it. Instead these chips inject text into the
 * live PTY (same mechanism as the "copy last response" button), giving new
 * users a discoverable on-ramp to slash commands and a sample task:
 *
 *   - slash chips run immediately (command + Return);
 *   - the example-task chip only *inserts* the text so the user can review
 *     and edit it before pressing Enter.
 *
 * It auto-hides as soon as the user interacts with the terminal (see
 * `hasStarted` in ChatPage), reclaiming vertical space for the conversation.
 */

import { BookOpen, Cpu, PencilLine } from "lucide-react";

interface ChatQuickStartProps {
  /** Run a slash command now (sends command + Return to the PTY). */
  onRun: (command: string) => void;
  /** Insert text into the prompt without submitting it. */
  onInsert: (text: string) => void;
}

const EXAMPLE_TASK =
  "Give me a tour of this repository: the main entry points and how the pieces fit together.";

export function ChatQuickStart({ onRun, onInsert }: ChatQuickStartProps) {
  return (
    <div className="px-1 pb-2">
      <div className="text-display pb-1.5 text-[0.625rem] uppercase tracking-wider text-text-tertiary">
        quick start
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => onRun("/help")}
          className="deck-chat-chip"
          title="List available commands"
        >
          <BookOpen className="size-3.5 shrink-0" />
          <span className="font-mono">/help</span>
        </button>

        <button
          type="button"
          onClick={() => onRun("/model")}
          className="deck-chat-chip"
          title="Choose the model from the terminal"
        >
          <Cpu className="size-3.5 shrink-0" />
          <span className="font-mono">/model</span>
        </button>

        <button
          type="button"
          onClick={() => onInsert(EXAMPLE_TASK)}
          className="deck-chat-chip"
          title="Insert an example prompt — review then press Enter to send"
        >
          <PencilLine className="size-3.5 shrink-0" />
          <span>Try an example task</span>
        </button>
      </div>
      <p className="pt-1.5 text-[0.6875rem] text-text-tertiary">
        Type <span className="font-mono text-text-secondary">/</span> in the
        prompt for commands · <span className="font-mono text-text-secondary">Enter</span>{" "}
        sends · <span className="font-mono text-text-secondary">Shift+Enter</span>{" "}
        for a newline.
      </p>
    </div>
  );
}
