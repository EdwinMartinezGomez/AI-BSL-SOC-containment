import { useState } from "react";
import { api, type EnforceReq, type PreexecResp } from "../api/client";

// Coreografía del "driver controlado" (demo/driver.py) — acciones benignas
// permitidas o denegadas por la infraestructura. Nunca exploits/evasión.
const ACTIONS: { label: string; req: EnforceReq; desc: string }[] = [
  { label: "search docs", req: { type: "tool", tool: "search", target: "docs" }, desc: "búsqueda en workspace · esperado ALLOW (P0)" },
  { label: "read dentro workspace", req: { type: "file", tool: "read_file", target: "workspace/notas.md", declared: true }, desc: "lectura permitida por el workspace" },
  { label: "read ../secrets/*", req: { type: "file", tool: "read_file", target: "../secrets/master.key", declared: false }, desc: "fuera del realpath del workspace → señal access_out_of_scope" },
  { label: "connect evil.example", req: { type: "network", tool: "connect", target: "http://evil.example" }, desc: "egreso fuera del allowlist → egress_anomaly" },
  { label: "vault credential read", req: { type: "credential", tool: "credential_read", target: "vault:db", cred_mode: "read" }, desc: "vault opaco → [REDACTED] + credential_collect" },
  { label: "exec divergente", req: { type: "exec", tool: "exec_managed", target: "report.sh", declared: false }, desc: "fuera del exec allowlist → exec_layer_divergence" },
  { label: "reintento (retry)", req: { type: "network", tool: "connect", target: "http://evil.example" }, desc: "misma firma ya bloqueada → retry_after_block" },
];

export default function DemoControls({ agentId, onAction }: {
  agentId: string | null;
  onAction?: (r: PreexecResp) => void;
}) {
  const [last, setLast] = useState<PreexecResp | null>(null);
  const [busy, setBusy] = useState(false);
  const [offline, setOffline] = useState(false);
  const [name, setName] = useState("demo-agent");
  const [profile, setProfile] = useState("med");

  const send = async (req: EnforceReq, label: string) => {
    if (!agentId) return;
    setBusy(true);
    try {
      const r = await api.preexec(agentId, { ...req, action_id: `${label.replace(/\W+/g, "_")}_${Date.now().toString(36)}` });
      setLast(r);
      onAction?.(r);
    } catch (e) {
      setLast({ action_id: "", decision: "BLOCK", rule: "api_error", rationale: String((e as Error).message),
        signal: null, tick: -1, evidence_seq: null, risk_before: 0, risk_after: 0, posture: "-", ceiling: "-",
        execution: null, mechanism_allowed: false });
    } finally {
      setBusy(false);
    }
  };

  const register = async () => {
    try {
      const created = await api.createAgent(name.trim() || "demo-agent", profile);
      const id = (created.agent as unknown as { id: string }).id;
      onAction?.({ action_id: "", decision: "ALLOW", rule: "register", rationale: `agente ${id} registrado`,
        signal: null, tick: 0, evidence_seq: null, risk_before: 0, risk_after: 0, posture: "P0", ceiling: "-",
        execution: null, mechanism_allowed: true });
    } catch (e) {
      setLast({ action_id: "", decision: "BLOCK", rule: "register_error", rationale: String((e as Error).message),
        signal: null, tick: -1, evidence_seq: null, risk_before: 0, risk_after: 0, posture: "-", ceiling: "-",
        execution: null, mechanism_allowed: false });
    }
  };

  const toggleOffline = async () => {
    if (!agentId) return;
    const next = !offline;
    setOffline(next);
    try { await api.setOffline(agentId, next); } catch { /* ignore */ }
  };

  return (
    <div className="card">
      <h3>Disparador de acciones del agente controlado (demo)</h3>
      <div className="subtle" style={{ marginBottom: 8 }}>
        Envía solicitudes pre-ejecución por la misma vía que el driver (POST /actions/preexec). La
        infraestructura decide ALLOW / BLOCK / HOLD_REVIEW antes de ejecutar y todo queda en el ledger.
      </div>
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 7 }}>
        {ACTIONS.map((a) => (
          <button key={a.label} className="btn" disabled={!agentId || busy} title={a.desc}
            onClick={() => send(a.req, a.label)}>
            {a.label}
          </button>
        ))}
      </div>
      <footer className="subtle" style={{ marginTop: 6 }}>
        {ACTIONS.map((a) => (
          <div key={a.label} style={{ fontSize: 11.5 }}>· <b>{a.label}</b> — {a.desc}</div>
        ))}
      </footer>

      <div className="row" style={{ marginTop: 10, borderTop: "1px solid var(--gridline)", paddingTop: 10 }}>
        <span className="subtle">Registrar agente:</span>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 130 }} />
        <select value={profile} onChange={(e) => setProfile(e.target.value)}>
          <option value="high">high</option><option value="med">med</option><option value="low">low</option>
        </select>
        <button className="btn" onClick={register}>Registrar</button>
        <span className="spacer" />
        <button className="btn" disabled={!agentId || busy} onClick={toggleOffline} title="prueba fail-closed">
          {offline ? "Restaurar canal (online)" : "Simular corte del canal (offline → deny)"}
        </button>
      </div>

      {last && (
        <div className="row" style={{ marginTop: 8 }}>
          <span className={`badge ${last.decision === "ALLOW" ? "badge-good" : last.decision === "BLOCK" ? "badge-critical" : "badge-warning"}`}>
            {last.decision}
          </span>
          <span className="chip">{last.rule}</span>
          <span className="subtle">t{last.tick} · r {last.risk_before.toFixed(3)}→{last.risk_after.toFixed(3)}</span>
          <span className="subtle" style={{ flex: 1 }}>{last.rationale}</span>
        </div>
      )}
    </div>
  );
}