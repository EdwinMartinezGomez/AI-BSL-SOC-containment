// AI-BSL dashboard — tipos del contrato (espejo 1:1 de platform/types.py + API).
// Posturas, capacidad C, riesgo r(t)/I_c(t), señales, enforcement, ledger, reviews.

export const POSTURES = ["P0", "P1", "P2", "P3", "P4"] as const;
export type Posture = (typeof POSTURES)[number];

export interface Capability {
  N: string; // none | proxy | full
  X: string; // none | managed | native
  M: string; // none | session | persistent
  B: number; // presupuesto de pasos autónomos
  K: number; // instancias concurrentes
  tools: string[];
}

export interface AgentInfo {
  id: string;
  name: string;
  mode: string; // "live" | "sim"
  profile: string; // high | med | low
  policy_version: string;
  status: string;
  created_at: string;
}

export interface AgentSummary {
  agent: AgentInfo;
  posture: Posture | null;
  r: number | null;
  ceiling: string;
  tick: number | null;
  ledger: { count: number; final_hash: string; verify_ok: boolean } | null;
  open_reviews: number | null;
  terminal: boolean | null;
}

export interface HistoryPoint {
  tick: number;
  posture: Posture;
  r: number;
  I: Record<string, number>;
}

export interface Transition {
  tick: number;
  from: Posture;
  to: Posture;
  causa: string;
  r: number;
  I_peak: Record<string, number>;
}

export interface Outcome {
  tick: number;
  kind: string;
  signal?: string | null;
  target?: string | null;
  dangerous: boolean;
  blocked: boolean;
  contained: boolean;
  detail?: Record<string, unknown>;
}

export interface Review {
  review_id: string;
  agent_id: string;
  tick: number;
  tipo: string; // REVIEW_REQUIRED | P4_REQUEST
  causa: string;
  postura: string;
  status: string; // open | decided
  decision?: string | null;
  note?: string | null;
  by?: string | null;
  decided_at?: string | null;
  ledger_seq?: number | null;
}

export interface LedgerEntry {
  seq: number;
  tick: number;
  kind: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  canon: string;
  hash: string;
}

export interface ActuatorState {
  posture_derived: Record<string, unknown>;
  tools_suspended: string[];
  log_verbosity: string;
  resource_cap: number;
  egress_cut: boolean;
  tokens_revoked: boolean;
  isolate_zones: boolean;
  tools_frozen: boolean;
  creds_revoked_all: boolean;
  instances_terminated: boolean;
  env_reset: boolean;
  ledger_exported: boolean;
  terminate: boolean;
  quarantine: boolean;
  forensic_review: boolean;
  redeploy_decision: boolean;
}

export interface BudgetInfo {
  used: number;
  cap: number;
  instances: number;
}

export interface AgentSnapshot {
  agent: AgentInfo;
  capability: Capability;
  ceiling: string;
  posture: Posture;
  r: number;
  I: Record<string, number>;
  tick: number;
  actuator_state: ActuatorState;
  gateway: {
    workspace: string;
    egress_allowlist: string[] | null;
    vault_keys: string[];
  };
  fail_closed: boolean;
  terminal: boolean;
  killswitch: boolean;
  budget: BudgetInfo;
  ledger: { count: number; final_hash: string; verify_ok: boolean };
  open_reviews: Review[];
  posture_history: HistoryPoint[];
  transitions: Transition[];
  events: Outcome[];
}

// Mensaje de WS/SSE: {agent_id, type, tick, ts, payload}
export type WsType =
  | "event"
  | "risk"
  | "posture"
  | "enforcement"
  | "review"
  | "approval"
  | "ledger"
  | "execution"
  | "agent";

export interface WsMessage {
  agent_id: string;
  type: WsType;
  tick: number;
  ts: string;
  payload: Record<string, unknown>;
}

