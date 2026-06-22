import { useEffect, useState } from "react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Markdown } from "@/components/Markdown";
import { api, type SessionMessage } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

const ROLE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  user: { bg: "bg-primary/10", text: "text-primary", label: "user" },
  assistant: { bg: "bg-success/10", text: "text-success", label: "assistant" },
  system: { bg: "bg-muted", text: "text-muted-foreground", label: "system" },
  tool: { bg: "bg-warning/10", text: "text-warning", label: "tool" },
};

function TranscriptBubble({ msg }: { msg: SessionMessage }) {
  const style = ROLE_STYLES[msg.role] ?? ROLE_STYLES.system;
  const label = msg.tool_name ? `tool: ${msg.tool_name}` : style.label;

  return (
    <div className={`${style.bg} rounded p-2`}>
      <div className="mb-1 flex items-center gap-2">
        <span className={`text-xs font-semibold ${style.text}`}>{label}</span>
        {msg.timestamp ? (
          <span className="text-xs text-text-tertiary">{timeAgo(msg.timestamp)}</span>
        ) : null}
      </div>
      {msg.content ? (
        msg.role === "system" ? (
          <div className="whitespace-pre-wrap text-xs leading-relaxed text-foreground">
            {msg.content}
          </div>
        ) : (
          <div className="text-xs">
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
      <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
        <Spinner />
        Loading transcript…
      </div>
    );
  }

  if (error) {
    return <p className="py-2 text-xs text-destructive">{error}</p>;
  }

  if (!messages || messages.length === 0) {
    return <p className="py-2 text-xs text-muted-foreground">No messages.</p>;
  }

  return (
    <div
      className="mt-2 flex flex-col gap-2 overflow-y-auto rounded border border-border bg-background/50 p-2"
      style={{ maxHeight }}
    >
      {messages.map((msg, i) => (
        <TranscriptBubble key={`${sessionId}-${i}`} msg={msg} />
      ))}
    </div>
  );
}
