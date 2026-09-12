# -*- coding: utf-8 -*-
"""AI-BSL platform — metricas de la plataforma.

Reutiliza metrics_for() del harness del paper para cada agente (t_detect,
t_respond, contained_rate, cometidos) y agrega la integridad del ledger y la
verificacion de equivalencia. Nada aqui reemplaza al modelo.
"""
from __future__ import annotations

from typing import List, Optional


def ledger_integrity(db, agent_id: str) -> dict:
    """Re-verifica la cadena en la base; [] => integra."""
    bad = db.ledger_verify(agent_id)
    return {"ok": len(bad) == 0, "bad_seqs": bad, "count": len(db.ledger_entries(agent_id))}


def agent_metrics(rt) -> dict:
    m = rt.metrics()          # metrics_for() + extensiones del runtime
    return {
        **{k: m[k] for k in ("eventos_totales", "peligrosos", "contenidos", "cometidos",
                            "contained_rate", "t_detect", "t_respond", "postura_final",
                            "posturas_alcanzadas", "verify_ok") if k in m},
        "ledger_hash": m.get("ledger_hash"),
        "transiciones": m.get("transiciones"),
        "revisiones_abiertas": m.get("revisiones_abiertas"),
        "modo": m.get("modo"),
    }


def t_delay(det: Optional[int], resp: Optional[int]) -> Optional[float]:
    if det is None or resp is None:
        return None
    return max(0, resp - det)