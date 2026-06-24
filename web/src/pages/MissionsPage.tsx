import { useCallback, useEffect, useLayoutEffect, useMemo, useState, memo } from "react";
import { useNavigate } from "react-router-dom";
import { LayoutTemplate, Plus, RefreshCw, Target } from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type {
  MissionRow,
  MissionDetailResponse,
  MissionTask,
  MissionDelegationNode,
  MissionTimelineEvent,
  MissionTopRun,
  TemplateRow,
} from "@/lib/api";
import { DeckPageShell } from "@/components/DeckPageShell";
import { DeckCard, DeckBtn, MetricTile } from "@/components/DeckOps";
import { StatusPill } from "@/components/ds/StatusPill";
import type { StatusVariant } from "@/components/ds/StatusPill";
import { DataTable } from "@/components/ds/DataTable";
import type { ColDef } from "@/components/ds/DataTable";
import { Drawer } from "@/components/ds/Drawer";
import { EmptyState, ErrorState, SkeletonTable } from "@/components/ds";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";

// ── Helpers ────────────────────────────────────────────────────────────────────

function missionStatusVariant(status: string): StatusVariant {
  const s = status.toLowerCase();
  if (s === "done" || s === "completed" || s === "closed") return "success";
  if (s === "in_progress" || s === "active" || s === "running") return "info";
  if (s === "blocked" || s === "error" || s === "failed") return "error";
  if (s === "paused" || s === "waiting") return "warning";
  return "neutral";
}

function taskStatusVariant(status: string): StatusVariant {
  const s = status.toLowerCase();
  if (s === "done") return "success";
  if (s === "in_progress") return "info";
  if (s === "blocked") return "error";
  return "neutral";
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n === 0) return "$0.00";
  if (n < 0.0001) return "<$0.0001";
  return `$${n.toFixed(4)}`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtRelTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return iso;
  }
}

/** Build depth map for delegation tree using parent_session_id */
function buildDelegationDepth(
  nodes: MissionDelegationNode[],
): Map<string, number> {
  const depthMap = new Map<string, number>();
  const parentMap = new Map<string, string | null>();
  const ids = new Set(nodes.map((n) => n.session_id));
  for (const n of nodes) {
    parentMap.set(n.session_id, n.parent_session_id);
  }

  function getDepth(id: string, visited = new Set<string>()): number {
    if (depthMap.has(id)) return depthMap.get(id)!;
    if (visited.has(id)) { depthMap.set(id, 0); return 0; }
    visited.add(id);
    const parent = parentMap.get(id);
    if (!parent || !ids.has(parent)) { depthMap.set(id, 0); return 0; }
    const d = getDepth(parent, visited) + 1;
    depthMap.set(id, d);
    return d;
  }
  for (const n of nodes) getDepth(n.session_id);
  return depthMap;
}

// ── Progress bar ───────────────────────────────────────────────────────────────

function ProgressBar({ pct, done, total }: { pct: number; done: number; total: number }) {
  const clamped = Math.min(100, Math.max(0, pct));
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div
        className="flex-1 min-w-0 h-1.5 rounded-full bg-[var(--dsd-layer-overlay)] overflow-hidden"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        role="progressbar"
      >
        <div
          className="h-full rounded-full bg-[var(--dsd-cat-mission)] transition-[width] duration-300"
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="text-xs text-[var(--dsd-text-faint)] tabular-nums shrink-0">
        {done}/{total}
      </span>
    </div>
  );
}

// ── Model chips ────────────────────────────────────────────────────────────────

