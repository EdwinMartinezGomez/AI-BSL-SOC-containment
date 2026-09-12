# -*- coding: utf-8 -*-
"""AI-BSL platform — tipos compartidos (contrato).

Mismo vocabulario que el modelo formal (engine/) + los tipos operativos de la
plataforma. Los nombres se reflejan 1:1 en `web/src/types/index.ts`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

POSTURES = ["P0", "P1", "P2", "P3", "P4"]


@dataclass
class Capability:
    """Vector de capacidades C = (T, N, X, M, B, K). Seccion 2.1 del modelo formal."""
    N: str                 # network: none | proxy | full
    X: str                 # exec: none | managed | native
    M: str                 # memory: none | session | persistent
    B: int                 # presupuesto de pasos autonomos
    K: int                 # instancias concurrentes
    tools: List[str] = field(default_factory=list)


@dataclass
class Agent:
    id: str
    name: str
    mode: str                      # "live" | "sim"
    profile: str                   # high | med | low
    policy_version: str
    capability: Capability
    ceiling: str
    status: str = "active"         # active | quarantined | terminated | fail_closed
    created_at: str = ""


@dataclass
class AgentEvent:
    """Evento bruto (observacion) emitido por un adapter o el gateway."""
    id: str
    tick: int
    ts: str                        # timestamp ISO
    kind: str                      # clase de evento del policy_config (o nueva benigna)
    target: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    source: str = "adapter"        # "scenario" | "gateway" | "adapter" | "gym" | "driver"


@dataclass
class AnnotatedSignal:
    """Senal detectada sigma, segun _eventos_a_senales + senal definida."""
    id: str
    conf: float
    categoria: str
    lambda_: float
    gamma: float
    tripwire: str


@dataclass
class RiskState:
    r: float
    I: Dict[str, float]
    tick: int
    posture: str


@dataclass
class PolicyDecision:
    """Fallo del Policy Enforcement Point para una accion pre-ejecucion."""
    action_id: str
    decision: str                  # ALLOW | BLOCK | HOLD_REVIEW
    rule: str                      # mecanismo | postura | actuador | fail_closed | base | techo
    signal: Optional[str]
    posture_from: str
    posture_to: str
    risk_before: float
    risk_after: float
    rationale: str
    tick: int
    evidence_seq: Optional[int] = None


@dataclass
class EnforcementAction:
    """Accion mecanica aplicada por los actuadores sobre el entorno controlado."""
    category: str                  # tool | file | network | credential | resource | exec | memory
    mechanism: str                 # workspace | egress_proxy | vault | tool_gateway | actuator
    posture: str
    applied: bool
    reversible: bool
    detail: str = ""


@dataclass
class HumanApproval:
    review_id: str
    agent_id: str
    kind: str                      # ceiling_override | p4 | restore | deny
    decision: str
    by: str
    note: str
    ts: str
    ledger_seq: Optional[int] = None


def as_dict(obj) -> dict:
    return asdict(obj)