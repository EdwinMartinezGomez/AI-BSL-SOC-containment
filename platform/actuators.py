# -*- coding: utf-8 -*-
"""AI-BSL platform — actuators (estado mecanico por postura).

Traduce la postura P0..P4 a los flags mecanicos que el gateway consulta ANTES de
ejecutar (defensa en profundidad: politica + mecanismo). Cargados desde la seccion
`actuadores` de la politica declarativa y aplicados de forma acumulativa.
"""
from __future__ import annotations

from typing import Any, Dict, List


class ActuatorState:
    def __init__(self, cfg: dict):
        self.table = {str(k): dict(v) for k, v in cfg.get("actuadores", {}).items()}
        self.categories = ["tool", "file", "network", "credential", "resource", "exec",
                           "memory", "instance"]
        self.reset()

    def reset(self):
        self.tools_suspended: List[str] = []
        self.log_verbosity = "normal"
        self.resource_cap: float | None = None
        self.egress_cut = False
        self.tokens_revoked = False
        self.isolate_zones = False
        self.tools_frozen = False
        self.creds_revoked_all = False
        self.instances_terminated = False
        self.env_reset = False
        self.ledger_exported = False
        self.terminate = False
        self.quarantine = False
        self.forensic_review = False
        self.redeploy_decision = False

    def apply(self, posture: str) -> Dict[str, Any]:
        """Aplica la postura: acumula los actuadores de P1..posture en orden."""
        self.reset()
        from engine.model import ORDER, POSTURES
        level = ORDER.get(posture, 0)
        for p in POSTURES[:level + 1]:
            if p in ("P0",):
                continue
            a = self.table.get(p, {})
            self._merge(a, level)
        return self.to_dict()

    def _merge(self, a: dict, _level: int):
        if a.get("suspend_tools"):
            self.tools_suspended = list(a["suspend_tools"])
        if a.get("log_verbosity"):
            self.log_verbosity = a["log_verbosity"]
        if a.get("resource_cap") is not None:
            self.resource_cap = float(a["resource_cap"])
        self.egress_cut = self.egress_cut or bool(a.get("cut_egress"))
        self.tokens_revoked = self.tokens_revoked or bool(a.get("revoke_tokens"))
        self.isolate_zones = self.isolate_zones or bool(a.get("isolate_zones"))
        self.tools_frozen = self.tools_frozen or bool(a.get("freeze_tool_pending"))
        self.creds_revoked_all = self.creds_revoked_all or bool(a.get("revoke_all_creds"))
        self.instances_terminated = self.instances_terminated or bool(a.get("terminate_instances"))
        self.env_reset = self.env_reset or bool(a.get("reset_env"))
        self.ledger_exported = self.ledger_exported or bool(a.get("export_ledger_external"))
        self.terminate = self.terminate or bool(a.get("terminate"))
        self.quarantine = self.quarantine or bool(a.get("quarantine"))
        self.forensic_review = self.forensic_review or bool(a.get("forensic_review"))
        self.redeploy_decision = self.redeploy_decision or bool(a.get("redeploy_decision"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "posture_derived": {},
            "tools_suspended": self.tools_suspended,
            "log_verbosity": self.log_verbosity,
            "resource_cap": self.resource_cap,
            "egress_cut": self.egress_cut,
            "tokens_revoked": self.tokens_revoked,
            "isolate_zones": self.isolate_zones,
            "tools_frozen": self.tools_frozen,
            "creds_revoked_all": self.creds_revoked_all,
            "instances_terminated": self.instances_terminated,
            "env_reset": self.env_reset,
            "ledger_exported": self.ledger_exported,
            "terminate": self.terminate,
            "quarantine": self.quarantine,
            "forensic_review": self.forensic_review,
            "redeploy_decision": self.redeploy_decision,
        }

    def is_frozen(self, category: str, tool: str = "") -> bool:
        if category in ("exec",) and self.tools_frozen:
            return True
        if self.tools_frozen and category in ("tool", "exec", "file"):
            return True
        if tool and tool in self.tools_suspended:
            return True
        if category == "network" and self.egress_cut:
            return True
        if category == "credential" and (self.tokens_revoked or self.creds_revoked_all):
            return True
        if category == "instance" and self.instances_terminated:
            return True
        return False