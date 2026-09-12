# -*- coding: utf-8 -*-
"""AI-BSL platform — WebSocket/SSE hub.

Broadcast en vivo de todos los tipos de mensaje que consume el dashboard:
evento, riesgo (r(t)/I_c), postura, enforcement, review, approval, ledger, metrics.
WebSocket bidireccional y fallback SSE. Interfaz: subscribe/unsubscribe/broadcast.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Set


class WSHub:
    def __init__(self):
        self._ws: Set[Any] = set()
        self._sse_queues: Set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    # ---------- ws ----------
    def register_ws(self, ws):
        self._ws.add(ws)

    def unregister_ws(self, ws):
        self._ws.discard(ws)

    # ---------- sse ----------
    def add_sse(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._sse_queues.add(q)
        return q

    def remove_sse(self, q):
        self._sse_queues.discard(q)

    # ---------- broadcast ----------
    def push(self, msg: Dict[str, Any]):
        """Emite el mensaje a todos los canales (ws + sse). Seguro para llamarlo
        desde codigo sincrono del event loop o desde threads."""
        loop = self._loop or asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), loop)
        else:
            asyncio.ensure_future(self._broadcast(msg))

    async def _broadcast(self, msg: Dict[str, Any]):
        data = json.dumps(msg, ensure_ascii=False)
        for ws in list(self._ws):
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                self._ws.discard(ws)
        for q in list(self._sse_queues):
            try:
                q.put_nowait(f"data: {data}\n\n")
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                q.put_nowait(f"data: {data}\n\n")

    def count(self) -> Dict[str, int]:
        return {"ws": len(self._ws), "sse": len(self._sse_queues)}