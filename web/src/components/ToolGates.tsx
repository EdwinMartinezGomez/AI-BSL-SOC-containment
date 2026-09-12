import type { AgentSnapshot } from "../types";

function GateRow({ name, open, note }: { name: string; open: boolean; note: string }) {
  return (
    <div className="gate-row">
      <span className={`gate-icon ${open ? "gate-open" : "gate-closed"}`}>{open ? "●" : "✕"}</span>
      <span style={{ fontWeight: 600, fontSize: 12.5 }}>{name}</span>
      <span className="spacer" />
      <span className="chip">{note}</span>
    </div>
  );
}

function FlagRow({ name, on }: { name: string; on: boolean }) {
  return <GateRow name={name} open={!on} note={on ? "activado por postura" : "desactivado"} />;
}

export default function ToolGates({ snap }: { snap: AgentSnapshot }) {
  const a = snap.actuator_state ?? {};
  const caps = snap.capability ?? {};
  const tools = caps.tools ?? [];
  const budget = snap.budget;
  const pct = budget.cap > 0 ? Math.min(100, Math.round((budget.used / budget.cap) * 100)) : 0;

  return (
    <div className="card">
      <h3>Capacidad C y compuertas físicas</h3>
      <div className="row" style={{ marginBottom: 10, gap: 5 }}>
        <span className="chip">N={caps.N}</span>
        <span className="chip">X={caps.X}</span>
        <span className="chip">M={caps.M}</span>
        <span className="chip">B={caps.B}</span>
        <span className="chip">K={caps.K}</span>
        <span className="chip">techo={snap.ceiling}</span>
      </div>

      <div style={{ marginBottom: 8 }}>
        <span className="subtle">Herramientas del perfil: </span>
        {tools.length === 0 && <span className="chip">sin tools</span>}
        {tools.map((t) => {
          const frozen = a.tools_frozen || a.tools_suspended.includes(t);
          return (
            <span key={t} className="chip"
              style={frozen ? { color: "var(--critical)", borderColor: "var(--critical)" } : undefined}>
              {frozen ? "✕ " : "✓ "}{t}
            </span>
          );
        })}
      </div>

      {budget.cap > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="subtle">Presupuesto de pasos autónomos (B)</span>
            <span className="mono tnum">{budget.used}/{budget.cap}</span>
          </div>
          <div style={{ height: 6, borderRadius: 4, background: "var(--surface-2)", border: "1px solid var(--border)", marginTop: 3 }}>
            <div style={{
              width: `${pct}%`, height: "100%", borderRadius: 4,
              background: pct >= 100 ? "var(--critical)" : pct >= 75 ? "var(--warning)" : "var(--series)",
            }} />
          </div>
        </div>
      )}

      <div className="subtle" style={{ marginBottom: 6 }}>Mecanismos de la infraestructura</div>
      <GateRow name="Workspace controlado (path-containment)" open={!snap.terminal} note={snap.gateway.workspace} />
      <GateRow
        name="Egress proxy (allowlist)"
        open={!a.egress_cut}
        note={snap.gateway.egress_allowlist?.join(", ") || "denegado por política"}
      />
      <GateRow
        name="Credential vault (opaco)"
        open={!a.creds_revoked_all}
        note={snap.gateway.vault_keys.length > 0 ? `${snap.gateway.vault_keys.length} claves · siempre [REDACTED]` : "sin claves"}
      />
      <GateRow name="Fail-closed guard" open={snap.fail_closed} note={snap.fail_closed ? "health ok" : "OFFLINE → deny por defecto"} />

      <div className="subtle" style={{ margin: "8px 0 6px" }}>Actuadores activados por postura</div>
      <FlagRow name="Egress cortado" on={a.egress_cut} />
      <FlagRow name="Tokens revocados" on={a.tokens_revoked} />
      <FlagRow name="Zonas aisladas" on={a.isolate_zones} />
      <FlagRow name="Tools congeladas (altas)" on={a.tools_frozen} />
      <FlagRow name="Credenciales revocadas (todas)" on={a.creds_revoked_all} />
      <FlagRow name="Instancias terminadas" on={a.instances_terminated} />
      <FlagRow name="Entorno reseteado" on={a.env_reset} />
      <FlagRow name="Ledger exportado a sink externo" on={a.ledger_exported} />
      <FlagRow name="Cuarentena" on={a.quarantine} />
      <FlagRow name="Terminación (P4)" on={a.terminate} />
      {a.resource_cap > 0 && a.resource_cap < 1 && (
        <GateRow name="Resource cap" open={a.resource_cap > 0} note={`×${a.resource_cap.toFixed(1)}`} />
      )}
    </div>
  );
}