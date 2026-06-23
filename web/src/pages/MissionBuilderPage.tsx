/**
 * Wave 9 — Mission Builder
 *
 * Lets operators compose a mission before running it:
 *   1. Pick a starting template (7 built-ins) OR start blank
 *   2. Edit name / objective / board
 *   3. Build an ordered step list with per-step assignee + model tier
 *   4. Review a transparent cost ESTIMATE (heuristic, clearly labeled)
 *   5. Save as a custom template OR instantiate the mission directly
 */
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  ChevronRight,
  CirclePlus,
  Hammer,
  Info,
  LayoutTemplate,
  Minus,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type { TemplateRow, FullTemplateResponse } from "@/lib/api";
import { DeckPageShell } from "@/components/DeckPageShell";
import { DeckBtn } from "@/components/DeckOps";
import { EmptyState, ErrorState, SkeletonTable } from "@/components/ds";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";

// ── Cost estimate constants ────────────────────────────────────────────────────

const MODEL_TIERS = ["fast", "balanced", "high", "custom"] as const;
type ModelTier = (typeof MODEL_TIERS)[number];

/** Default $/1M tokens rates (input / output). These are transparent estimates. */
const DEFAULT_RATES: Record<ModelTier, { inputPerM: number; outputPerM: number }> = {
  fast:     { inputPerM: 0.10,  outputPerM: 0.30 },
  balanced: { inputPerM: 0.50,  outputPerM: 1.50 },
  high:     { inputPerM: 3.00,  outputPerM: 15.00 },
  custom:   { inputPerM: 1.00,  outputPerM: 3.00 },
};

const DEFAULT_EST_INPUT  = 5_000;
const DEFAULT_EST_OUTPUT = 2_000;

// ── Draft types ────────────────────────────────────────────────────────────────

interface DraftStep {
  id: string;
  title: string;
  description: string;
  assignee: string;
  modelTier: ModelTier;
  estInputTokens: number;
  estOutputTokens: number;
}

interface MissionDraft {
  name: string;
  objective: string;
  board: string;
  steps: DraftStep[];
}

function makeBlankStep(overrides?: Partial<DraftStep>): DraftStep {
  return {
    id: Math.random().toString(36).slice(2),
    title: "",
    description: "",
    assignee: "",
    modelTier: "balanced",
    estInputTokens: DEFAULT_EST_INPUT,
    estOutputTokens: DEFAULT_EST_OUTPUT,
    ...overrides,
  };
}

function blankDraft(): MissionDraft {
  return { name: "", objective: "", board: "", steps: [] };
}

// ── Draft reducer ──────────────────────────────────────────────────────────────

type DraftAction =
  | { type: "RESET"; draft: MissionDraft }
  | { type: "SET_NAME"; value: string }
  | { type: "SET_OBJECTIVE"; value: string }
  | { type: "SET_BOARD"; value: string }
  | { type: "ADD_STEP" }
  | { type: "REMOVE_STEP"; id: string }
  | { type: "MOVE_UP"; id: string }
  | { type: "MOVE_DOWN"; id: string }
  | { type: "UPDATE_STEP"; id: string; patch: Partial<DraftStep> };

function draftReducer(state: MissionDraft, action: DraftAction): MissionDraft {
  switch (action.type) {
    case "RESET":
      return action.draft;
    case "SET_NAME":
      return { ...state, name: action.value };
    case "SET_OBJECTIVE":
      return { ...state, objective: action.value };
    case "SET_BOARD":
      return { ...state, board: action.value };
    case "ADD_STEP":
      return { ...state, steps: [...state.steps, makeBlankStep()] };
    case "REMOVE_STEP":
      return { ...state, steps: state.steps.filter((s) => s.id !== action.id) };
    case "MOVE_UP": {
      const idx = state.steps.findIndex((s) => s.id === action.id);
      if (idx <= 0) return state;
      const steps = [...state.steps];
      [steps[idx - 1], steps[idx]] = [steps[idx], steps[idx - 1]];
      return { ...state, steps };
    }
    case "MOVE_DOWN": {
      const idx = state.steps.findIndex((s) => s.id === action.id);
      if (idx < 0 || idx >= state.steps.length - 1) return state;
      const steps = [...state.steps];
      [steps[idx], steps[idx + 1]] = [steps[idx + 1], steps[idx]];
      return { ...state, steps };
    }
    case "UPDATE_STEP":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.id === action.id ? { ...s, ...action.patch } : s,
        ),
      };
    default:
      return state;
  }
}

