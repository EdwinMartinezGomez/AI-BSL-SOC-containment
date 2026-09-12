import { useState } from "react";
import type { LedgerResponse } from "../types";
import { shortHash } from "../types";

async function sha256Hex(s: string): Promise<string> {
  if (!crypto?.subtle) throw new Error("crypto.subtle no disponible");
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

const KIND_CLS: Record<string, string> = {
  evento: "badge-neutral", postura: "badge-serious", final: "badge-good",
  enforcement: "badge-critical", review: "badge-warning", approval_human: "badge-good",
  agent_state: "badge-neutral", forensic: "badge-neutral",
};

type VerState = "idle" | "running" | "ok" | "bad" | "unsupported";

export default function LedgerPanel({ ledger }: { ledger: LedgerResponse }) {
  const [ver, setVer] = useState<VerState>("idle");
  const [detail, setDetail] = useState<string>("");

  const runVerify = async () => {
    setVer("running");
    try {
      let prev = "";
      for (const e of ledger.entries) {
        if (e.prev_hash !== prev) {
          setVer("bad");
          setDetail(`Entrada ${e.seq}: prev_hash ${shortHash(e.prev_hash)} ≠ hash de la anterior (${shortHash(prev)})`);
          return;
        }
        const h = await sha256Hex(`${e.prev_hash}|${e.tick}|${e.kind}|${e.canon}`);
        if (h !== e.hash) {
          setVer("bad");
          setDetail(`Entrada ${e.seq}: SHA-256 recomputado ${shortHash(h)} ≠ almacenado ${shortHash(e.hash)}`);
          return;
        }
        prev = e.hash;
      }
      setVer("ok");
      setDetail(`${ledger.entries.length} entradas verificadas en el navegador (misma cadena sha256(prev|tick|kind|canon)).`);
    } catch {
      setVer("unsupported");
      setDetail("crypto.subtle no disponible aquí — usa la verificación del servidor (verify_ok).");
    }
  };

  const entries = [...ledger.entries].reverse().slice(0, 60);

  return (
    <div className="card">
      <h3>
        Ledger inmutable · SHA-256 hash-chain
        <span className="hint">
          <span className="row" style={{ gap: 6 }}>
            <span className={`chip ${ledger.verify_ok ? "" : ""}`} style={ledger.verify_ok ? { color: "var(--good)", borderColor: "var(--good)" } : { color: "var(--critical)", borderColor: "var(--critical)" }}>
              {ledger.verify_ok ? "✓ verificado (servidor)" : "✕ verify server"}
            </span>
            <span className="chip">espejo externo: {ledger.mirror_len} entradas</span>
          </span>
        </span>
      </h3>

      <div className="row" style={{ marginBottom: 9 }}>
        <button className="btn btn-primary" onClick={runVerify} disabled={ver === "running"}>
          {ver === "running" ? "Verificando…" : "Re-verificar SHA-256 en el navegador"}
        </button>
        {ver === "ok" && <span className="badge badge-good"><span className="icon">✓</span>cadena íntegra</span>}
        {ver === "bad" && <span className="badge badge-critical"><span className="icon">✕</span>¡tamper detectado!</span>}
        {ver === "unsupported" && <span className="badge badge-warning">sin crypto.subtle</span>}
      </div>
      {detail && <div className="subtle mono" style={{ marginBottom: 8 }}>{detail}</div>}

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
        {(["evento", "postura", "enforcement", "review", "approval_human", "agent_state", "final", "forensic"] as const).map((k) => {
          const n = ledger.entries.filter((e) => e.kind === k).length;
          return n > 0 ? <span key={k} className={`badge ${KIND_CLS[k] ?? "badge-neutral"}`}>{k}·{n}</span> : null;
        })}
      </div>

      <div className="scroll-y" style={{ maxHeight: 300 }}>
        <table className="data">
          <thead>
            <tr><th>seq</th><th>tick</th><th>kind</th><th>payload</th><th>prev_hash</th><th>hash</th></tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.seq}>
                <td className="tnum">{e.seq}</td>
                <td className="tnum">t{e.tick}</td>
                <td><span className={`badge ${KIND_CLS[e.kind] ?? "badge-neutral"}`}>{e.kind}</span></td>
                <td className="mono" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {JSON.stringify(e.payload).slice(0, 70)}
                </td>
                <td className="mono tnum">{shortHash(e.prev_hash, 8)}</td>
                <td className="mono tnum">{shortHash(e.hash, 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {ledger.entries.length === 0 && <div className="subtle" style={{ marginTop: 8 }}>Ledger vacío.</div>}
      </div>
      <div className="subtle" style={{ marginTop: 8 }}>
        final_hash: <span className="mono">{ledger.final_hash}</span> · {ledger.count} entradas · esquema
        <span className="mono"> sha256(prev|tick|kind|canonical_json)</span> — nunca se modificó.
      </div>
    </div>
  );
}