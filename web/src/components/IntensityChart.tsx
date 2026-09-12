import { useState } from "react";
import type { HistoryPoint } from "../types";
import { catColor, useTheme, useWidth } from "./charts";

function lastAtOrBefore<T extends { tick: number }>(arr: T[], tick: number): T | undefined {
  let best: T | undefined;
  for (const p of arr) if (p.tick <= tick) best = p; else break;
  return best;
}
function niceY(max: number): number {
  const c = Math.ceil(max * 2) / 2;
  return Math.max(0.2, c);
}

export default function IntensityChart({ history = [], height = 250 }: { history: HistoryPoint[]; height?: number }) {
  const theme = useTheme();
  const [ref, w] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  if (history.length < 2 || w < 40) {
    return (
      <div ref={ref} className="card">
        <h3>Intensidad por categoría I<sub>c</sub>(t)</h3>
        <div className="subtle" style={{ height, display: "grid", placeItems: "center" }}>
          {history.length < 2 ? "Esperando datos…" : ""}
        </div>
      </div>
    );
  }

  const cats = [...new Set(history.flatMap((h) => Object.keys(h.I)))].sort();
  const yMax = niceY(Math.max(0.01, ...history.flatMap((h) => Object.values(h.I))));

  const M = { top: 12, right: 16, bottom: 26, left: 34 };
  const t0 = history[0].tick;
  const t1 = history[history.length - 1].tick;
  const span = Math.max(1, t1 - t0);
  const X = (t: number) => M.left + ((t - t0) / span) * (w - M.left - M.right);
  const Y = (v: number) => M.top + (1 - Math.min(1, Math.max(0, v)) / yMax) * (height - M.top - M.bottom);

  const series = cats.map((c, i) => ({
    cat: c, color: catColor(i),
    pts: history.map((h) => ({ tick: h.tick, value: h.I[c] ?? 0 })),
  }));

  const ticks = [0.0, 0.25, 0.5, 0.75, 1.0].map((t) => Math.round(t * yMax * 100) / 100).filter((v, i, a) => a.indexOf(v) === i);
  const xEvery = Math.max(1, Math.floor(history.length / 8));
  const near = hover !== null ? lastAtOrBefore(history, hover) : undefined;

  return (
    <div className="card">
      <h3>
        Intensidad por categoría I<sub>c</sub>(t)
        <span className="hint">
          <span className="legend">
            {series.map((s) => (
              <span key={s.cat}><span className="sw" style={{ background: s.color }} />{s.cat}</span>
            ))}
          </span>
        </span>
      </h3>
      <div ref={ref} style={{ position: "relative", width: "100%" }}>
        <svg width={w} height={height} role="img">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={w - M.right} y1={Y(t)} y2={Y(t)} stroke={theme.gridline} strokeWidth={1} />
              <text x={M.left - 6} y={Y(t) + 3} textAnchor="end" fontSize={10.5} fill={theme.muted}>
                {t.toFixed(2)}</text>
            </g>
          ))}
          <line x1={M.left} x2={w - M.right} y1={Y(0)} y2={Y(0)} stroke={theme.baseline} strokeWidth={1.4} strokeLinecap="square" />
          {history.filter((_, i) => i % xEvery === 0).map((h) => (
            <text key={h.tick} x={X(h.tick)} y={height - 6} textAnchor="middle" fontSize={10.5} fill={theme.muted}>
              {h.tick}</text>
          ))}
          {series.map((s) => {
            const d = s.pts.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.tick).toFixed(2)},${Y(p.value).toFixed(2)}`).join(" ");
            return <path key={s.cat} d={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />;
          })}
          {hover !== null && near && (
            <g>
              <line x1={X(near.tick)} x2={X(near.tick)} y1={M.top} y2={height - 14}
                stroke={theme.baseline} strokeWidth={1} strokeDasharray="3 3" />
              {series.map((s) => {
                const p = s.pts.find((q) => q.tick === near.tick) ?? { tick: near.tick, value: 0 };
                return <circle key={s.cat} cx={X(near.tick)} cy={Y(p.value)} r={4} fill={theme.surface} stroke={s.color} strokeWidth={2} />;
              })}
            </g>
          )}
          <rect x={M.left} y={M.top} width={Math.max(0, w - M.left - M.right)}
            height={Math.max(0, height - M.top - M.bottom)} fill="transparent"
            onMouseMove={(e) => {
              const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
              const tick = Math.round(t0 + ((e.clientX - r.left) / (w - M.left - M.right)) * (t1 - t0));
              setHover(tick);
            }}
            onMouseLeave={() => setHover(null)} />
        </svg>
        {hover !== null && near && (
          <div className="tt" style={{
            left: Math.min(Math.max(X(near.tick) - 60, 8), w - 150),
            top: 8,
          }}>
            <div className="k">tick</div><span className="v">{near.tick}</span>
            {series.map((s) => (
              <div key={s.cat}>
                <span className="k">{s.cat} </span>
                <span className="v">{(s.pts.find((q) => q.tick === near.tick)?.value ?? 0).toFixed(3)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}