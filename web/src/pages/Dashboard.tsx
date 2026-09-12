import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  EnforcementMsg, LedgerResponse, Metrics, Review, WsMessage,
} from "../types";
import RiskTimeline from "../components/RiskTimeline";
import PostureGauge from "../components/PostureGauge";
import IntensityChart from "../components/IntensityChart";
import EventFeed from "../components/EventFeed";
import EnforcementLog from "../components/EnforcementLog";
import ToolGates from "../components/ToolGates";
import LedgerPanel from "../components/LedgerPanel";
import ReviewQueue from "../components/ReviewQueue";
import MetricsPanel from "../components/MetricsPanel";
import DemoControls from "../components/DemoControls";

function usePoll<T>(fn: () => Promise<T>, ms: number, enabled: boolean): T | null {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const tick = async () => {
      try { const v = await fn(); if (alive) setData(v); } catch { /* servidor reiniciando */ }
    };
    tick();
    const id = window.setInterval(tick, ms);
    return () => { alive = false; window.clearInterval(id); };
  }, [fn, ms, enabled]);
  return data;
}

export default function Dashboard({
  agentId, live,
}: {
  agentId: string | null;
  live: { feed: WsMessage[]; state: string };
}) {
  const snap = usePoll(() => (agentId ? api.agent(agentId) : Promise.resolve(null)), 2000, !!agentId);
  const metrics = usePoll(() => (agentId ? api.metrics(agentId) : Promise.resolve(null)), 3000, !!agentId);
  const ledger = usePoll(() => (agentId ? api.ledger(agentId) : Promise.resolve(null)), 4000, !!agentId);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewBusy, setReviewBusy] = useState(false);

  // enforcement en vivo desde WS (marcador inmediato en la timeline)
  const liveEnf = useMemo(() => {
    const out: (EnforcementMsg & { tick: number })[] = [];
    for (const m of live.feed) {
      if (m.agent_id !== agentId || m.type !== "enforcement") continue;
      out.push({ tick: m.tick, ...(m.payload as unknown as EnforcementMsg) });
    }
    return out.slice(-40);
  }, [live.feed, agentId]);

  useEffect(() => {
    if (!agentId) { setReviews([]); return; }
    let alive = true;
    const load = async () => {
      try {
        const r = await api.reviews(agentId, "open");
        if (alive) setReviews(r.reviews);
      } catch { /* ignore */ }
    };
    load();
    const id = window.setInterval(load, 2000);
    return () => { alive = false; window.clearInterval(id); };
  }, [agentId]);

  const decide = async (rid: string, decision: "approve" | "deny", note: string) => {
    if (!agentId) return;
    setReviewBusy(true);
    try {
      await api.decide(agentId, rid, decision, note);
      const r = await api.reviews(agentId, "open");
      setReviews(r.reviews);
    } finally { setReviewBusy(false); }
  };

  if (!agentId) {
    return (
      <div className="grid layout" style={{ placeItems: "center" }}>
        <div className="card">Registra o selecciona un agente para monitorear su contención en vivo.</div>
      </div>
    );
  }

  return (
    <div className="layout" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))" }}>
      {snap ? (
        <>
          <div style={{ gridColumn: "span 2" }}>
            <RiskTimeline history={snap.posture_history} transitions={snap.transitions} enforcements={liveEnf} />
          </div>
          <div>
            <PostureGauge snap={snap} />
          </div>
          <div>
            <MetricsPanel metrics={metrics as Metrics | null} snap={snap} />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <IntensityChart history={snap.posture_history} />
          </div>
          <div>
            <ReviewQueue reviews={reviews} onDecide={decide} busy={reviewBusy} />
          </div>
          <div>
            <EventFeed events={snap.events} />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <EnforcementLog entries={ledger?.entries ?? []} />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            {ledger && <LedgerPanel ledger={ledger as LedgerResponse} />}
          </div>
          <div>
            <ToolGates snap={snap} />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <DemoControls agentId={agentId} />
          </div>
        </>
      ) : (
        <div className="card" style={{ gridColumn: "1 / -1" }}>Cargando agente…</div>
      )}
    </div>
  );
}