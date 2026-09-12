# -*- coding: utf-8 -*-
"""AI-BSL platform — adapter de escenarios (Simulation/Lab).

El Lab usa DIRECTAMENTE el motor formal: Engine(config).run(scenario), la misma
ruta del paper. Asi los hashes del Lab coinciden byte a byte con
engine/exports/. El runtime incremental NO interviene aqui.
"""
from __future__ import annotations

from typing import Any, Dict, List


class LabAdapter:
    def __init__(self, platform: Any):
        self.platform = platform

    def catalog(self) -> List[dict]:
        return self.platform.list_scenarios()

    def run(self, scenario_id: str) -> Dict:
        return self.platform.run_lab(scenario_id)