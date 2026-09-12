import { useState } from "react";
import type { Review } from "../types";

export default function ReviewQueue({
  reviews, onDecide, busy,
}: {
  reviews: Review[];
  onDecide: (rid: string, decision: "approve" | "deny", note: string) => void;
  busy: boolean;
}) {
  const [note, setNote] = useState<Record<string, string>>({});
  const open = reviews.filter((r) => r.status === "open");
  const decided = reviews.filter((r) => r.status !== "open").slice(-8);

  return (
    <div className="card" style={{ maxHeight: 560, display: "flex", flexDirection: "column" }}>
      <h3>
        Aprobación humana (authority)
        <span className="hint">{open.length} abiertas</span>
      </h3>
      <div className="scroll-y">
        {open.length === 0 && (
          <div className="subtle" style={{ padding: "6px 0" }}>
            Sin revisiones pendientes. Los REVIEW_REQUIRED (techo) y P4_REQUEST aparecerán aquí para que el operador decida.
          </div>
        )}
        {open.map((r) => (
          <div key={r.review_id} className={`review-card open`} style={{ marginBottom: 8 }}>
            <div className="row" style={{ gap: 6 }}>
              <span className={`badge ${r.tipo === "P4_REQUEST" ? "badge-critical" : "badge-warning"}`}>
                {r.tipo === "P4_REQUEST" ? "■ P4_REQUEST" : "▲ REVIEW_REQUIRED"}
              </span>
              <span className="chip">t{r.tick} · postura {r.postura}</span>
              <span className="spacer" />
              <span className="subtle mono">{r.review_id}</span>
            </div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              <b>¿Por qué?</b> {r.causa}
            </div>
            {r.tipo === "REVIEW_REQUIRED" ? (
              <div className="subtle" style={{ marginTop: 3 }}>
                Aprobar = aplicar <b>ceiling override</b> (permitir sobrepasar el techo {r.postura === "P3" ? "" : "de la postura"} del perfil, permaneciendo dentro del modelo). Denegar = mantener el bloqueo.
              </div>
            ) : (
              <div className="subtle" style={{ marginTop: 3 }}>
                Aprobar = autorizar <b>P4</b>: terminación, cuarentena y revisión forense del agente.
              </div>
            )}
            <div className="row" style={{ marginTop: 6 }}>
              <input type="text" placeholder="nota del operador (opcional)"
                value={note[r.review_id] ?? ""}
                onChange={(e) => setNote((n) => ({ ...n, [r.review_id]: e.target.value }))}
                style={{ flex: 1, minWidth: 120 }} />
              <button className="btn btn-primary" disabled={busy}
                onClick={() => onDecide(r.review_id, "approve", note[r.review_id] ?? "")}>Aprobar</button>
              <button className="btn" disabled={busy}
                onClick={() => onDecide(r.review_id, "deny", note[r.review_id] ?? "")}>Denegar</button>
            </div>
          </div>
        ))}
        {decided.length > 0 && (
          <>
            <div className="subtle" style={{ margin: "8px 0 4px" }}>Decididas recientemente</div>
            {decided.map((r) => (
              <div key={r.review_id} className="row" style={{ gap: 6, fontSize: 12, padding: "3px 0" }}>
                <span className={`badge ${r.decision === "approve" ? "badge-good" : "badge-neutral"}`}>{r.decision}</span>
                <span className="chip">t{r.tick}</span>
                <span>{r.tipo}</span>
                <span className="spacer" />
                <span className="subtle mono">{r.review_id}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}