import { SkipBack, SkipForward, ChevronLeft, ChevronRight, Play, Pause } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PlaybackControlsProps {
  currentStep: number;
  totalSteps: number;
  isPlaying: boolean;
  speed: number;
  onPlay: () => void;
  onPause: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onJumpTo: (index: number) => void;
  onSpeedChange: (speed: number) => void;
}

const SPEEDS = [0.5, 1, 2, 4];

const CTL_BTN =
  "inline-flex items-center justify-center h-7 w-7 rounded-[var(--dsd-radius-sm)] border border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-raised)] text-[var(--dsd-text-dim)] transition-colors duration-[var(--dsd-dur-fast)] hover:text-[var(--dsd-text-base)] hover:border-[var(--dsd-border-default)] focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)]";

const CTL_BTN_PRIMARY =
  "inline-flex items-center justify-center h-7 w-7 rounded-[var(--dsd-radius-sm)] border bg-[var(--dsd-accent-primary-bg)] border-[var(--dsd-accent-primary)]/40 text-[var(--dsd-accent-primary)] transition-colors duration-[var(--dsd-dur-fast)] hover:bg-[var(--dsd-accent-primary)]/20 focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)]";

export function PlaybackControls({
  currentStep,
  totalSteps,
  isPlaying,
  speed,
  onPlay,
  onPause,
  onStepBack,
  onStepForward,
  onJumpTo,
  onSpeedChange,
}: PlaybackControlsProps) {
  const atStart = currentStep === 0;
  const atEnd = currentStep >= totalSteps - 1;

  return (
    <div
      role="toolbar"
      aria-label="Playback controls"
      className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b border-[var(--dsd-border-subtle)] bg-[var(--dsd-layer-surface)]"
    >
      <button
        type="button"
        aria-label="Jump to first step"
        title="Jump to first (Home)"
        disabled={atStart || totalSteps === 0}
        onClick={() => onJumpTo(0)}
        className={cn(CTL_BTN, (atStart || totalSteps === 0) && "opacity-40 cursor-not-allowed")}
      >
        <SkipBack className="h-3.5 w-3.5" />
      </button>

      <button
        type="button"
        aria-label="Step back (←)"
        title="Step back (←)"
        disabled={atStart || totalSteps === 0}
        onClick={onStepBack}
        className={cn(CTL_BTN, (atStart || totalSteps === 0) && "opacity-40 cursor-not-allowed")}
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </button>

      <button
        type="button"
        aria-label={isPlaying ? "Pause (Space)" : "Play (Space)"}
        title={isPlaying ? "Pause (Space)" : "Play (Space)"}
        onClick={isPlaying ? onPause : onPlay}
        disabled={totalSteps === 0}
        className={cn(CTL_BTN_PRIMARY, totalSteps === 0 && "opacity-40 cursor-not-allowed")}
      >
        {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      </button>

      <button
        type="button"
        aria-label="Step forward (→)"
        title="Step forward (→)"
        disabled={atEnd || totalSteps === 0}
        onClick={onStepForward}
        className={cn(CTL_BTN, (atEnd || totalSteps === 0) && "opacity-40 cursor-not-allowed")}
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </button>

      <button
        type="button"
        aria-label="Jump to last step"
        title="Jump to last (End)"
        disabled={atEnd || totalSteps === 0}
        onClick={() => onJumpTo(totalSteps - 1)}
        className={cn(CTL_BTN, (atEnd || totalSteps === 0) && "opacity-40 cursor-not-allowed")}
      >
        <SkipForward className="h-3.5 w-3.5" />
      </button>

      <div className="flex items-center gap-1.5 ml-2" aria-label="Step position">
        <span className="text-[11px] text-[var(--dsd-text-faint)] font-mono">step</span>
        <input
          type="number"
          min={1}
          max={Math.max(1, totalSteps)}
          value={totalSteps === 0 ? 0 : currentStep + 1}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            if (!isNaN(v) && v >= 1 && v <= totalSteps) onJumpTo(v - 1);
          }}
          aria-label="Jump to step number"
          className="w-12 text-center text-[11px] font-mono bg-[var(--dsd-layer-raised)] border border-[var(--dsd-border-subtle)] rounded-[var(--dsd-radius-sm)] px-1 py-0.5 text-[var(--dsd-text-base)] focus-visible:outline-1 focus-visible:outline-[var(--dsd-border-focus)]"
        />
        <span className="text-[11px] text-[var(--dsd-text-faint)] font-mono">/ {totalSteps}</span>
      </div>

      <div className="flex items-center gap-1 ml-auto" aria-label="Playback speed">
        <span className="text-[10px] text-[var(--dsd-text-faint)] uppercase tracking-wide mr-0.5">
          Speed
        </span>
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            aria-label={`${s}x speed`}
            aria-pressed={speed === s}
            onClick={() => onSpeedChange(s)}
            className={cn(
              "px-2 py-0.5 text-[10px] font-mono rounded-[var(--dsd-radius-sm)] border transition-colors duration-[var(--dsd-dur-fast)] focus-visible:outline-2 focus-visible:outline-[var(--dsd-border-focus)]",
              speed === s
                ? "bg-[var(--dsd-accent-primary-bg)] text-[var(--dsd-accent-primary)] border-[var(--dsd-accent-primary)]/40"
                : "bg-transparent text-[var(--dsd-text-faint)] border-[var(--dsd-border-subtle)] hover:text-[var(--dsd-text-base)] hover:border-[var(--dsd-border-default)]",
            )}
          >
            {s}x
          </button>
        ))}
      </div>

      <span className="text-[10px] text-[var(--dsd-text-faint)] ml-3 hidden sm:block" aria-hidden>
        Space=play/pause · ←→=step
      </span>
    </div>
  );
}
