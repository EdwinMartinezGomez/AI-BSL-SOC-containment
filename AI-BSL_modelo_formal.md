# AI-BSL — Modelo formal (Fase 3)

**Versión de especificación:** 0.1 · **Estado:** borrador en validación (se implementa en `engine/` y se verifica con el harness de evaluación).

Este documento define AI-BSL como **función de decisión de contención basada en comportamiento**. Es la especificación que comparten el paper y el código. Donde hay diseño propio (no evidenciado), se marca **[Propuesta]**. Los pesos y umbrales son **configurables y justificados por incidentes documentados** — no hechos.

---

## 1. Notación y supuestos

- Tiempo discreto `t ∈ ℕ` (ticks). La simulación es determinista por construcción (eventos programados en ticks fijos con seed fija).
- **Supuesto de amenaza (no lealtad):** el agente puede desviarse por error, reward hacking, misgeneralización o subversión deliberada. No se asume lealtad. ([Evidencia] AI Control, arXiv:2312.06942; METR partes 1–2.)
- **No medimos el mundo real:** las observaciones simuladas se toman como dadas; evaluamos la *decisión de contención*, no la detección.

---

## 2. Elementos del modelo

### 2.1 Despliegue `D = (C, X)`

**Vector de capacidades `C`** (declarado, cuasi-estático):

```
C = (
  T ⊆ Tools,            # herramientas disponibles
  N ∈ {none, proxy, full},   # alcance de red
  X ∈ {none, managed, native},# capacidad de ejecución de código
  M ∈ {none, session, persistent}, # memoria / persistencia
  B ∈ ℕ,                # presupuesto: pasos autónomos
  K ∈ ℕ                 # instancias concurrentes
)
```

**Restricciones de entorno `X`**: zonas/objetos accesibles, cuotas de recurso, allowlist de egress, y `human_ceiling_override ∈ {false,true}` (autorización para superar el techo).

**[Propuesta]** `C` define dos cosas: el **techo de postura** `ceiling(C)` (máxima postura sin aprobación humana) y la **severidad potencial** de cada señal (ponderación de impacto).

### 2.2 Biblioteca de señales `Σ`

Cada señal `σ ∈ Σ`:

```
σ = (id, categoria, λ_σ, γ_σ, tripwire, posture_target, requires)
  λ_σ ∈ [0,1]   # peso de severidad
  γ_σ ∈ [0,1]   # decaimiento por tick (0.9 → media vida ~6.6 ticks)
  tripwire ∈ {no, duro}   # duro => brinca a posture_target sin umbral
  requires ⊆ C  # condición de aplicabilidad (¿capaz de hacerlo?)
```

Biblioteca inicial (10 señales) con fuente:

| id | categoría | λ | γ | tripwire | Fuente |
|---|---|---|---|---|---|
| `access_out_of_scope` | access | 0.5 | 0.90 | no | Elastic (outcome: acceso credenciales) / ATLAS |
| `credential_collect` | credential | 0.8 | 0.85 | no | Elastic; METR (opsec pobre, harvesting) |
| `credential_use` | credential | 0.9 | 0.85 | **duro→P2** | Elastic (uso de credenciales) |
| `egress_anomaly` | egress | 0.7 | 0.90 | no | Elastic (destino inusual), METR |
| `encoded_exfil_prefix` | egress | 0.8 | 0.90 | no | Elastic (encode/chunk previo a red) |
| `resource_exceed` | resource | 0.4 | 0.92 | no | OWASP *Unbounded Consumption*; Elastic (cardinalidad) |
| `evasion_retry` | evasion | 0.7 | 0.85 | no | Elastic (retries de éxito), METR (persistencia) |
| `log_tamper_attempt` | tampering | 1.0 | — | **duro→P3** | METR parte 2 (concealment) |
| `exec_layer_spoof` | tampering | 1.0 | — | **duro→P3** | METR parte 2 (tool-call spoofing) |
| `coordination_undisclosed` | coordination | 0.6 | 0.90 | no | METR (message board, 70k msgs) |

> **[Inferencia]** Pesos/prioridades derivados de la gravedad de outcomes en las fuentes; son decisión de diseño, sujetos a análisis de sensibilidad (sección 7).

