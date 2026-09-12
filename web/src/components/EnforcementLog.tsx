import type { LedgerEntry } from "../types";
import { KIND_EN } from "../types";

const DEC_BDG: Record<string, string> = {
  ALLOW: "badge-good", BLOCK: "badge-critical", HOLD_REVIEW: "badge-warning",
};

export interface EnfRow {
  action_id?: unknown;
  decision: string;
  rule: string;
  signal?: unknown;
  kind?: unknown;
  category?: unknown;
  tool?: unknown;
  target?: unknown;
  risk_before?: number;
  risk_after?: number;
  posture_from?: string;
  posture_to?: string;
  rationale?: string;
}

export default function EnforcementLog({ entries, limit = 30 }: { entries: LedgerEntry[]; limit?: number }) {
  const enf = entries.filter((e) => e.kind === "enforcement").reverse().slice(0, limit);
  return (
    <div className="card" style={{ maxHeight: 520, display: "flex", flexDirection: "column" }}>
      <h3>Registro de enforcement — qué ocurrió → qué señal → qué regla → qué evidencia</h3>
      <div className="scroll-y">
        {enf.length === 0 && <div className="subtle">Sin decisiones de enforcement todavía.</div>}
        {enf.map((e) => {
          const p = e.payload as unknown as EnfRow;
          const kindLabel = KIND_EN[String(p.kind ?? p.signal ?? "")] ?? String(p.kind ?? p.signal ?? "—");
          const target = p.target ? String(p.target) : "";
          return (
            <div key={e.seq} style={{
              border: "1px solid var(--border)", borderRadius: 9, padding: "8px 12px",
              marginBottom: 7, background: "var(--surface)",
            }}>
              <div className="row" style={{ gap: 7 }}>
                <span className={`badge ${DEC_BDG[p.decision] ?? "badge-neutral"}`}>{p.decision}</span>
                <span className="chip">{p.rule}</span>
                <span className="mono chip">t{e.tick}</span>
                <span className="spacer" />
                <span className="subtle tnum mono">evidencia #{e.seq}</span>
              </div>
              <div style={{ marginTop: 5, fontSize: 12.5 }}>
                Qué ocurrió: <b>{kindLabel}</b>{target && <> · <span className="mono">{target}</span></>}
                {p.tool ? <> · <span className="mono">{String(p.tool)}</span></> : null}
              </div>
              <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 2 }}>
                riesgo <span className="tnum">{p.risk_before?.toFixed(3)}</span> →{" "}
                <span className="tnum">{p.risk_after?.toFixed(3)}</span> · postura{" "}
                <b>{p.posture_from}</b> → <b>{p.posture_to}</b>
              </div>
              <div style={{ fontSize: 12, marginTop: 3 }}>
                <span className="subtle">regla: </span>{p.rationale ?? "—"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}