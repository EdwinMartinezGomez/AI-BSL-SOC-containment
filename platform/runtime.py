# -*- coding: utf-8 -*-
"""AI-BSL platform — runtime incremental (mismo g(C, r(t)) del modelo, sin tocar engine/).

El motor formal vive en `engine/engine.run()`. Este runtime ejecuta el MISMO paso de
decision por tick para eventos en vivo, reutilizando los parametros ya parseados de
`engine.Engine(config)` (señales, eventos, pesos, umbrales, histéresis, techo,
autoridad humana) y el esquema de ledger de `engine/ledger`.

`mirror_sim=True` reproduce byte a byte la cadena de `run()` (solo kinds evento/
postura/final); se usa en verify_equivalence.py para probar que el modelo quedo
intacto. En modo live se extiende el ledger con kinds nuevos (enforcement/review/
approval/agent_state/forensic) sin cambiar el esquema de hash SHA-256.
"""
from __future__ import annotations

import copy
import datetime
import uuid
from typing import Any, Dict, List, Optional

from engine.engine import Engine, TRIPWIRE_KINDS
from engine.model import ORDER, POSTURES

from .actuators import ActuatorState
from .ledger_store import RuntimeLedger
from .gateway.gateway import ControlledGateway
from .gateway.failclosed import FailClosedGuard


def _event_for_action(cat: str, tool: str, mech: dict, retry: bool, encoded: bool,
                      cred_mode: str) -> str:
    """Traduce una accion del agente al kind de evento que el policy_config entiende."""
    if retry:
        return "retry_after_block"
    if cat == "file":
        return ("file_access_out_of_scope" if not mech.get("allowed") else "tool_request_low")
    if cat == "network":
        if not mech.get("allowed"):
            return "network_encoded_post" if encoded else "network_request_blocked"
        return "benign_action"
    if cat == "credential":
        return "credential_use_anomalous" if cred_mode == "use" else "credential_collect"
    if cat == "resource":
        return "resource_budget_exceed"
    if cat == "exec":
        return "exec_layer_divergence" if not mech.get("allowed") else "tool_request_low"
    if cat == "memory":
        return "benign_action"
    # tool (categorias por defecto del tool gateway)
    risk = "low"
    if tool in ("write_text", "remove_file", "install_pkg", "spawn_process", "network_post",
                "exec_managed", "exec_native"):
        risk = "high"
    return "tool_request_high" if risk == "high" else "tool_request_low"


