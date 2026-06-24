import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Key,
  Lock,
  Package,
  Power,
  RefreshCw,
  Server,
  ShieldOff,
  Trash2,
  Unlock,
  WifiOff,
  X,
  Zap,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import { DeckPageShell } from "@/components/DeckPageShell";
import { StatusPill, EmptyState, SkeletonCard, Toolbar } from "@/components/ds";
import type { StatusVariant } from "@/components/ds";
import type {
  McpCatalogDiagnostic,
  McpCatalogEntry,
  McpControlCenter,
  McpControlCenterServer,
  McpServer,
  McpServerCreate,
  McpStatusChip,
  McpTestResult,
} from "@/lib/api";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { useConfirmDelete } from "@nous-research/ui/hooks/use-confirm-delete";
import { useModalBehavior } from "@/hooks/useModalBehavior";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn, themedBody } from "@/lib/utils";

type Transport = "http" | "stdio";

// ---------------------------------------------------------------------------
// Status chip helpers
// ---------------------------------------------------------------------------

const STATUS_TONE: Record<
  McpStatusChip | string,
  "success" | "warning" | "destructive" | "outline" | "secondary"
> = {
  READY: "success",
  DEGRADED: "warning",
  WAITING_CREDENTIAL: "warning",
  WAITING_SERVICE: "warning",
  WAITING_BITWARDEN: "warning",
  FAILED: "destructive",
  DISABLED: "outline",
  NOT_INSTALLED: "secondary",
};

const STATUS_LABEL: Record<McpStatusChip | string, string> = {
  READY: "Ready",
  DEGRADED: "Degraded",
  WAITING_CREDENTIAL: "Waiting credential",
  WAITING_SERVICE: "Waiting service",
  WAITING_BITWARDEN: "Waiting Bitwarden",
  FAILED: "Failed",
  DISABLED: "Disabled",
  NOT_INSTALLED: "Not installed",
};

const STATUS_ICON: Record<McpStatusChip | string, React.ReactNode> = {
  READY: <CheckCircle className="h-3 w-3" />,
  DEGRADED: <AlertTriangle className="h-3 w-3" />,
  WAITING_CREDENTIAL: <Key className="h-3 w-3" />,
  WAITING_SERVICE: <Clock className="h-3 w-3" />,
  WAITING_BITWARDEN: <Lock className="h-3 w-3" />,
  FAILED: <ShieldOff className="h-3 w-3" />,
  DISABLED: <Power className="h-3 w-3" />,
  NOT_INSTALLED: <Package className="h-3 w-3" />,
};

function StatusChip({ status }: { status: McpStatusChip | string }) {
  return (
    <Badge tone={STATUS_TONE[status] ?? "secondary"} className="flex items-center gap-1">
      {STATUS_ICON[status]}
      {STATUS_LABEL[status] ?? status}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}

function truncateText(value: string, maxLength: number): string {
  return value.length > maxLength ? value.slice(0, maxLength) + "..." : value;
}

function parseArgs(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function parseEnv(raw: string): Record<string, string> {
  const env: Record<string, string> = {};
  raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const idx = line.indexOf("=");
      if (idx === -1) return;
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim();
      if (key) env[key] = value;
    });
  return env;
}

const TRANSPORT_VARIANT: Record<string, StatusVariant> = {
  http: "success",
  stdio: "warning",
  unknown: "neutral",
};
// ---------------------------------------------------------------------------
// Bitwarden status banner
// ---------------------------------------------------------------------------

