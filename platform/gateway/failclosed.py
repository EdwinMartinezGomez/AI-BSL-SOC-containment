# -*- coding: utf-8 -*-
"""Guard fail-closed / fail-safe.

Una accion de alto riesgo SOLO se ejecuta si hay una decision de enforcement
FRESCA del runtime (mismo tick) y el ledger esta integro. Si el motor, el policy
engine o el canal de control no responden (heartbeat vencido, ledger roto,
offline simulado), la puerta DENIEGA por defecto — no continua nada peligroso.
"""
from __future__ import annotations

import time
from typing import Callable, Dict


class FailClosedGuard:
    def __init__(self, cfg: dict, ledger_ok: Callable[[], bool] | None = None):
        fc = cfg.get("fail_closed", {}) if isinstance(cfg, dict) else {}
        self.enabled = bool(fc.get("enabled", True))
        self.max_age_ms = int(fc.get("max_age_ms", 5000))
        self.offline = bool(fc.get("offline", False))   # simula perdida del canal de control
        self._ledger_ok = ledger_ok or (lambda: True)
        self._heartbeat: float = time.time()

    def ping(self):
        self._heartbeat = time.time()

    def heartbeat_age_ms(self) -> float:
        return (time.time() - self._heartbeat) * 1000.0

    def is_healthy(self) -> Dict[str, bool]:
        ledger = self._ledger_ok() if self._ledger_ok else True
        return {
            "enabled": self.enabled,
            "offline": self.offline,
            "heartbeat_fresh": self.heartbeat_age_ms() <= self.max_age_ms,
            "ledger_ok": bool(ledger),
            "healthy": self.enabled and not self.offline and self.heartbeat_age_ms() <= self.max_age_ms and bool(ledger),
        }

    def allow(self, category: str, decision_fresh: bool) -> (bool, str):
        """Para accion de alto riesgo: requiere decision fresca + ledger ok.
        Devuelve (permitido, razon)."""
        if not self.enabled:
            return True, "fail_closed deshabilitado"
        if self.offline:
            return False, "fail_closed: canal de control offline — accion de alto riesgo denegada"
        if self.heartbeat_age_ms() > self.max_age_ms:
            return False, "fail_closed: heartbeat del motor vencido — accion de alto riesgo denegada"
        if not decision_fresh:
            return False, "fail_closed: sin decision de enforcement fresca para esta accion"
        if category in ("network", "credential", "exec", "instance"):
            if not self._ledger_ok():
                return False, "fail_closed: ledger no verificable — accion de alto riesgo denegada"
        return True, ""