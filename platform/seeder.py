# -*- coding: utf-8 -*-
"""AI-BSL platform — semilla inicial: agentes por defecto y politica activa.

Los agentes seed representan el parque inicial que el SOC ve en el dashboard:
el protagonista de la demo ("workhorse", med => techo P2) y de contraste
("analyst" low, "sentinel" high).
"""
from __future__ import annotations

from typing import List


def seed_agents(platform, demo: bool = True) -> List[dict]:
    created = []
    # Agentes que ya existen en la base (por id) se dejan; si el proceso no los
    # tiene en memoria (restart), se rehidratan desde el row persistido.
    existing = {r["id"] for r in platform.db.agents()}
    for spec in ({"name": "workhorse", "profile": "med", "mode": "live"},
                 {"name": "analyst", "profile": "low", "mode": "live"},
                 {"name": "sentinel", "profile": "high", "mode": "live"}):
        row = next((r for r in platform.db.agents()
                    if r["name"] == spec["name"] and r["active"]), None)
        if row is not None:
            if row["id"] not in platform.runtimes:
                platform.register_agent(spec["name"], spec["profile"], spec["mode"])
            created.append({"id": row["id"], "name": spec["name"], "existing": True})
            continue
        agent = platform.register_agent(spec["name"], spec["profile"], spec["mode"])
        created.append({"id": agent["agent"]["id"], "name": spec["name"],
                        "existing": False})
    return created