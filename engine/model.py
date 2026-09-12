# -*- coding: utf-8 -*-
"""AI-BSL engine — modelo de datos y constantes.

Fiel a AI-BSL_modelo_formal.md secc. 2. Ver `modelo_formal.md` para la especificacion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Posturas ordenadas (poseta simple, secc. 2.5)
POSTURES = ["P0", "P1", "P2", "P3", "P4"]
ORDER = {p: i for i, p in enumerate(POSTURES)}


@dataclass
class Capability:
    """Vector de capacidades C = (T, N, X, M, B, K). Seccion 2.1."""
    N: str               # network: none | proxy | full
    X: str               # exec: none | managed | native
    M: str               # memory: none | session | persistent
    B: int               # presupuesto de pasos autónomos
    K: int               # instancias concurrentes
    tools: list = field(default_factory=list)


@dataclass
class SignalConfig:
    """Definición de una señal sigma (secc. 2.2)."""
    id: str
    categoria: str
    lambda_: float          # peso de severidad
    gamma: float            # decaimiento por tick
    tripwire: str           # "no" | "duro"
    posture_target: Optional[str] = None


@dataclass
class EventCfg:
    """Config de una clase de evento: señal que dispara y postura de enforcement."""
    kind: str
    signal: Optional[str]
    conf: float
    enforcement_posture: Optional[str]
    dangerous: bool


@dataclass
class LedgerEntry:
    """Entrada del ledger de evidencia L (secc. 2.7)."""
    seq: int
    tick: int
    kind: str                      # "evento" | "postura" | "review" | "final"
    payload: dict                  # contenido del evento/transicion
    prev_hash: str
    hash: str


def canonical_json(obj: Any) -> str:
    """JSON canónico estable para hashing determinista (secc. 2.7)."""
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def sha256_hex(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()