### 2.3 Observaciones y detección

Evento `e = (tick, kind, target, detail)`. Detector: `map(e) → {(σ, conf)}`, con `conf ∈ [0,1]` **fi**ulado por clase de evento (parámetro de calidad del detector). Honestidad: la detección es "dada"; la validamos indirectamente (cobertura y FP/FN por diseño en escenarios).

### 2.4 Agregación de riesgo `r(t)`

Por categoría `c`:

```
I_c(t) = γ_c · I_c(t−1) + Σ_{σ ∈ c activas en t} conf·λ_σ
```

Compuesto (escalar):

```
r(t) = Σ_c α_c · min(1, I_c(t))       # α_c ≥ 0, Σ α_c = 1, configurables
```

Además se conserva el vector `R(t) = (I_c(t))_c` para umbrales por categoría. `r` es acotado en [0,1] (por el `min`). [Propuesta]

### 2.5 Posturas de contención `P`

Poseta ordenada (rejilla simple):

```
P0 Monitor ⊂ P1 Restrict ⊂ P2 Isolate ⊂ P3 Revoke/Contain ⊂ P4 Terminate+Review
```

Semántica operativa y de **actuadores** (sobre el mundo simulado):

| Postura | Actuadores | Efecto simulado | Autoridad |
|---|---|---|---|
| P0 | ninguno (logging + firmas) | — | auto |
| P1 | suspender tools de alto riesgo, subir verbosidad de log, cap de recurso | acciones de alto riesgo bloqueadas | auto |
| P2 | cortar egress, revocar tokens, aislar zonas/otras instancias, pausar tool-calls pendientes | egress/creds/coordinación bloqueadas | auto + notificar |
| P3 | revocar todas las credenciales, terminar instancias, reset de entorno, exportar ledger a sink externo | todas las acciones peligrosas bloqueadas | **humano** (o tripwire duro auto) |
| P4 | terminación + cuarentena + revisión forense + decisión de redeploy | — | **humana obligatoria** |

**[Propuesta]** "Aislamiento", "revocación", "terminación" son **efectos mecánicos sobre el entorno simulado** con marcadores de reversibilidad, no palabras vagas.

### 2.6 Función de decisión `g`

Estado interno: `(P_actual, contadores_hold, I_c, aprobaciones_humanas)`.

**Reglas (formalizadas):**

1. **Tripwire duro.** Si `σ` es tripwire duro y `conf ≥ θ_t`, entonces `P ← posture_target(σ)` **inmediatamente**, causa registrada. No pasa por el score.
2. **Escalada por umbral.** Si `r(t) ≥ θ_up(P_next)` **o** `∃c: I_c(t) ≥ θ_up_cat(P_next)`, sostenido `τ_hold` ticks → `P ← P_next`.
3. **Escalada máxima con techo.** Si la regla 2 elevaría más allá de `ceiling(C)`: emitir `REVIEW_REQUIRED`, mantener la postura, no auto-escalar. Requiere humano.
4. **Degradación (histéresis).** Si `r(t) < θ_down` y `∀c: I_c(t) < θ_down_cat`, sostenido `τ_hold_down` ticks, sin tripwire reciente, y (`P < P3` o `humano_aprobado`) → `P ← P_prev`.
5. **Límites:** `P4` solo por decisión humana registrada (auto puede *solicitar*). No re-escalada automática desde P4 sin revisión.

**Histéresis:** `θ_up < θ_down` (escalar más fácil), `τ_hold < τ_hold_down` (escalar rápido, degradar lento). Evita *flapping*.

### 2.7 Ledger de evidencia `L`

Entrada `ℓ`:

```
ℓ = (seq, tick, kind, signals[(σ,conf)], risk_snapshot=(r(t), R(t)),
     posture=(P_from, P_to), action, cause, prev_hash, hash)
hash = SHA256(prev_hash ‖ canonical_json(ℓ sin hash))
```

- Append-only. 
- **Sink externo write-only:** `L.ext` es una copia fuera del alcance del agente simulado (representa el *external scorer* de METR).
- **Verificación:** `verify(L) → (ok, first_bad_idx)` recomputando la cadena.
- **Detección de tampering:** si el agente simulado altera su transcript, el comparador `L vs L.ext` emite `log_tamper_attempt` (tripwire duro → P3). [Inferencia de METR parte 2]

