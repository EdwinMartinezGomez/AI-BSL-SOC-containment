import { postureTone, type AgentSummary } from "../types";

const TONE_CLS: Record<string, string> = {
  good: "badge-good", warning: "badge-warning",
  serious: "badge-serious", critical: "badge-critical", neutral: "badge-neutral",
};

export default function AgentPicker({
  agents, selected, onSelect, loading,
}: {
  agents: AgentSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
}) {
  const sel = agents.length ? agents.find((a) => a.agent.id === selected) ?? agents[0] : null;
  return (
    <div className="row" style={{ gap: 8 }}>
      {loading && <span className="status-dot warn" title="cargando" />}
      <select
        value={selected ?? ""}
        disabled={agents.length === 0 || loading}
        onChange={(e) => { if (e.target.value) onSelect(e.target.value); }}
        style={{ minWidth: 180 }}
      >
        {agents.length === 0 && <option value="">sin agentes</option>}
        {agents.map((a) => (
          <option key={a.agent.id} value={a.agent.id}>
            {a.agent.name} · {a.agent.mode} · {a.agent.profile}
          </option>
        ))}
      </select>
      {sel && (
        <>
          {sel.agent.mode === "sim" && <span className="badge badge-neutral">lab</span>}
          <span className={`badge ${sel.terminal ? "badge-critical" : TONE_CLS[postureTone(sel.posture ?? "P0")]}`}>
            {sel.posture ?? "—"}
          </span>
          {sel.r !== null && <span className="chip tnum">r={sel.r?.toFixed(3)}</span>}
          <span className="chip">techo {sel.ceiling}</span>
          {sel.ledger && (
            <span className={`chip`} title="ledger verify">
              <span style={{ color: sel.ledger.verify_ok ? "var(--good)" : "var(--critical)" }}>
                {sel.ledger.verify_ok ? "ledger ✓" : "ledger ✕"}
              </span>
            </span>
          )}
          {sel.terminal && <span className="badge badge-neutral">terminado (P4)</span>}
        </>
      )}
    </div>
  );
}