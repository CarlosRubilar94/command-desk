import { useEffect, useState } from "react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Markdown } from "@/components/Markdown";
import { api, type SessionMessage } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

const ROLE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  user: { bg: "deck-transcript-user", text: "text-[var(--dsd-sem-info)]", label: "user" },
  assistant: {
    bg: "deck-transcript-assistant",
    text: "text-[var(--dsd-sem-ok)]",
    label: "assistant",
  },
  system: {
    bg: "deck-transcript-system",
    text: "text-[var(--dsd-text-muted)]",
    label: "system",
  },
  tool: {
    bg: "deck-transcript-tool",
    text: "text-[var(--dsd-sem-warning)]",
    label: "tool",
  },
};

function TranscriptBubble({ msg }: { msg: SessionMessage }) {
  const style = ROLE_STYLES[msg.role] ?? ROLE_STYLES.system;
  const label = msg.tool_name ? `tool: ${msg.tool_name}` : style.label;

  return (
    <div className={`deck-transcript-bubble ${style.bg}`}>
      <div className="mb-1 flex items-center gap-2">
        <span className={`text-xs font-semibold ${style.text}`}>{label}</span>
        {msg.timestamp ? (
          <span className="text-xs text-[var(--dsd-text-muted)]">{timeAgo(msg.timestamp)}</span>
        ) : null}
      </div>
      {msg.content ? (
        msg.role === "system" ? (
          <div className="whitespace-pre-wrap text-xs leading-relaxed text-[var(--dsd-text-primary)]">
            {msg.content}
          </div>
        ) : (
          <div className="deck-transcript-markdown text-xs">
            <Markdown content={msg.content} />
          </div>
        )
      ) : null}
    </div>
  );
}

export function SessionTranscript({
  sessionId,
  profile,
  maxHeight = "280px",
}: {
  sessionId: string;
  profile: string;
  maxHeight?: string;
}) {
  const [messages, setMessages] = useState<SessionMessage[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setMessages(null);
    void api
      .getSessionMessages(sessionId, profile)
      .then((resp) => setMessages(resp.messages))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [sessionId, profile]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-xs text-[var(--dsd-text-secondary)]">
        <Spinner />
        Loading transcript…
      </div>
    );
  }

  if (error) {
    return <p className="py-2 text-xs text-[var(--dsd-sem-critical)]">{error}</p>;
  }

  if (!messages || messages.length === 0) {
    return <p className="py-2 text-xs text-[var(--dsd-text-muted)]">No messages.</p>;
  }

  return (
    <div className="deck-transcript-panel" style={{ maxHeight }}>
      {messages.map((msg, i) => (
        <TranscriptBubble key={`${sessionId}-${i}`} msg={msg} />
      ))}
    </div>
  );
}
