import type { SpanRow } from "@/lib/api";
import type { StatusVariant } from "@/components/ds/StatusPill";

export function fmtMs(ms: number): string {
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`;
  if (ms >= 1_000) return `${(ms / 1_000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

export function fmtTokens(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  if (n < 0.0001) return "<$0.0001";
  return `$${n.toFixed(4)}`;
}

export function fmtTs(epoch: number): string {
  return new Date(epoch * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function spanStatusVariant(status: string): StatusVariant {
  if (status === "ok") return "success";
  if (status === "error") return "error";
  if (status === "running") return "info";
  return "neutral";
}

export function kindVariant(kind: string): StatusVariant {
  if (kind === "llm_call") return "model";
  if (kind === "tool_call") return "tool";
  if (kind === "delegation") return "mission";
  if (kind === "agent_turn") return "agent";
  return "trace";
}

export function kindCatToken(kind: string): string {
  if (kind === "llm_call") return "model";
  if (kind === "tool_call") return "tool";
  if (kind === "delegation") return "mission";
  if (kind === "agent_turn") return "agent";
  return "trace";
}

export function buildDepthMap(spans: SpanRow[]): Map<string, number> {
  const depthMap = new Map<string, number>();
  const parentMap = new Map<string, string | null>();
  const spanIds = new Set<string>(spans.map((s) => s.span_id));

  for (const s of spans) {
    parentMap.set(s.span_id, s.parent_id);
  }

  function getDepth(id: string, visited = new Set<string>()): number {
    if (depthMap.has(id)) return depthMap.get(id)!;
    if (visited.has(id)) {
      depthMap.set(id, 0);
      return 0;
    }
    visited.add(id);
    const parent = parentMap.get(id);
    if (!parent || !spanIds.has(parent)) {
      depthMap.set(id, 0);
      return 0;
    }
    const d = getDepth(parent, visited) + 1;
    depthMap.set(id, d);
    return d;
  }

  for (const s of spans) getDepth(s.span_id);
  return depthMap;
}
