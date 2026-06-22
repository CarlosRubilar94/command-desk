import { useMemo } from "react";
import { cn } from "@/lib/utils";

/* ── Shared helpers ───────────────────────────────────────────────── */

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function normalize(values: number[]): number[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values.map((v) => (v - min) / range);
}

/* ── Sparkline (SVG line chart) ───────────────────────────────────── */

export interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fillOpacity?: number;
  className?: string;
  "aria-label"?: string;
}

export function Sparkline({
  data,
  width = 80,
  height = 28,
  color = "var(--dsd-accent-cyan)",
  fillOpacity = 0.15,
  className,
  "aria-label": ariaLabel,
}: SparklineProps) {
  const { linePath, fillPath } = useMemo(() => {
    if (data.length < 2) return { linePath: "", fillPath: "" };
    const norm = normalize(data);
    const step = width / (norm.length - 1);
    const pts = norm.map((v, i) => [i * step, height - clamp(v * height, 1, height - 1)] as [number, number]);
    const d = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const fill = `${d} L${pts[pts.length - 1][0].toFixed(1)},${height} L0,${height} Z`;
    return { linePath: d, fillPath: fill };
  }, [data, width, height]);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-label={ariaLabel ?? "Sparkline chart"}
      role="img"
      className={cn("overflow-visible", className)}
    >
      {fillPath && (
        <path d={fillPath} fill={color} fillOpacity={fillOpacity} strokeWidth={0} />
      )}
      {linePath && (
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

/* ── MiniBar (SVG bar chart) ──────────────────────────────────────── */

export interface MiniBarProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  gap?: number;
  className?: string;
  "aria-label"?: string;
}

export function MiniBar({
  data,
  width = 80,
  height = 28,
  color = "var(--dsd-accent-cyan)",
  gap = 2,
  className,
  "aria-label": ariaLabel,
}: MiniBarProps) {
  const bars = useMemo(() => {
    if (!data.length) return [];
    const norm = normalize(data);
    const barW = (width - gap * (data.length - 1)) / data.length;
    return norm.map((v, i) => {
      const barH = Math.max(2, clamp(v * height, 2, height));
      return {
        x: i * (barW + gap),
        y: height - barH,
        w: barW,
        h: barH,
        opacity: 0.5 + v * 0.5,
      };
    });
  }, [data, width, height, gap]);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-label={ariaLabel ?? "Bar chart"}
      role="img"
      className={cn("overflow-visible", className)}
    >
      {bars.map((b, i) => (
        <rect
          key={i}
          x={b.x}
          y={b.y}
          width={b.w}
          height={b.h}
          rx={1}
          fill={color}
          fillOpacity={b.opacity}
        />
      ))}
    </svg>
  );
}
