# AI-BSL → Plataforma de contención en tiempo real (MVP)

> Este documento es el entregable de "propuesta de arquitectura final" del MVP de
> hackathon: cómo **el motor del modelo formal AI-BSL permanece intacto** y cómo se
> construye alrededor una capa de **runtime containment real** (enforcement point,
> gateway físico, ledger, API y dashboard SOC), con un **agente controlado** que
> demuestra la contención en ejecución, no en simulación.

---

## 1. Principio rector: el modelo no se toca

El modelo formal (`engine/`, catálogo de 11 escenarios, `exports/`) es la fuente de
verdad científica del proyecto y **no se modificó en ninguna línea**:

- `engine/model.py`, `engine/ledger.py`, `engine/engine.py` — tipos, ledger SHA-256,
  motor `g(C, r(t))`, tripwires, `τ_hold`, histéresis, `ceiling(C)`, P4 humano.
- `engine/policy_config.json`, `engine/scenarios.json` — configuración declarativa.
- `engine/evaluate.py`, `engine/sweep.py`, `engine/exports/` — harness y hashes del
  paper reproducibles.
- `ui/` (visor 2D), `AI-BSL_modelo_formal.md`, `AI-BSL_revision_critica.md`,
  `README.md` (a este último solo se le añade una sección, nada se borra).

La plataforma **envuelve** el modelo: el motor de decisión se reutiliza tal cual
para ejecución en vivo por medio de un **runtime incremental por agente** que
replica, tick a tick, el mismo paso de decisión de `Engine.run()`. Se demuestra la
igualdad con una **prueba de equivalencia** (ver §6): si algún día el wrapper
divergiera del modelo, se corrige el wrapper, nunca `engine/`.

Garantía: `python -m engine.evaluate` produce exactamente los mismos hashes que hoy
(regresión del modelo intacta); `platform.verify_equivalence` confirma 11/11 en
`/api/v1/health`.

---

## 2. Cadena de datos (la contención completa)

```
Agente (driver controlado hoy; LLM mañana — provider-agnóstico)
   │  solicita acción (tool / file / network / credential / exec)
   ▼
Agent Adapter ──────────►  POST /api/v1/agents/{id}/actions/preexec
   ▼
Event Collector       (timestamp, tick, id de acción, heartbeat)
   ▼
Signal Mapper         (kind → señal + confianza; evento desconocido → sin señal, pasa)
   ▼
AI-BSL Engine (runtime)  (mismo g(C,r(t)) del modelo: I_c, r, tripwires, τ_hold,
                           histéresis, ceiling(C), autoridad humana P4)
   ▼
Policy Enforcement Point  (ALLOW | BLOCK | HOLD_REVIEW según postura + enforcement
                            por clase de acción + techo de capacidad)
   ▼
Actuators               (suspender tool, log verbosity, cortar egress, revocar tokens,
                          aislar zonas, congelar tools, revocar credenciales,
                          terminar instancias, reset, exportar ledger, kill/P4)
   ▼
Gateway físico          (workspace con path-containment, egress allowlist,
                          vault opaco, exec allowlist, guard fail-closed)
   ▼
Immutable Audit Ledger  (mismo esquema sha256(prev|tick|kind|canon) + espejo externo;
                          se extiende con kinds nuevos — sin reemplazar SHA-256)
   │
   ▼
WS / SSE + REST  →  Dashboard SOC (React + TypeScript)
```

Cada eslabón es un módulo con responsabilidad única; la cadena es la misma para el
modo **Live** (agente controlado) y para el **Lab** (simulación del paper), con una
única diferencia documentada en §5.

---

## 3. Qué papel juega cada pieza (intacto → envuelto)

### Intacto y reutilizado

| Pieza | Rol en la plataforma |
|---|---|
| `engine.Engine(config)` | fuente de la lógica de decisión y de los parámetros ya parseados (señales, pesos, umbrales, techos, actuadores) |
| `engine.model.LedgerEntry` / `sha256_hex` | esquema de hashing del ledger, sin cambios |
| `engine/scenarios.json` + `engine/evaluate` | catálogo del Laboratorio simulado y exports de referencia |
| `engine/policy_config.json` | política declarativa inicial (v0.1) del `policy_store` |

### Envuelto (nuevo código, nunca toca `engine/`)

