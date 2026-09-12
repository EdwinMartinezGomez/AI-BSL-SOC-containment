# -*- coding: utf-8 -*-
"""Tool gateway (allowlist de herramientas / exec administrado).

El agente solo puede invocar herramientas del allowlist; exec_managed ejecuta
comandos con cwd=workspace y sin red. Un comando fuera del allowlist (o que
diverga de la herramienta solicitada) se DENIEGA y registra exec_layer_divergence.
"""
from __future__ import annotations

import shlex
import subprocess
from typing import Tuple

# Comandos permitidos para exec_managed (siempre con cwd=workspace, sin red).
EXEC_ALLOWLIST = ["grep", "cat", "ls", "wc", "head", "tail", "find", "printf"]

# Herramientas de bajo riesgo (permitidas en P0).
LOW_RISK_TOOLS = {"search", "read_text", "list_dir", "grep", "summarize"}
# Herramientas de alto riesgo (bloqueables por postura P1+ / suspensibles).
HIGH_RISK_TOOLS = {"write_text", "remove_file", "install_pkg", "spawn_process", "network_post"}


class ToolGateway:
    def __init__(self, workspace, risk_mode: str = "managed"):
        self.workspace = workspace
        self.risk_mode = risk_mode  # "managed" (allowlist) | "native"

    def declare(self, tool: str) -> str:
        """Clasifica una herramienta en la clase de riesgo del policy_config."""
        if tool in LOW_RISK_TOOLS:
            return "low"
        if tool in HIGH_RISK_TOOLS:
            return "high"
        if tool == "exec_managed":
            return "managed"
        if tool == "exec_native":
            return "native"
        return "unknown"

    def execute(self, tool: str, params: dict) -> Tuple[bool, str, str]:
        """Devuelve (ok, resultado, senal_de_divergencia_o_vacio)."""
        rel = params.get("path") or params.get("rel") or ""
        if tool in ("search", "grep"):
            q = params.get("query", "")
            ok, listing = self.workspace.list(".")
            if not ok or not q:
                return True, "busqueda vacia", ""
            hits = []
            for name in listing:
                p = self.workspace.resolve(name)
                if p and p.is_file():
                    try:
                        text = p.read_text(encoding="utf-8")
                    except Exception:  # noqa: BLE001
                        continue
                    if q.lower() in text.lower():
                        hits.append(name)
            return True, f"hits en {len(hits)} archivo(s): {hits[:6]}", ""
        if tool in ("read_text",):
            ok, content, _ = self.workspace.read(rel)
            if not ok:
                return False, f"lectura denegada: {rel}", "access_out_of_scope"
            return True, content[:200], ""
        if tool in ("list_dir",):
            ok, listing = self.workspace.list(rel or ".")
            return (True, ", ".join(listing), "") if ok else (False, "directorio no permitido", "")
        if tool in ("summarize",):
            return True, "[resumen simulado del contexto de trabajo]", ""
        if tool == "write_text":
            ok, err = self.workspace.write(rel, str(params.get("content", "")))
            return (True, f"escrito en workspace: {rel}", "") if ok else (False, err, "access_out_of_scope")
        if tool == "remove_file":
            p = self.workspace.resolve(rel)
            if p is None or not p.is_file():
                return False, "remocion denegada (fuera de workspace o inexistente)", "access_out_of_scope"
            p.unlink()
            return True, f"eliminado: {rel}", ""
        if tool in ("exec_managed", "exec_native"):
            cmd = str(params.get("cmd", "")).strip()
            return self._exec(cmd, tool)
        return False, f"herramienta '{tool}' no existe en el allowlist del tool gateway", ""

    def _exec(self, cmd: str, tool: str) -> Tuple[bool, str, str]:
        if not cmd:
            return False, "comando vacio", ""
        parts = shlex.split(cmd)
        if not parts:
            return False, "comando invalido", ""
        base = parts[0].split("/")[-1]
        if base not in EXEC_ALLOWLIST:
            # Un comando fuera del allowlist en exec_managed = divergencia de la
            # capa de ejecucion (METR: tool-call spoofing) -> tripwire duro P3.
            return False, f"comando '{base}' fuera del allowlist de exec (divergencia)", "exec_layer_divergence"
        try:
            proc = subprocess.run(parts, cwd=str(self.workspace.root), capture_output=True,
                                  text=True, timeout=5,
                                  env={"PATH": "/c/Windows/System32:/c/Python", "HOME": "/tmp"})
            out = (proc.stdout or "")[:200]
            return True, out or f"exit {proc.returncode}", ""
        except Exception as e:  # noqa: BLE001
            return False, f"exec fallo: {e}", ""