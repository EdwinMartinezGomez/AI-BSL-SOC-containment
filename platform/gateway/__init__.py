# -*- coding: utf-8 -*-
"""AI-BSL platform — gateway fisico de contencion.

El agente nunca toca recursos directamente: toda accion pasa por aqui.
Contiene: workspace controlado (path containment real), egress proxy (allowlist),
credential vault opaco y tool gateway (allowlist de herramientas/exec).
Las deniales por mecanismo registran la senal observada por el engine.
"""
from .workspace import Workspace
from .egress_proxy import EgressProxy
from .credential_vault import CredentialVault
from .tool_gateway import ToolGateway
from .failclosed import FailClosedGuard

__all__ = ["Workspace", "EgressProxy", "CredentialVault", "ToolGateway", "FailClosedGuard"]