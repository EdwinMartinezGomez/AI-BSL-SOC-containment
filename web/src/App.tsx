import { useEffect, useState } from "react";
import { api } from "./api/client";
import { useEvents } from "./ws/useEvents";
import { applyTheme, toggleTheme, isDark } from "./lib/theme";
import type { AgentSummary } from "./types";
import AgentPicker from "./components/AgentPicker";
import Dashboard from "./pages/Dashboard";
import Lab from "./pages/Lab";

const CONN: Record<string, { cls: string; label: string }> = {
  open: { cls: "on", label: "en vivo" },
  sse: { cls: "warn", label: "SSE" },
  connecting: { cls: "warn", label: "conectando" },
  closed: { cls: "off", label: "sin conexión" },
};

export default function App() {
  const [mode, setMode] = useState<"live" | "lab">("live");
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [, setTick] = useState(0);

  useEffect(() => { applyTheme(); }, []);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { agents: list } = await api.agents();
        if (!alive) return;
        setAgents(list);
        setSelected((s) => (s && list.some((a) => a.agent.id === s) ? s : (list[0]?.agent.id ?? null)));
      } catch { /* servidor no disponible aún */ }
    };
    load();
    const id = window.setInterval(load, 4000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);

  const live = useEvents(mode === "live" ? selected : null);
  const conn = CONN[live.state] ?? CONN.closed;

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          AI-BSL <span style={{ color: "var(--muted)", fontWeight: 500 }}>· SOC containment</span>
        </div>

        <div className="mode-switch">
          <button className={mode === "live" ? "active" : ""} onClick={() => setMode("live")}>Live</button>
          <button className={mode === "lab" ? "active" : ""} onClick={() => setMode("lab")}>Lab</button>
        </div>

        {mode === "live" && (
          <AgentPicker
            agents={agents}
            selected={selected}
            onSelect={setSelected}
            loading={agents.length === 0}
          />
        )}

        <span className="spacer" />

        <span className="row" style={{ gap: 6 }}>
          <span className={`status-dot ${conn.cls}`} title={conn.label} />
          <span className="subtle">{conn.label}</span>
        </span>

        <button className="btn btn-ghost" onClick={() => { toggleTheme(); setTick((n) => n + 1); }}>
          {isDark() ? "🌙 dark" : "☀ light"}
        </button>
      </header>

      {mode === "live"
        ? <Dashboard agentId={selected} live={live} />
        : <Lab />}
    </>
  );
}