# -*- coding: utf-8 -*-
"""AI-BSL platform — Platform/controller: registro de agentes, orquestacion.

Capa que une el modelo formal (via AgentRuntime), la persistencia, el hub de
eventos y el gateway fisico. Expone las operaciones que sirve la API REST:
registrar/conectar agente, ingesta, pre-execution gate, revisiones humanas,
Lab (escenarios) y estado.
"""
from __future__ import annotations

import datetime
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from engine.engine import Engine, load_config, load_scenarios

from .db import Database
from .ws_hub import WSHub
from .policy_store import PolicyStore
from .runtime import AgentRuntime

PROFILES = {
    "high": {"N": "full", "X": "native", "M": "persistent", "B": 40, "K": 4,
             "tools": ["file", "net", "exec", "search"]},
    "med": {"N": "proxy", "X": "managed", "M": "session", "B": 20, "K": 2,
            "tools": ["file", "net"]},
    "low": {"N": "none", "X": "none", "M": "none", "B": 5, "K": 1, "tools": ["search"]},
}


def _profiles_from_scenarios() -> Dict[str, dict]:
    try:
        data = __import__("json").loads(
            (Path(__file__).parent.parent / "engine" / "scenarios.json")
            .read_text(encoding="utf-8"))
        return data["_perfiles"]
    except Exception:  # noqa: BLE001
        return PROFILES


