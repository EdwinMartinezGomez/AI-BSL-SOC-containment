import type { Outcome } from "../types";
import { KIND_EN } from "../types";

export default function EventFeed({ events = [], limit = 40 }: { events: Outcome[]; limit?: number }) {
  const rows = [...events].reverse().slice(0, limit);
  return (
    <div className="card">
      <h3>Feed de eventos observados</h3>
      <div className="feed">
        {rows.length === 0 && <div className="subtle">Sin eventos todavía.</div>}
        {rows.map((e, i) => {
          const kindLabel = KIND_EN[e.kind] ?? e.kind;
          return (
            <div className="item" key={i}>
              <span className="t">t{e.tick}</span>
              <span className="mono chip">{e.kind}</span>
              <span className="body">{kindLabel}</span>
              <span className="spacer" />
              {e.dangerous && <span className="badge badge-serious">peligroso</span>}
              {e.blocked && <span className="badge badge-critical">bloqueado</span>}
              {e.contained && !e.blocked && <span className="badge badge-good">contenido</span>}
              {e.dangerous && !e.contained && <span className="badge badge-critical">cometido</span>}
              {e.signal && <span className="chip">{e.signal}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}