| Módulo | Responsabilidad |
|---|---|
| `platform/runtime.py` | `AgentRuntime` incremental por agente (mismo paso de decisión por tick), `AgentSession`, snapshot completo |
| `platform/signal_mapper.py` | kind → señal (+ confianza) a partir de la config del engine; enriquece eventos |
| `platform/enforcement.py` | `EnforcementDecision`: ALLOW / BLOCK / HOLD_REVIEW, regla, rationale, evidencia |
| `platform/actuators.py` | `ActuatorState` por postura (flags físicos) + aplicar |
| `platform/policy_store.py` | política declarativa versionada (v0.1 = `policy_config.json`; carga validada con el loader del engine) |
| `platform/db.py` + `platform/ledger_store.py` | SQLite append-only: agentes, sesiones, ledger (hash-chain + verify), mirror externo `ledger_ext`, reviews, approvals |
| `platform/review.py` | review requests + `HumanApproval` (ceiling override, P4, restauración, deny) |
| `platform/controller.py` | coordinación runtime ↔ enforcement ↔ actuators ↔ gateway ↔ ledger |
| `platform/metrics.py` | `t_detect`, `t_respond`, `contained_rate`, cometidos/contenidos, integridad |
| `platform/ws_hub.py` | broadcast WS + SSE (event, risk, posture, enforcement, review, approval, ledger, execution) |
| `platform/seeder.py` | perfiles iniciales high/med/low, política v0.1, catálogo |
| `platform/verify_equivalence.py` | **prueba de equivalencia**: 11 escenarios por el runtime incremental == hashes de `exports/` (se integra en `/health`) |
| `platform/adapters/` | `base.py` (protocolo AgentAdapter), `controlled_agent_adapter.py` (Live: canaliza preexec/exec), `scenario_adapter.py` (Lab: corre `engine.run` del paper) |
| `platform/gateway/` | contenedor físico real (ver §7): `workspace`, `egress_proxy`, `credential_vault`, `tool_gateway`, `failclosed`, `echo` |
| `platform/api/main.py` | FastAPI: REST + `/ws/events` + `/sse/events` + sirve el build del frontend (si `web/dist` existe al arrancar) |
| `platform/demo/driver.py` | el **agente controlado** de la demo (scripted, determinista, provider-agnóstico) |
| `web/` | dashboard SOC React + TypeScript (ver §9) |

---

## 4. Tipos compartidos (contrato backend ↔ frontend)

`platform/types.py` y `web/src/types/index.ts` son un espejo 1:1:

- `Agent`, `AgentInfo`, `Capability` (N, X, M, B, K, tools) — la capacidad `C`.
- `RiskState` — postura, riesgo agregado `r`, intensidad `I_c` por categoría, tick.
- `AgentEvent` / `Outcome` — id, tick, kind, target, dangerous, blocked, contained.
- `AnnotatedSignal` — id, confianza, categoría, ponderación.
- `PolicyDecision` / `EnforcementMsg` — ALLOW|BLOCK|HOLD_REVIEW, regla, rationale,
  riesgo antes/después, postura de/a, evidencia seq.
- `Review` / `HumanApproval` — tipo (REVIEW_REQUIRED | P4_REQUEST), decisión, por, nota.
- `LedgerEntry` — seq, tick, kind, payload, prev_hash, `canon`, hash (mismo canon que `engine.model`).
- `ActuatorState` — flags mecánicos por postura.
- `HistoryPoint` — `{tick, posture, r, I}` (esto es lo que hace que las gráficas del
  Lab y del Live usen exactamente los mismos componentes heredados del runtime).

---

## 5. Dos modos, una sola cadena

### Live — Controlled Agent (runtime containment)

```
demo/driver.py (o cualquier adapter) ── POST /agents/{id}/actions/preexec
```
El driver solicita cada acción **antes de ejecutarla**. El enforcement responde
ALLOW / BLOCK / HOLD_REVIEW. Si ALLOW, el gateway **mecánico** verifica de nuevo
contención (workspace, egress, vault, exec, heartbeat fail-closed) y es quien
ejecuta contra recursos controlados (archivos en `sandbox/`, socket echo local,
tool allowlist). Cualquier decisión/señal/transición se vuelca al ledger y se
emite por WS/SSE. Las aprobaciones humanas (P4, exceder `ceiling(C)`) entran por
`POST /reviews/{id}/decide` y alimentan el mismo `human_state` que `run()` recibía.

### Lab — Simulación del paper

```
POST /api/v1/scenarios/{scenario_id}/run  →  engine.run(scenario)
```
El adapter de escenarios llama **directamente** a `Engine(config).run(scenario)` —
la misma ruta del paper — y el dashboard reproduce el resultado tick a tick con
los mismos componentes de gráficas. Los hashes finales del Lab **coinciden
exactamente** con `engine/exports/scenario_*.json` (verificado en el UI con el
badge ✓/✕ contra el prefijo esperado, p. ej. s08 → `1574a1ad…`). El runtime
incremental **no** se usa en Lab; solo en Live.

---

## 6. Equivalencia: cómo se garantiza "modelo intacto + ejecución real"

`platform/verify_equivalence.py`:

1. Lee los 11 escenarios de `engine/scenarios.json`.
2. Alimenta cada uno a través de `AgentRuntime(mirror_sim=True, platform=None)`
   tick por tick (el runtime consume los mismos parámetros ya parseados de
   `engine.Engine(config)`).
