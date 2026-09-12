# -*- coding: utf-8 -*-
"""AI-BSL — prueba de equivalencia: el runtime incremental produce EXACTAMENTE
los mismos hashes que el motor formal engine/engine.run().

Para probar que el modelo quedo intacto, se alimentan los 11 escenarios del catalogo
a traves del AgentRuntime (modo espejo) y se compara tick a tick con los hashes ya
exportados en engine/exports/scenario_<id>.json. Si algo diverge, el wrapper se
corrige — jamas engine/.

Uso:  python -m platform.verify_equivalence
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from engine.engine import Engine, load_config, load_scenarios
from .runtime import AgentRuntime

EXPORTS = Path(__file__).parent.parent / "engine" / "exports"


def replay_scenario(cfg: dict, sc: dict) -> AgentRuntime:
    """Corre el escenario con el runtime incremental (mirror_sim) tick a tick."""
    hum = sc.get("humano", {})
    rt = AgentRuntime(
        cfg=cfg,
        agent_id=f"mirror_{sc['id']}",
        name=f"Lab {sc['id']}",
        profile=sc["agente"],
        capability=sc["agente_capability"],
        policy_version="v0.1",
        platform=None,                       # sin db/hub: cadena pura
        mode="lab",
        mirror_sim=True,
        ceiling_override0=bool(hum.get("ceiling_override", False)),
        p4_approved_tick0=hum.get("p4_aprobado_tick"),  # None => 1e9 como run()
    )
    by_tick: Dict[int, List[dict]] = {}
    for e in sc["eventos"]:
        by_tick.setdefault(int(e["tick"]), []).append(e)
    win = int(sc["window_ticks"])
    for t in range(win):
        rt.ingest(by_tick.get(t, []), source="scenario")
    rt.finish_scenario(win - 1)
    return rt


def _expected_hash(sc: dict) -> Tuple[str, str]:
    """(hash exportado, path) para el escenario."""
    p = EXPORTS / f"scenario_{sc['id']}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return str(data["ledger_final_hash"]), p.name


def check_all(verbose: bool = False) -> Tuple[int, int, List[str]]:
    cfg = load_config()
    scenarios = load_scenarios()
    passed = 0
    failures: List[str] = []
    for sc in scenarios:
        exp_hash, fname = _expected_hash(sc)
        rt = replay_scenario(cfg, sc)
        got_hash = rt.ledger.final_hash()
        verify_ok = rt.ledger.verify()[0]
        ok = got_hash == exp_hash and verify_ok
        if ok:
            passed += 1
        else:
            failures.append(
                f"[{sc['id']}] esperado={exp_hash[:16]}.. obtenido={got_hash[:16]}.. "
                f"verify={verify_ok} (vs exports/{fname})")
        if verbose:
            print(f"  {sc['id']:>24} {'OK' if ok else 'DIVERGE'}  final={rt.post} "
                  f"hash={got_hash[:16]}..")
    return passed, len(scenarios), failures


if __name__ == "__main__":
    passed, total, failures = check_all(verbose=True)
    print(f"\nEquivalencia: {passed}/{total} escenarios replican byte a byte el hash "
          f"del motor formal.")
    if failures:
        print("DIVERGENCIAS:")
        for f in failures:
            print("  -", f)
        raise SystemExit(1)
    print("Modelo intacto: el runtime incremental usa exactamente el mismo g(C, r(t)).")