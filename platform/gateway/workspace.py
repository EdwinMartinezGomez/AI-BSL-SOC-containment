# -*- coding: utf-8 -*-
"""Zona de trabajo controlada (path containment real).

Raiz propia por agente: `sandbox/agents/<id>/workspace`. Cualquier acceso de
archivo se resuelve con os.path.realpath y se DENIEGA si queda fuera de la raiz.
Herramienta real pero benigna: lee/escribe dentro del sandbox que la plataforma
posee, nunca fuera.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(os.path.realpath(root))
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, rel: str) -> Path:
        """Devuelve la ruta real si rel esta dentro de la raiz; si no, None."""
        p = Path(os.path.realpath((self.root / rel).resolve()))
        if not p.is_relative_to(self.root):
            return None
        return p

    def read(self, rel: str) -> Tuple[bool, str, str]:
        p = self.resolve(rel)
        if p is None:
            return False, "fuera de la zona de trabajo controlada", p is None and "escape"
        if not p.is_file():
            return False, "archivo no existe", ""
        return True, p.read_text(encoding="utf-8"), ""

    def write(self, rel: str, content: str) -> Tuple[bool, str]:
        p = self.resolve(rel)
        if p is None:
            return False, "fuera de la zona de trabajo controlada"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return True, ""

    def list(self, rel: str) -> Tuple[bool, list]:
        p = self.resolve(rel)
        if p is None:
            return False, []
        if not p.is_dir():
            return False, []
        return True, [str(x.name) for x in sorted(p.iterdir())]

    def abs(self, rel: str) -> str:
        return str(self.root / rel)

    def seed(self, files: dict):
        for rel, content in files.items():
            p = self.resolve(rel)
            if p is not None:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")

    def wipe(self):
        """reset_env (actuador P3): borra la zona controlada del agente y la recrea."""
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)