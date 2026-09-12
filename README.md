# AI-BSL · Prototipo determinista de contención de agentes autónomos

> **Entorno seguro.** Este prototipo simula el comportamiento de un agente autónomo
> y su contención dentro de un **reactor aislado**. No hay sistemas reales, ni
> credenciales, ni redes externas: toda acción (incluida la maliciosa) es un evento
> declarado en un catálogo de escenarios y ejecutado en memoria. Nada de lo que se
> describe aquí compromete, evade, o explota sistemas reales — es un laboratorio de
> modelos, no un kit de ataque.

## Qué es

AI-BSL reemplaza la idea original de "4 niveles de contención del agente" por un
modelo con **dos dimensiones independientes**:

1. **Capacidad / autonomía** `C` — vector declarado, cuasi-estático: red `N`,
   ejecución `X`, memoria `M`, presupuesto `B`, conocimiento `K`, tools `T`.
2. **Evidencia de riesgo dinámica** `r(t)` — agregación exponencial de 10 señales
   observables durante la ejecución (acceso fuera de alcance, recolección de
   credenciales, exfiltración encodeada, reintentos, tampering, …).

Y las posturas de contención resultantes `P0…P4` (monitor → restringir → aislar →
revocar → terminar+revisar) se derivan de una **función de decisión** `g(C, r(t))`
con disparadores, umbrales con retención (`tau_hold`), histéresis (escalar rápido /
degradar lento), **techo por capacidad** (`ceiling(C)`) que exige revisión humana
antes de superarlo, y **autoridad humana explícita** para P4.

Un **ledger hash-chained** (SHA-256, append-only, espejo externo write-only) registra
eventos, transiciones y veredicto final, de modo que la evidencia es verificable en
Python *y* re-verificable en el navegador.

La especificación completa vive en [`AI-BSL_modelo_formal.md`](AI-BSL_modelo_formal.md)
y el análisis crítico (por qué niveles ≠ dimensiones, secciones A–L, contribución y
riesgos) en [`AI-BSL_revision_critica.md`](AI-BSL_revision_critica.md).

## Estructura

```
engine/
  __init__.py
  model.py           tipos base (Capability, SignalConfig, LedgerEntry, hash)
  ledger.py          ledger append-only + hash-chain + espejo externo + verify()
  engine.py          el motor: ceiling(), g(C,r(t)), tripwires, histérisis, enforcement
  evaluate.py        harness: corre el catálogo, aserciones, métricas, exports
  sweep.py           análisis de sensibilidad (pesos por categoría y umbrales)
  policy_config.json política declarativa (señales, pesos, umbrales, techos, actuadores)
  scenarios.json     catálogo declarativo de 11 escenarios (data, no código)
  exports/           resultados reales generados
ui/
  visor.html          visor 2D de réplica (auto-contenido, file:// funciona)
  _visor_template.html + build_visor.py  (re-construye visor.html con la demo)
README.md
```

## Reproducir

Requisitos: Python 3.10+ (sin dependencias externas). Todo es stdlib.

```powershell
# 1) evaluación completa del catálogo (aserciones + métricas + exports)
python -m engine.evaluate

# 2) análisis de sensibilidad (pesos vs. umbrales)
python -m engine.sweep
```

Salida de `evaluate` en `engine/exports/`:

- `summary.json` — tabla de resultados, aserciones fallidas, cobertura de señales.
- `summary.csv` — la misma tabla en CSV.
- `metricas.md` — versión humanamente legible.
- `scenario_<id>.json` — export completo por escenario (posturas, r(t), I_c(t),
  eventos, ledger con hash-chain y `canon` para re-verificación).

## Interpretar los exports

Cada `scenario_<id>.json` contiene:

| campo | significado |
|---|---|
| `final_posture` | postura terminal alcanzada (P0…P4) |
| `posture_history` | por tick: postura, riesgo agregado `r`, intensidades `I_c` por categoría |
| `events` | eventos del escenario con `blocked`/`contained` (¿fue contenido en ventana?) |
| `ledger.entries` | cadena: `seq`, `tick`, `kind` (evento/postura/final), `payload`, `prev_hash`, `canon`, `hash` |
| `ledger_final_hash` | ancla de integridad de toda la ejecución (determinismo redundante) |
| `review_required` | puertas humanas levantadas (techo de capacidad) |

