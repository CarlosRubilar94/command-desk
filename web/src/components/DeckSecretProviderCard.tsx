import { Download, LockOpen } from "lucide-react";
import { DeckCard, DeckToolbar, MetricRow, MetricTile } from "@/components/DeckOps";
import type { SecretsStatus } from "@/lib/api";

type BwState = SecretsStatus["bitwarden"]["state"];
type TileState = "ok" | "warning" | "critical" | "degraded";

const BW_STATE_META: Record<BwState, { label: string; tile: TileState; hint: string }> = {
  unlocked: { label: "Unlocked", tile: "ok", hint: "Vault unlocked — secrets can sync." },
  locked: { label: "Locked", tile: "warning", hint: "Unlock locally in a terminal: bw unlock" },
  unauthenticated: { label: "Not signed in", tile: "warning", hint: "Sign in locally in a terminal: bw login" },
  "not-installed": { label: "Not installed", tile: "critical", hint: "Install the Bitwarden CLI to enable the provider." },
  unknown: { label: "Unknown", tile: "degraded", hint: "Could not read bw status." },
};

function rowTone(tile: TileState): "ok" | "warn" | "bad" {
  if (tile === "ok") return "ok";
  if (tile === "critical") return "bad";
  return "warn";
}

export function DeckSecretProviderCard({ status }: { status: SecretsStatus | null }) {
  const bw = status?.bitwarden;
  const meta = BW_STATE_META[bw?.state ?? "unknown"] ?? BW_STATE_META.unknown;
  const missing = status?.env.missing ?? 0;

  return (
    <DeckCard title="Secrets provider" subtitle="Bitwarden-first · .env fallback" colClass="col-12">
      <div className="mb-3 flex flex-wrap gap-3">
        <MetricTile
          label="Bitwarden"
          value={meta.label}
          context={bw?.version ? `bw ${bw.version}` : "Bitwarden CLI"}
          state={meta.tile}
        />
        <MetricTile
          label="Env fallback"
          value={status?.env.fallback_enabled ? "Enabled" : "Off"}
          context={`${status?.env.set ?? 0}/${status?.env.known ?? 0} keys set`}
          state="ok"
        />
        <MetricTile
          label="Missing"
          value={String(missing)}
          context="optional keys unset"
          state={missing > 0 ? "degraded" : "ok"}
        />
      </div>

      <MetricRow label="Provider status" value={meta.hint} tone={rowTone(meta.tile)} />
      <MetricRow
        label="Safety"
        value="Values stay redacted. Copy the command, never the secret."
        tone="ok"
      />

      <DeckToolbar>
        <button
          type="button"
          className="deck-btn-sm"
          onClick={() => void navigator.clipboard?.writeText("bw unlock")}
          title="Copies the unlock command to run locally — not any secret value"
        >
          <LockOpen className="h-3.5 w-3.5" />
          Copy &ldquo;bw unlock&rdquo;
        </button>
        <a
          href="https://bitwarden.com/help/cli/"
          target="_blank"
          rel="noreferrer"
          className="deck-btn-sm ghost"
        >
          <Download className="h-3.5 w-3.5" />
          Bitwarden CLI docs
        </a>
      </DeckToolbar>
    </DeckCard>
  );
}