3. Asevera que `ledger_final_hash` del runtime == `ledger_final_hash` de
   `engine/exports/scenario_<id>.json`.

Resultado actual: **11/11 ok**, reportado en `GET /api/v1/health` →
`equivalence: {"ok": true, "passed": 11, "total": 11, "failures": []}`.
Cualquier desliz se corrige en el wrapper, nunca en `engine/`.

---

## 7. Gateway físico (contención real, acciones benignas y controladas)

Todo lo que el gateway hace es **permitir o denegar**; nunca implementa exploits ni
evasión. Las acciones de la demo son benignas y su acceso está decidido por la
infraestructura:

| Módulo | Mecanismo |
|---|---|
| `workspace.py` | raíz `sandbox/agents/<id>/`. `read/write` se resuelven con `os.path.realpath` y se **deniegan por mecanismo** fuera de la raíz (además del bloqueo por política) → señal `access_out_of_scope` |
| `egress_proxy.py` | **allowlist de hosts** (solo `localhost` echo). Cualquier destino no permitido → denegado + `network_request_blocked` / `egress_anomaly`; el socket real solo existe hacia el echo local inofensivo |
| `credential_vault.py` | **vault opaco**: ninguna lectura devuelve material de secretos (`[REDACTED]`); patrón de lectura/uso → `credential_collect` / `credential_use_anomalous`. **Los secretos no llegan al modelo ni al frontend** |
| `tool_gateway.py` | exec bajo allowlist (search/grep en workspace, reportes) con cwd=workspace, sin red; P1+ suspende herramientas de alto riesgo vía actuators |
| `failclosed.py` | guard fail-closed: antes de una acción de alto riesgo exige un `EnforcementDecision` fresco (heartbeat). Si el runtime/ledger no responden → **deniega por defecto** |
| `echo.py` | servicio echo local para el egress permitido (inofensivo, sin salida a Internet) |

Defensa en profundidad: no basta con que la **política** diga BLOCK; el **mecanismo**
vuelve a comprobar antes de ejecutar (workspace containment, allowlist, vault,
heartbeat). Los `ActuatorState` por postura (egress_cut, tokens_revoked,
tools_frozen, creds_revoked_all, instances_terminated, quarantine…) son consultados
por el gateway como segunda barrera.

---

## 8. Ledger (extendido, sin tocar el esquema SHA-256)

- **Mismo esquema exacto** de `engine/ledger.py`:
  `hash = sha256_hex(f"{prev}|{tick}|{kind}|{canonical_json(payload)}")` — no se
  reemplaza SHA-256 ni la lógica de integridad.
- Se **añaden kinds** nuevos al payload junto a los existentes
  (`evento`, `postura`, `final`): `review`, `approval_human`, `enforcement`,
  `agent_state`, `signal`.
- Persistencia append-only en SQLite (`ledger_store.py`) + **espejo externo
  write-only** (`ledger_ext`) — el mirror no puede ser reescrito por la aplicación.
- `verify()` recomputa toda la cadena **en el servidor** y, de forma independiente,
  **en el navegador** (`crypto.subtle` re-hashea `sha256(prev|tick|kind|canon)`
  usando el `canon` almacenado). Ambos resultados se muestran en el dashboard.
- Toda decisión de enforcement, aprobación humana y estado del actuador queda
  encadenada: la demo P0→P4 cierra con 46 entradas, `verify=True`.

---

## 9. Frontend React + TypeScript (SOC / Agent Containment Dashboard)

`web/` — Vite + React + TS, tema SOC claro/oscuro con variables CSS, **SVG propio**
sin librerías de charts (guía `dataviz`: paleta categórica fija, ejes, marcas finas,
hover crosshair + tooltip).

**Página Dashboard (Live):**
- Selector de agente controlado; estado de conexión WS (en vivo) con fallback SSE.
- `RiskTimeline` — evolución r(t) con bandas de postura P0–P4, transiciones y
  marcadores de enforcement (ALLOW / HOLD_REVIEW / BLOCK).
- `IntensityChart` — I_c(t) por categoría (multi-serie).
- `PostureGauge`, `MetricsPanel`, `EventFeed`, `EnforcementLog` (qué ocurrió / qué
  señal / qué riesgo / qué postura / qué regla / qué acción / qué evidencia),
  `ToolGates` (tools y qué se suspende/revoca por postura; vault siempre `[REDACTED]`).
- `ReviewQueue` — aprobación humana (ceiling override, P4) con causa y nota.
- `LedgerPanel` — tabla hash-chained + **botón "Re-verificar SHA-256 en el navegador"**
  + badge de espejo externo.
