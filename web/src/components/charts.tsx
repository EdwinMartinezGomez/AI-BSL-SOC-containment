// Primitivas SVG propias (dataviz): ejes, grid, crosshair, area+linea.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { isDark } from "../lib/theme";

export interface ThemeColors {
  dark: boolean;
  ink: string; ink2: string; muted: string;
  gridline: string; baseline: string; surface: string;
  series: string; wash: string;
}

export function useTheme(): ThemeColors {
  const [dark, setDark] = useState(isDark());
  useEffect(() => {
    const m = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => setDark(isDark());
    m.addEventListener("change", listener);
    return () => m.removeEventListener("change", listener);
  }, []);
  const d = dark;
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  return {
    dark: d,
    ink: v("--ink") || (d ? "#ffffff" : "#0b0b0b"),
    ink2: v("--ink-2") || (d ? "#c3c2b7" : "#52514e"),
    muted: v("--muted") || "#898781",
    gridline: v("--gridline") || (d ? "#2c2c2a" : "#e1e0d9"),
    baseline: v("--baseline") || (d ? "#383835" : "#c3c2b7"),
    surface: v("--surface") || (d ? "#1a1a19" : "#fcfcfb"),
    series: v("--series") || (d ? "#3987e5" : "#2a78d6"),
    wash: v("--wash") || (d ? "rgba(57,135,229,0.10)" : "rgba(42,120,214,0.10)"),
  };
}

// Respeta el orden fijo de la paleta categórica: slot por nombre estable.
const CAT_KEY = ["cat-1", "cat-2", "cat-3", "cat-4", "cat-5", "cat-6", "cat-7", "cat-8"];
export function catColor(i: number): string {
  const cs = getComputedStyle(document.documentElement);
  const key = CAT_KEY[i % CAT_KEY.length];
  return cs.getPropertyValue(key).trim() || "#3987e5";
}

export function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T | null>(null) as React.RefObject<T>;
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setW(e.contentRect.width);
    });
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export interface Pt { tick: number; value: number }

function niceTicks(max: number, count: number): number[] {
  const step = max / count;
  const out: number[] = [];
  for (let i = 0; i <= count; i++) out.push(Math.round(i * step * 1000) / 1000);
  return out;
}

export interface Marker {
  tick: number;
  color: string;
  shape: "dot" | "x" | "ring";
  label?: string;
}

interface AxisChartProps {
  points: Pt[];
  width: number;
  height: number;
  yMax: number;
  thresholds: { value: number; label: string; color: string }[];
  markers?: Marker[];
  bands?: { fromTick: number; toTick: number; color: string; label: string }[];
  yTicks?: number;
  tooltip: (tick: number) => ReactNode;
  fillStroke?: string; // color de la línea/área
  directLabel?: ReactNode;
}

