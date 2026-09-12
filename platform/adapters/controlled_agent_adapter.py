# -*- coding: utf-8 -*-
"""AI-BSL platform — adapter del agente controlado (driver/LLM futuro).

SDK provider-agnostico: el agente (un driver de demo, o en el futuro un LLM
via cualquier proveedor) solicita acciones a traves del mismo contrato. En el
MVP funciona en dos modos:
  * in-process: habla directo con el Platform/AgentRuntime (sin red).
  * http: habla con la API FastAPI (urllib, sin dependencias externas).
El gateway y el Policy Enforcement Point son los que deciden; este adapter solo
cana el trafico de solicitudes.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


class ControlledAgentSDK:
    def __init__(self, base_url: Optional[str] = None, platform: Any = None):
        self.base_url = (base_url or "").rstrip("/")
        self.platform = platform

    @property
    def in_process(self) -> bool:
        return self.platform is not None

    # ------------------------------------------------------------------
    # transporte
    # ------------------------------------------------------------------
    def _post(self, path: str, payload: dict) -> dict:
        if self.in_process:
            return self._route_in_process(path, payload)
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"API {e.code} en {path}: {e.read().decode('utf-8')[:300]}")

    def _route_in_process(self, path: str, payload: dict) -> dict:
        p = self.platform
        if path == "/api/v1/agents":
            agent = p.register_agent(payload.get("name"), payload.get("profile", "med"),
                                     payload.get("mode", "live"))
            return {"agent_id": agent["agent"]["id"], "agent": agent}
        bits = path.strip("/").split("/")            # api/v1/agents/{id}/actions/preexec
        try:
            i = bits.index("agents")
            agent_id = bits[i + 1]
            rest = bits[i + 2:]
        except (ValueError, IndexError):
            raise RuntimeError(f"ruta inesperada: {path}")
        if rest == ["actions", "preexec"]:
            return p.preexec_action(agent_id, payload)
        if rest == ["events"]:
            return p.inject_events(agent_id, payload.get("events", []))
        if len(rest) >= 3 and rest[0] == "reviews" and rest[2] == "decide":
            return p.decide_review(agent_id, rest[1], payload.get("decision"),
                                   payload.get("by", "sdk"), payload.get("note", ""))
        raise RuntimeError(f"ruta inesperada: {path}")

    # ------------------------------------------------------------------
    # API del agente controlado
    # ------------------------------------------------------------------
    def register(self, name: str, profile: str = "med", mode: str = "live") -> str:
        resp = self._post("/api/v1/agents",
                          {"name": name, "profile": profile, "mode": mode})
        if "agent_id" in resp:
            return resp["agent_id"]
        return resp["agent"]["id"]

    def preexec(self, agent_id: str, req: Dict) -> Dict:
        """Solicita autorizacion ANTES de ejecutar. Devuelve la decision del PEP."""
        return self._post(f"/api/v1/agents/{agent_id}/actions/preexec", req)

    def send_events(self, agent_id: str, events: List[Dict]) -> Dict:
        return self._post(f"/api/v1/agents/{agent_id}/events", {"events": events})

    def decide(self, agent_id: str, review_id: str, decision: str,
               by: str = "operator", note: str = "") -> Dict:
        return self._post(f"/api/v1/agents/{agent_id}/reviews/{review_id}/decide",
                          {"decision": decision, "by": by, "note": note})

    # Conveniencia: esperar a que una review del tipo deseado este abierta.
    def wait_open_review(self, agent_id: str, tipo: str, timeout: float = 10.0,
                         poll: float = 0.3) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            row = self.get_agent(agent_id)
            for rv in row.get("open_reviews", []):
                if rv["tipo"] == tipo:
                    return rv
            time.sleep(poll)
        raise TimeoutError(f"no aparecio review {tipo} para {agent_id}")

    def get_agent(self, agent_id: str) -> dict:
        if self.in_process:
            return self.platform.get_agent(agent_id, include_history=False)
        url = f"{self.base_url}/api/v1/agents/{urllib.parse.quote(agent_id)}"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))