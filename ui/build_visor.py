# -*- coding: utf-8 -*-
"""Construye ui/visor.html inyectando el export real de s08 como demo por defecto.

Garantiza que el JSON embebido sea EXACTAMENTE el que produjo el motor
(sin transcripcion manual), de modo que la re-verificacion SHA-256 del
ledger en el navegador coincida con la de Python.
"""
from pathlib import Path
import json

ROOT = Path(__file__).parent
EXPORT_SRC = ROOT.parent / "engine" / "exports" / "scenario_s08_persistence.json"
TEMPLATE = ROOT / "_visor_template.html"
OUT = ROOT / "visor.html"

demo = json.loads(EXPORT_SRC.read_text(encoding="utf-8"))
tpl = TEMPLATE.read_text(encoding="utf-8")

marker = "const DEMO_DATA = null;"
assert marker in tpl, "marcador de demo no encontrado en el template"

payload = json.dumps(demo, ensure_ascii=False, indent=1)
out = tpl.replace(marker, "const DEMO_DATA = " + payload + ";")
OUT.write_text(out, encoding="utf-8")
print(f"visor.html escrito: {OUT} ({len(out)} bytes)")
print(f"hash ledger final de la demo: {demo['ledger_final_hash']}")