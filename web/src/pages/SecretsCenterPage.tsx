import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Copy, Eye, EyeOff, Plus, Trash2 } from "lucide-react";
import { DeckPageShell } from "@/components/DeckPageShell";
import { DataTable, type ColDef } from "@/components/ds/DataTable";
import { api, type SecretListItem, type SecretsListResponse } from "@/lib/api";
import { Button } from "@nous-research/ui/ui/components/button";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";

const AUTO_HIDE_MS = 30_000;
const CLIPBOARD_CLEAR_MS = 15_000;

type RevealMap = Record<string, string>;

export default function SecretsCenterPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<SecretsListResponse | null>(null);
  const [revealed, setRevealed] = useState<RevealMap>({});
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const hideTimersRef = useRef<Map<string, number>>(new Map());

  const clearReveal = useCallback((name: string) => {
    const timerId = hideTimersRef.current.get(name);
    if (timerId !== undefined) {
      window.clearTimeout(timerId);
      hideTimersRef.current.delete(name);
    }
    setRevealed((prev) => {
      if (!(name in prev)) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      for (const timerId of hideTimersRef.current.values()) {
        window.clearTimeout(timerId);
      }
      hideTimersRef.current.clear();
    };
  }, []);

  const scheduleAutoHide = useCallback((name: string) => {
    const previous = hideTimersRef.current.get(name);
    if (previous !== undefined) {
      window.clearTimeout(previous);
    }
    const timerId = window.setTimeout(() => {
      clearReveal(name);
    }, AUTO_HIDE_MS);
    hideTimersRef.current.set(name, timerId);
  }, [clearReveal]);

  const loadSecrets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPayload(await api.getSecrets());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSecrets();
  }, [loadSecrets]);

  const revealSecret = useCallback(async (name: string) => {
    if (revealed[name]) {
      clearReveal(name);
      return;
    }
    try {
      const resp = await api.revealSecret(name);
      setRevealed((prev) => ({ ...prev, [name]: resp.value }));
      scheduleAutoHide(name);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [clearReveal, revealed, scheduleAutoHide]);

  const copySecret = useCallback(async (name: string) => {
    const value = revealed[name];
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      window.setTimeout(() => {
        navigator.clipboard.writeText("").catch(() => {});
      }, CLIPBOARD_CLEAR_MS);
    } catch {
      setError("Clipboard unavailable on this browser session.");
    }
  }, [revealed]);

  const createEnvSecret = useCallback(async () => {
    const key = newKey.trim();
    if (!key || !newValue) return;
    setSaving(true);
    setError(null);
    try {
      await api.setEnvVar(key, newValue);
      setNewValue("");
      await loadSecrets();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [newKey, newValue, loadSecrets]);

  const removeEnvSecret = useCallback(async (name: string) => {
    setSaving(true);
    setError(null);
    try {
      await api.deleteEnvVar(name);
      clearReveal(name);
      await loadSecrets();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [clearReveal, loadSecrets]);

  const rows = useMemo(() => payload?.items ?? [], [payload]);
  const bitwarden = payload?.bitwarden;

  const cols: ColDef<SecretListItem>[] = useMemo(() => [
    {
      key: "name",
      header: "Name",
      sortKey: "name",
      cell: (row) => <code className="font-mono text-xs">{row.name}</code>,
    },
    {
      key: "source",
      header: "Source",
      sortKey: "source",
      cell: (row) => (
        <Badge tone={row.source === "bitwarden" ? "secondary" : "outline"}>
          {row.source === "bitwarden" ? "Bitwarden" : ".env"}
        </Badge>
      ),
    },
    {
      key: "value",
      header: "Reveal",
      cell: (row) => (
        <div className="flex items-center gap-2">
          <code className="max-w-[300px] truncate text-xs">
            {revealed[row.name] ? revealed[row.name] : "••••••••"}
          </code>
          <Button
            size="sm"
            outlined
            prefix={revealed[row.name] ? <EyeOff /> : <Eye />}
            onClick={() => void revealSecret(row.name)}
          >
            {revealed[row.name] ? "Hide" : "Reveal"}
          </Button>
          <Button
            size="sm"
            outlined
            prefix={<Copy />}
            disabled={!revealed[row.name]}
            onClick={() => void copySecret(row.name)}
          >
            Copy
          </Button>
          {row.source === "env" ? (
            <Button
              size="sm"
              outlined
              destructive
              prefix={<Trash2 />}
              onClick={() => void removeEnvSecret(row.name)}
              disabled={saving}
            >
              Delete
            </Button>
          ) : null}
        </div>
      ),
    },
  ], [copySecret, removeEnvSecret, revealSecret, revealed, saving]);

  return (
    <DeckPageShell
      intro={(
        <div className="px-5 pt-5">
          <h1 className="text-xl font-semibold">Secrets Center</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Names-only inventory. Values are revealed per item, auto-hidden, and never shown in the list payload.
          </p>
        </div>
      )}
    >
      <div className="grid gap-4 px-5 pb-6">
        <Card>
          <CardHeader>
            <CardTitle>Bitwarden state</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3 text-sm">
            <Badge tone={bitwarden?.available ? "success" : "outline"}>
              {bitwarden?.available ? "Available" : bitwarden?.locked ? "Locked" : "Unavailable"}
            </Badge>
            <span className="text-muted-foreground">{bitwarden?.message ?? "Loading status..."}</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Secrets list</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-xs text-muted-foreground">
              Bitwarden entries are read-only here and managed externally in Bitwarden Secrets Manager.
            </p>
            {loading ? <div className="text-sm text-muted-foreground">Loading...</div> : null}
            {error ? <div className="text-sm text-red-500">{error}</div> : null}
            {!loading && !error ? (
              <DataTable
                aria-label="Secrets inventory"
                cols={cols}
                rows={rows}
                rowKey={(row) => `${row.source}:${row.name}`}
                quickFilter
                filterPlaceholder="Filter secret names..."
                emptyLabel="No secrets found."
              />
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>.env fallback management</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-[1fr_2fr_auto] md:items-end">
            <div className="grid gap-1">
              <Label htmlFor="secret-name-input">Name</Label>
              <Input
                id="secret-name-input"
                autoComplete="off"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value.toUpperCase())}
                placeholder="OPENROUTER_API_KEY"
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="secret-value-input">Value</Label>
              <Input
                id="secret-value-input"
                autoComplete="off"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="Enter value"
                type="password"
              />
            </div>
            <Button
              onClick={() => void createEnvSecret()}
              disabled={saving || !newKey.trim() || !newValue}
              prefix={<Plus />}
            >
              Save .env
            </Button>
          </CardContent>
        </Card>
      </div>
    </DeckPageShell>
  );
}
