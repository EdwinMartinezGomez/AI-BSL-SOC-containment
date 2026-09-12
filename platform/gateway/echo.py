# -*- coding: utf-8 -*-
"""Servidor echo local (inofensivo) para demostrar egress permitido real.
Escucha en localhost:ECHO_PORT y devuelve lo que recibe. Seguro: solo local.
"""
from __future__ import annotations

import socketserver
import threading


class _Echo(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(64)
        if data:
            self.request.sendall(b"ack:" + data)


def start_echo_server(port: int = 8099):
    try:
        srv = socketserver.TCPServer(("127.0.0.1", port), _Echo)
    except OSError:
        return None  # ya en marcha / puerto ocupado
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv