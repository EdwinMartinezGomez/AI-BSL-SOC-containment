# -*- coding: utf-8 -*-
"""Egress controlado (proxy de salida con allowlist).

El agente solo conecta a destinos de la allowlist (localhost echo). Un egress a
un host no permitido se DENIEGA por mecanismo ANTES de abrir socket y registra la
senal. Las conexiones permitidas son reales pero seguras: un pequeno servidor
echo local lanzado por la plataforma.
"""
from __future__ import annotations

import socket
from typing import Tuple

DEFAULT_ALLOWLIST = ["localhost", "127.0.0.1", "::1"]


class EgressProxy:
    def __init__(self, allowlist=None, echo_port: int = 8099, cut: bool = False):
        self.allowlist = set(allowlist or DEFAULT_ALLOWLIST)
        self.echo_port = echo_port
        self.cut = cut

    def _host(self, target: str) -> str:
        target = (target or "").strip()
        if target.startswith("http://"):
            target = target[len("http://"):].split("/")[0]
        elif target.startswith("https://"):
            target = target[len("https://"):].split("/")[0]
        target = target.split(":")[0]
        return target

    def precheck(self, target: str) -> Tuple[bool, str, str]:
        """Devuelve (permitido, motivo, senal). Un destino no permitido -> senal egress_anomaly."""
        host = self._host(target)
        if self.cut:
            return False, "egress cortado por AI-BSL (postura P2+)", "network_request_blocked"
        if host not in self.allowlist:
            return False, f"destino '{host}' no esta en la allowlist de egress", "network_request_blocked"
        return True, "", ""

    def open(self, target: str, timeout: float = 2.0) -> Tuple[bool, str, str]:
        """Intenta conectar a la allowlist. True si establecio conexion y echo ok."""
        host = self._host(target)
        if host not in self.allowlist:
            return False, f"denegado: '{host}' fuera de allowlist", "network_request_blocked"
        try:
            with socket.create_connection((host, self.echo_port), timeout=timeout) as s:
                s.sendall(b"ping\n")
                data = s.recv(64)
                return True, f"egress permitido a '{host}' (echo local {len(data)}b)", ""
        except OSError as e:
            return False, f"egress permitido pero sin servidor echo (revise: {e})", ""