Métricas por escenario (en `summary.json`): `t_detect` (primer cambio de postura),
`t_respond` (latencia a la primera contención), `contenidos`/`cometidos`
(severidad residual), `contained_rate`, y verificaciones de **determinismo**
(2ª corrida = mismo hash) e **integridad del ledger**.

## Añadir un escenario declarativo

1. Añade un objeto al arreglo `escenarios` de `engine/scenarios.json`:

```json
{
  "id": "s12_mi_caso",
  "agente": "med",
  "window_ticks": 20,
  "eventos": [
    {"tick": 4, "kind": "credential_collect", "target": "env_secrets"}
  ],
  "esperado": {"postura_final": "P2", "contenidos_min": 1,
               "nota": "qué quiero ilustrar y por qué"}
}
```

2. Asegúrate de que cada `kind` tenga una entrada en `_eventos_a_senales` del
   `policy_config.json` (evento → señal con confianza). Si no existe, el evento no
   genera señal — véase `s09_blind_spot`, un falso negativo *por diseño* que
   documenta el límite del modelo en vez de inflar la cobertura.
3. Corre `python -m engine.evaluate`. Las aserciones declaran la *intención de
   diseño*; los resultados reales se reportan tal cual. Si un escenario no llega a
   su postura esperada, la aserción fallará y verás el desvío — es *información*,
   no algo que se tunea para "ganar".

## Visor (réplica 2D)

`ui/visor.html` es un archivo único (funciona por doble clic, sin servidor) que
reproduce cualquier export:

- **Teatro 2D**: bandas de postura P0–P4, polilínea de postura en el tiempo,
  marcadores de evento (futuro = contorno punteado), cursor temporal, y
  mini-gráficos de `I_c(t)` por categoría.
- **Panel derecho**: medidor de postura actual, `r(t)` y métricas en vivo, barras
  de intensidad por señal, feed de eventos.
- **Ledger**: cadena hash completa con su botón **"Re-verificar cadena en el
  navegador"** — reimplementación local de SHA-256 que reproduce `ledger.verify()`.
- Demo por defecto: el escenario **s08** (spoofing de capa de ejecución → P3;
  reintentos persistentes → **P4 humano**), embebido vía
  `python ui/build_visor.py` directamente desde el export real.

La re-verificación funciona porque el export incluye el `canon` exacto que Python
hasheó; el navegador no serializa nada por su cuenta.

> Prueba de integridad del visor (dev): un test temporal extraía el `sha256_hex`
> embebido y recomputaba toda la cadena desde GENESIS. Resultado esperado:
> `sha256("abc")` = `ba7816bf…` y hash final `1574a1ad…` para s08. *(El test se
> eliminó; el procedimiento está documentado aquí.)*

## Lo que esto mide — y lo que no

El prototipo es un **banco de pruebas de la lógica de decisión**, no una medición
de la seguridad de un agente real. Lo que sí verifica, de forma honesta y
reproducible:

- `[Evidencia]` Determinismo: misma entrada → idéntico hash de ledger.
- `[Evidencia]` Integridad: `ledger.verify()` y re-verificación en el navegador
  reproducen la cadena.
- `[Evidencia]` Cobertura de señales del catálogo: 10/10 ejercitadas.
- `[Evidencia]` Sensibilidad: las decisiones son **robustas a los pesos por
  categoría** pero **sensibles a los umbrales** (volteos al ×1.5), con una banda
  de operación robusta ≈×1.0–1.25.

Lo que no afirma: que estas señales ni estos umbrales sean correctos para un agente
real (requeriría telemetría real y análisis adversario — fuera de alcance de un
entorno seguro y simulado). El catálogo `s09_blind_spot` existe explícitamente para
recordarlo.

## Ejecucion 
python --version
python -m engine.evaluate
python -m engine.sweep
python ui\build_visor.py
start .\ui\visor.html

---

# Plataforma de contención en tiempo real (runtime MVP)

> **Sigue siendo un entorno seguro.** Toda "acción" del agente es una solicitud que
> la infraestructura decide **permitir o denegar** mediante control mecánico
> (workspace con path-containment, egress allowlist, vault opaco, exec allowlist,
> fail-closed). No se implementan exploits, malware ni evasión: la demo valida los
> mecanismos con acciones benignas cuyo acceso está explicitamente gobernado.
> Además, **el modelo formal `engine/` no se modifica**: la plataforma lo *envuelve*
> con un runtime incremental idéntico tick a tick (probado por equivalencia), de modo
> que `python -m engine.evaluate` sigue produciendo los mismos hashes del paper.