function ModelChips({ models }: { models: string[] }) {
  if (!models.length) return <span className="text-xs text-[var(--dsd-text-faint)]">—</span>;
  const shown = models.slice(0, 3);
  const rest = models.length - shown.length;
  return (
    <span className="flex flex-wrap gap-1 min-w-0">
      {shown.map((m) => (
        <span
          key={m}
          className="inline-block rounded px-1.5 py-0.5 text-[9px] font-medium tracking-wide uppercase border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-secondary)] bg-[var(--dsd-layer-overlay)]"
        >
          {m.split("/").pop() ?? m}
        </span>
      ))}
      {rest > 0 && (
        <span className="inline-block rounded px-1.5 py-0.5 text-[9px] text-[var(--dsd-text-faint)]">
          +{rest}
        </span>
      )}
    </span>
  );
}

// ── Mission table column definitions ──────────────────────────────────────────

function buildMissionCols(
  onSelect: (m: MissionRow) => void,
): ColDef<MissionRow>[] {
  return [
    {
      key: "mission",
      header: "Mission",
      sortKey: "title",
      width: "240px",
      cell: (m) => (
        <span
          className="block cursor-pointer"
          onClick={() => onSelect(m)}
        >
          <span className="block truncate text-sm font-medium text-[var(--dsd-text-primary)]">
            {m.title}
          </span>
          <span className="block truncate text-[11px] text-[var(--dsd-text-faint)]">
            {m.owner ?? m.board_slug}
          </span>
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortKey: "status",
      cell: (m) => (
        <StatusPill
          variant={missionStatusVariant(m.status)}
          label={m.status}
          dot
        />
      ),
    },
    {
      key: "progress",
      header: "Progress",
      width: "140px",
      cell: (m) => (
        <ProgressBar
          pct={m.progress.pct}
          done={m.progress.done}
          total={m.progress.total}
        />
      ),
    },
    {
      key: "models",
      header: "Models",
      width: "180px",
      cell: (m) => <ModelChips models={m.models} />,
    },
    {
      key: "cost",
      header: "Spend",
      sortKey: "cost_usd",
      align: "right",
      cell: (m) => (
        <span className="tabular-nums text-sm text-[var(--dsd-cat-cost)]">
          {fmtUsd(m.cost_usd)}
        </span>
      ),
    },
    {
      key: "runs",
      header: "Runs",
      sortKey: "run_count",
      align: "right",
      cell: (m) => (
        <span className="tabular-nums text-xs text-[var(--dsd-text-secondary)]">
          {m.run_count}
        </span>
      ),
    },
    {
      key: "updated",
      header: "Updated",
      align: "right",
      cell: (m) => (
        <span className="text-xs text-[var(--dsd-text-faint)]">
          {fmtRelTime(m.updated_at)}
        </span>
      ),
    },
  ];
}

// ── Mission detail drawer ──────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold tracking-widest uppercase text-[var(--dsd-text-faint)] mb-1.5 mt-4 first:mt-0">
      {children}
    </div>
  );
}

function DelegationTreeRows({
  nodes,
  navigate,
  onClose,
}: {
  nodes: MissionDelegationNode[];
  navigate: ReturnType<typeof useNavigate>;
  onClose: () => void;
}) {
  const depthMap = useMemo(() => buildDelegationDepth(nodes), [nodes]);
  const sorted = useMemo(() => [...nodes].sort((a, b) => {
    const da = depthMap.get(a.session_id) ?? 0;
    const db = depthMap.get(b.session_id) ?? 0;
    return da - db;
  }), [nodes, depthMap]);

  return (
    <div className="flex flex-col gap-0.5">
      {sorted.map((node) => {
        const depth = depthMap.get(node.session_id) ?? 0;
        return (
          <div
            key={node.session_id}
            className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-[var(--dsd-layer-overlay)] transition-colors group"
            style={{ paddingLeft: `${8 + depth * 16}px` }}
          >
            {depth > 0 && (
              <span
                aria-hidden
                className="shrink-0 h-3 w-px bg-[var(--dsd-border-subtle)] mr-1"
              />
            )}
            <StatusPill
              variant={
                node.status === "ok"
                  ? "success"
                  : node.status === "error"
                    ? "error"
                    : node.status === "running"
                      ? "info"
                      : "neutral"
              }
              label={node.status}
              dot
              size="sm"
            />
            <span className="flex-1 min-w-0 text-xs text-[var(--dsd-text-secondary)] truncate">
              {node.agent ?? node.session_id.slice(0, 12)}
              {node.model ? (
                <span className="ml-1 text-[var(--dsd-text-faint)]">
                  · {node.model.split("/").pop()}
                </span>
              ) : null}
            </span>
            {node.cost_usd != null && (
              <span className="text-[10px] tabular-nums text-[var(--dsd-cat-cost)] shrink-0">
                {fmtUsd(node.cost_usd)}
              </span>
            )}
            <button
              type="button"
              className="text-[10px] text-[var(--dsd-cat-trace)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0 hover:underline focus-visible:opacity-100"
              onClick={() => {
                navigate(`/traces?session=${encodeURIComponent(node.session_id)}`);
                onClose();
              }}
              aria-label={`View trace for ${node.agent ?? node.session_id.slice(0, 12)}`}
            >
              trace →
            </button>
          </div>
        );
      })}
    </div>
  );
}