// ── Formatting helpers ─────────────────────────────────────────────────────────

function fmtEstCost(usd: number): string {
  if (usd < 0.0001) return "<$0.0001";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function computeStepCost(
  step: DraftStep,
  customRate: { inputPerM: number; outputPerM: number },
): number {
  const rates = step.modelTier === "custom" ? customRate : DEFAULT_RATES[step.modelTier];
  return (
    (step.estInputTokens  / 1_000_000) * rates.inputPerM +
    (step.estOutputTokens / 1_000_000) * rates.outputPerM
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[11px] font-semibold tracking-widest uppercase text-[var(--dsd-text-faint)] mb-3 mt-0">
      {children}
    </h2>
  );
}

function InputField({
  label,
  id,
  value,
  onChange,
  placeholder,
  multiline,
  required,
}: {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
  required?: boolean;
}) {
  const cls =
    "w-full rounded border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] px-3 py-1.5 text-sm text-[var(--dsd-text-primary)] placeholder:text-[var(--dsd-text-faint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--dsd-border-focus)]";
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-[var(--dsd-text-secondary)]">
        {label}
        {required && <span className="ml-0.5 text-[var(--dsd-sem-critical)]">*</span>}
      </label>
      {multiline ? (
        <textarea
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={3}
          className={cn(cls, "resize-y")}
          aria-required={required}
        />
      ) : (
        <input
          id={id}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cls}
          aria-required={required}
        />
      )}
    </div>
  );
}

// ── Template picker ────────────────────────────────────────────────────────────

interface TemplatePickerProps {
  onPick: (template: FullTemplateResponse | null) => void;
}

function TemplatePicker({ onPick }: TemplatePickerProps) {
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTemplates()
      .then((r) => setTemplates(r.templates))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function handlePick(id: string) {
    setLoadingId(id);
    try {
      const full = await api.getTemplateDetail(id);
      onPick(full);
    } catch {
      // fall back to blank if detail fetch fails
      onPick(null);
    } finally {
      setLoadingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <SectionHeading>Start from a template</SectionHeading>

      {loading && <SkeletonTable rows={3} cols={1} />}
      {error && (
        <ErrorState
          error={new Error(error)}
          onRetry={() => {
            setError(null);
            setLoading(true);
            api
              .getTemplates()
              .then((r) => setTemplates(r.templates))
              .catch((e) => setError(e instanceof Error ? e.message : String(e)))
              .finally(() => setLoading(false));
          }}
        />
      )}

      {!loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {/* Blank option */}
          <button
            type="button"
            onClick={() => onPick(null)}
            className="text-left rounded-lg border border-dashed border-[var(--dsd-border-subtle)] p-3 hover:border-[var(--dsd-border-emphasis)] transition-colors focus-visible:outline-none focus-visible:ring-2"
          >
            <p className="text-sm font-semibold text-[var(--dsd-text-primary)] flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 opacity-60" />
              Start blank
            </p>
            <p className="text-xs text-[var(--dsd-text-faint)] mt-0.5">
              Build a mission from scratch
            </p>
          </button>

          {templates.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => void handlePick(t.id)}
              disabled={loadingId === t.id}
              aria-busy={loadingId === t.id}
              className={cn(
                "text-left rounded-lg border p-3 transition-colors focus-visible:outline-none focus-visible:ring-2",
                "border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] hover:border-[var(--dsd-border-emphasis)]",
                "disabled:opacity-60 disabled:cursor-not-allowed",
              )}
            >
              <p className="text-sm font-semibold text-[var(--dsd-text-primary)] flex items-center gap-1.5">
                {loadingId === t.id && <Spinner className="h-3 w-3" />}
                {t.name}
              </p>
              <p className="text-xs text-[var(--dsd-text-secondary)] mt-0.5 line-clamp-2">
                {t.description}
              </p>
              <div className="flex flex-wrap gap-1.5 mt-2">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--dsd-layer-overlay)] border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-faint)] uppercase tracking-wide">
                  {t.creates.tasks_count} tasks
                </span>
                {t.creates.cron && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--dsd-layer-overlay)] border border-[var(--dsd-border-subtle)] text-[var(--dsd-text-faint)] uppercase tracking-wide">
                    cron
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Step editor ────────────────────────────────────────────────────────────────

