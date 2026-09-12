// AI-BSL — hook WebSocket (con reconexión) con fallback SSE.
import { useEffect, useRef, useState } from "react";
import type { WsMessage } from "../types";

const MAX_FEED = 400;

export type ConnState = "connecting" | "open" | "closed" | "sse";

export function useEvents(agentId?: string | null): {
  state: ConnState;
  feed: WsMessage[];
  lastPerType: Map<string, WsMessage>;
} {
  const [state, setState] = useState<ConnState>("connecting");
  const [feed, setFeed] = useState<WsMessage[]>([]);
  const lastRef = useRef(new Map<string, WsMessage>());
  const [, force] = useState(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let es: EventSource | null = null;
    let disposed = false;
    let retries = 0;

    const incoming = (msg: WsMessage) => {
      if (agentId && msg.agent_id !== agentId) return;
      lastRef.current.set(msg.type, msg);
      setFeed((f) => [...f.slice(-(MAX_FEED - 1)), msg]);
      force((n) => n + 1);
    };

    const openWs = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      try {
        ws = new WebSocket(`${proto}://${location.host}/ws/events`);
      } catch {
        openSSE();
        return;
      }
      ws.onopen = () => { setState("open"); retries = 0; };
      ws.onmessage = (ev) => {
        try { incoming(JSON.parse(ev.data as string) as WsMessage); } catch { /* ignore */ }
      };
      ws.onclose = () => {
        if (disposed) return;
        setState((s) => (s === "open" ? "closed" : s));
        const backoff = Math.min(1000 * 2 ** retries, 8000);
        retries += 1;
        window.setTimeout(() => { if (!disposed) openWs(); }, backoff);
      };
      ws.onerror = () => { /* onclose handles retry */ };
    };

    const openSSE = () => {
      setState("sse");
      const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
      es = new EventSource(`/sse/events${query}`);
      es.onmessage = (ev) => {
        try { incoming(JSON.parse((ev as MessageEvent).data as string) as WsMessage); } catch { /* ignore */ }
      };
      es.onerror = () => {
        es?.close();
        if (!disposed) window.setTimeout(() => { if (!disposed) openSSE(); }, 3000);
      };
    };

    openWs();
    return () => {
      disposed = true;
      ws?.close();
      es?.close();
    };
  }, [agentId]);

  return { state, feed, lastPerType: lastRef.current };
}

export function lastOf<T extends WsMessage>(map: Map<string, WsMessage>, type: string): T | undefined {
  const m = map.get(type);
  return m ? (m as unknown as T) : undefined;
}