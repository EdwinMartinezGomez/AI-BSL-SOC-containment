# -*- coding: utf-8 -*-
"""AI-BSL platform — ledger persistente con integridad SHA-256.

Reutiliza EXACTAMENTE el esquema de `engine/model.py` (canonical_json + sha256_hex)
y `engine/ledger.Ledger` para la cadena en memoria, anade su `ext` (espejo externo
write-only) y persiste cada entrada en SQLite. verify() recomputa la cadena.
La forma `hash = sha256(prev | tick | kind | canonical_json(payload))` NO cambia.
"""
from __future__ import annotations

from typing import List, Optional

from engine.ledger import Ledger
from engine.model import canonical_json, sha256_hex


def make_hash(prev: str, tick: int, kind: str, payload: dict) -> str:
    return sha256_hex(f"{prev}|{tick}|{kind}|{canonical_json(payload)}")


def verify_entries(entries: List[dict]) -> List[int]:
    """Recomputa la cadena; devuelve seqs con hash invalido (vacia => integra)."""
    bad: List[int] = []
    prev = "GENESIS"
    for e in entries:
        h = make_hash(prev, e["tick"], e["kind"], e["payload"])
        if h != e["hash"]:
            bad.append(e["seq"])
        prev = e["hash"]
    return bad


class RuntimeLedger:
    """Ledger append-only con persistencia. `extended` controla si se registran
    kinds nuevos de la plataforma (enforcement/review/approval/agent_state)."""

    def __init__(self, agent_id: str, db=None, extended: bool = True):
        self.agent_id = agent_id
        self.db = db
        self.extended = extended
        self._inner = Ledger()

    def append(self, tick: int, kind: str, payload: dict) -> dict:
        e = self._inner.append(tick, kind, payload)
        if self.db is not None:
            self.db.append_ledger(self.agent_id, e.seq, e.tick, e.kind, e.payload,
                                  e.prev_hash, canonical_json(e.payload), e.hash)
        return {"seq": e.seq, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                "prev_hash": e.prev_hash, "canon": canonical_json(e.payload), "hash": e.hash}

    def verify(self) -> tuple:
        return self._inner.verify()

    def final_hash(self) -> str:
        return self._inner.final_hash()

    def entries(self) -> List[dict]:
        return self._inner.to_dict()["entries"]

    def outer_mirror(self) -> List[dict]:
        return self._inner.ext

    def count(self) -> int:
        return len(self._inner.entries)