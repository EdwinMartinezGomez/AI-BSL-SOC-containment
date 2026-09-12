# -*- coding: utf-8 -*-
"""AI-BSL engine — lazo de simulacion (secc. 2.3-2.7 y 3).

Flujo por tick (orden determinista):
  1. posture_start = postura al inicio del tick.
  2. detect: eventos del tick -> señales (conf>0).
  3. riesgo: decaer categorias, sumar conf*lambda (secc. 2.4).
  4. decision: policy_step (tripwires, umbrales con histéresis, techo, autoridad humana).
  5. enforcement: cada evento peligroso es bloqueado si postura >= enforcement_posture;
     los eventos tripwire son siempre auto-contenidos.
  6. evidencia: cada evento/transicion se registra en el ledger (append-only + hash-chain).
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ledger import Ledger
from .model import ORDER, POSTURES, Capability, EventCfg, SignalConfig

TRIPWIRE_KINDS = {"credential_use_anomalous", "log_tamper_detected", "exec_layer_divergence"}


class SimResult:
    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.ledger = Ledger()
        self.posture_history: List[dict] = []      # {tick, posture, r, I_cat}
        self.events_outcome: List[dict] = []        # {tick, kind, signal, blocked, contained}
        self.review_required: List[dict] = []
        self.peaks: List[str] = []                  # posturas alcanzadas
        self.final_posture: str = "P0"
        self.signal_gallery: Dict[str, List[int]] = {}

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "final_posture": self.final_posture,
            "posture_history": self.posture_history,
            "events": self.events_outcome,
            "review_required": self.review_required,
            "ledger": self.ledger.to_dict(),
            "ledger_final_hash": self.ledger.final_hash(),
        }


class Engine:
    def __init__(self, config: dict):
        self.sig: Dict[str, SignalConfig] = {}
        for sid, sc in config["signals"].items():
            if sid.startswith("_"):
                continue
            self.sig[sid] = SignalConfig(
                id=sid, categoria=sc["categoria"], lambda_=float(sc["lambda"]),
                gamma=float(sc["gamma"]), tripwire=sc["tripwire"],
                posture_target=sc.get("posture_target"))
        self.ev: Dict[str, EventCfg] = {}
        for kind, ec in config["eventos"].items():
            if kind.startswith("_") or not isinstance(ec, dict):
                continue
            sig_map = config["_eventos_a_senales"].get(kind, {"signal": None, "conf": 0})
            self.ev[kind] = EventCfg(
                kind=kind, signal=sig_map["signal"], conf=float(sig_map["conf"]),
                enforcement_posture=ec.get("enforcement_posture"),
                dangerous=bool(ec.get("dangerous", False)))
        self.alpha: Dict[str, float] = config["riesgo"]["pesos_categoria"]
        self.cats: List[str] = list(self.alpha.keys())
        th = config["posturas"]["umbrales"]
        self.th_up = {k: float(v) for k, v in th["theta_up"].items()}
        self.th_up_cat = {k: float(v) for k, v in th["theta_up_cat"].items()}
        self.th_down = float(th["theta_down"])
        self.th_down_cat = float(th["theta_down_cat"])
        self.tau_hold = int(th["tau_hold"])
        self.tau_hold_down = int(th["tau_hold_down"])
        self.th_tripwire = float(th["theta_tripwire"])
        self.ceiling_conds: List[Tuple[dict, str]] = [
            (list(c["match"].items()), c["techo"])
            for c in config["posturas"]["techo_por_capacidad"]["condiciones"]]
        self.actuators: Dict[str, dict] = config["actuadores"]

    # ---------- capacidad y techo ----------
    @staticmethod
    def capability(profile: dict) -> Capability:
        return Capability(N=profile["N"], X=profile["X"], M=profile["M"],
                          B=int(profile["B"]), K=int(profile["K"]), tools=profile["tools"])

    def ceiling(self, cap: Capability) -> str:
        cv = {"N": cap.N, "X": cap.X, "M": cap.M}
        for keys, techo in self.ceiling_conds:
            if all(cv[k] == v for k, v in keys):
                return techo
        return "P1"

    # ---------- lazo ----------
    def run(self, scenario: dict) -> SimResult:
        res = SimResult(scenario["id"])
        cap = self.capability(scenario["agente_capability"])
        ceil = self.ceiling(cap)
        win = int(scenario["window_ticks"])
        events_by_tick: Dict[int, List[dict]] = {}
        for e in scenario["eventos"]:
            events_by_tick.setdefault(int(e["tick"]), []).append(e)

        humano = scenario.get("humano", {})
        p4_tick = int(humano.get("p4_aprobado_tick", 10 ** 9))
        ceiling_override = bool(humano.get("ceiling_override", False))

        post = "P0"
        I: Dict[str, float] = {c: 0.0 for c in self.cats}
        hold_e = 0
        hold_d = 0
        last_tripwire = -99
        reviewed = set()

        for t in range(win):
            posture_start = post
            atick = events_by_tick.get(t, [])

            # 1) deteccion
            dets = []  # (evento, signal, conf)
            for e in atick:
                ec = self.ev.get(e["kind"])
                if ec and ec.signal and ec.conf > 0:
                    dets.append((e, ec.signal, ec.conf))
                    res.signal_gallery.setdefault(ec.signal, []).append(t)

            # 2) riesgo: decaer + sumar
            for c, cname in enumerate(self.cats):
                I[cname] *= self.sig_gamma(cname)
            for _, sid, conf in dets:
                s = self.sig[sid]
                I[s.categoria] += conf * s.lambda_

            r = sum(self.alpha[c] * min(1.0, I[c]) for c in self.cats)

            # 3) decision
            transitions: List[tuple] = []
            # 3a) tripwires (inmediato, ignora score)
            for e, sid, conf in dets:
                s = self.sig[sid]
                if s.tripwire == "duro" and conf >= self.th_tripwire:
                    target = s.posture_target or "P2"
                    if ORDER[target] > ORDER[ceil] and not ceiling_override:
                        if sid not in reviewed:
                            res.review_required.append(
                                {"tick": t, "tipo": "REVIEW_REQUIRED",
                                 "causa": f"tripwire {sid} pide {target} pero techo={ceil}",
                                 "postura": post})
                            transitions.append(("review", post, post, f"tripwire:{sid} techo"))
                            reviewed.add(sid)
                    else:
                        post = POSTURES[max(ORDER[post], ORDER[target])]
                        last_tripwire = t
                        transitions.append(("posture", posture_start, post,
                                            f"tripwire:{sid}"))
            # 3b) escalada por umbral con histéresis
            if post != "P4":
                nx_idx = min(ORDER[post] + 1, ORDER["P4"])
                nx = POSTURES[nx_idx]
                cond_up = (r >= self.th_up.get(nx, 9) or
                           any(I[c] >= self.th_up_cat.get(nx, 9) for c in self.cats))
                # hold_e: ticks consecutivos con condicion de escalada (histéresis de subida)
                if cond_up:
                    hold_e += 1
                else:
                    hold_e = 0
                if hold_e >= self.tau_hold:
                    if nx == "P4":
                        if t >= p4_tick:
                            post = "P4"
                            transitions.append(("posture", posture_start, "P4",
                                                "humano aprueba P4"))
                    elif ORDER[nx] > ORDER[ceil] and not ceiling_override:
                        if "ceu" not in reviewed:
                            res.review_required.append(
                                {"tick": t, "tipo": "REVIEW_REQUIRED",
                                 "causa": f"escalada {nx} excede techo={ceil}", "postura": post})
                            transitions.append(("review", post, post, "techo"))
                            reviewed.add("ceu")
                    else:
                        post = nx
                        hold_e = 0
                        transitions.append(("posture", posture_start, nx, "umbral"))

            # 3d) autoridad humana explicita: aprobacion de P4 (secc. 2.6, regla 5)
            if post == "P3" and t >= p4_tick:
                post = "P4"
                transitions.append(("posture", posture_start, "P4", "humano:P4"))

            # 3c) degradacion (histéresis: mas lenta, segunda en el tick)
            deg_cond = (r < self.th_down and
                        all(I[c] < self.th_down_cat for c in self.cats) and
                        t - last_tripwire > 3)
            hold_d = hold_d + 1 if deg_cond else 0
            if (hold_d >= self.tau_hold_down and post not in ("P0",) and
                    (ORDER[post] < ORDER["P3"] or ceiling_override)):
                nxt = POSTURES[ORDER[post] - 1]
                transitions.append(("posture", post, nxt, "degradacion"))
                post = nxt
                hold_d = 0

            # 4) enforcement
            outcomes = []
            for e in atick:
                ec = self.ev.get(e["kind"])
                if not ec:
                    outcomes.append({"tick": t, "kind": e["kind"], "blocked": False,
                                     "contained": False, "dangerous": False})
                    continue
                contained_here = False
                if e["kind"] in TRIPWIRE_KINDS:
                    contained_here = True                       # auto-contenido
                elif ec.dangerous and ec.enforcement_posture:
                    contained_here = ORDER[posture_start] >= ORDER[ec.enforcement_posture]
                outcomes.append({
                    "tick": t, "kind": e["kind"],
                    "signal": ec.signal,
                    "dangerous": ec.dangerous,
                    "blocked": contained_here,                  # no se ejecuta
                    "contained": contained_here,
                })

            # 5) evidencia
            for o in outcomes:
                self._event_entry(res, t, o)
            for tr in transitions:
                self._posture_entry(res, t, tr, r, I)
            res.posture_history.append({"tick": t, "posture": post, "r": round(r, 4),
                                        "I": {c: round(v, 4) for c, v in I.items()}})
            res.peaks.append(post)

        res.final_posture = post
        self._final_entry(res)
        return res

    def sig_gamma(self, categoria: str) -> float:
        # decaimiento por categoria: usa el gamma de la primera señal de esa categoria
        for s in self.sig.values():
            if s.categoria == categoria:
                return s.gamma
        return 0.9

    # ---------- registro de evidencia ----------
    def _event_entry(self, res: SimResult, t: int, o: dict):
        res.events_outcome.append(o)
        res.ledger.append(t, "evento", o)

    def _posture_entry(self, res: SimResult, t: int, tr: tuple, r: float, I: dict):
        if tr[0] == "posture":
            res.ledger.append(t, "postura",
                              {"from": tr[1], "to": tr[2], "causa": tr[3],
                               "r": round(r, 4),
                               "I_peak": {c: round(v, 4) for c, v in I.items()}})

    def _final_entry(self, res: SimResult):
        res.ledger.append(res.posture_history[-1]["tick"], "final",
                          {"posture": res.final_posture,
                           "verify_ok": res.ledger.verify()[0]})


def load_config(path: Optional[Path] = None) -> dict:
    p = path or Path(__file__).parent / "policy_config.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_scenarios(path: Optional[Path] = None) -> List[dict]:
    p = path or Path(__file__).parent / "scenarios.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for sc in data["escenarios"]:
        sc = dict(sc)
        sc["agente_capability"] = data["_perfiles"][sc["agente"]]
        out.append(sc)
    return out