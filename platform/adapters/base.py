# -*- coding: utf-8 -*-
"""AI-BSL platform — contrato de adapters de agente (provider-agnostic).

El adapter es la frontera: un LLM real, un driver controlado o una entidad
remota cualquiera se conecta implementando este protocolo. El motor de decision
nunca conoce al proveedor.
"""
from __future__ import annotations

from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class AgentAdapter(Protocol):
    agent_id: str

    def connect(self) -> None: ...
    def preexec(self, req: Dict) -> Dict: ...
    def send_events(self, events: List[Dict]) -> Dict: ...
    def state(self) -> Dict: ...
    def close(self) -> None: ...