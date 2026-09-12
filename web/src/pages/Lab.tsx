import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { AgentSnapshot, LabResult, Outcome, ScenarioInfo, Transition } from "../types";
import RiskTimeline from "../components/RiskTimeline";
import IntensityChart from "../components/IntensityChart";
import EventFeed from "../components/EventFeed";
import { fmtTick } from "../lib/format";

// Hash final reproducido por `engine/export_scenarios.py` (paper). El Lab debe
// recomponer EXACTAMENTE el mismo hash: misma ruta engine.run, mismo modelo.
const EXPORT_HASH: Record<string, string> = {
  s01_normal: "0a1aa0851b", s02_out_of_scope: "2121a82ca0", s03_resource: "82240bfa15",
  s04_egress: "c1ef7c696f", s05_combinacion: "b351b71e78", s06_credential: "a6df8ab9eb",
  s07_tampering: "61d9e3eb51", s08_persistence: "1574a1ad7b", s09_blind_spot: "f3b32b9743",
  s10_fp_probe: "b10b754cca", s11_ceiling_gate: "708bc7dc50",
};

function deriveTransitions(hist: LabResult["posture_history"]): Transition[] {
  const out: Transition[] = [];
  for (let i = 1; i < hist.length; i++) {
    const prev = hist[i - 1]; const cur = hist[i];
    if (cur.posture !== prev.posture) {
      out.push({ tick: cur.tick, from: prev.posture, to: cur.posture, causa: "cambio de postura", r: cur.r, I_peak: cur.I });
    }
  }
  return out;
}

const EMPTY_ACT = {
  posture_derived: {}, tools_suspended: [], log_verbosity: "normal", resource_cap: 0,
  egress_cut: false, tokens_revoked: false, isolate_zones: false, tools_frozen: false,
  creds_revoked_all: false, instances_terminated: false, env_reset: false,
  ledger_exported: false, terminate: false, quarantine: false, forensic_review: false,
  redeploy_decision: false,
};

export default function Lab() {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [result, setResult] = useState<LabResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    api.scenarios().then(({ scenarios: s }) => {
      setScenarios(s);
      if (s.length) setSelected((cur) => cur || s[0].id);
    }).catch(() => setError("No se pudo cargar el catálogo de escenarios."));
  }, []);

  const run = async () => {
    setError("");
    setRunning(true);
    try {
      const r = await api.runScenario(selected);
      setResult(r);
    } catch (e) {
      setError(String((e as Error).message) || "Error al correr el escenario");
    } finally { setRunning(false); }
  };

  const snap: AgentSnapshot | null = useMemo(() => {
    if (!result) return null;
    const last = result.posture_history[result.posture_history.length - 1];
    return {
      agent: { id: result.scenario_id, name: result.scenario_id, mode: "sim", profile: result.profile ?? "med",
        policy_version: "", status: result.final_posture === "P4" ? "terminated" : "active", created_at: "" },
      capability: { N: "-", X: "-", M: "-", B: 0, K: 0, tools: [] },
      ceiling: "", posture: result.final_posture as AgentSnapshot["posture"],
      r: last?.r ?? 0, I: last?.I ?? {}, tick: last?.tick ?? 0,
      actuator_state: EMPTY_ACT,
      gateway: { workspace: "engine (sim)", egress_allowlist: null, vault_keys: [] },
      fail_closed: true, terminal: result.final_posture === "P4", killswitch: result.final_posture === "P4",
      budget: { used: 0, cap: 0, instances: 0 },
      ledger: { count: 0, final_hash: result.ledger_final_hash, verify_ok: true },
      open_reviews: [],
      posture_history: result.posture_history,
      transitions: deriveTransitions(result.posture_history),
      events: result.events as Outcome[],
    };
  }, [result]);

  const meta = scenarios.find((s) => s.id === selected);
  const exported = result ? EXPORT_HASH[result.scenario_id] : undefined;
  const match = result && exported ? result.ledger_final_hash.startsWith(exported) : null;

  return (
    <div className="layout" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))" }}>
      <div className="card" style={{ gridColumn: "1 / -1" }}>
        <h3>Laboratorio (simulación) — misma ruta del paper</h3>
        <div className="row" style={{ gap: 8 }}>
          <span className="subtle">Escenario:</span>
          <select value={selected} onChange={(e) => { setSelected(e.target.value); setResult(null); }}
            style={{ minWidth: 220 }}>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.id} · {s.nota}</option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={run} disabled={running || !selected}>
            {running ? "Corriendo…" : "Correr escenario"}
          </button>
          {error && <span className="badge badge-critical">{error}</span>}
        </div>
        {meta && (
          <div className="row" style={{ marginTop: 6 }}>
            <span className="chip">agente: {meta.agente}</span>
            <span className="chip">ventana: {meta.window_ticks} ticks</span>
            <span className="chip">postura esperada: {meta.postura_esperada}</span>
          </div>
        )}
      </div>

      {result && snap && (
        <>
          <div style={{ gridColumn: "span 2" }}>
            <RiskTimeline
              history={result.posture_history}
              transitions={snap.transitions}
              enforcements={[]}
            />
          </div>
          <div className="card">
            <h3>Resultado del scenario</h3>
            <div className="stat-wrap">
              <div className="stat-label">postura final</div>
              <div className="hero" style={{
                color: result.final_posture === "P4" ? "var(--critical)"
                  : result.final_posture === "P3" ? "var(--critical)"
                  : result.final_posture === "P2" ? "var(--serious)"
                  : result.final_posture === "P1" ? "var(--warning)" : "var(--good)",
              }}>{result.final_posture}</div>
            </div>
            <div style={{ marginTop: 8 }}>
              <div className="subtle">ledger_final_hash</div>
              <div className="mono" style={{ fontSize: 12, wordBreak: "break-all" }}>{result.ledger_final_hash}</div>
              {exported && (
                <div className="row" style={{ marginTop: 6 }}>
                  <span className={`badge ${match ? "badge-good" : "badge-critical"}`}>
                    <span className="icon">{match ? "✓" : "✕"}</span>
                    {match ? "coincide con engine/exports/" + result.scenario_id + ".json" : "¡DIVERGE del export!"}
                  </span>
                  <span className="chip mono">esperado {exported}…</span>
                </div>
              )}
            </div>
            {result.review_required.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div className="subtle">revisiones humanas solicitadas ({result.review_required.length})</div>
                {result.review_required.map((r, i) => (
                  <div key={i} className="subtle" style={{ fontSize: 12 }}>
                    · {fmtTick(Number(r.tick))} {String(r.tipo)} — {String(r.causa)}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <IntensityChart history={result.posture_history} />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <EventFeed events={result.events as Outcome[]} />
          </div>
        </>
      )}
    </div>
  );
}