function TimelineEvents({ events }: { events: MissionTimelineEvent[] }) {
  if (!events.length) {
    return <p className="text-xs text-[var(--dsd-text-faint)] py-2">No timeline events.</p>;
  }
  return (
    <div className="flex flex-col gap-1">
      {events.map((ev, i) => (
        <div key={i} className="flex items-start gap-2 text-xs">
          <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-[var(--dsd-cat-trace)] opacity-70" aria-hidden />
          <span className="flex-1 min-w-0 text-[var(--dsd-text-secondary)]">{ev.label}</span>
          <span className="shrink-0 text-[var(--dsd-text-faint)]">{fmtRelTime(ev.ts)}</span>
        </div>
      ))}
    </div>
  );
}

function TopRunsList({
  runs,
  navigate,
  onClose,
}: {
  runs: MissionTopRun[];
  navigate: ReturnType<typeof useNavigate>;
  onClose: () => void;
}) {
  if (!runs.length) {
    return <p className="text-xs text-[var(--dsd-text-faint)] py-2">No runs recorded.</p>;
  }
  return (
    <div className="flex flex-col gap-0.5">
      {runs.map((run) => (
        <div key={run.session_id} className="flex items-center gap-2 text-xs group rounded px-1 py-1 hover:bg-[var(--dsd-layer-overlay)]">
          <StatusPill
            variant={
              run.status === "ok" ? "success" : run.status === "error" ? "error" : "info"
            }
            label={run.status}
            dot
            size="sm"
          />
          <span className="flex-1 min-w-0 text-[var(--dsd-text-secondary)] truncate font-mono text-[10px]">
            {run.session_id.slice(0, 16)}…
          </span>
          <span className="tabular-nums text-[var(--dsd-cat-cost)] shrink-0">
            {fmtUsd(run.cost_usd)}
          </span>
          <button
            type="button"
            className="text-[10px] text-[var(--dsd-cat-trace)] opacity-0 group-hover:opacity-100 transition-opacity hover:underline focus-visible:opacity-100"
            onClick={() => {
              navigate(`/traces?session=${encodeURIComponent(run.session_id)}`);
              onClose();
            }}
            aria-label={`View trace for run ${run.session_id.slice(0, 16)}`}
          >
            trace →
          </button>
        </div>
      ))}
    </div>
  );
}