class Platform:
    def __init__(self, data_dir: Optional[Path] = None):
        data_dir = data_dir or (Path(__file__).parent.parent / "data")
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir
        self.sandbox = data_dir / "sandbox"
        self.sandbox.mkdir(parents=True, exist_ok=True)

        self.config = load_config()
        self.db = Database(data_dir / "aibsl.db")
        self.hub = WSHub()
        self.policy = PolicyStore(db=self.db)
        self.runtimes: Dict[str, AgentRuntime] = {}
        self.start_time = datetime.datetime.now().isoformat()
        self._profiles = _profiles_from_scenarios()

    # ------------------------------------------------------------------
    # agentes
    # ------------------------------------------------------------------
    def register_agent(self, name: str, profile: str = "med", mode: str = "live",
                       policy_version: str = "v0.1") -> dict:
        if profile not in self._profiles:
            raise ValueError(f"perfil desconocido: {profile} (disponibles: "
                             f"{sorted(self._profiles)})")
        agent_id = "a-" + uuid.uuid4().hex[:8]
        cap = dict(self._profiles[profile])
        rt = AgentRuntime(self.config, agent_id, name, profile, cap, policy_version,
                          platform=self, mode=mode)
        self.db.save_agent({
            "id": agent_id, "name": name, "mode": mode, "profile": profile,
            "policy_version": policy_version, "capability": cap,
            "ceiling": rt.ceiling, "status": "active", "active": 1,
            "created_at": rt.created_at,
            "state_json": rt.snapshot(include_history=False),
        })
        return self.get_agent(agent_id, include_history=False)

    # -- snapshot default para un agente cuya fila persiste en la BD pero cuyo
    #    runtime NO esta vivo en este proceso (resurrected de un run anterior).
    #    Nunca devuelve colecciones undefined: el frontend itera estos campos.
    def _stale_snapshot(self, row: dict, include_history: bool = True) -> dict:
        cap = row.get("capability")
        # la BD guarda capability/state_json como JSON serializado (db.py).
        if isinstance(cap, str):
            try:
                cap = __import__("json").loads(cap)
            except Exception:  # noqa: BLE001
                cap = {}
        cap = cap or {}
        status = row.get("status") or "active"
        snapshot = {
            "agent": {"id": row["id"], "name": row["name"], "mode": row.get("mode", "live"),
                      "profile": row["profile"], "policy_version": row.get("policy_version", "v0.1"),
                      "created_at": row.get("created_at"), "status": status},
            "capability": cap,
            "ceiling": row.get("ceiling") or "P0",
            "posture": "P0",
            "r": 0.0,
            "I": {},
            "tick": 0,
            "actuator_state": {
                "posture_derived": {}, "tools_suspended": [], "log_verbosity": "normal",
                "resource_cap": 0, "egress_cut": False, "tokens_revoked": False,
                "isolate_zones": False, "tools_frozen": False, "creds_revoked_all": False,
                "instances_terminated": False, "env_reset": False, "ledger_exported": False,
                "terminate": False, "quarantine": False, "forensic_review": False,
                "redeploy_decision": False,
            },
            "gateway": {"workspace": "", "egress_allowlist": None, "vault_keys": []},
            "fail_closed": True,
            "terminal": status == "terminated",
            "killswitch": status == "terminated",
            "budget": {"used": 0, "cap": cap.get("B", 0), "instances": cap.get("K", 0)},
            "ledger": {"count": 0, "final_hash": "", "verify_ok": True},
            "open_reviews": [],
        }
        if include_history:
            snapshot["posture_history"] = []
            snapshot["transitions"] = []
            snapshot["events"] = []
        return snapshot

    def get_agent(self, agent_id: str, include_history: bool = True) -> dict:
        rt = self.runtimes.get(agent_id)
        if rt is None:
            row = self.db.get_agent_row(agent_id)
            if row is None:
                raise KeyError(f"agente {agent_id} no existe")
            return self._stale_snapshot(row, include_history=include_history)
        return rt.snapshot(include_history=include_history)

    def list_agents(self) -> List[dict]:
        rows = self.db.agents()
        out = []
        for r in rows:
            rt = self.runtimes.get(r["id"])
            if rt is not None:
                snap = rt.snapshot(include_history=False)
                out.append({
                    "agent": {"id": r["id"], "name": r["name"], "mode": r["mode"],
                              "profile": r["profile"],
                              "policy_version": r["policy_version"],
                              "status": rt.status,
                              "created_at": rt.created_at},
                    "posture": rt.post, "r": round(rt.r, 4), "ceiling": rt.ceiling,
                    "tick": rt.tick,
                    "ledger": {"count": rt.ledger.count(),
                               "final_hash": rt.ledger.final_hash(),
                               "verify_ok": rt.ledger_verify_ok()},
                    "open_reviews": len(snap["open_reviews"]),
                    "terminal": rt.terminal,
                })
            else:
                out.append({
                    "agent": {"id": r["id"], "name": r["name"], "mode": r["mode"],
                              "profile": r["profile"],
                              "policy_version": r["policy_version"],
                              "status": r["status"], "created_at": r["created_at"]},
                    "posture": None, "r": None, "ceiling": r["ceiling"], "tick": None,
                    "ledger": None, "open_reviews": None, "terminal": None,
                })
        return out

    # ------------------------------------------------------------------
    # operaciones por agente
    # ------------------------------------------------------------------
    def preexec_action(self, agent_id: str, req: dict) -> dict:
        return self._require(agent_id).preexec_action(req)

    def inject_events(self, agent_id: str, events: List[dict]) -> dict:
        rt = self._require(agent_id)
        return rt.ingest(events, source="api")

    def decide_review(self, agent_id: str, review_id: str, decision: str,
                      by: str, note: str = "") -> dict:
        return self._require(agent_id).decide_review(review_id, decision, by, note)

    def metrics(self, agent_id: str) -> dict:
        rt = self.runtimes.get(agent_id)
        if rt is not None:
            return rt.metrics()
        row = self.db.get_agent_row(agent_id)
        if row is None:
            raise KeyError(f"agente {agent_id} no existe")
        # agente persistido sin runtime vivo: metricas vacias y validas,
        # nunca 404 — el dashboard no debe crashear ni recibir un error.
        return {"agent_id": agent_id, "modo": "stale", "ledger_hash": "",
                "verify_ok": True, "t_detect": None, "t_respond": None,
                "contained_rate": None, "cometidos": 0, "contenidos": 0,
                "transiciones": 0, "revisiones_abiertas": 0, "determinismo": True}

    def set_offline(self, agent_id: str, offline: bool) -> dict:
        rt = self._require(agent_id)
        rt.failclosed.offline = bool(offline)
        return rt.failclosed.is_healthy()

    def tick_all_idle(self):
        for rt in self.runtimes.values():
            if rt.mode == "live" and not rt.terminal:
                rt.idle_tick()

    def _require(self, agent_id: str) -> AgentRuntime:
        rt = self.runtimes.get(agent_id)
        if rt is None:
            raise KeyError(f"agente {agent_id} no registrado")
        return rt

    # ------------------------------------------------------------------
    # Lab (simulacion = misma ruta del paper)
    # ------------------------------------------------------------------
    def list_scenarios(self) -> List[dict]:
        scs = load_scenarios()
        return [{"id": sc["id"], "agente": sc["agente"], "window_ticks": sc["window_ticks"],
                 "nota": sc.get("esperado", {}).get("nota", ""),
                 "postura_esperada": sc.get("esperado", {}).get("postura_final")}
                for sc in scs]

    def run_lab(self, scenario_id: str) -> dict:
        eng = Engine(self.config)
        sc = next((s for s in load_scenarios() if s["id"] == scenario_id), None)
        if sc is None:
            raise KeyError(f"escenario {scenario_id} no existe")
        res = eng.run(sc)
        out = res.to_dict()
        out["profile"] = sc["agente"]
        return out

    # ------------------------------------------------------------------
    # salud / equivalencia
    # ------------------------------------------------------------------
    def health(self) -> dict:
        from .verify_equivalence import check_all
        try:
            passed, total, failures = check_all(verbose=False)
            equiv = {"ok": passed == total, "passed": passed, "total": total,
                     "failures": failures}
        except Exception as e:  # noqa: BLE001
            equiv = {"ok": False, "error": str(e)}
        return {
            "status": "ok",
            "started_at": self.start_time,
            "agents": len(self.runtimes),
            "ws_connections": self.hub.count(),
            "equivalence": equiv,
            "fail_closed": {"enabled": bool(self.config.get("fail_closed", {}).get("enabled", True))},
        }