function BitwardenBanner({
  bw,
}: {
  bw: McpControlCenter["bitwarden"] | null;
}) {
  if (!bw) return null;
  if (bw.status === "not_installed") {
    return (
      <div className="flex items-center gap-2 px-4 py-2 text-xs text-warning bg-warning/10 border border-warning/30">
        <Lock className="h-3.5 w-3.5 shrink-0" />
        <span>
          Bitwarden CLI not found. Some MCP servers use Bitwarden SM for secrets
          and will show{" "}
          <strong>Waiting Bitwarden</strong>.
        </span>
      </div>
    );
  }
  if (bw.locked) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 text-xs text-warning bg-warning/10 border border-warning/30">
        <Lock className="h-3.5 w-3.5 shrink-0" />
        <span>
          Bitwarden is <strong>{bw.status}</strong>. Servers that read secrets
          from Bitwarden SM show <strong>Waiting Bitwarden</strong>. Unlock with{" "}
          <code className="font-mono">bw login</code> (or{" "}
          <code className="font-mono">bw unlock</code> if already logged in).
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-xs text-success bg-success/10 border border-success/30">
      <Unlock className="h-3.5 w-3.5 shrink-0" />
      <span>Bitwarden is unlocked — secret resolution active.</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gateway warning banner
// ---------------------------------------------------------------------------

function GatewayBanner({ running }: { running: boolean }) {
  if (running) return null;
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground bg-muted/30 border border-border">
      <WifiOff className="h-3.5 w-3.5 shrink-0" />
      <span>
        Gateway is not running. MCP servers in the configured list will not be
        probed until the gateway starts. Start with{" "}
        <code className="font-mono">hermes gateway start</code>.
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function McpPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [catalog, setCatalog] = useState<McpCatalogEntry[]>([]);
  const [diagnostics, setDiagnostics] = useState<McpCatalogDiagnostic[]>([]);
  const [controlCenter, setControlCenter] = useState<McpControlCenter | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const { toast, showToast } = useToast();
  const { setEnd } = usePageHeader();

  // Add server modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<Transport>("http");
  const [url, setUrl] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [env, setEnv] = useState("");
  const [creating, setCreating] = useState(false);
  const closeCreateModal = useCallback(() => setCreateModalOpen(false), []);
  const createModalRef = useModalBehavior({
    open: createModalOpen,
    onClose: closeCreateModal,
  });

  // Test results keyed by server name
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, McpTestResult>
  >({});

  // Enable/disable state
  const [togglingName, setTogglingName] = useState<string | null>(null);
  const [restartNote, setRestartNote] = useState<string | null>(null);

  // Catalog install modal state
  const [installEntry, setInstallEntry] = useState<McpCatalogEntry | null>(
    null,
  );
  const [installEnv, setInstallEnv] = useState<Record<string, string>>({});
  const [installingName, setInstallingName] = useState<string | null>(null);
  const closeInstallModal = useCallback(() => setInstallEntry(null), []);
  const installModalRef = useModalBehavior({
    open: installEntry !== null,
    onClose: closeInstallModal,
  });

  const loadServers = useCallback(() => {
    return api
      .getMcpServers()
      .then((res) => setServers(res.servers))
      .catch((e) => showToast(`Error: ${e}`, "error"));
  }, [showToast]);

  const loadCatalog = useCallback(() => {
    return api
      .getMcpCatalog()
      .then((res) => {
        setCatalog(res.entries);
        setDiagnostics(res.diagnostics);
      })
      .catch((e) => showToast(`Error: ${e}`, "error"));
  }, [showToast]);

  const loadControlCenter = useCallback(() => {
    return api
      .getMcpControlCenter()
      .then((res) => setControlCenter(res))
      .catch(() => {
        // Non-critical — control center data is supplemental.
      });
  }, []);

  useEffect(() => {
    Promise.all([loadServers(), loadCatalog(), loadControlCenter()]).finally(
      () => setLoading(false),
    );
  }, [loadServers, loadCatalog, loadControlCenter]);

  const handleCreate = async () => {
    if (!name.trim()) {
      showToast("Name required", "error");
      return;
    }
    if (transport === "http" && !url.trim()) {
      showToast("URL required", "error");
      return;
    }
    if (transport === "stdio" && !command.trim()) {
      showToast("Command required", "error");
      return;
    }
    setCreating(true);
    try {
      const body: McpServerCreate = { name: name.trim() };
      if (transport === "http") {
        body.url = url.trim();
      } else {
        body.command = command.trim();
        const argList = parseArgs(args);
        if (argList.length) body.args = argList;
      }
      const envMap = parseEnv(env);
      if (Object.keys(envMap).length) body.env = envMap;

      await api.addMcpServer(body);
      showToast("Add ✓", "success");
      setName("");
      setUrl("");
      setCommand("");
      setArgs("");
      setEnv("");
      setTransport("http");
      setCreateModalOpen(false);
      loadServers();
      loadControlCenter();
    } catch (e) {
      showToast(`Failed to add: ${e}`, "error");
    } finally {
      setCreating(false);
    }
  };

  const handleTest = async (server: McpServer | McpControlCenterServer) => {
    setTesting(server.name);
    try {
      const result = await api.testMcpServer(server.name);
      setTestResults((prev) => ({ ...prev, [server.name]: result }));
      if (result.ok) {
        showToast(`${server.name}: ${result.tools.length} tool(s)`, "success");
      } else {
        showToast(`${server.name}: ${result.error ?? "Failed"}`, "error");
      }
    } catch (e) {
      showToast(`Error: ${e}`, "error");
    } finally {
      setTesting(null);
    }
  };

  const handleToggleEnabled = async (server: McpServer) => {
    const next = !server.enabled;
    setTogglingName(server.name);
    try {
      await api.setMcpServerEnabled(server.name, next);
      setServers((prev) =>
        prev.map((s) =>
          s.name === server.name ? { ...s, enabled: next } : s,
        ),
      );
      setRestartNote(
        "Enable/disable takes effect on the next gateway restart.",
      );
      loadControlCenter();
    } catch (e) {
      showToast(`Error: ${e}`, "error");
    } finally {
      setTogglingName(null);
    }
  };

  const serverDelete = useConfirmDelete({
    onDelete: useCallback(
      async (serverName: string) => {
        try {
          await api.removeMcpServer(serverName);
          showToast(`Delete: "${truncateText(serverName, 30)}"`, "success");
          setTestResults((prev) => {
            const next = { ...prev };
            delete next[serverName];
            return next;
          });
          loadServers();
          loadControlCenter();
        } catch (e) {
          showToast(`Error: ${e}`, "error");
          throw e;
        }
      },
      [loadServers, loadControlCenter, showToast],
    ),
  });

  // ── Catalog install ──────────────────────────────────────────────────
  const runInstall = useCallback(
    async (entry: McpCatalogEntry, envMap: Record<string, string>) => {
      setInstallingName(entry.name);
      try {
        const res = await api.installMcpCatalogEntry(entry.name, envMap, true);
        if (res.background) {
          showToast("Installing in background…", "success");
        } else {
          showToast(`Installed: "${truncateText(entry.name, 30)}"`, "success");
        }
        setInstallEntry(null);
        setInstallEnv({});
        await Promise.all([loadServers(), loadCatalog(), loadControlCenter()]);
      } catch (e) {
        showToast(`Failed to install: ${e}`, "error");
      } finally {
        setInstallingName(null);
      }
    },
    [loadServers, loadCatalog, loadControlCenter, showToast],
  );

  const handleInstallClick = (entry: McpCatalogEntry) => {
    if (entry.required_env.length > 0) {
      const initial: Record<string, string> = {};
      entry.required_env.forEach((item) => {
        initial[item.name] = "";
      });
      setInstallEnv(initial);
      setInstallEntry(entry);
    } else {
      void runInstall(entry, {});
    }
  };

  const handleInstallSubmit = () => {
    if (!installEntry) return;
    const missing = installEntry.required_env.filter(
      (item) => item.required && !(installEnv[item.name] ?? "").trim(),
    );
    if (missing.length > 0) {
      showToast(`${missing[0].prompt} required`, "error");
      return;
    }
    const envMap: Record<string, string> = {};
    Object.entries(installEnv).forEach(([k, v]) => {
      if (v.trim()) envMap[k] = v.trim();
    });
    void runInstall(installEntry, envMap);
  };

  // ── Status map from control center (name → status) ──────────────────
  const ccStatusMap: Record<string, McpStatusChip> = {};
  (controlCenter?.servers ?? []).forEach((s) => {
    ccStatusMap[s.name] = s.status;
  });

  // Put "Add Server" button in page header
  useLayoutEffect(() => {
    setEnd(
      <Button
        className="uppercase"
        size="sm"
        onClick={() => setCreateModalOpen(true)}
      >
        Add Server
      </Button>,
    );
    return () => {
      setEnd(null);
    };
  }, [setEnd, loading]);

  if (loading) {
    return (
      <DeckPageShell>
        <div className="flex flex-col gap-4 p-5">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </DeckPageShell>
    );
  }

  const diagnosticsByName: Record<string, McpCatalogDiagnostic[]> = {};
  diagnostics.forEach((d) => {
    (diagnosticsByName[d.name] ??= []).push(d);
  });

  return (
    <DeckPageShell>
    <div className="flex flex-col gap-6 p-5">
      <Toast toast={toast} />

      <DeleteConfirmDialog
        open={serverDelete.isOpen}
        onCancel={serverDelete.cancel}
        onConfirm={serverDelete.confirm}
        title="Remove MCP server"
        description={
          serverDelete.pendingId
            ? `"${truncateText(serverDelete.pendingId, 40)}" — this will remove the server.`
            : "This will remove the server."
        }
        loading={serverDelete.isDeleting}
      />

      {/* Add server modal */}
      {createModalOpen && (
        <div
          ref={createModalRef}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background/85 backdrop-blur-sm p-4"
          onClick={(e) =>
            e.target === e.currentTarget && setCreateModalOpen(false)
          }
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-mcp-title"
        >
          <div
            className={cn(
              themedBody,
              "relative w-full max-w-lg border border-border bg-card shadow-2xl flex flex-col",
            )}
          >
            <Button
              ghost
              size="icon"
              onClick={() => setCreateModalOpen(false)}
              className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X />
            </Button>

            <header className="p-5 pb-3 border-b border-border">
              <h2
                id="create-mcp-title"
                className="font-mondwest text-display text-base tracking-wider"
              >
                Add MCP server
              </h2>
            </header>

            <div className="p-5 grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="mcp-name">Name</Label>
                <Input
                  id="mcp-name"
                  autoFocus
                  placeholder="my-server"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="mcp-transport">Transport</Label>
                <Select
                  id="mcp-transport"
                  value={transport}
                  onValueChange={(v) => setTransport(v as Transport)}
                >
                  <SelectOption value="http">HTTP/SSE</SelectOption>
                  <SelectOption value="stdio">stdio</SelectOption>
                </Select>
              </div>

              {transport === "http" ? (
                <div className="grid gap-2">
                  <Label htmlFor="mcp-url">URL</Label>
                  <Input
                    id="mcp-url"
                    placeholder="https://example.com/mcp"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                </div>
              ) : (
                <>
                  <div className="grid gap-2">
                    <Label htmlFor="mcp-command">Command</Label>
                    <Input
                      id="mcp-command"
                      placeholder="npx"
                      value={command}
                      onChange={(e) => setCommand(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="mcp-args">Args</Label>
                    <Input
                      id="mcp-args"
                      placeholder="-y @modelcontextprotocol/server-foo"
                      value={args}
                      onChange={(e) => setArgs(e.target.value)}
                    />
                  </div>
                </>
              )}

              <div className="grid gap-2">
                <Label htmlFor="mcp-env">Environment (KEY=VALUE per line)</Label>
                <textarea
                  id="mcp-env"
                  className="flex min-h-[80px] w-full border border-border bg-background/40 px-3 py-2 text-sm font-courier shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground/30 focus-visible:border-foreground/25"
                  placeholder={"API_KEY=secret\nDEBUG=1"}
                  value={env}
                  onChange={(e) => setEnv(e.target.value)}
                />
              </div>

              <div className="flex justify-end">
                <Button
                  className="uppercase"
                  size="sm"
                  onClick={handleCreate}
                  disabled={creating}
                  prefix={creating ? <Spinner /> : undefined}
                >
                  {creating ? "Adding..." : "Add"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Catalog install modal (required env vars) */}
      {installEntry && (
        <div
          ref={installModalRef}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background/85 backdrop-blur-sm p-4"
          onClick={(e) =>
            e.target === e.currentTarget && setInstallEntry(null)
          }
          role="dialog"
          aria-modal="true"
          aria-labelledby="install-mcp-title"
        >
          <div
            className={cn(
              themedBody,
              "relative w-full max-w-lg border border-border bg-card shadow-2xl flex flex-col",
            )}
          >
            <Button
              ghost
              size="icon"
              onClick={() => setInstallEntry(null)}
              className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X />
            </Button>

            <header className="p-5 pb-3 border-b border-border">
              <h2
                id="install-mcp-title"
                className="font-mondwest text-display text-base tracking-wider"
              >
                Install {installEntry.name}
              </h2>
            </header>

            <div className="p-5 grid gap-4">
              <p className="text-xs text-muted-foreground">
                This MCP requires the following values to be configured.
              </p>
              {installEntry.required_env.map((item) => (
                <div className="grid gap-2" key={item.name}>
                  <Label htmlFor={`install-env-${item.name}`}>
                    {item.prompt}
                    {item.required ? " *" : ""}
                  </Label>
                  <Input
                    id={`install-env-${item.name}`}
                    type="password"
                    placeholder={item.name}
                    value={installEnv[item.name] ?? ""}
                    onChange={(e) =>
                      setInstallEnv((prev) => ({
                        ...prev,
                        [item.name]: e.target.value,
                      }))
                    }
                  />
                </div>
              ))}

              <div className="flex justify-end">
                <Button
                  className="uppercase"
                  size="sm"
                  onClick={handleInstallSubmit}
                  disabled={installingName === installEntry.name}
                  prefix={
                    installingName === installEntry.name ? (
                      <Spinner />
                    ) : undefined
                  }
                >
                  {installingName === installEntry.name
                    ? "Installing..."
                    : "Install"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── MCP Control Center status banners ── */}
      {controlCenter && (
        <div className="flex flex-col gap-1">
          <BitwardenBanner bw={controlCenter.bitwarden} />
          <GatewayBanner running={controlCenter.gateway_running} />
        </div>
      )}

      {/* ── Your MCP servers ── */}
      <div className="flex flex-col gap-3">
        <Toolbar
          left={
            <span className="flex items-center gap-2 text-[var(--dsd-text-xs)] font-[var(--dsd-fw-semibold)] uppercase tracking-wider text-[var(--dsd-text-dim)]">
              <Server className="h-4 w-4" />
              Your MCP servers ({servers.length})
            </span>
          }
          right={
            controlCenter ? (
              <Button
                ghost
                size="sm"
                onClick={() => loadControlCenter()}
                className="uppercase"
                prefix={<RefreshCw className="h-3.5 w-3.5" />}
              >
                Refresh status
              </Button>
            ) : undefined
          }
        />

        {restartNote && (
          <p className="text-xs text-warning">{restartNote}</p>
        )}

        {servers.length === 0 && (
          <EmptyState
            icon={<Server className="h-6 w-6" />}
            title="No MCP servers configured"
            description="Add a server to connect an MCP endpoint to your agent."
            compact
          />
        )}

        {servers.map((server) => {
          const envCount = Object.keys(server.env ?? {}).length;
          const result = testResults[server.name];
          const statusChip = ccStatusMap[server.name] ?? (
            server.enabled ? undefined : "DISABLED"
          );

          return (
            <Card key={server.name}>
              <CardContent
                className={cn(
                  "flex items-start gap-4 py-4",
                  !server.enabled && "opacity-60",
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium text-sm truncate">
                      {server.name}
                    </span>
                    <StatusPill
                      variant={TRANSPORT_VARIANT[server.transport] ?? "neutral"}
                      label={server.transport}
                    />
                    {statusChip && <StatusChip status={statusChip} />}
                    {!server.enabled && !statusChip && (
                      <StatusPill variant="neutral" label="disabled" />
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    {server.transport === "http" ? (
                      <span className="font-mono truncate">
                        {server.url ?? "—"}
                      </span>
                    ) : (
                      <span className="font-mono truncate">
                        {[server.command, ...(server.args ?? [])]
                          .filter(Boolean)
                          .join(" ") || "—"}
                      </span>
                    )}
                    {envCount > 0 && (
                      <span>
                        {envCount} env var{envCount === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                  {result && (
                    <div className="mt-2 text-xs">
                      {result.ok ? (
                        <p className="text-success">
                          {result.tools.length === 0
                            ? "Connected — no tools"
                            : `Tools: ${result.tools
                                .map((tool) => tool.name)
                                .join(", ")}`}
                        </p>
                      ) : (
                        <p className="text-destructive">
                          {result.error ?? "Connection failed"}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    ghost
                    size="sm"
                    title={server.enabled ? "Disable" : "Enable"}
                    aria-label={server.enabled ? "Disable" : "Enable"}
                    onClick={() => handleToggleEnabled(server)}
                    disabled={togglingName === server.name}
                    prefix={
                      togglingName === server.name ? (
                        <Spinner />
                      ) : (
                        <Power />
                      )
                    }
                    className={server.enabled ? "text-success" : undefined}
                  >
                    {server.enabled ? "Disable" : "Enable"}
                  </Button>

                  <Button
                    ghost
                    size="icon"
                    title="Test connection"
                    aria-label="Test connection"
                    onClick={() => handleTest(server)}
                    disabled={testing === server.name}
                  >
                    {testing === server.name ? <Spinner /> : <Zap />}
                  </Button>

                  <Button
                    ghost
                    destructive
                    size="icon"
                    title="Delete"
                    aria-label="Delete"
                    onClick={() => serverDelete.requestDelete(server.name)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* ── Catalog ── */}
      <div className="flex flex-col gap-3">
        <Toolbar
          left={
            <span className="flex items-center gap-2 text-[var(--dsd-text-xs)] font-[var(--dsd-fw-semibold)] uppercase tracking-wider text-[var(--dsd-text-dim)]">
              <Package className="h-4 w-4" />
              Catalog ({catalog.length})
            </span>
          }
        />

        <p className="text-xs text-muted-foreground">
          Browse Nous-approved MCP servers and install them with one click.
        </p>

        {catalog.length === 0 && (
          <EmptyState
            icon={<Package className="h-6 w-6" />}
            title="No catalog entries available"
            description="The MCP catalog is empty or could not be loaded."
            compact
          />
        )}

        {catalog.map((entry) => {
          const entryDiags = diagnosticsByName[entry.name] ?? [];
          const isInstalling = installingName === entry.name;
          const ccEntry = controlCenter?.catalog.find(
            (c) => c.name === entry.name,
          );

          return (
            <Card key={entry.name}>
              <CardContent className="flex items-start gap-4 py-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium text-sm truncate">
                      {entry.name}
                    </span>
                    <StatusPill
                      variant={TRANSPORT_VARIANT[entry.transport] ?? "neutral"}
                      label={entry.transport}
                    />
                    <StatusPill variant="neutral" label={`auth: ${entry.auth_type}`} />
                    {ccEntry?.status && (
                      <StatusChip status={ccEntry.status} />
                    )}
                    {isHttpUrl(entry.source) ? (
                      <a
                        href={entry.source}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary underline underline-offset-2 hover:opacity-80"
                      >
                        source ↗
                      </a>
                    ) : (
                      entry.source && (
                        <StatusPill variant="neutral" label={entry.source} />
                      )
                    )}
                    {entry.installed && (
                      <StatusPill variant="success" label="Installed" />
                    )}
                    {entry.installed && !entry.enabled && (
                      <StatusPill variant="neutral" label="disabled" />
                    )}
                  </div>
                  {entry.description && (
                    <p className="text-xs text-muted-foreground">
                      {entry.description}
                    </p>
                  )}
                  {/* Required credentials list (names only, no values) */}
                  {entry.required_env.length > 0 && (
                    <p className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
                      <Key className="h-3 w-3 shrink-0" />
                      Requires:{" "}
                      {entry.required_env
                        .map((e) => e.name)
                        .join(", ")}
                    </p>
                  )}
                  {/* Connection detail */}
                  {entry.transport === "http" && entry.url && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      <span className="font-medium">Endpoint:</span>{" "}
                      <code className="font-mono">{entry.url}</code>
                    </p>
                  )}
                  {entry.transport === "stdio" && entry.command && (
                    <p className="mt-1 text-xs text-muted-foreground break-all">
                      <span className="font-medium">Runs:</span>{" "}
                      <code className="font-mono">
                        {[entry.command, ...entry.args].join(" ")}
                      </code>
                    </p>
                  )}
                  {entry.install_url && (
                    <p className="mt-1 text-xs text-muted-foreground break-all">
                      <span className="font-medium">Installs from:</span>{" "}
                      {isHttpUrl(entry.install_url) ? (
                        <a
                          href={entry.install_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary underline underline-offset-2 hover:opacity-80"
                        >
                          {entry.install_url}
                        </a>
                      ) : (
                        <code className="font-mono">{entry.install_url}</code>
                      )}
                      {entry.install_ref && (
                        <span> @ {entry.install_ref}</span>
                      )}
                    </p>
                  )}
                  {entry.bootstrap.length > 0 && (
                    <details className="mt-1 text-xs text-muted-foreground">
                      <summary className="cursor-pointer select-none">
                        Bootstrap commands ({entry.bootstrap.length})
                      </summary>
                      <ul className="mt-1 ml-3 list-disc space-y-0.5">
                        {entry.bootstrap.map((cmd, i) => (
                          <li key={`${entry.name}-bs-${i}`} className="break-all">
                            <code className="font-mono">{cmd}</code>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {entry.post_install && (
                    <details className="mt-1 text-xs text-muted-foreground">
                      <summary className="cursor-pointer select-none">
                        Setup notes
                      </summary>
                      <p className="mt-1 whitespace-pre-wrap">
                        {entry.post_install.trim()}
                      </p>
                    </details>
                  )}
                  {entryDiags.map((d, i) => (
                    <p
                      key={`${entry.name}-diag-${i}`}
                      className="text-xs text-warning mt-1"
                    >
                      {d.message}
                    </p>
                  ))}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {entry.installed ? (
                    <StatusPill variant="success" label="Installed" />
                  ) : (
                    <Button
                      className="uppercase"
                      size="sm"
                      onClick={() => handleInstallClick(entry)}
                      disabled={isInstalling}
                      prefix={isInstalling ? <Spinner /> : undefined}
                    >
                      {isInstalling ? "Installing..." : "Install"}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
    </DeckPageShell>
  );
}