function StepEditor({
  step,
  index,
  total,
  dispatch,
}: {
  step: DraftStep;
  index: number;
  total: number;
  dispatch: React.Dispatch<DraftAction>;
}) {
  const inputCls =
    "rounded border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] px-2 py-1 text-sm text-[var(--dsd-text-primary)] placeholder:text-[var(--dsd-text-faint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--dsd-border-focus)]";

  return (
    <div
      className="rounded-lg border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] p-3 flex flex-col gap-2"
      aria-label={`Step ${index + 1}`}
    >
      {/* Step header row */}
      <div className="flex items-center gap-2">
        <span className="shrink-0 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--dsd-layer-overlay)] text-[10px] font-semibold text-[var(--dsd-text-faint)]">
          {index + 1}
        </span>
        <input
          type="text"
          value={step.title}
          onChange={(e) => dispatch({ type: "UPDATE_STEP", id: step.id, patch: { title: e.target.value } })}
          placeholder="Step title"
          aria-label={`Step ${index + 1} title`}
          className={cn(inputCls, "flex-1 min-w-0")}
        />
        {/* Reorder buttons */}
        <button
          type="button"
          onClick={() => dispatch({ type: "MOVE_UP", id: step.id })}
          disabled={index === 0}
          aria-label="Move step up"
          className="shrink-0 p-1 rounded text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-primary)] disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2"
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => dispatch({ type: "MOVE_DOWN", id: step.id })}
          disabled={index === total - 1}
          aria-label="Move step down"
          className="shrink-0 p-1 rounded text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-primary)] disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2"
        >
          <ArrowDown className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => dispatch({ type: "REMOVE_STEP", id: step.id })}
          aria-label="Remove step"
          className="shrink-0 p-1 rounded text-[var(--dsd-text-faint)] hover:text-[var(--dsd-sem-critical)] focus-visible:outline-none focus-visible:ring-2"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Description */}
      <textarea
        value={step.description}
        onChange={(e) => dispatch({ type: "UPDATE_STEP", id: step.id, patch: { description: e.target.value } })}
        placeholder="Description (optional)"
        aria-label={`Step ${index + 1} description`}
        rows={2}
        className={cn(inputCls, "resize-y w-full")}
      />

      {/* Assignee + model tier row */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-0.5">
          <label className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-wide">
            Assignee / profile
          </label>
          <input
            type="text"
            value={step.assignee}
            onChange={(e) => dispatch({ type: "UPDATE_STEP", id: step.id, patch: { assignee: e.target.value } })}
            placeholder="e.g. researcher"
            aria-label={`Step ${index + 1} assignee`}
            className={inputCls}
          />
        </div>
        <div className="flex flex-col gap-0.5">
          <label className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-wide">
            Model tier
          </label>
          <select
            value={step.modelTier}
            onChange={(e) =>
              dispatch({
                type: "UPDATE_STEP",
                id: step.id,
                patch: { modelTier: e.target.value as ModelTier },
              })
            }
            aria-label={`Step ${index + 1} model tier`}
            className={cn(inputCls, "cursor-pointer")}
          >
            {MODEL_TIERS.map((t) => (
              <option key={t} value={t}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Token estimates row */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-0.5">
          <label className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-wide">
            Est. input tokens
          </label>
          <input
            type="number"
            min={0}
            value={step.estInputTokens}
            onChange={(e) =>
              dispatch({
                type: "UPDATE_STEP",
                id: step.id,
                patch: { estInputTokens: Math.max(0, Number(e.target.value) || 0) },
              })
            }
            aria-label={`Step ${index + 1} estimated input tokens`}
            className={inputCls}
          />
        </div>
        <div className="flex flex-col gap-0.5">
          <label className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-wide">
            Est. output tokens
          </label>
          <input
            type="number"
            min={0}
            value={step.estOutputTokens}
            onChange={(e) =>
              dispatch({
                type: "UPDATE_STEP",
                id: step.id,
                patch: { estOutputTokens: Math.max(0, Number(e.target.value) || 0) },
              })
            }
            aria-label={`Step ${index + 1} estimated output tokens`}
            className={inputCls}
          />
        </div>
      </div>
    </div>
  );
}

// ── Cost estimate panel ────────────────────────────────────────────────────────

function CostEstimatePanel({
  steps,
}: {
  steps: DraftStep[];
}) {
  const [customRate, setCustomRate] = useState({ inputPerM: 1.00, outputPerM: 3.00 });
  const [showRates, setShowRates] = useState(false);

  const perStep = useMemo(
    () => steps.map((s) => computeStepCost(s, customRate)),
    [steps, customRate],
  );
  const total = useMemo(() => perStep.reduce((a, b) => a + b, 0), [perStep]);

  const inputCls =
    "w-full rounded border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] px-2 py-1 text-xs text-[var(--dsd-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--dsd-border-focus)]";

  return (
    <div className="rounded-lg border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] p-4 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-[var(--dsd-text-secondary)] uppercase tracking-wide">
            Cost estimate
          </p>
          <p className="text-[10px] text-[var(--dsd-text-faint)] mt-0.5 flex items-center gap-1">
            <Info className="h-3 w-3 shrink-0" />
            Heuristic — actual cost may vary
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-lg font-semibold tabular-nums text-[var(--dsd-cat-cost)]">
            {fmtEstCost(total)}
          </p>
          <p className="text-[9px] text-[var(--dsd-text-faint)] uppercase tracking-wide">
            ≈ estimate
          </p>
        </div>
      </div>

      {/* Per-step breakdown */}
      {steps.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {steps.map((step, i) => (
            <div key={step.id} className="flex items-center gap-2 text-[11px]">
              <span className="shrink-0 w-4 text-center text-[var(--dsd-text-faint)]">{i + 1}</span>
              <span className="flex-1 min-w-0 truncate text-[var(--dsd-text-secondary)]">
                {step.title || `Step ${i + 1}`}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--dsd-cat-cost)]">
                {fmtEstCost(perStep[i])}
              </span>
            </div>
          ))}
        </div>
      )}

      {steps.length === 0 && (
        <p className="text-xs text-[var(--dsd-text-faint)]">Add steps to see estimates.</p>
      )}

      {/* Rate assumptions toggle */}
      <button
        type="button"
        onClick={() => setShowRates((p) => !p)}
        className="text-[10px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-secondary)] text-left underline underline-offset-2 focus-visible:outline-none"
        aria-expanded={showRates}
      >
        {showRates ? "Hide" : "Show"} rate assumptions
      </button>

      {showRates && (
        <div className="flex flex-col gap-2 pt-1 border-t border-[var(--dsd-border-subtle)]">
          <p className="text-[10px] text-[var(--dsd-text-faint)]">
            Built-in tiers ($/1M tokens — input / output):
          </p>
          {(["fast", "balanced", "high"] as const).map((tier) => (
            <div key={tier} className="flex items-center gap-2 text-[10px]">
              <span className="w-14 capitalize text-[var(--dsd-text-faint)]">{tier}</span>
              <span className="text-[var(--dsd-text-secondary)]">
                ${DEFAULT_RATES[tier].inputPerM.toFixed(2)} / ${DEFAULT_RATES[tier].outputPerM.toFixed(2)}
              </span>
            </div>
          ))}
          <p className="text-[10px] text-[var(--dsd-text-faint)] mt-1">
            Custom tier — edit below ($/1M tokens):
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-0.5">
              <label className="text-[9px] text-[var(--dsd-text-faint)] uppercase">Input</label>
              <input
                type="number"
                min={0}
                step={0.01}
                value={customRate.inputPerM}
                onChange={(e) => setCustomRate((r) => ({ ...r, inputPerM: Math.max(0, Number(e.target.value) || 0) }))}
                aria-label="Custom input rate per 1M tokens"
                className={inputCls}
              />
            </div>
            <div className="flex flex-col gap-0.5">
              <label className="text-[9px] text-[var(--dsd-text-faint)] uppercase">Output</label>
              <input
                type="number"
                min={0}
                step={0.01}
                value={customRate.outputPerM}
                onChange={(e) => setCustomRate((r) => ({ ...r, outputPerM: Math.max(0, Number(e.target.value) || 0) }))}
                aria-label="Custom output rate per 1M tokens"
                className={inputCls}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Action panel ───────────────────────────────────────────────────────────────

function ActionPanel({
  draft,
  onReset,
}: {
  draft: MissionDraft;
  onReset: () => void;
}) {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  const valid = draft.name.trim().length > 0;

  function buildDraftPayload() {
    return {
      name: draft.name.trim(),
      description: draft.objective.trim() || undefined,
      board: draft.board.trim() || draft.name.trim(),
      tasks: draft.steps.map((s) => ({
        title: s.title || "Untitled step",
        description: s.description || undefined,
        assignee: s.assignee || undefined,
        status: "todo" as const,
      })),
      defaults: {
        model_tier:
          draft.steps.length > 0 ? draft.steps[0].modelTier : "balanced",
      },
    };
  }

  async function handleSaveTemplate() {
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.saveCustomTemplate(buildDraftPayload());
      setSavedId(result.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateMission() {
    if (!valid) return;
    setCreating(true);
    setError(null);
    try {
      const result = await api.instantiateDraft(buildDraftPayload());
      navigate(`/missions?mission=${encodeURIComponent(result.mission_id)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="rounded-lg border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)] p-4 flex flex-col gap-3">
      <p className="text-xs font-semibold text-[var(--dsd-text-secondary)] uppercase tracking-wide">
        Actions
      </p>

      {savedId && (
        <p className="text-xs text-[var(--dsd-sem-ok)] flex items-center gap-1">
          <span>✓</span> Saved as template{" "}
          <code className="font-mono text-[10px] opacity-70">{savedId}</code>
        </p>
      )}

      {error && (
        <p className="text-xs text-[var(--dsd-sem-critical)]">{error}</p>
      )}

      {!valid && (
        <p className="text-xs text-[var(--dsd-text-faint)]">
          Enter a mission name to enable actions.
        </p>
      )}

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => void handleSaveTemplate()}
          disabled={!valid || saving || creating}
          aria-busy={saving}
          className={cn(
            "deck-btn-sm flex items-center gap-1.5 justify-center",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {saving ? <Spinner className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
          Save as template
        </button>

        <button
          type="button"
          onClick={() => void handleCreateMission()}
          disabled={!valid || saving || creating}
          aria-busy={creating}
          className={cn(
            "deck-btn-sm flex items-center gap-1.5 justify-center",
            "bg-[var(--dsd-accent-primary)] text-[var(--dsd-bg-base)] hover:opacity-90",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {creating ? <Spinner className="h-3.5 w-3.5" /> : <Hammer className="h-3.5 w-3.5" />}
          Create mission
        </button>

        <button
          type="button"
          onClick={onReset}
          className="text-[10px] text-[var(--dsd-text-faint)] hover:text-[var(--dsd-text-secondary)] flex items-center gap-1 justify-center mt-1 focus-visible:outline-none"
        >
          <RotateCcw className="h-3 w-3" />
          Start over
        </button>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

type BuilderPhase = "pick" | "edit";

export default function MissionBuilderPage() {
  const { setEnd } = usePageHeader();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<BuilderPhase>("pick");
  const [draft, dispatch] = useReducer(draftReducer, undefined, blankDraft);
  const nameRef = useRef<HTMLInputElement | null>(null);

  const handleTemplatePick = useCallback(
    (template: FullTemplateResponse | null) => {
      if (template) {
        dispatch({
          type: "RESET",
          draft: {
            name: template.name,
            objective: template.description,
            board: template.creates.board,
            steps: template.creates.tasks.map((t) =>
              makeBlankStep({
                title: t.title,
                assignee: t.assignee ?? template.defaults?.assignee ?? "",
              }),
            ),
          },
        });
      } else {
        dispatch({ type: "RESET", draft: blankDraft() });
      }
      setPhase("edit");
      // Focus name field on next paint
      setTimeout(() => nameRef.current?.focus(), 50);
    },
    [],
  );

  const handleReset = useCallback(() => {
    dispatch({ type: "RESET", draft: blankDraft() });
    setPhase("pick");
  }, []);

  useLayoutEffect(() => {
    setEnd(
      <button
        type="button"
        className="deck-btn-sm ghost flex items-center gap-1.5"
        onClick={() => navigate("/missions")}
      >
        <ChevronRight className="h-3.5 w-3.5 rotate-180" />
        Back to Missions
      </button>,
    );
    return () => setEnd(null);
  }, [navigate, setEnd]);

  return (
    <DeckPageShell>
      <div className="flex flex-col gap-5 py-4 px-5">
        {/* Page title */}
        <div className="flex flex-col gap-1">
          <h1 className="text-[var(--dsd-text-h2)] font-semibold tracking-[-0.01em] text-[var(--dsd-text-primary)] flex items-center gap-2">
            <LayoutTemplate className="h-5 w-5 text-[var(--dsd-cat-mission)]" />
            Mission Builder
          </h1>
          <p className="text-sm text-[var(--dsd-text-secondary)]">
            Compose a mission, define steps, and review a cost estimate before running.
          </p>
        </div>

        {/* Phase: pick template */}
        {phase === "pick" && (
          <TemplatePicker onPick={handleTemplatePick} />
        )}

        {/* Phase: edit */}
        {phase === "edit" && (
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
            {/* ── Left column: editor ── */}
            <div className="flex-1 min-w-0 flex flex-col gap-6">
              {/* Mission basics */}
              <section aria-label="Mission basics" className="flex flex-col gap-4">
                <SectionHeading>Mission basics</SectionHeading>

                <InputField
                  label="Mission name"
                  id="mb-name"
                  value={draft.name}
                  onChange={(v) => dispatch({ type: "SET_NAME", value: v })}
                  placeholder="e.g. Q3 Research Sprint"
                  required
                />

                <InputField
                  label="Objective / description"
                  id="mb-objective"
                  value={draft.objective}
                  onChange={(v) => dispatch({ type: "SET_OBJECTIVE", value: v })}
                  placeholder="What should this mission accomplish?"
                  multiline
                />

                <InputField
                  label="Board name"
                  id="mb-board"
                  value={draft.board}
                  onChange={(v) => dispatch({ type: "SET_BOARD", value: v })}
                  placeholder="Leave blank to use mission name"
                />
              </section>

              {/* Steps */}
              <section aria-label="Mission steps">
                <div className="flex items-center justify-between mb-3">
                  <SectionHeading>Steps / tasks</SectionHeading>
                  <button
                    type="button"
                    onClick={() => dispatch({ type: "ADD_STEP" })}
                    className="deck-btn-sm ghost flex items-center gap-1"
                    aria-label="Add step"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add step
                  </button>
                </div>

                {draft.steps.length === 0 ? (
                  <EmptyState
                    icon="📋"
                    title="No steps yet"
                    description="Add steps to define what agents will do in this mission."
                  />
                ) : (
                  <div className="flex flex-col gap-2">
                    {draft.steps.map((step, i) => (
                      <StepEditor
                        key={step.id}
                        step={step}
                        index={i}
                        total={draft.steps.length}
                        dispatch={dispatch}
                      />
                    ))}
                    <button
                      type="button"
                      onClick={() => dispatch({ type: "ADD_STEP" })}
                      className="mt-1 deck-btn-sm ghost flex items-center gap-1 self-start"
                      aria-label="Add another step"
                    >
                      <CirclePlus className="h-3.5 w-3.5" />
                      Add another step
                    </button>
                  </div>
                )}
              </section>
            </div>

            {/* ── Right column: estimate + actions ── */}
            <div className="w-full lg:w-80 shrink-0 flex flex-col gap-4">
              <CostEstimatePanel steps={draft.steps} />
              <ActionPanel draft={draft} onReset={handleReset} />
            </div>
          </div>
        )}
      </div>
    </DeckPageShell>
  );
}
