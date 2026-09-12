# -*- coding: utf-8 -*-
"""AI-BSL engine — ledger de evidencia con integridad (secc. 2.7).

- Append-only con hash-chain.
- Sink externo write-only (espejo que se escribe en cada entrada).
- verify(L): recomputa la cadena y reporta la primera entrada con fallo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .model import LedgerEntry, canonical_json, sha256_hex


@dataclass
class Ledger:
    entries: List[LedgerEntry] = field(default_factory=list)
    # Espejo externo "write-only": representa el external scorer de METR.
    ext: List[dict] = field(default_factory=list)
    _seq: int = 0

    def _prev_hash(self) -> str:
        return self.entries[-1].hash if self.entries else "GENESIS"

    def append(self, tick: int, kind: str, payload: dict) -> LedgerEntry:
        self._seq += 1
        prev = self._prev_hash()
        body = canonical_json(payload)
        h = sha256_hex(f"{prev}|{tick}|{kind}|{body}")
        e = LedgerEntry(seq=self._seq, tick=tick, kind=kind, payload=payload,
                        prev_hash=prev, hash=h)
        self.entries.append(e)
        # Sink externo write-only: espejo completo (fuera del alcance del agente).
        self.ext.append({"seq": e.seq, "tick": e.tick, "kind": e.kind,
                         "payload": payload, "hash": e.hash})
        return e

    def verify(self) -> Tuple[bool, Optional[int]]:
        """Recomputa la cadena; devuelve (ok, primera entrada con hash inválido)."""
        prev = "GENESIS"
        for e in self.entries:
            body = canonical_json(e.payload)
            h = sha256_hex(f"{prev}|{e.tick}|{e.kind}|{body}")
            if h != e.hash:
                return False, e.seq
            prev = e.hash
        return True, None

    def final_hash(self) -> str:
        return self.entries[-1].hash if self.entries else "EMPTY"

    def to_dict(self) -> dict:
        return {
            "entries": [{"seq": e.seq, "tick": e.tick, "kind": e.kind,
                         "payload": e.payload, "prev_hash": e.prev_hash,
                         "canon": canonical_json(e.payload),
                         "hash": e.hash} for e in self.entries],
        }