# -*- coding: utf-8 -*-
"""AI-BSL platform — capa de seguridad runtime alrededor de un agente.

El motor del modelo formal vive en `engine/` (intacto). Esta plataforma lo envuelve
para aplicar AI-BSL a agentes reales en un entorno controlado: event collector,
signal mapper, runtime incremental (mismo g(C, r(t))), policy enforcement point,
actuators y gateway físico + ledger hash-chained persistente.
"""
from .runtime import AgentRuntime, _event_for_action
from .policy_store import PolicyStore
from .db import Database
from .ws_hub import WSHub
from .controller import Platform
from .ledger_store import RuntimeLedger, make_hash, verify_entries
from .metrics import agent_metrics, ledger_integrity
from .seeder import seed_agents

__all__ = ["AgentRuntime", "PolicyStore", "Database", "WSHub", "Platform",
           "RuntimeLedger", "make_hash", "verify_entries", "agent_metrics",
           "ledger_integrity", "seed_agents"]