class AgentRuntime:
    """Runtime por agente: mismo modelo que engine.run() + orquestacion live."""

    def __init__(self, cfg: dict, agent_id: str, name: str, profile: str,
                 capability: dict, policy_version: str, platform: Any = None,
                 mode: str = "live", mirror_sim: bool = False,
                 ceiling_override0: bool = False,
                 p4_approved_tick0: Optional[int] = None):
        self.cfg = cfg
        self.eng = Engine(copy.deepcopy(cfg))
        self.agent_id = agent_id
        self.name = name
        self.profile = profile
        self.policy_version = policy_version
        self.mode = mode
        self.mirror_sim = mirror_sim

        self.cap = capability
        self.ceiling = self.eng.ceiling(self.eng.capability(self.cap))
        self.cat_list = list(self.eng.alpha.keys())

        # estado del modelo (mismas variables que run())
        self.post = "P0"
        self.I: Dict[str, float] = {c: 0.0 for c in self.cat_list}
        self.r = 0.0
        self.tick = 0
        self.hold_e = 0
        self.hold_d = 0
        self.last_tripwire = -99
        self.reviewed: set = set()
        self.ceiling_override = bool(ceiling_override0)
        self.p4_approved_at = p4_approved_tick0   # int (tick) o None; None => 1e9 como run()

        # entorno
        from pathlib import Path as _Path
        self.created_at = datetime.datetime.now().isoformat()
        self.sandbox = (platform.sandbox if platform else
                        (_Path(__file__).parent.parent / "data" / "sandbox"))
        self.db = getattr(platform, "db", None)
        self.hub = getattr(platform, "hub", None)

        self.actuator = ActuatorState(cfg)
        self.actuator_state = self.actuator.apply(self.post)
        self.failclosed = FailClosedGuard(cfg.get("fail_closed", {}),
                                          ledger_ok=lambda: self.ledger_verify_ok())
        self.gateway = ControlledGateway(agent_id, self.sandbox, cfg,
                                         actuator_ref=lambda: self.actuator,
                                         failclosed=self.failclosed)
        self.ledger = RuntimeLedger(agent_id, db=None if mirror_sim else self.db,
                                    extended=not mirror_sim)

        # historia
        self.posture_history: List[dict] = []
        self.transitions: List[dict] = []
        self.outcomes: List[dict] = []
        self.reviews: Dict[str, dict] = {}
        self.blocked_signatures: set = set()          # (categoria, target) ya bloqueadas
        self.budget_used = 0
        self.terminal = False
        self.finalized = False
        self.killswitch = False
        self.status = "active"
        self._ledger_verified = True

        if platform is not None:
            platform.runtimes[agent_id] = self

    # ------------------------------------------------------------------
    # utilidades
    # ------------------------------------------------------------------
    def _sig_gamma(self, c: str) -> float:
        return self.eng.sig_gamma(c)

    def ledger_verify_ok(self) -> bool:
        ok, _ = self.ledger.verify()
        self._ledger_verified = bool(ok)
        return self._ledger_verified

    def _emit(self, mtype: str, payload: dict):
        if self.hub is not None:
            self.hub.push({"agent_id": self.agent_id, "type": mtype,
                           "tick": self.tick,
                           "ts": datetime.datetime.now().isoformat(),
                           "payload": payload})

    def _human_p4_ok(self, t: int) -> bool:
        if self.p4_approved_at is None:
            return t >= 10 ** 9
        return t >= self.p4_approved_at

    # ------------------------------------------------------------------
    # paso de decision POR TICK — replica exacta de engine.run()
    # ------------------------------------------------------------------
    def _step(self, t: int, atick: List[dict]) -> dict:
        posture_start = self.post
        # 1) deteccion
        dets = []
        for e in atick:
            ec = self.eng.ev.get(e["kind"])
            if ec and ec.signal and ec.conf > 0:
                dets.append((e, ec.signal, ec.conf))
        # 2) riesgo: decaer + sumar
        for c in self.cat_list:
            self.I[c] *= self._sig_gamma(c)
        for _, sid, conf in dets:
            s = self.eng.sig[sid]
            self.I[s.categoria] += conf * s.lambda_
        r = sum(self.eng.alpha[c] * min(1.0, self.I[c]) for c in self.cat_list)
        self.r = r

        transitions: List[tuple] = []
        new_reviews: List[dict] = []
        # 3a) tripwires (inmediato, ignora score)
        for e, sid, conf in dets:
            s = self.eng.sig[sid]
            if s.tripwire == "duro" and conf >= self.eng.th_tripwire:
                target = s.posture_target or "P2"
                if ORDER[target] > ORDER[self.ceiling] and not self.ceiling_override:
                    if sid not in self.reviewed:
                        rv = self._register_review(
                            {"tipo": "REVIEW_REQUIRED",
                             "causa": f"tripwire {sid} pide {target} pero techo={self.ceiling}",
                             "postura": self.post}, tick=t)
                        new_reviews.append(rv)
                        transitions.append(("review", self.post, self.post,
                                            f"tripwire:{sid} techo"))
                        self.reviewed.add(sid)
                else:
                    self.post = POSTURES[max(ORDER[self.post], ORDER[target])]
                    self.last_tripwire = t
                    transitions.append(("posture", posture_start, self.post,
                                        f"tripwire:{sid}"))
        # 3b) escalada por umbral con histéresis
        if self.post != "P4":
            nx_idx = min(ORDER[self.post] + 1, ORDER["P4"])
            nx = POSTURES[nx_idx]
            cond_up = (r >= self.eng.th_up.get(nx, 9) or
                       any(self.I[c] >= self.eng.th_up_cat.get(nx, 9) for c in self.cat_list))
            self.hold_e = self.hold_e + 1 if cond_up else 0
            if self.hold_e >= self.eng.tau_hold:
                if nx == "P4":
                    if self._human_p4_ok(t):
                        self.post = "P4"
                        transitions.append(("posture", posture_start, "P4",
                                            "humano aprueba P4"))
                    elif not self.mirror_sim:
                        # live: pedimos autorizacion humana (el modelo se queda en P3)
                        if not any(x.get("tipo") == "P4_REQUEST" and x.get("status") == "open"
                                   for x in self.reviews.values()):
                            rv = self._register_review(
                                {"tipo": "P4_REQUEST",
                                 "causa": "P3 sostenido: se solicita autorizacion humana para P4",
                                 "postura": self.post}, tick=t)
                            new_reviews.append(rv)
                elif ORDER[nx] > ORDER[self.ceiling] and not self.ceiling_override:
                    if "ceu" not in self.reviewed:
                        rv = self._register_review(
                            {"tipo": "REVIEW_REQUIRED",
                             "causa": f"escalada {nx} excede techo={self.ceiling}",
                             "postura": self.post}, tick=t)
                        new_reviews.append(rv)
                        transitions.append(("review", self.post, self.post, "techo"))
                        self.reviewed.add("ceu")
                else:
                    self.post = nx
                    self.hold_e = 0
                    transitions.append(("posture", posture_start, nx, "umbral"))
        # 3d) autoridad humana explicita para P4
        if self.post == "P3" and self._human_p4_ok(t):
            self.post = "P4"
            transitions.append(("posture", posture_start, "P4", "humano:P4"))
        # 3c) degradacion (histéresis: mas lenta, segunda en el tick)
        deg_cond = (r < self.eng.th_down and
                    all(self.I[c] < self.eng.th_down_cat for c in self.cat_list) and
                    t - self.last_tripwire > 3)
        self.hold_d = self.hold_d + 1 if deg_cond else 0
        if (self.hold_d >= self.eng.tau_hold_down and self.post not in ("P0",) and
                (ORDER[self.post] < ORDER["P3"] or self.ceiling_override)):
            nxt = POSTURES[ORDER[self.post] - 1]
            transitions.append(("posture", self.post, nxt, "degradacion"))
            self.post = nxt
            self.hold_d = 0

        # 4) enforcement
        outcomes = []
        for e in atick:
            ec = self.eng.ev.get(e["kind"])
            if not ec:
                outcomes.append({"tick": t, "kind": e["kind"], "blocked": False,
                                 "contained": False, "dangerous": False})
                continue
            contained_here = False
            if e["kind"] in TRIPWIRE_KINDS:
                contained_here = True                       # auto-contenido
            elif ec.dangerous and ec.enforcement_posture:
                contained_here = ORDER[posture_start] >= ORDER[ec.enforcement_posture]
            outcomes.append({"tick": t, "kind": e["kind"], "signal": ec.signal,
                             "dangerous": ec.dangerous, "blocked": contained_here,
                             "contained": contained_here})

        return {"t": t, "r": r, "posture_start": posture_start, "post": self.post,
                "transitions": transitions, "outcomes": outcomes,
                "new_reviews": new_reviews, "I": dict(self.I), "dets": dets}

    # ------------------------------------------------------------------
    # commit: ledger + historia + broadcast (mismo orden de evidencia que run())
    # ------------------------------------------------------------------
    def _commit(self, step: dict):
        t = step["t"]
        for o in step["outcomes"]:
            self.outcomes.append(o)
            e = self.ledger.append(t, "evento", o)
            if self.db is not None:
                self.db.append_event(self.agent_id, t, datetime.datetime.now().isoformat(),
                                     o["kind"], None, {}, o.get("dangerous", False),
                                     o["blocked"], o["contained"], o.get("signal"))
            self._emit("event", {"event": o, "seq": e["seq"]})
        for tr in step["transitions"]:
            if tr[0] == "posture":
                self.ledger.append(t, "postura",
                                   {"from": tr[1], "to": tr[2], "causa": tr[3],
                                    "r": round(step["r"], 4),
                                    "I_peak": {c: round(v, 4) for c, v in step["I"].items()}})
                self.transitions.append({"tick": t, "from": tr[1], "to": tr[2],
                                         "causa": tr[3], "r": round(step["r"], 4),
                                         "I_peak": {c: round(v, 4) for c, v in step["I"].items()}})
        if not self.mirror_sim:
            for rv in step["new_reviews"]:
                self._publish_review(rv, t)
            if step["post"] != step["posture_start"]:
                self.actuator_state = self.actuator.apply(step["post"])
                self.ledger.append(t, "agent_state", {
                    "posture": step["post"], "r": round(step["r"], 4),
                    "I": {c: round(v, 4) for c, v in step["I"].items()},
                    "actuators": self.actuator_state})
                causa = step["transitions"][-1][3] if step["transitions"] else ""
                self._emit("posture", {"from": step["posture_start"], "to": step["post"],
                                       "causa": causa, "actuators": self.actuator_state})
        self.posture_history.append({"tick": t, "posture": step["post"],
                                     "r": round(step["r"], 4),
                                     "I": {c: round(v, 4) for c, v in step["I"].items()}})
        self._emit("risk", {"tick": t, "r": round(step["r"], 4),
                            "I": {c: round(v, 4) for c, v in step["I"].items()},
                            "posture": step["post"]})
        self._emit("ledger", {"seq": self.ledger.count(),
                              "final_hash": self.ledger.final_hash(),
                              "verify_ok": self.ledger_verify_ok()})

        if not self.mirror_sim and step["post"] == "P4" and not self.terminal:
            self.terminal = True
            self.killswitch = True
            self.status = "terminated"
            self.actuator_state = self.actuator.apply("P4")
            self.finalize(t)
            if self.db is not None:
                self.db.update_agent_state(self.agent_id, "terminated", 0,
                                           self.snapshot(include_history=False))
            self._emit("agent", {"status": "terminated", "killswitch": True,
                                 "actuators": self.actuator_state})

    def finalize(self, t: Optional[int] = None):
        if self.finalized:
            return
        self.finalized = True
        tick = t if t is not None else (self.posture_history[-1]["tick"]
                                        if self.posture_history else 0)
        self.ledger.append(tick, "final", {"posture": self.post,
                                           "verify_ok": self.ledger_verify_ok()})
        if not self.mirror_sim and self.post == "P4":
            e = self.ledger.append(tick, "forensic",
                                   {"resumen": "P4: terminacion, cuarentena, revision forense",
                                    "final_hash": self.ledger.final_hash()})
            self._emit("ledger", {"seq": e["seq"], "final_hash": self.ledger.final_hash()})

    def finish_scenario(self, final_tick: Optional[int] = None):
        """Equivale al cierre de run() (entry 'final') — lo usa el Lab/equivalencia."""
        self.finalize(final_tick)

    # ------------------------------------------------------------------
    # revisiones humanas
    # ------------------------------------------------------------------
    def _register_review(self, data: dict, tick: Optional[int] = None) -> dict:
        rid = uuid.uuid4().hex[:10]
        rv = {"review_id": rid, "agent_id": self.agent_id,
              "tick": tick if tick is not None else self.tick,
              "tipo": data["tipo"], "causa": data["causa"], "postura": data["postura"],
              "status": "open", "note": ""}
        self.reviews[rid] = rv
        if self.db is not None:
            self.db.save_review(rv)
        return rv

    def _publish_review(self, rv: dict, t: int):
        """Publica una revision: al ledger (live), a la db y por WS."""
        try:
            e = self.ledger.append(t, "review", {"tipo": rv["tipo"], "causa": rv["causa"],
                                                 "postura": self.post,
                                                 "review_id": rv["review_id"]})
            rv["ledger_seq"] = e["seq"]
            if self.db is not None:
                self.db.updates_review(rv["review_id"], rv["status"], None,
                                       rv.get("note"), None, None, e["seq"])
        except Exception:  # noqa: BLE001
            pass
        self._emit("review", rv)

    def decide_review(self, review_id: str, decision: str, by: str, note: str = "") -> dict:
        rv = self.reviews.get(review_id)
        if rv is None and self.db is not None:
            rows = self.db.reviews(self.agent_id)
            rv = next((r for r in rows if r["review_id"] == review_id), None)
        if rv is None or rv.get("status") != "open":
            raise KeyError(f"revision {review_id} no abierta")
        dtime = datetime.datetime.now().isoformat()
        rv["status"] = "decided"
        rv["decision"] = decision
        rv["note"] = note
        rv["by"] = by
        rv["decided_at"] = dtime
        seq = None
        if decision == "approve":
            if rv["tipo"] == "REVIEW_REQUIRED":
                self.ceiling_override = True
            elif rv["tipo"] == "P4_REQUEST":
                self.p4_approved_at = self.tick if self.p4_approved_at is None else self.p4_approved_at
        if not self.mirror_sim:
            try:
                e = self.ledger.append(self.tick, "approval_human",
                                       {"review_id": review_id, "tipo": rv["tipo"],
                                        "decision": decision, "by": by, "note": note})
                seq = e["seq"]
            except Exception:  # noqa: BLE001
                pass
        if self.db is not None:
            self.db.updates_review(review_id, "decided", decision, note, by, dtime, seq)
            self.db.save_human(self.agent_id, self.tick, rv["tipo"], decision, by, note, dtime)
        self._emit("approval", {"review_id": review_id, "tipo": rv["tipo"],
                                "decision": decision, "by": by, "note": note,
                                "ledger_seq": seq})
        return rv

    # ------------------------------------------------------------------
    # ingesta de eventos (live y mirror)
    # ------------------------------------------------------------------
    def ingest(self, atick: List[dict], source: str = "live") -> dict:
        self.failclosed.ping()
        t = self.tick
        self.tick += 1
        step = self._step(t, atick)
        self._commit(step)
        return {"tick": t, "posture": step["post"], "r": step["r"],
                "posture_start": step["posture_start"],
                "transitions": step["transitions"], "outcomes": step["outcomes"],
                "new_reviews": step["new_reviews"]}

    def idle_tick(self):
        if self.terminal:
            return
        self.ingest([], source="idle")

    # ------------------------------------------------------------------
    # pre-execution gate (Policy Enforcement Point + gateway)
    # ------------------------------------------------------------------
    def preexec_action(self, req: dict) -> dict:
        cat = req.get("type", "tool")
        tool = req.get("tool") or req.get("name") or ""
        target = req.get("target") or ""
        action_id = req.get("action_id") or uuid.uuid4().hex[:10]

        # 1) mecanismo (gateway)
        mech = self.gateway.precheck(req)

        # 2) fail-closed: alto riesgo requiere decision fresca + ledger ok
        if not self.failclosed.allow(cat, decision_fresh=True)[0] and cat in (
                "file", "network", "credential", "exec", "resource", "instance"):
            fc = self.failclosed.allow(cat, decision_fresh=True)
            d = self._enforcement_resp(req, "BLOCK", "fail_closed", fc[1], None)
            self._emit("enforcement", {**d, "evidence_seq": None,
                                       "mechanism_allowed": mech.get("allowed", True)})
            return self._finalize_preexec(d, mech)

        # 3) derivar el evento observado
        retry = (cat, target) in self.blocked_signatures
        cred_mode = req.get("cred_mode", "read")
        encoded = bool(req.get("encoded", False))
        evkind = _event_for_action(cat, tool, mech, retry, encoded, cred_mode)
        if mech.get("signal_hint") == "credential_use_anomalous":
            evkind = "credential_use_anomalous"
        risky_event = self.eng.ev.get(evkind)

        # 4) avanza el modelo con esta observacion (mismo paso que run())
        atick = [{"kind": evkind, "target": target, "detail": {
            "action_id": action_id, "type": cat, "tool": tool,
            "mechanism_allowed": mech.get("allowed", True),
            "requested": bool(req.get("declared"))}}]
        self.budget_used += 1
        ingest_res = self.ingest(atick, source="gateway")

        # 5) decision del Policy Enforcement Point
        decision, rule, rationale = self._pep(evkind, risky_event, cat, tool, mech, self.post)

        # 6) accion que dispara REVIEW_REQUIRED (ceiling) y el mecanismo la permitiria
        #    => HOLD_REVIEW hasta que el humano decida.
        if decision == "ALLOW":
            triggered = [rv for rv in ingest_res["new_reviews"]
                         if rv["tipo"] == "REVIEW_REQUIRED" and rv.get("status") == "open"]
            if triggered:
                decision, rule, rationale = ("HOLD_REVIEW", "revision_requerida",
                                             f"la accion dispara revision humana: {triggered[0]['causa']}")

        decision_obj = self._record_enforcement(action_id, decision, rule, evkind, cat,
                                                tool, target, mech, ingest_res, rationale)

        # 7) ejecutar solo si ALLOW
        execution = None
        if decision == "ALLOW":
            execution = self.gateway.execute(req, decision)
            self._emit("execution", {"action_id": action_id, "ok": execution["ok"],
                                     "result": execution["result"], "target": target})
            if execution.get("signal_hint"):
                self.ingest([{"kind": execution["signal_hint"], "target": target,
                              "detail": {"action_id": action_id}}], source="gateway")

        if decision in ("BLOCK", "HOLD_REVIEW"):
            self.blocked_signatures.add((cat, target))

        # P4 solo entra por autoridad humana explicita. En live, un agente en P3
        # cuya accion es bloqueada solicita P4 (el modelo se queda en P3 hasta que
        # el humano autoriza; luego el siguiente tick entra por la regla 3d).
        if (not self.mirror_sim and self.post == "P3" and not self.terminal
                and decision != "ALLOW"):
            if not any(x.get("tipo") == "P4_REQUEST" and x.get("status") == "open"
                       for x in self.reviews.values()):
                rv = self._register_review(
                    {"tipo": "P4_REQUEST",
                     "causa": "agente en P3 con accion bloqueada: se solicita "
                              "autorizacion humana para P4 (terminacion)",
                     "postura": "P3"}, tick=self.tick - 1)
                self._publish_review(rv, self.tick - 1)
                decision_obj["p4_request"] = rv["review_id"]

        return self._finalize_preexec(decision_obj, mech, execution)

    def _pep(self, evkind: str, risky_event, cat: str, tool: str, mech: dict,
             post: str) -> tuple:
        """Devuelve (decision, rule, rationale)."""
        if self.terminal:
            return "BLOCK", "terminal", "agente terminado (P4): no se ejecutan nuevas acciones"
        if not mech.get("allowed", True):
            hint = mech.get("signal_hint") or ""
            return ("BLOCK", "mecanismo",
                    f"la infraestructura deniega esta accion: {mech.get('reason', '')}"
                    f"{(' [senal: ' + hint + ']') if hint else ''}")
        # eventos de tripwire se auto-contienen (igual que run())
        if evkind in TRIPWIRE_KINDS or evkind == "retry_after_block":
            return "BLOCK", "tripwire", f"evento auto-contenido por tripwire ({evkind})"
        if risky_event and risky_event.dangerous and risky_event.enforcement_posture:
            if ORDER[post] >= ORDER[risky_event.enforcement_posture]:
                return ("BLOCK", "postura",
                        f"postura {post} >= enforcement {risky_event.enforcement_posture} para {evkind}")
        if self.actuator.is_frozen(cat, tool):
            return "BLOCK", "actuador", f"actuador de postura suspende {tool or cat}"
        return "ALLOW", "base", "accion dentro del alcance declarado y de la postura actual"

    def _record_enforcement(self, action_id: str, decision: str, rule: str, evkind: str,
                            cat: str, tool: str, target: str, mech: dict,
                            ingest_res: dict, rationale: str) -> dict:
        seq = None
        risk_before = round(ingest_res["r"], 4)
        posture_from = (ingest_res["transitions"][0][1]
                        if ingest_res["transitions"] else self.post)
        if not self.mirror_sim:
            try:
                e = self.ledger.append(self.tick - 1, "enforcement", {
                    "action_id": action_id, "decision": decision, "rule": rule,
                    "signal": evkind, "category": cat, "tool": tool, "target": target,
                    "risk_before": risk_before, "risk_after": round(self.r, 4),
                    "posture_from": posture_from, "posture_to": self.post,
                    "rationale": rationale})
                seq = e["seq"]
            except Exception:  # noqa: BLE001
                pass
        d = {"action_id": action_id, "decision": decision, "rule": rule,
             "signal": evkind, "kind": evkind, "category": cat, "tool": tool,
             "target": target, "risk_before": risk_before, "risk_after": round(self.r, 4),
             "posture_from": posture_from, "posture_to": self.post,
             "rationale": rationale, "evidence_seq": seq,
             "mechanism_allowed": mech.get("allowed", True)}
        self._emit("enforcement", d)
        return d

    def _enforcement_resp(self, req: dict, decision: str, rule: str, rationale: str,
                          signal: str) -> dict:
        return {"action_id": req.get("action_id") or uuid.uuid4().hex[:10],
                "decision": decision, "rule": rule, "rationale": rationale,
                "signal": signal, "category": req.get("type", "tool"),
                "target": req.get("target", ""), "tick": self.tick,
                "evidence_seq": None, "risk_before": self.r, "risk_after": self.r,
                "posture": self.post, "ceiling": self.ceiling}

    def _finalize_preexec(self, decision_obj: dict, mech: dict, execution=None) -> dict:
        return {"action_id": decision_obj["action_id"], "decision": decision_obj["decision"],
                "rule": decision_obj["rule"], "rationale": decision_obj["rationale"],
                "signal": decision_obj["signal"], "category": decision_obj["category"],
                "target": decision_obj["target"], "tick": self.tick - 1,
                "evidence_seq": decision_obj.get("evidence_seq"),
                "risk_before": decision_obj["risk_before"],
                "risk_after": decision_obj["risk_after"],
                "posture": self.post, "ceiling": self.ceiling,
                "execution": execution,
                "mechanism_allowed": mech.get("allowed", True)}

    # ------------------------------------------------------------------
    # snapshot / metrics
    # ------------------------------------------------------------------
    def snapshot(self, include_history: bool = True) -> dict:
        s = {
            "agent": {"id": self.agent_id, "name": self.name, "mode": self.mode,
                      "profile": self.profile, "policy_version": self.policy_version,
                      "created_at": self.created_at, "status": self.status},
            "capability": self.cap,
            "ceiling": self.ceiling,
            "posture": self.post,
            "r": round(self.r, 4),
            "I": {c: round(v, 4) for c, v in self.I.items()},
            "tick": self.tick,
            "actuator_state": self.actuator_state,
            "gateway": {"workspace": str(self.gateway.workspace.root),
                        "egress_allowlist": sorted(self.gateway.egress.allowlist)
                        if self.gateway.egress.allowlist else None,
                        "vault_keys": self.gateway.vault.keys()},
            "fail_closed": self.failclosed.is_healthy(),
            "terminal": self.terminal,
            "killswitch": self.killswitch,
            "budget": {"used": self.budget_used, "cap": self.cap.get("B", 0),
                       "instances": self.cap.get("K", 0)},
            "ledger": {"count": self.ledger.count(), "final_hash": self.ledger.final_hash(),
                       "verify_ok": self.ledger_verify_ok()},
            "open_reviews": [rv for rv in self.reviews.values() if rv["status"] == "open"],
        }
        if include_history:
            s["posture_history"] = self.posture_history
            s["transitions"] = self.transitions
            s["events"] = self.outcomes[-60:]
        return s

    def metrics(self) -> dict:
        res = type("R", (), {})()
        res.events_outcome = self.outcomes
        res.ledger = self.ledger._inner
        res.peaks = [h["posture"] for h in self.posture_history]
        res.final_posture = self.post
        res.review_required = [rv for rv in self.reviews.values()
                               if rv["tipo"] == "REVIEW_REQUIRED" and rv["status"] == "open"]
        try:
            from engine.evaluate import metrics_for
            m = metrics_for(res)
        except Exception:  # noqa: BLE001
            m = {}
        m["ledger_hash"] = self.ledger.final_hash()
        m["verify_ok"] = self.ledger_verify_ok()
        m["transiciones"] = len(self.transitions)
        m["revisiones_abiertas"] = len([rv for rv in self.reviews.values()
                                        if rv["status"] == "open"])
        m["modo"] = "mirror_sim" if self.mirror_sim else "live"
        return m