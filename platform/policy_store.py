# -*- coding: utf-8 -*-
"""AI-BSL platform — politica declarativa versionada.

Carga la politica del engine (engine/policy_config.json) como v0.1 y permite
registrar nuevas versiones sin modificar el codigo del motor: se valida
instanciando `Engine(config)` (el parser del propio modelo) y se guarda un
`version` + `content` en memoria (y en SQLite para durabilidad).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Dict, Optional

from engine.engine import Engine, load_config

ENGINE_POLICY = Path(__file__).parent.parent / "engine" / "policy_config.json"


class PolicyStore:
    def __init__(self, db=None):
        self.versions: Dict[str, dict] = {}
        self.active_version: str = "v0.1"
        self._db = db
        self._load_default()

    def _load_default(self):
        cfg = load_config(ENGINE_POLICY)
        self._register("v0.1", cfg, author="engine", note="politica declarativa del modelo formal")

    def _register(self, version: str, cfg: dict, author: str, note: str):
        # verificacion de que el parser del motor acepta la politica
        Engine(copy.deepcopy(cfg))
        self.versions[version] = copy.deepcopy(cfg)
        if self._db is not None:
            self._db.save_policy(version=version, content=json.dumps(cfg, ensure_ascii=False),
                                 author=author, note=note)

    def get(self, version: Optional[str] = None) -> dict:
        v = version or self.active_version
        return copy.deepcopy(self.versions[v])

    def register(self, cfg: dict, author: str = "operator", note: str = "") -> str:
        n = len([v for v in self.versions if v.startswith("v")])
        version = f"v{0}.{n+1}" if n < 9 else f"v{1}.{n-8}"
        self._register(version, cfg, author, note)
        return version

    def activate(self, version: str):
        if version not in self.versions:
            raise KeyError(version)
        self.active_version = version

    def to_dict(self):
        return {
            "active_version": self.active_version,
            "versions": [
                {"version": v, "author": x.get("author"), "note": x.get("note"),
                 "registered_at": x.get("registered_at")}
                for v, x in self._meta().items()],
        }

    def _meta(self):
        # metadatos de version guardados en db si existe
        if self._db is not None:
            return self._db.policy_meta()
        return {}


def validate_policy(cfg: dict) -> Optional[str]:
    """Devuelve un error como string si la politica no es valida; None si lo es."""
    try:
        Engine(copy.deepcopy(cfg))
    except Exception as e:  # noqa: BLE001 - el parser del engine lanza KeyError/TypeError/ValueError
        return f"politica invalida: {e}"
    return None