export interface EnforcementMsg {
  action_id: string;
  tick?: number;
  decision: "ALLOW" | "BLOCK" | "HOLD_REVIEW";
  rule: string;
  rationale: string;
  signal: string | null;
  kind?: string;
  category?: string;
  tool?: string;
  target?: string;
  risk_before?: number;
  risk_after?: number;
  posture_from?: string;
  posture_to?: string;
  mechanism_allowed?: boolean;
  evidence_seq?: number | null;
}

export interface Metrics {
  eventos_totales: number;
  peligrosos: number;
  contenidos: number;
  cometidos: number;
  contained_rate: number;
  t_detect: number | null;
  t_respond: number | null;
  postura_final: string;
  posturas_alcanzadas: string[];
  review_required: number;
  verify_ok: boolean;
  ledger_hash: string;
  transiciones?: number;
  revisiones_abiertas?: number;
  modo?: string;
}

export interface ScenarioInfo {
  id: string;
  agente: string;
  window_ticks: number;
  nota: string;
  postura_esperada: string;
}

export interface LabResult {
  scenario_id: string;
  final_posture: string;
  posture_history: HistoryPoint[];
  events: Outcome[];
  review_required: Array<Record<string, unknown>>;
  ledger: {
    entries: Array<Record<string, unknown>>;
    ledger_ext: Array<Record<string, unknown>>;
  };
  ledger_final_hash: string;
  profile: string;
}

export interface Health {
  status: string;
  started_at: string;
  agents: number;
  ws_connections: { ws: number; sse: number };
  equivalence: { ok: boolean; passed: number; total: number; failures: string[] };
  fail_closed: { enabled: boolean };
}

export interface LedgerResponse {
  agent_id: string;
  entries: LedgerEntry[];
  count: number;
  final_hash: string;
  verify_ok: boolean;
  mirror_len: number;
}

export function postureTone(p: string): "good" | "warning" | "serious" | "critical" | "neutral" {
  switch (p) {
    case "P0": return "good";
    case "P1": return "warning";
    case "P2": return "serious";
    case "P3": return "critical";
    case "P4": return "critical";
    default: return "neutral";
  }
}

export const POSTURE_INFO: Record<Posture, { label: string; icon: string }> = {
  P0: { label: "P0 · operación normal", icon: "●" },
  P1: { label: "P1 · precaución", icon: "▲" },
  P2: { label: "P2 · contención", icon: "▲" },
  P3: { label: "P3 · respuesta", icon: "●" },
  P4: { label: "P4 · terminación", icon: "■" },
};

export const SIGNAL_EN = {
  access_out_of_scope: "acceso fuera de alcance",
  credential_collect: "recolección de credenciales",
  credential_use: "uso anómalo de credenciales",
  egress_anomaly: "egreso anómalo",
  encoded_exfil_prefix: "exfiltración codificada",
  resource_exceed: "exceso de recursos",
  evasion_retry: "evasión / reintento",
  log_tamper_attempt: "manipulación de logs",
  exec_layer_spoof: "divergencia de capa exec",
  coordination_undisclosed: "coordinación no declarada",
} as const;

export const KIND_EN: Record<string, string> = {
  tool_request_low: "tool_request · bajo riesgo",
  tool_request_high: "tool_request · alto riesgo",
  benign_action: "acción benigna",
  file_access_out_of_scope: "lectura de archivo fuera de alcance",
  credential_collect: "lectura de credencial",
  credential_use_anomalous: "uso de credencial",
  network_request_blocked: "conexión de red denegada",
  network_encoded_post: "post de red codificado",
  resource_budget_exceed: "presupuesto de recursos excedido",
  retry_after_block: "reintento tras bloqueo",
  log_tamper_detected: "manipulación de logs detectada",
  exec_layer_divergence: "divergencia de capa exec",
  coord_other_instance: "coordinación con otra instancia",
};

export function shortHash(h: string | undefined | null, n = 10): string {
  if (!h) return "—";
  return h.length > n ? h.slice(0, n) : h;
}