- `DemoControls` — dispara la coreografía del driver y las acciones del agente
  controlado desde el propio dashboard (search/read dentro del workspace, acceso
  fuera de alcance, egress a host no permitido, vault, exec divergente, reintentos).

**Página Lab (Simulación):**
- Catálogo de los 11 escenarios; correr vía `engine.run`; reproducir tick a tick con
  los mismos componentes de gráficas; badge ✓/✕ que **coincide con
  `engine/exports/scenario_<id>.json`** (hash final del paper).

**Tiempo real:** WS `/ws/events` (todos los temas) con reconexión exponencial, SSE
como fallback, y polling REST autoritativo como tercera vía. El dashboard se actualiza
sin recargar.

---

## 10. Contrato API (resumen)

```
GET  /api/v1/health                     status + fail-closed + equivalencia 11/11
POST /api/v1/policy                     cargar / versionar política (validada con el loader del engine)
GET  /api/v1/policy_versions            versiones de política
POST /api/v1/agents                     registrar/conectar agente {name, profile, mode}
GET  /api/v1/agents                     listado + resumen
GET  /api/v1/agents/{id}                snapshot completo (postura, r, I_c, ceiling, actuators, gateway,
                                        fail_closed, terminal, killswitch, budget, ledger, reviews abiertas,
                                        posture_history, transitions, events)
POST /api/v1/agents/{id}/events         ingesta de eventos (adapters)
POST /api/v1/agents/{id}/actions/preexec  gate del agente controlado: ALLOW | BLOCK | HOLD_REVIEW + ejecución
POST /api/v1/agents/{id}/actions/result   telemetría post-ejecución
GET  /api/v1/agents/{id}/history        posture_history + riesgo
GET  /api/v1/agents/{id}/events         log de eventos
GET  /api/v1/agents/{id}/ledger         ledger hash-chained + mirror
POST /api/v1/agents/{id}/ledger/verify  verify() en servidor
GET  /api/v1/agents/{id}/reviews        cola de revisiones humanas abiertas
POST /api/v1/agents/{id}/reviews/{id}/decide  aprobar/denegar (ceiling, P4, restaurar)
POST /api/v1/agents/{id}/offline        toggle fail-closed / fail-open del agente
GET  /api/v1/agents/{id}/metrics        t_detect, t_respond, contained_rate, cometidos, integridad
GET  /api/v1/scenarios                  catálogo de los 11 escenarios (Lab)
POST /api/v1/scenarios/{scenario_id}/run  correr escenario (misma ruta del paper) → hashes = exports
WS   /ws/events                         feed en vivo {agent_id, type, tick, ts, payload}
SSE  /sse/events?agent_id=              fallback de streaming para el browser
```

El frontend se sirve por la propia API si `web/dist` existe al arrancar
(`GET /` → dashboard); durante el desarrollo se usa `npm run dev` en Vite con proxy
`/api`, `/ws`, `/sse` hacia `127.0.0.1:8000`.

---

## 11. Verificación (lo que se ha corrido)

1. `python -m engine.evaluate` — regresión del modelo: hashes idénticos a `exports/`.
2. `python -m platform.verify_equivalence` — **11/11** hashes runtime == exports
   (reportado en `/health`).
3. API arrancada (`uvicorn platform.api.main:app`, 127.0.0.1:8000) → `GET /health` ok,
   3 agentes, equivalence 11/11, fail_closed enabled; `GET /` sirve el dashboard.
4. `web/`: `npm run build` compila limpio (`tsc -b && vite build`); el dashboard se
   sirve desde `dist`; Lab reproduce el hash del paper (p. ej. s08 `1574a1ad…`).
5. **Demo live end-to-end** (`python -m platform.demo.driver`): el agente controlado
   sube P0→P1→P2→P3→(ceiling override humano)→P4 (aprobación humana), con egress a
   `evil.example` bloqueado por allowlist, vault opaco bloqueando lecturas de
   credenciales, workspace fuera de alcance bloqueado por realpath, exec divergente
   bloqueado por actuators; ledger final 46 entradas, `verify=True`.
6. Prueba fail-closed: `POST /agents/{id}/offline` corta el heartbeat → las acciones
   de alto riesgo se deniegan por defecto.

---

## 12. Fuera de alcance del MVP (trabajo futuro documentado)

- Conexión de LLMs reales (Claude/OpenAI/otros) — la frontera del adapter queda
  lista (`platform/adapters/base.py`, `preexec/result` provider-agnósticos).
- Orquestación multi-agente (coordinación P2), hardening del egress proxy hacia
  infraestructura y DNS reales, authn/authz del API, despliegue no-local.
- Según la restricción de seguridad del proyecto, **no se implementan exploits,
  malware, evasión de controles ni ataques reales**: la demo valida los mecanismos
  con acciones controladas y benignas cuyo acceso está explícitamente permitido o
  denegado por la infraestructura.