function TaskList({
  tasks,
  navigate,
  onClose,
}: {
  tasks: MissionTask[];
  navigate: ReturnType<typeof useNavigate>;
  onClose: () => void;
}) {
  if (!tasks.length) {
    return <p className="text-xs text-[var(--dsd-text-faint)] py-2">No tasks found.</p>;
  }
  return (
    <div className="flex flex-col gap-0.5">
      {tasks.map((task) => (
        <div
          key={task.id}
          className="flex items-center gap-2 rounded px-1 py-1.5 text-xs hover:bg-[var(--dsd-layer-overlay)] transition-colors group"
        >
          <StatusPill variant={taskStatusVariant(task.status)} label={task.status} dot size="sm" />
          <span className="flex-1 min-w-0 text-[var(--dsd-text-secondary)] truncate">
            {task.title}
          </span>
          {task.assignee && (
            <span className="text-[10px] text-[var(--dsd-text-faint)] shrink-0">
              @{task.assignee}
            </span>
          )}
          {task.session_id && (
            <button
              type="button"
              className="text-[10px] text-[var(--dsd-cat-trace)] opacity-0 group-hover:opacity-100 transition-opacity hover:underline shrink-0 focus-visible:opacity-100"
              onClick={() => {
                navigate(`/sessions`);
                onClose();
              }}
              aria-label={`View session for task ${task.title}`}
            >
              session →
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Detail drawer ──────────────────────────────────────────────────────────────

function MissionDetailDrawer({
  mission,
  open,
  onClose,
}: {
  mission: MissionRow | null;
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState<MissionDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mission || !open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);
    api
      .getMission(mission.mission_id)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mission, open]);

  const drawerFooter = mission ? (
    <div className="flex gap-2 flex-wrap">
      <button
        type="button"
        className="deck-btn-sm"
        onClick={() => { navigate(`/costs`); onClose(); }}
      >
        Spend →
      </button>
      <button
        type="button"
        className="deck-btn-sm"
        onClick={() => { navigate(`/traces`); onClose(); }}
      >
        Runs →
      </button>
    </div>
  ) : null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={mission?.title ?? "Mission"}
      width={520}
      footer={drawerFooter}
    >
      {loading && (
        <div className="flex items-center gap-2 py-8 text-sm text-[var(--dsd-text-secondary)]">
          <Spinner />
          Loading mission detail…
        </div>
      )}
      {error && (
        <div className="py-6 text-sm text-[var(--dsd-sem-critical)]">
          {error}
        </div>
      )}
      {mission && !loading && !error && (
        <div className="flex flex-col gap-0">
          {/* Header KPIs */}
          <div className="flex flex-wrap gap-3 pb-4 border-b border-[var(--dsd-border-subtle)] mb-2">
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-widest">Status</span>
              <StatusPill variant={missionStatusVariant(mission.status)} label={mission.status} dot />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-widest">Progress</span>
              <span className="text-sm font-mono text-[var(--dsd-text-primary)]">
                {mission.progress.done}/{mission.progress.total} ({Math.round(mission.progress.pct)}%)
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-widest">Cost</span>
              <span className="text-sm font-mono text-[var(--dsd-cat-cost)]">{fmtUsd(mission.cost_usd)}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-widest">Tokens</span>
              <span className="text-sm font-mono text-[var(--dsd-text-secondary)]">{fmtTokens(mission.total_tokens)}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-widest">Runs</span>
              <span className="text-sm font-mono text-[var(--dsd-text-secondary)]">{mission.run_count}</span>
            </div>
          </div>

          {detail ? (
            <>
              {/* Tasks */}
              <SectionTitle>Tasks ({detail.tasks.length})</SectionTitle>
              <TaskList tasks={detail.tasks} navigate={navigate} onClose={onClose} />

              {/* Delegation tree */}
              <SectionTitle>
                Delegation Tree ({detail.delegation_tree.length} agents)
              </SectionTitle>
              {detail.delegation_tree.length > 0 ? (
                <DelegationTreeRows
                  nodes={detail.delegation_tree}
                  navigate={navigate}
                  onClose={onClose}
                />
              ) : (
                <p className="text-xs text-[var(--dsd-text-faint)] py-2">No delegations recorded.</p>
              )}

              {/* Timeline */}
              <SectionTitle>Timeline</SectionTitle>
              <TimelineEvents events={detail.timeline} />

              {/* Top runs */}
              <SectionTitle>Most Expensive Runs</SectionTitle>
              <TopRunsList runs={detail.top_runs} navigate={navigate} onClose={onClose} />
            </>
          ) : null}
        </div>
      )}
    </Drawer>
  );
}

// ── Empty / Error / Skeleton ───────────────────────────────────────────────────

function MissionsSkeleton() {
  return (
    <DeckPageShell>
      <div className="flex flex-col gap-4 py-4">
        <SkeletonTable rows={6} cols={7} />
      </div>
    </DeckPageShell>
  );
}

function MissionsError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <DeckPageShell>
      <ErrorState
        title="Failed to load missions"
        message={message}
        onRetry={onRetry}
      />
    </DeckPageShell>
  );
}

function MissionsEmpty() {
  return (
    <DeckPageShell>
      <EmptyState
        icon={<Target className="h-8 w-8" />}
        title="No missions yet"
        description="Create a Kanban board and link it to a mission to start tracking objectives, costs, and agent delegation."
      />
    </DeckPageShell>
  );
}

// ── Summary strip ──────────────────────────────────────────────────────────────

function MissionsSummaryStrip({ missions }: { missions: MissionRow[] }) {
  const { active, totalCost, totalRuns } = useMemo(() => ({
    active: missions.filter(
      (m) =>
        m.status.toLowerCase() === "in_progress" ||
        m.status.toLowerCase() === "active" ||
        m.status.toLowerCase() === "running",
    ).length,
    totalCost: missions.reduce((s, m) => s + (m.cost_usd ?? 0), 0),
    totalRuns: missions.reduce((s, m) => s + m.run_count, 0),
  }), [missions]);

  return (
    <div className="metrics-strip col-12">
      <MetricTile label="Total Missions" value={String(missions.length)} state="ok" />
      <MetricTile
        label="Active"
        value={String(active)}
        state={active > 0 ? "ok" : undefined}
      />
      <MetricTile
        label="Total Spend"
        value={fmtUsd(totalCost)}
        state="ok"
        context="across all missions"
      />
      <MetricTile
        label="Total Runs"
        value={String(totalRuns)}
        state="ok"
      />
    </div>
  );
}

// ── Templates Drawer (Wave 6) ─────────────────────────────────────────────────

interface TemplatesDrawerProps {
  open: boolean;
  onClose: () => void;
}

function TemplatesDrawer({ open, onClose }: TemplatesDrawerProps) {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TemplateRow | null>(null);
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getTemplates()
      .then((r) => setTemplates(r.templates))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  function handleClose() {
    setSelected(null);
    setTitle("");
    setSubmitError(null);
    onClose();
  }

  async function handleInstantiate() {
    if (!selected) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await api.instantiateTemplate(selected.id, title ? { title } : undefined);
      handleClose();
      navigate(`/missions?mission=${encodeURIComponent(result.mission_id)}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Drawer open={open} onClose={handleClose} title="New Mission from Template" width={480}>
      <div className="flex flex-col gap-4 p-1">
        {loading && <SkeletonTable rows={3} cols={1} />}
        {error && <ErrorState error={new Error(error)} onRetry={load} />}
        {!loading && !error && templates.length === 0 && (
          <EmptyState
            icon="📋"
            title="No templates available"
            description="Ask an admin to create mission templates."
          />
        )}
        {!loading && !error && templates.length > 0 && (
          <div className="flex flex-col gap-2">
            {templates.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelected(selected?.id === t.id ? null : t)}
                className={cn(
                  "text-left rounded-lg border p-3 transition-colors focus-visible:outline-none focus-visible:ring-2",
                  selected?.id === t.id
                    ? "border-[var(--dsd-accent-primary)] bg-[var(--dsd-layer-overlay)]"
                    : "border-[var(--dsd-border-subtle)] hover:border-[var(--dsd-border-emphasis)] bg-[var(--dsd-layer-surface)]",
                )}
              >
                <p className="text-sm font-semibold text-[var(--dsd-text-primary)]">{t.name}</p>
                <p className="text-xs text-[var(--dsd-text-secondary)] mt-0.5">{t.description}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--dsd-layer-overlay)] border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-faint)]">
                    board: {t.creates.board}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--dsd-layer-overlay)] border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-faint)]">
                    {t.creates.tasks_count} tasks
                  </span>
                  {t.creates.cron && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--dsd-layer-overlay)] border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-faint)]">
                      cron: {t.creates.cron}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}

        {selected && (
          <div className="flex flex-col gap-2 pt-2 border-t border-[var(--dsd-border-subtle)]">
            <label className="text-xs font-medium text-[var(--dsd-text-secondary)]">
              Mission title (optional)
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={selected.name}
              className="rounded border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] px-3 py-1.5 text-sm text-[var(--dsd-text-primary)] placeholder:text-[var(--dsd-text-faint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--dsd-border-focus)]"
            />
            {submitError && (
              <p className="text-xs text-[var(--dsd-status-error)]">{submitError}</p>
            )}
            <DeckBtn
              onClick={handleInstantiate}
              disabled={submitting}
              className="mt-1"
            >
              {submitting ? <Spinner className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
              Create Mission
            </DeckBtn>
          </div>
        )}
      </div>
    </Drawer>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function MissionsPage() {
  const navigate = useNavigate();
  const { setEnd } = usePageHeader();
  const [missions, setMissions] = useState<MissionRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MissionRow | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [templatesOpen, setTemplatesOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.getMissions({ limit: 100 });
      setMissions(resp.missions);
      setTotal(resp.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useLayoutEffect(() => {
    setEnd(
      <div className="flex items-center gap-2">
        <DeckBtn onClick={() => navigate("/missions/builder")}>
          <LayoutTemplate className="h-3.5 w-3.5" />
          Build Mission
        </DeckBtn>
        <DeckBtn onClick={() => setTemplatesOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          New Mission
        </DeckBtn>
        <DeckBtn onClick={load} disabled={loading} ghost>
          {loading ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Refresh
        </DeckBtn>
      </div>,
    );
    return () => setEnd(null);
  }, [loading, load, navigate, setEnd, setTemplatesOpen]);

  const openMission = useCallback((m: MissionRow) => {
    setSelected(m);
    setDrawerOpen(true);
  }, []);

  const missionCols = useMemo(() => buildMissionCols(openMission), [openMission]);

  if (loading && !missions.length) return <MissionsSkeleton />;
  if (error) return <MissionsError message={error} onRetry={load} />;
  if (!missions.length) return <MissionsEmpty />;

  return (
    <>
      <DeckPageShell>
        <div className="flex flex-col gap-5 py-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-[var(--dsd-text-h2)] font-semibold tracking-[-0.01em] text-[var(--dsd-text-primary)]">
              Missions
            </h1>
            <p className="text-sm text-[var(--dsd-text-secondary)]">
              {total} mission{total !== 1 ? "s" : ""} · click a row to drill into tasks, delegation tree, and cost.
            </p>
          </div>

          <MissionsSummaryStrip missions={missions} />

          <DeckCard title="All Missions" colClass="col-12">
            <DataTable<MissionRow>
              cols={missionCols}
              rows={missions}
              rowKey={(m) => m.mission_id}
              onRowClick={openMission}
              dense
              quickFilter
              filterPlaceholder="Filter missions…"
              aria-label="All missions"
              emptyLabel="No missions found"
            />
          </DeckCard>
        </div>
      </DeckPageShell>

      <MissionDetailDrawer
        mission={selected}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />

      <TemplatesDrawer
        open={templatesOpen}
        onClose={() => setTemplatesOpen(false)}
      />
    </>
  );
}
