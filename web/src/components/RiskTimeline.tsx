import type { EnforcementMsg, HistoryPoint, Transition } from "../types";
import { AreaLine, type Marker, type Pt, useTheme, useWidth } from "./charts";

// Umbrales de escalada de la política declarativa (policy_config.json · umbrales.theta_up).
export const UP_THRESHOLDS = [
  { value: 0.15, label: "P1·0.15", color: "var(--warning)" },
  { value: 0.40, label: "P2·0.40", color: "var(--serious)" },
  { value: 0.70, label: "P3·0.70", color: "var(--critical)" },
];

export default function RiskTimeline({
  history = [], transitions = [], enforcements = [], height = 250,
}: {
  history: HistoryPoint[];
  transitions: Transition[];
  enforcements: EnforcementMsg[];
  height?: number;
}) {
  const theme = useTheme();
  const [ref, w] = useWidth<HTMLDivElement>();

  if (history.length < 2 || w < 40) {
    return (
      <div ref={ref} className="card">
        <h3>Riesgo r(t) y postura</h3>
        <div className="subtle" style={{ height, display: "grid", placeItems: "center" }}>
          {history.length < 2 ? "Sin datos de evolución (esperando ticks…)" : ""}
        </div>
      </div>
    );
  }

  const points: Pt[] = history.map((h) => ({ tick: h.tick, value: h.r }));
  const yMax = 1;

  // bandas de postura: segmentos consecutivos
  const bands: { fromTick: number; toTick: number; color: string; label: string }[] = [];
  for (let i = 0; i < history.length; i++) {
    const h = history[i];
    const color = postureHex(h.posture, theme);
    if (i === 0) { bands.push({ fromTick: h.tick, toTick: h.tick, color, label: h.posture }); continue; }
    const prev = history[i - 1];
    if (postureHex(prev.posture, theme) === color && bands.length) {
      bands[bands.length - 1].toTick = h.tick;
    } else {
      bands.push({ fromTick: h.tick, toTick: h.tick, color, label: h.posture });
    }
  }

  const markers: Marker[] = [];
  for (const e of enforcements) {
    const tick = e.tick ?? 0;
    if (e.decision === "BLOCK") markers.push({ tick, color: "var(--critical)", shape: "x" });
    else if (e.decision === "HOLD_REVIEW") markers.push({ tick, color: "var(--warning)", shape: "ring" });
    else markers.push({ tick, color: "var(--good)", shape: "dot" });
  }
  // transiciones de postura (marcador de anillo si no coinciden con un nodo exacto)
  const seen = new Set<number>();
  for (const t of transitions) {
    if (!seen.has(t.tick)) { markers.push({ tick: t.tick, color: theme.series, shape: "ring" }); seen.add(t.tick); }
  }

  const last = history[history.length - 1];

  return (
    <div className="card">
      <h3>
        Riesgo r(t) y postura
        <span className="hint">
          <span className="legend">
            <span><span className="sw" style={{ background: "var(--series)" }} />r(t)</span>
            <span><span className="sw" style={{ background: "var(--critical)" }} />✕ bloqueo</span>
            <span><span className="sw" style={{ background: "var(--warning)" }} />○ revisión humana</span>
          </span>
        </span>
      </h3>
      <div ref={ref} style={{ width: "100%" }}>
        <AreaLine
          points={points}
          width={w}
          height={height}
          yMax={yMax}
          thresholds={UP_THRESHOLDS}
          markers={markers}
          bands={bands}
          directLabel={<span className="v">r = {last.r.toFixed(3)} · {last.posture}</span>}
          tooltip={(tick) => {
            const h = history[history.length - 1] && history.reduce(
              (a, b) => (Math.abs(b.tick - tick) < Math.abs(a.tick - tick) ? b : a));
            const at = enforcements.filter((e) => (e.tick ?? -1) === tick).slice(0, 2);
            return (
              <>
                <div className="k">tick</div><span className="v">{tick}</span>
                <div className="k">r(t)</div><span className="v">{h ? h.r.toFixed(3) : "—"}</span>
                <div className="k">postura</div><span className="v">{h ? h.posture : "—"}</span>
                {at.map((a, i) => (
                  <div key={i}>
                    <div className="k">{a.decision} · {a.rule}</div>
                    <span className="v">{a.rationale}</span>
                  </div>
                ))}
              </>
            );
          }}
        />
      </div>
    </div>
  );
}

function postureHex(p: string, theme: ReturnType<typeof useTheme>): string {
  switch (p) {
    case "P0": return "var(--good)";
    case "P1": return "var(--warning)";
    case "P2": return "var(--serious)";
    case "P3": return "var(--critical)";
    case "P4": return theme.dark ? "#b3261e" : "#8f1d1c";
    default: return theme.baseline;
  }
}
export { postureHex };