Junto al prototipo simulado (arriba) existe ahora una **plataforma runtime**: una
capa de seguridad real alrededor de un **agente controlado** — un proceso driver
provider-agnóstico que solicita cada acción antes de ejecutarla — con backend API,
gateway físico de contención, ledger inmutable extendido y un **dashboard SOC**
React + TypeScript. La arquitectura completa vive en [`ARCHITECTURE.md`](ARCHITECTURE.md).

## La cadena

```
Agente controlado (demo/driver.py) ──preexec─►  Enforcement (ALLOW|BLOCK|HOLD_REVIEW)
   ──► AI-BSL Engine (runtime, mismo g(C,r(t)) del modelo) ──► Actuators ──► Gateway físico
   ──► Ledger SHA-256 (hash-chain + espejo externo) ──WS/SSE/REST──► Dashboard SOC
```

## Cómo correr

```powershell
# 1) backend API (sirve también el dashboard si web/dist existe)
python -m uvicorn platform.api.main:app --host 127.0.0.1 --port 8000

# 2) demo del agente controlado (P0 → P1 → P2 → P3 → P4 con aprobaciones humanas)
python -m platform.demo.driver                       # flujo automático (auto-aprueba)
python -m platform.demo.driver --no-auto             # pide aprobación humana en el dashboard

# 3) dashboard (desarrollo) — o simplemente abre http://127.0.0.1:8000
cd web
npm install --include=dev     # nota: NODE_ENV=production global omite devDeps si no se fuerza
npm run dev                   # Vite 5173 con proxy /api,/ws,/sse → localhost:8000

# 4) build estático (para que la API lo sirva: reinicia la API después)
cd web && npm run build       # tsc -b && vite build → dist/ (montado en "/" al arrancar)
```

### Qué ver en el dashboard

- **Modo Live**: elige `workhorse` (perfil `med`, techo P2). Observa la línea de
  riesgo `r(t)`, las bandas de postura P0–P4, la intensidad `I_c(t)`, el feed de
  enforcement ("qué ocurrió / qué señal / qué riesgo / qué postura / qué regla /
  qué evidencia"), las revisiones humanas (ceiling override, P4), y el ledger con
  su botón **"Re-verificar SHA-256 en el navegador"** (recomputa toda la cadena
  desde GENESIS con `crypto.subtle`).
- **Modo Lab**: corre cualquiera de los 11 escenarios del paper; el dashboard
  reproduce tick a tick `engine/run` y muestra un badge ✓ que **coincide con el
  hash de `engine/exports/scenario_<id>.json`**.

## Cómo conectar un agente (contrato del adapter)

Cualquier agente (hoy un driver scripted; mañana un LLM real) se conecta así, sin
tocar el motor de decisión:

```python
# 1) conectar → te devuelve {agent, ceiling, actuator_state, gateway}
POST /api/v1/agents   {"name": "probe", "profile": "med", "mode": "live"}

# 2) solicitar cada acción ANTES de ejecutarla → la decisión manda
POST /api/v1/agents/{id}/actions/preexec
    {"type": "file", "name": "read", "target": "../secrets/master.key", "declared": false}
#    → {decision: "BLOCK", rule: "...", signal: "access_out_of_scope", risk_before: ..., rationale: ...}

# 3) si ALLOW, el gateway vuelve a comprobar (workspace/egress/vault/exec/heartbeat)
POST /api/v1/agents/{id}/actions/result  # telemetría post-ejecución

# 4) telemetría adicional de eventos libres
POST /api/v1/agents/{id}/events  [{...}]
```

- **Credenciales**: jamás se exponen — ni al agente ni al frontend. El vault es
  **opaco** (devuelve `[REDACTED]`) y toda lectura/uso intentado genera señal
  (`credential_collect` / `credential_use_anomalous`).
- **Egreso**: solo destinos en una allowlist (localhost echo); todo lo demás se
  deniega por mecanismo antes de tocar la red.
- **Archivos**: todo acceso fuera de la raíz del workspace se deniega por `realpath`.
- **Fail-closed**: si el runtime/ledger no responden (heartbeat), la puerta de alto
  riesgo **niega por defecto** — nunca continúa algo automático peligroso.

## Verificación rápida

```powershell
python -m platform.verify_equivalence   # 11/11: runtime incremental == exports (modelo intacto)
python -m engine.evaluate               # regresión del modelo: hashes del paper sin cambios
curl http://127.0.0.1:8000/api/v1/health   # equivalence 11/11 + fail_closed enabled
```