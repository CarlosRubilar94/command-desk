import { AlertTriangle, Lock } from "lucide-react";
import type { SpanRow } from "@/lib/api";
import { StatusPill } from "@/components/ds/StatusPill";
import { KeyValueGrid } from "@/components/ds/KeyValueGrid";
import { EmptyState } from "@/components/ds/EmptyState";
import { kindVariant, spanStatusVariant, fmtMs, fmtTokens, fmtUsd, fmtTs } from "./utils";

export interface StepInspectorProps {
  span: SpanRow | null;
  stepIndex: number;
  totalSteps: number;
}

export function StepInspector({ span, stepIndex, totalSteps }: StepInspectorProps) {
  if (!span) {
    return (
      <EmptyState
        icon="🔍"
        title="No step selected"
        description="Select a step from the timeline or use the playback controls."
        compact
      />
    );
  }

  const kvEntries = [
    { key: "name", value: span.name, mono: true },
    { key: "kind", value: <StatusPill variant={kindVariant(span.kind)} label={span.kind} size="sm" /> },
    { key: "status", value: <StatusPill variant={spanStatusVariant(span.status)} label={span.status} dot size="sm" /> },
    { key: "step", value: `${stepIndex + 1} / ${totalSteps}`, mono: true },
    { key: "span_id", value: span.span_id, mono: true, copyText: span.span_id },
    { key: "trace_id", value: "—", mono: true },
    { key: "parent_id", value: span.parent_id ?? "—", mono: true },
    { key: "started_at", value: fmtTs(span.started_at), mono: true },
    { key: "duration", value: fmtMs(span.duration_ms), mono: true },
    { key: "agent", value: span.agent ?? "—", mono: true },
    { key: "model", value: span.model ?? "—", mono: true },
    { key: "provider", value: span.provider ?? "—", mono: true },
    { key: "input_tokens", value: fmtTokens(span.input_tokens), mono: true },
    { key: "output_tokens", value: fmtTokens(span.output_tokens), mono: true },
    { key: "total_tokens", value: fmtTokens(span.total_tokens), mono: true },
    { key: "cost_usd", value: fmtUsd(span.cost_usd), mono: true },
    ...(span.session_id ? [{ key: "session_id", value: span.session_id, mono: true, copyText: span.session_id }] : []),
  ];

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto">
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-medium uppercase tracking-wider text-[var(--dsd-text-faint)]">
          Step {stepIndex + 1}
        </span>
        <StatusPill variant={kindVariant(span.kind)} label={span.kind} size="sm" />
      </div>

      {/* Error banner */}
      {span.error && (
        <div
          role="alert"
          className="flex items-start gap-2 px-3 py-2 rounded-[var(--dsd-radius-sm)] bg-[var(--dsd-status-error-bg)] border border-[var(--dsd-status-error)]/30"
        >
          <AlertTriangle className="h-3.5 w-3.5 text-[var(--dsd-status-error)] shrink-0 mt-0.5" />
          <p className="text-[11px] font-mono text-[var(--dsd-status-error)] break-words min-w-0">
            {span.error}
          </p>
        </div>
      )}

      {/* Span fields */}
      <section aria-labelledby="inspector-fields-hd">
        <h3
          id="inspector-fields-hd"
          className="text-[10px] uppercase tracking-wider text-[var(--dsd-text-faint)] mb-2"
        >
          Span attributes
        </h3>
        <KeyValueGrid entries={kvEntries} cols={2} compact />
      </section>

      {/* Tool-call details */}
      {span.kind === "tool_call" && (
        <section aria-labelledby="inspector-tool-hd">
          <h3
            id="inspector-tool-hd"
            className="text-[10px] uppercase tracking-wider text-[var(--dsd-text-faint)] mb-2"
          >
            Tool call
          </h3>
          <KeyValueGrid
            entries={[
              { key: "tool_name", value: span.name, mono: true },
              { key: "status", value: span.status, mono: true },
            ]}
            cols={1}
            compact
          />
        </section>
      )}

      {/* Payload capture notice */}
      <section aria-labelledby="inspector-payload-hd">
        <h3
          id="inspector-payload-hd"
          className="text-[10px] uppercase tracking-wider text-[var(--dsd-text-faint)] mb-2"
        >
          Prompt / output
        </h3>
        <div className="flex items-start gap-2 px-3 py-2.5 rounded-[var(--dsd-radius-sm)] bg-[var(--dsd-layer-raised)] border border-[var(--dsd-border-subtle)]">
          <Lock className="h-3.5 w-3.5 text-[var(--dsd-text-faint)] shrink-0 mt-0.5" />
          <p className="text-[11px] text-[var(--dsd-text-faint)] leading-relaxed">
            Payload capture is <strong className="text-[var(--dsd-text-dim)]">disabled</strong> by
            default for security. Raw prompts and model outputs are not stored. Enable{" "}
            <code className="font-mono text-[10px]">tracing.capture_payloads = true</code> in your
            Hermes config to record them.
          </p>
        </div>
      </section>
    </div>
  );
}