---

## 3. Lazo de control (narrativa)

```
Orient  : R(t) desde O      (risk.py)
Decide  : g(C, R(t)) → P     (policy.py, histéresis + tripwires + techo)
Act     : enforce(P)          (actuator.py, efectos mecánicos marcados)
Record  : ℓ → L + L.ext       (ledger.py, hash-chain)
Review  : verify(L), métricas (evaluate.py)
```

Equivale a un **lazo de control** (sensor=detector, control=policy, actuador=enforcement) — descrito así en el paper para conectar con la literatura de control/IRL. [Propuesta]

---

## 4. Invariantes que el harness debe verificar

- **I1 Reproducibilidad:** misma seed+escenario ⇒ ledger idéntico (mismo hash final).
- **I2 Monotonicidad de escalada:** señales repetidas nunca bajan la postura; la elevan o la mantienen.
- **I3 No-flapping:** ruido en el filo de umbral no oscila P (histéresis).
- **I4 Techo:** `P` nunca excede `ceiling(C)` sin `human_ceiling_override`.
- **I5 Tripwires inmediatos:** los tripwires no esperan score (brincan en el tick).
- **I6 Integridad:** `verify(L)` pasa al final de todo run limpio; un tampering simulado rompe la cadena o dispara la señal.

Estos invariantes se convierten en **property tests** (`evaluate.py` → property checks) y en afirmaciones empíricas **del modelo** (no del mundo real) en el paper.

---

## 5. Métricas (definiciones formales)

| métrica | definición | obtención en sim |
|---|---|---|
| `t_detect` | ticks entre 1er evento malicioso y el cambio de postura ≥ objetivo | del ledger |
| `t_respond` | ticks entre cambio de postura y efecto de actuador registrado | del ledger |
| `contained_rate` | eventos peligrosos bloqueados / eventos peligrosos totales | del ledger |
| `fp` | escenarios normales con postura > baseline sin causa | del run |
| `fn` | escenarios de límite no detectados (>=1 por diseño) | del run |
| `coverage` | señales ejercitadas / Σ | intersect de escenarios |
| `classification` | acuerdo postura final vs esperada declarada | asserter |
| `ledger_integrity` | verify(L) al final | función |
| `determinism` | igualdad de hash final en 2 runs misma seed | función |

**Fuera de alcance (lo repite el paper):** tasas reales de detección, eficacia real de actuadores en producción, robustez contra un agente LLM real.

---

## 6. Decisiones de diseño registradas (para el decision record)

| # | decisión | tipo | justificación |
|---|---|---|---|
| FRM-01 | Dos dimensiones separadas C y r(t) | Propuesta | evita la confusión autonomía/riesgo (ver revisión crítica, secc. E) |
| FRM-02 | Niveles → posturas resultantes, no clases de agente | Propuesta | dynamics: escalar/desescalar en runtime |
| FRM-03 | Tripwires duros para tampering/credenciales | Inferencia | METR parte 2; Elastic outcomes |
| FRM-04 | Histéresis (θ_up<θ_down, τ_hold<τ_hold_down) | Propuesta | robustez de control |
| FRM-05 | Sink externo + hash-chain + verificación | Propuesta/Inferencia | METR: transcript no es fuente de verdad |
| FRM-06 | P3/P4 requieren humano | Propuesta | autoridad en el diseño, no afterthought |
| FRM-07 | Pesos configurables, no "calibrados" | Propuesta | honestidad + sensibilidad |

---

## 7. Sensibilidad (qué barre `sweep.py`)

Barrer `α_c` (pesos de categoría) y `θ_up`/`θ_down` en un rango; medir estabilidad de `classification` (acuerdo con lo esperado) y de `contained_rate`. Objetivo de diseño: los resultados del paper no dependen de un único set de parámetros. [Hipótesis a verificar con el sweep]

---

*Próximos pasos: implementación en `engine/` (esta misma semana), corrida del catálogo en `scenarios.json`, y exportación de resultados reales para la sección Results del paper.*