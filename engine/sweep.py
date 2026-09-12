# -*- coding: utf-8 -*-
"""AI-BSL — analisis de sensibilidad v2 (secc. 7).

Leccion de la v1 (documentada): escalar TODOS los pesos y renormalse es un
no-op matematico, y omitir theta_up_cat hacia invisible la sensibilidad real.
Esta version perturba:
  (a) peso de UNA categoria a la vez (renormalizando el resto),
      factores {0.5, 1.5}.
  (b) umbrales theta_up Y theta_up_cat juntos (y theta_down en la direccion
      opuesta), factores {0.5, 0.75, 1.0, 1.25, 1.5}.

Reporta por punto: acuerdo (fracción de escenarios con postura_final igual a la
esperada) y contained_rate medio. Si algunos escenarios voltean, se reporta.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .engine import Engine, load_config, load_scenarios
from .evaluate import metrics_for

EXPORTS = Path(__file__).parent / "exports"
CATS = ["access", "credential", "egress", "resource", "evasion", "tampering", "coordination"]


def _clone(config: dict) -> dict:
    return copy.deepcopy(config)


def _eval_catalog(cfg: dict, scenarios) -> dict:
    eng = Engine(cfg)
    acuerdos = 0
    crates = []
    flips = []
    for sc in scenarios:
        m = metrics_for(eng.run(sc))
        exp = sc["esperado"].get("postura_final")
        if m["postura_final"] == exp:
            acuerdos += 1
        else:
            flips.append({"id": sc["id"], "esperado": exp, "obtenido": m["postura_final"]})
        if m["peligrosos"]:
            crates.append(m["contained_rate"])
    return {"acuerdos": acuerdos, "n": len(scenarios),
            "agreement": round(acuerdos / len(scenarios), 3),
            "contained_rate_medio": round(sum(crates) / len(crates), 3) if crates else None,
            "flips": flips}


def sweep_weights(factores=(0.5, 1.5)) -> list:
    config = load_config()
    scenarios = load_scenarios()
    base_w = dict(config["riesgo"]["pesos_categoria"])
    rows = []
    for cat in CATS:
        for fac in factores:
            w = {k: (v * fac if k == cat else v) for k, v in base_w.items()}
            s = sum(w.values())
            w = {k: v / s for k, v in w.items()}
            cfg = _clone(config)
            cfg["riesgo"]["pesos_categoria"] = w
            res = _eval_catalog(cfg, scenarios)
            rows.append({"param": f"peso:{cat}", "factor": fac, **res})
    return rows


def sweep_thresholds(factores=(0.5, 0.75, 1.0, 1.25, 1.5)) -> list:
    config = load_config()
    scenarios = load_scenarios()
    base = dict(config["posturas"]["umbrales"])
    rows = []
    for fac in factores:
        th = copy.deepcopy(base)
        for p in th.get("theta_up", {}):
            th["theta_up"][p] = base["theta_up"][p] * fac
        for p in th.get("theta_up_cat", {}):
            th["theta_up_cat"][p] = base["theta_up_cat"][p] * fac
        th["theta_down"] = base["theta_down"] / fac
        th["theta_down_cat"] = base["theta_down_cat"] / fac
        cfg = _clone(config)
        cfg["posturas"]["umbrales"] = th
        res = _eval_catalog(cfg, scenarios)
        rows.append({"param": "umbrales_up+cat", "factor": fac, **res})
    return rows


def run_sweep() -> dict:
    out = {"pesos_por_categoria": sweep_weights(), "umbrales": sweep_thresholds()}
    (EXPORTS / "sensibilidad.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run_sweep()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    n_flip = sum(len(x.get("flips", [])) for group in r.values() for x in group)
    print(f"\nEscenarios con volteo en algun punto: {n_flip}")
    print("Escrito en exports/sensibilidad.json")