// AI-BSL — cliente REST tipado contra /api/v1 (proxy Vite → 127.0.0.1:8000).
export const API_BASE = "/api/v1";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = (body && typeof body === "object" && "error" in body)
      ? String((body as { error: unknown }).error)
      : String(body);
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return body as T;
}

const get = <T>(p: string) => http<T>(p);
const post = <T>(p: string, data?: unknown) =>
  http<T>(p, { method: "POST", body: data !== undefined ? JSON.stringify(data) : undefined });

export const api = {
  health: () => get<HealthShape>("/health"),
  agents: () => get<{ agents: AgentSummaryShape[] }>("/agents"),
  createAgent: (name: string, profile: string, mode = "live") =>
    post<{ agent: AgentInfoShape }>(`/agents`, { name, profile, mode }),
  agent: (id: string) => get<AgentSnapshotShape>(`/agents/${id}`),
  preexec: (id: string, req: EnforceReq) => post<PreexecResp>(`/agents/${id}/actions/preexec`, req),
  inject: (id: string, events: unknown[]) => post<unknown>(`/agents/${id}/events`, events),
  ledger: (id: string) => get<LedgerRespShape>(`/agents/${id}/ledger`),
  ledgerVerify: (id: string) => post<{ ok: boolean; bad_seqs: number[]; count: number }>(`/agents/${id}/ledger/verify`),
  reviews: (id: string, status = "open") => get<{ reviews: ReviewShape[] }>(`/agents/${id}/reviews?status=${status}`),
  decide: (id: string, reviewId: string, decision: string, note: string) =>
    post<unknown>(`/agents/${id}/reviews/${reviewId}/decide`, { decision, by: "operator", note }),
  metrics: (id: string) => get<MetricsShape>(`/agents/${id}/metrics`),
  setOffline: (id: string, offline: boolean) =>
    post<{ ok: boolean; fresh: boolean; reason: string; checked_at: string }>(`/agents/${id}/offline`, { offline }),
  scenarios: () => get<{ scenarios: ScenarioShape[] }>("/scenarios"),
  runScenario: (id: string) => post<LabResultShape>(`/scenarios/${id}/run`),
};

type HealthShape = import("../types").Health;
type AgentSummaryShape = import("../types").AgentSummary;
type AgentInfoShape = import("../types").AgentInfo;
type AgentSnapshotShape = import("../types").AgentSnapshot;
type LedgerRespShape = import("../types").LedgerResponse;
type ReviewShape = import("../types").Review;
type MetricsShape = import("../types").Metrics;
type ScenarioShape = import("../types").ScenarioInfo;
type LabResultShape = import("../types").LabResult;

export interface EnforceReq {
  action_id?: string;
  type: string; // file | network | credential | exec | resource | memory | tool
  tool?: string;
  name?: string;
  target?: string;
  declared?: boolean;
  cred_mode?: "read" | "use";
  encoded?: boolean;
  detail?: Record<string, unknown>;
}

export interface PreexecResp {
  action_id: string;
  decision: "ALLOW" | "BLOCK" | "HOLD_REVIEW";
  rule: string;
  rationale: string;
  signal: string | null;
  category?: string;
  target?: string;
  tick: number;
  evidence_seq: number | null;
  risk_before: number;
  risk_after: number;
  posture: string;
  ceiling: string;
  execution: { ok: boolean; result: string; signal_hint?: string } | null;
  mechanism_allowed: boolean;
}