export function AreaLine({
  points, width, height, yMax, thresholds, markers, bands,
  yTicks = 4, tooltip, fillStroke, directLabel,
}: AxisChartProps) {
  const theme = useTheme();
  const [hover, setHover] = useState<number | null>(null);
  const M = { top: 12, right: 16, bottom: 26, left: 34 };
  const X = (t: number) => {
    const t0 = points[0]?.tick ?? 0;
    const t1 = points[points.length - 1]?.tick ?? t0 + 1;
    const span = Math.max(1, t1 - t0);
    return M.left + ((t - t0) / span) * (width - M.left - M.right);
  };
  const Y = (v: number) => M.top + (1 - v / yMax) * (height - M.top - M.bottom);
  const stroke = fillStroke || theme.series;
  const wash = theme.wash;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.tick).toFixed(2)},${Y(p.value).toFixed(2)}`).join(" ");
  const area = points.length
    ? `${line} L${X(points[points.length - 1].tick).toFixed(2)},${Y(0).toFixed(2)} L${X(points[0].tick).toFixed(2)},${Y(0).toFixed(2)} Z`
    : "";

  const ticks = niceTicks(yMax, yTicks);
  const near = hover !== null ? lastAtOrBefore(points, hover) : undefined;

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <svg width={width} height={height} role="img">
        {/* area */}
        {area && <path d={area} fill={wash} stroke="none" />}
        {/* gridlines + y labels */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={width - M.right} y1={Y(t)} y2={Y(t)}
              stroke={theme.gridline} strokeWidth={1} />
            <text x={M.left - 6} y={Y(t) + 3} textAnchor="end" fontSize={10.5}
              fill={theme.muted}>
              {t.toFixed(2)}
            </text>
          </g>
        ))}
        {/* thresholds */}
        {thresholds.map((th) => {
          const y = Y(th.value);
          return (
            <g key={th.label}>
              <line x1={M.left} x2={width - M.right} y1={y} y2={y}
                stroke={th.color} strokeWidth={1} strokeDasharray="5 4" opacity={0.75} />
              <text x={width - M.right} y={y - 3} textAnchor="end" fontSize={10}
                fill={theme.muted}>{th.label}</text>
            </g>
          );
        })}
        {/* posture bands (tape bajo el eje) */}
        {bands?.map((b) => (
          <rect key={`${b.fromTick}-${b.toTick}`}
            x={X(b.fromTick)} y={height - 12}
            width={Math.max(2, X(b.toTick) - X(b.fromTick))} height={8}
            fill={b.color} rx={2} />
        ))}
        {/* axis baseline */}
        <line x1={M.left} x2={width - M.right} y1={Y(0)} y2={Y(0)} stroke={theme.baseline} strokeWidth={1.4} strokeLinecap="square" />
        {/* x labels */}
        {points.filter((_, i) => i % Math.max(1, Math.floor(points.length / 8)) === 0).map((p) => (
          <text key={p.tick} x={X(p.tick)} y={height - 6} textAnchor="middle" fontSize={10.5}
            fill={theme.muted}>{p.tick}</text>
        ))}
        {/* line */}
        {line && <path d={line} fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
        {/* markers */}
        {markers?.map((m, i) => {
          const x = X(m.tick); const y = Y(m.shape === "dot" ? valueAt(points, m.tick) : (lastAtOrBefore(points, m.tick)?.value ?? NaN));
          if (isNaN(y)) return null;
          return (
            <g key={i}>
              {m.shape === "x" ? (
                <g>
                  <circle cx={x} cy={y} r={7} fill={theme.surface} stroke={theme.surface} strokeWidth={2} />
                  <path d={`M${x - 4},${y - 4}L${x + 4},${y + 4}M${x + 4},${y - 4}L${x - 4},${y + 4}`}
                    stroke={m.color} strokeWidth={2.2} strokeLinecap="round" />
                </g>
              ) : m.shape === "ring" ? (
                <circle cx={x} cy={y} r={5.5} fill={theme.surface} stroke={m.color} strokeWidth={2.2} />
              ) : (
                <g>
                  <circle cx={x} cy={y} r={4.6} fill={theme.surface} />
                  <circle cx={x} cy={y} r={4.6} fill="none" stroke={m.color} strokeWidth={2.2} />
                </g>
              )}
            </g>
          );
        })}
        {/* hover crosshair */}
        {hover !== null && near && (
          <g>
            <line x1={X(near.tick)} x2={X(near.tick)} y1={M.top} y2={height - 14}
              stroke={theme.baseline} strokeWidth={1} strokeDasharray="3 3" />
            <circle cx={X(near.tick)} cy={Y(near.value)} r={4.5} fill={theme.surface} stroke={stroke} strokeWidth={2} />
          </g>
        )}
        {/* overlay captura mouse */}
        <rect x={M.left} y={M.top} width={Math.max(0, width - M.left - M.right)}
          height={Math.max(0, height - M.top - M.bottom)} fill="transparent"
          onMouseMove={(e) => {
            const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
            const px = e.clientX - r.left;
            const t0 = points[0]?.tick ?? 0;
            const t1 = points[points.length - 1]?.tick ?? t0;
            const tick = Math.round(t0 + (px / (width - M.left - M.right)) * (t1 - t0));
            setHover(tick);
          }}
          onMouseLeave={() => setHover(null)} />
      </svg>
      {hover !== null && near && (
        <div className="tt" style={{
          left: Math.min(Math.max(X(near.tick) - 60, 8), width - 120),
          top: Math.max(8, Y(near.value) - 46),
        }}>
          {tooltip(near.tick)}
        </div>
      )}
      {!hover && directLabel && points.length > 0 && (
        <div className="tt" style={{
          left: X(points[points.length - 1].tick) + 8, top: Y(points[points.length - 1].value) - 30,
          opacity: 0.92,
        }}>
          {directLabel}
        </div>
      )}
    </div>
  );
}

function valueAt(points: Pt[], tick: number): number {
  const p = points.find((q) => q.tick === tick);
  return p ? p.value : NaN;
}
function lastAtOrBefore(points: Pt[], tick: number): Pt | undefined {
  let best: Pt | undefined;
  for (const p of points) {
    if (p.tick <= tick) best = p; else break;
  }
  return best;
}