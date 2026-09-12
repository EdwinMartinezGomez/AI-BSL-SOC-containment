import { POSTURES, postureTone, type AgentSnapshot } from "../types";
import { fmtTick } from "../lib/format";

const TONE_CLS: Record<string, string> = {
  good: "badge-good", warning: "badge-warning",
  serious: "badge-serious", critical: "badge-critical", neutral: "badge-neutral",
};
const TONE_HEX: Record<string, string> = {
  good: "var(--good)", warning: "var(--warning)",
  serious: "var(--serious)", critical: "var(--critical)", neutral: "var(--baseline)",
};

export default function PostureGauge({ snap }: { snap: AgentSnapshot }) {
  const transitions = snap.transitions ?? [];
  const idx = POSTURES.indexOf(snap.posture);
  const tone = postureTone(snap.posture);
  const last = transitions[transitions.length - 1];
  return (
    <div className="card">
      <h3>Postura del agente</h3>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <div style={{ textAlign: "center" }}>
          <div className="hero" style={{ color: TONE_HEX[tone] }}>{snap.posture}</div>
          <span className={`badge ${TONE_CLS[tone]}`}>
            <span className="icon">{tone === "critical" ? "■" : tone === "warning" || tone === "serious" ? "▲" : "●"}</span>
            {snap.posture === "P0" ? "operación normal"
              : snap.posture === "P1" ? "precaución"
              : snap.posture === "P2" ? "contención"
              : snap.posture === "P3" ? "respuesta"
              : "terminación"}
          </span>
        </div>
        <div className="row" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
          <div className="subtle">r(t) = <span className="tnum mono" style={{ color: "var(--ink)" }}>{snap.r.toFixed(3)}</span></div>
          <div className="subtle">tick <span className="mono">{snap.tick}</span> · techo <span className="mono">{snap.ceiling}</span></div>
          {last && (
            <div className="subtle">
              última transición: <span className="mono">{last.from}→{last.to}</span> · {last.causa}
            </div>
          )}
          <div className="row" style={{ gap: 5 }}>
            {snap.killswitch && <span className="badge badge-critical"><span className="icon">■</span>killswitch</span>}
            {snap.terminal && <span className="badge badge-neutral">terminado</span>}
            {snap.actuator_state.quarantine && <span className="badge badge-neutral">cuarentena</span>}
          </div>
        </div>
      </div>
      {/* ruta P0..P4 */}
      <div className="row" style={{ marginTop: 12, gap: 5 }}>
        {POSTURES.map((p, i) => (
          <div key={p} style={{ flex: 1, textAlign: "center" }}>
            <div style={{
              height: 7, borderRadius: 4,
              background: i <= idx ? TONE_HEX[postureTone(p)] : "var(--surface-2)",
              border: "1px solid var(--border)",
              opacity: i <= idx ? 1 : 0.6,
            }} />
            <div style={{ fontSize: 11, marginTop: 3, color: i === idx ? "var(--ink)" : "var(--muted)", fontWeight: i === idx ? 700 : 500 }}>
              {p}
            </div>
          </div>
        ))}
      </div>
      <table className="data" style={{ marginTop: 10 }}>
        <thead>
          <tr><th>tick</th><th>transición</th><th>causa</th><th>r</th></tr>
        </thead>
        <tbody>
          {snap.transitions.slice(-6).reverse().map((t, i) => (
            <tr key={i}>
              <td className="tnum">{fmtTick(t.tick)}</td>
              <td className="mono">{t.from} → {t.to}</td>
              <td>{t.causa}</td>
              <td className="tnum">{t.r.toFixed(3)}</td>
            </tr>
          ))}
          {snap.transitions.length === 0 && (
            <tr><td colSpan={4} className="subtle">Sin transiciones de postura todavía.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}