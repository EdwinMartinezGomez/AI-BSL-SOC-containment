# -*- coding: utf-8 -*-
"""ControlledGateway — arma todos los mecanismos fisicos de contencion.

El agente controlado envia ActionRequest; el gateway responde con un chequeo
mecanico (`precheck`) y, solo si el Policy Enforcement Point lo autoriza, ejecuta
(`execute`) dentro de la zona controlada. Las denegaciones por mecanismo registran
la senal que observara el engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

from .workspace import Workspace
from .egress_proxy import EgressProxy
from .credential_vault import CredentialVault
from .tool_gateway import ToolGateway

SEED_FILES = {
    "reports/ok.md": "# Informe semanal (simulado)\n\nActividad rutinaria del agente.\n",
    "notes/todo.txt": "pendientes: revisar pipeline, actualizar graficos\n",
}


class ControlledGateway:
    def __init__(self, agent_id: str, sandbox_root: Path, cfg: dict,
                 actuator_ref: Callable[[], object],
                 failclosed: object):
        self.agent_id = agent_id
        self.cfg = cfg
        gw = cfg.get("gateway", {})
        ws_root = Path(sandbox_root) / agent_id / "workspace"
        self.workspace = Workspace(ws_root)
        self.workspace.seed(SEED_FILES)
        self.egress = EgressProxy(allowlist=gw.get("egress_allowlist"),
                                  echo_port=int(gw.get("echo_port", 8099)))
        self.vault = CredentialVault()
        self.tools = ToolGateway(self.workspace, risk_mode=gw.get("exec_mode", "managed"))
        self.failclosed = failclosed
        self._actuator_ref = actuator_ref

    def actuators(self):
        return self._actuator_ref()

    # ------------------------------------------------------------------
    # precheck mecanico: ¿la accion es base-permitida por la infraestructura?
    # ------------------------------------------------------------------
    def precheck(self, req: Dict[str, object]) -> Dict[str, object]:
        cat = req.get("type", "tool")
        tool = req.get("tool") or req.get("name") or ""
        target = req.get("target") or ""
        params = req.get("params") or {}
        act = self.actuators()

        base = {"allowed": True, "reason": "", "signal_hint": "", "category": cat, "tool": tool}

        # mecanico: archivos fuera del workspace
        if cat == "file":
            rel = target or params.get("path") or ""
            p = self.workspace.resolve(rel)
            if p is None:
                base = {"allowed": False, "reason": "ruta fuera de la zona de trabajo controlada",
                        "signal_hint": "access_out_of_scope", "category": cat, "tool": tool}

        # mecanico: egress fuera de allowlist
        if cat == "network":
            ok, reason, sig = self.egress.precheck(target)
            if not ok:
                base = {"allowed": False, "reason": reason, "signal_hint": sig,
                        "category": cat, "tool": tool}
            elif act.egress_cut:
                base = {"allowed": False, "reason": "egress cortado por postura P2+",
                        "signal_hint": "network_request_blocked", "category": cat, "tool": tool}

        # mecanico: vault opaco nunca devuelve material
        if cat == "credential":
            base = {"allowed": False,
                    "reason": "el credential vault es opaco: nunca expone secretos al agente",
                    "signal_hint": "credential_collect" if req.get("cred_mode", "read") != "use"
                    else "credential_use_anomalous",
                    "category": cat, "tool": tool}

        # mecanico: herramienta/exec suspendido por actuador
        risk = self.tools.declare(tool) if cat in ("tool", "exec") else ""
        if cat in ("tool", "exec") and act.is_frozen(cat, tool):
            base = {"allowed": False, "reason": f"actuador de postura: {tool} suspendido/helado",
                    "signal_hint": "", "category": cat, "tool": tool}

        return base

    # ------------------------------------------------------------------
    # ejecucion (solo si el PEP autorizo ALLOW)
    # ------------------------------------------------------------------
    def execute(self, req: Dict[str, object], decision: str) -> Dict[str, object]:
        cat = req.get("type", "tool")
        tool = req.get("tool") or req.get("name") or ""
        target = req.get("target") or ""
        params = req.get("params") or {}
        out = {"ok": False, "result": "", "signal_hint": ""}

        if cat == "file":
            op = params.get("op", "read")
            if op in ("read",):
                ok, content, _ = self.workspace.read(target)
                out = {"ok": ok, "result": content if ok else _ , "signal_hint": ""}
            else:
                ok, err = self.workspace.write(target, str(params.get("content", "")))
                out = {"ok": ok, "result": "escrito: " + target if ok else err, "signal_hint": ""}
        elif cat == "network":
            ok, reason, _ = self.egress.open(target)
            out = {"ok": ok, "result": reason, "signal_hint": ""}
        elif cat == "credential":
            # no se da el caso (vault opaco), pero por si acaso: redactado
            out = {"ok": False, "result": "acceso a credenciales denegado por el vault", "signal_hint": "credential_collect"}
        elif cat in ("tool", "exec"):
            ok, result, sig = self.tools.execute(tool, params)
            out = {"ok": ok, "result": result, "signal_hint": sig}
        elif cat == "memory":
            out = {"ok": True, "result": "[memoria de sesion simulada: estado del agente]", "signal_hint": ""}
        else:
            out = {"ok": True, "result": f"[{cat}] accion benigna (no mediada)", "signal_hint": ""}
        return out