import type { AgentSnapshot, Metrics } from "../types";
import { fmtTick } from "../lib/format";

function Tile({ label, value, unit, tone }: { label: string; value: string | number; unit?: string; tone?: string }) {
  return (
    <div className="card" style={{ padding: "10px 12px" }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={tone ? { color: `var(--${tone})` } : undefined}>
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
    </div>
  );
}

export default function MetricsPanel({ metrics, snap }: { metrics: Metrics | null; snap: AgentSnapshot }) {
  const m = metrics;
  const containedRate = m?.contained_rate ?? 1;
  const rateTone = containedRate >= 0.9 ? "good" : containedRate >= 0.6 ? "warning" : "critical";
  const openReviews = snap.open_reviews ?? [];
  return (
    <div className="card">
      <h3>
        Métricas de contención
        <span className="hint">t_detect / t_respond / contained_rate</span>
      </h3>
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(92px, 1fr))", gap: 8 }}>
        <Tile label="postura final" value={m?.postura_final ?? snap.posture} />
        <Tile label="t_detect" value={fmtTick(m?.t_detect ?? null)} />
        <Tile label="t_respond" value={fmtTick(m?.t_respond ?? null)} />
        <Tile label="contained_rate" value={m ? (containedRate * 100).toFixed(0) : "—"} unit="%" tone={rateTone} />
        <Tile label="cometidos" value={m?.cometidos ?? 0} />
        <Tile label="peligrosos" value={m?.peligrosos ?? 0} />
        <Tile label="contenidos" value={m?.contenidos ?? 0} />
        <Tile label="review_required" value={m?.review_required ?? openReviews.length} />
      </div>
      <div className="row" style={{ marginTop: 10, gap: 6, flexWrap: "wrap" }}>
        <span className="chip">posturas: {m?.posturas_alcanzadas?.join("→") ?? "—"}</span>
        <span className={`badge ${m?.verify_ok ? "badge-good" : "badge-critical"}`}>
          <span className="icon">{m?.verify_ok ? "✓" : "✕"}</span>ledger {m?.verify_ok ? "íntegro" : "roto"}
        </span>
        <span className="chip mono">{m?.ledger_hash ? m.ledger_hash.slice(0, 12) : "—"}</span>
        {m?.modo && <span className="chip">{m.modo}</span>}
      </div>
    </div>
  );
}