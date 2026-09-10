# Jet MarIA — Plan de construcción bajo Spec-Driven Development

**Alcance de este plan:** el motor del Índice de Visibilidad en IA. Nada más.
**Vertical:** aviación ejecutiva (panel Argentina) · **Metodología:** SDD (mouredev/hello-sdd) · **Stack:** Python
**Ejecución:** Claude Code CLI sobre el servidor (fetch estático, scoring, salida) + Chromium remoto en notebook local (fetch renderizado, ver §9.3) · **Estado:** borrador para aprobación · rev. 4 · 28-08-2026

---

## 0. Qué construimos y por qué así

El proyecto ya produjo, a mano, el activo diferencial: una auditoría técnica de 7 cuentas (Fase 2) y una rúbrica de 6 dimensiones que las ordena de 26 a 73 puntos (Fase 5). El problema es que ese activo **no es reproducible**: cada cuenta nueva cuesta lo mismo que la primera, los criterios viven en la cabeza del analista, y la Fase 2 ya documentó cómo una limitación de herramienta produjo un falso negativo publicado ("0 de 7 con schema.org" cuando eran 4 de 7).

Este ciclo convierte esa rúbrica en un **motor determinista**: entra una URL, sale un JSON con puntaje, tier y evidencia citada por sub-criterio.

La razón de usar SDD y no prompting libre es exactamente el incidente de la Fase 2: en una consultoría que vende rigor técnico, **un dato mal medido destruye más valor que diez datos no medidos**. La spec es el contrato que hace que cada dimensión tenga un test que la respalde.

### Decisión de alcance (validada)

| Dimensión de la decisión | Elegido | Descartado |
|---|---|---|
| Artefacto | Motor del Índice de Visibilidad IA | Servidor MCP, pipeline completo, monorepo |
| Stack | Python 3.12 | Node/TS |
| Alcance | Panel completo de 14 cuentas AR (batch) | 1 sola URL |
| Metodología | Constitución + `AGENTS.md` + skill en el repo | Subagente de Cowork |

El batch de 14 mete concurrencia en el MVP. Se acepta porque el entregable comercial es la **tabla comparativa** (Grupo A vs Grupo B), no la ficha individual — sin batch no hay informe que abra una reunión. Se mitiga tratando el batch como un módulo delgado sobre el auditor de una URL (T18–T19), no como una arquitectura distinta.

---

## 0.b Contexto — hacia dónde va esto (no forma parte de este plan)

El modelo de agencia por niveles (herramientas internas → portal por cliente →
empleados digitales) y las dos advertencias para cuando se retome (el portal no va
primero; un Triage sobre webs de terceros necesita dos corridas antes de crear una
tarea) **se movieron a [`~/docs/producto.md`](../../docs/producto.md)** — son
contexto de negocio del ecosistema, no de este plan.

Lo único que importa acá: las decisiones técnicas del ciclo 1 no deben cerrar
puertas a que un consumidor externo (portal, agente) lea el JSON del motor. El
principio 8 (el JSON es la fuente) ya lo garantiza.

---

## 1. Constitución del proyecto

Diez principios cortos y verificables. **Ya extraídos a [`constitution.md`](../constitution.md)** en la raíz del repo — esa es la versión vigente (con los ajustes de la arquitectura de dos herramientas). La lista de abajo es la original de la rev. 4 y se conserva como registro histórico; ante cualquier diferencia, manda `constitution.md`.

1. **Evidencia o silencio.** Ningún puntaje se emite sin al menos un ítem de evidencia con URL, timestamp UTC y método de obtención (`static` | `rendered` | `robots` | `manual`).
2. **Nada del `<head>` sin renderizado real.** `title`, `meta description`, `canonical` y `JSON-LD` se leen del HTML crudo y del DOM renderizado por Playwright; si difieren, se reportan **ambos**. (Regla nacida del error de Fase 2.)
3. **El núcleo es determinista.** Ningún LLM participa del cálculo del puntaje. Dos ejecuciones sobre el mismo fixture dan byte a byte el mismo JSON.
4. **Lo no verificado se marca, no se infiere.** Un sub-criterio no comprobable se puntúa neutro (mitad del máximo) y se etiqueta `status: unverified`. El informe lista los `unverified` en su propia sección. El estado de la cuenta completa usa el enum de cinco valores de §3 (`medido` · `bloqueado` · `inaccesible` · `unverified` · `no_aplica`); `unverified` a nivel cuenta y a nivel sub-criterio significan lo mismo —hay dato parcial y no se completa por inferencia.
5. **Tests primero, y con fixture congelado.** Ninguna dimensión se implementa antes que su test, y ningún test de la suite base toca la red.
6. **Rastreo cortés y sin suplantación.** User-agent identificable (`MarIA-GEO-Audit/x.y (+https://maria.ar/bot)`), máximo 1 request concurrente por dominio, respeto del `Crawl-delay`, sin autenticación ni evasión de anti-bot. **No se suplanta el crawler de un tercero:** la política declarada para GPTBot, ClaudeBot, CCBot, PerplexityBot y Google-Extended se lee de `robots.txt` (dato público); la respuesta real del servidor se mide una sola vez, con el UA propio. Si un sitio rechaza a ese cliente identificado, eso **es** el hallazgo, no un obstáculo a esquivar.
7. **Solo datos públicos.** No se almacenan datos personales, no se envían formularios, no se guardan cookies de sesión de terceros.
8. **El JSON es la fuente.** Salida canónica versionada con `schema_version`. El Markdown y la tabla comparativa se derivan del JSON; nunca al revés.
9. **Stack cerrado.** Python 3.12, `httpx`, `selectolax`, `playwright`, `pydantic`, `typer`, `pytest`. Toda dependencia nueva se justifica en `plan.md` con la alternativa descartada.
10. **Un RF, un test que lo nombra.** El identificador del requisito aparece en el nombre del test (`test_rf07_...`). La validación final recorre la spec RF por RF.

---

## 2. Rúbrica operativa — de Fase 5 a criterios medibles

Esto es lo que convierte la rúbrica en algo especificable. Total 100 + 5 de bonus.

### D1 · Estructura Semántica — 25 pts

| Sub-criterio | Pts | Cómo se mide |
|---|---|---|
| JSON-LD presente y parseable | 5 | `script[type="application/ld+json"]` en DOM renderizado, `json.loads` sin error |
| Nodo `Organization` o `LocalBusiness` con `name` + `url` | 5 | Recorrido de `@graph` |
| `address` + `telephone` dentro del schema | 5 | Presencia de propiedades |
| `Service` / `Offer` / `Product` describiendo el chárter | 5 | Presencia de tipo |
| `sameAs` + `logo` + `aggregateRating` | 5 | 1,7 pts c/u |

**Tope por boilerplate:** si solo hay `WebPage`/`WebSite`/`BreadcrumbList` sin `Organization` con datos (patrón Yoast detectado en HeliAir, Sky, Sundown), la dimensión no supera 10/25.

### D2 · Accesibilidad para Crawlers de IA — 20 pts

| Sub-criterio | Pts |
|---|---|
| `robots.txt` accesible y sin `Disallow` para GPTBot, ClaudeBot, CCBot, PerplexityBot, Google-Extended | 8 |
| Acceso para clientes no-navegador | 7 |
| `sitemap.xml` presente y referenciado desde `robots.txt` | 3 |
| HTTPS sin degradación a HTTP en la cadena de redirects | 2 |

**Acceso para clientes no-navegador (7 pts) — se mide en dos partes:**

- **(a) Política declarada:** qué dice `robots.txt` para GPTBot, ClaudeBot, CCBot, PerplexityBot y Google-Extended, más las Content Signals presentes. Es dato público y no requiere suplantar a ningún crawler (principio 6). Una Content Signal **explícita** en `no` para `ai-train` o `ai-input` cuenta como bloqueo —es una reserva expresa de derechos (Art. 4 de la Directiva UE 2019/790, según el propio texto de Cloudflare). La **ausencia** de señal es neutra: la cláusula (c) del texto no concede ni restringe.
- **(b) Respuesta real:** código HTTP ante el user-agent propio `MarIA-GEO-Audit/x.y (+https://maria.ar/bot)`. Un 403, un 503 o un fallo de obtención puntúa 0 y eleva el hallazgo a severidad **crítica**: es acceso bloqueado, no ausencia de estructura.

**Límite para el informe:** un 200 con el UA propio no prueba que GPTBot también pase. El informe puede afirmar «rechaza clientes que no son navegadores» o «declara tal política», nunca «bloquea a GPTBot», salvo que la política declarada lo diga. Un `robots.txt` que solo trae el preámbulo de Content Signals sin una sola directiva —caso Modena Air Service, verificado 01-09-2026— **no declara política alguna** y esta regla no lo penaliza.

### D3 · Legibilidad sin JavaScript — 20 pts

| Sub-criterio | Pts |
|---|---|
| Ratio de texto útil (HTML crudo ÷ DOM renderizado) ≥ 0,80 | 8 (escalado lineal desde 0,40) |
| `title` + `meta description` en el HTML servido | 4 |
| `canonical` en el HTML servido | 2 |
| Navegación principal presente sin JS (≥ 5 enlaces internos) | 3 |
| Teléfono o email presentes en el HTML servido | 3 |

**Definición normativa del ratio de texto útil** — cambiar el momento de captura cambia el puntaje, así que esto es rúbrica, no implementación:

> `ratio = palabras(HTML servido) / palabras(DOM renderizado)`, donde ambos lados se extraen con `textContent` tras remover `script`, `style`, `noscript` y `template`, incluyendo el texto oculto por CSS en los dos, y el DOM se captura con `wait_until="networkidle"`, timeout 45 s.

Evidencia: sobre `southjets.com`, leer el DOM apenas termina la navegación dio ratio 0,999; leerlo tras `networkidle` dio 0,460 — misma página, misma hora, 6,8 puntos de D3 de diferencia.

Un ratio > 1,10 se informa como **anomalía**, no como puntaje. Entre 1,00 y 1,10 es ruido esperable (el cliente sin cookies recibe marcado que el navegador no muestra: banners de consentimiento); medido, 5 de 10 cuentas del panel entre 1,003 y 1,076. *El umbral 1,10 queda pendiente de confirmación.*

**D3 no discrimina, y se acepta.** El sub-criterio del ratio otorga 8/8 a la gran mayoría del panel (8 de 10 con ratio ≥ 0,92). Es el resultado, no un descuido: documenta que el sector no tiene un problema de renderizado y hace más creíbles los dos casos que sí fallan. Se conserva el peso de 20 pts. En el informe, D3 se presenta como **control negativo**, no como diferenciador; el orden del panel lo dan D1 (25 pts) y el sub-criterio de acceso de D2.

### D4 · Divulgación y Confianza — 15 pts

| Sub-criterio | Pts |
|---|---|
| Política de privacidad localizable (rastreo de enlaces del footer + rutas comunes) | 4 |
| Política de cookies completa (si anuncia tabla, la tabla existe) | 3 |
| CMP presente y coherente con la analítica cargada | 3 |
| Identidad legal publicada (razón social, CUIT/CIF, domicilio) | 3 |
| Coherencia dominio web ↔ dominio de email de contacto | 2 |

Los tres primeros dependen de rastreo multi-página; si el sitio no expone footer sin JS, van a `unverified` (principio 4) — es el hueco que Fase 5 dejó abierto en 3 de 7 cuentas y que este ciclo cierra.

### D5 · Captura de Leads sin Fricción — 15 pts

| Sub-criterio | Pts |
|---|---|
| Formulario de cotización alcanzable en ≤ 2 clics desde home | 4 |
| Campos requeridos ≤ 6 | 3 (escalado) |
| Canal directo: `tel:` o `wa.me` clickable | 3 |
| **Compromiso de respuesta publicado** (regex multiidioma sobre plazos) | 3 |
| Cotizador con precio en pantalla (no formulario disfrazado) | 2 |

El sub-criterio de compromiso publicado es el que conecta el Índice con el Paso Cero: hoy da 0/3 en las 9 cuentas argentinas y 3/3 en South American Jets. Es la fila que vende.

### D6 · Frontera WebMCP/MCP — 5 pts bonus

| Sub-criterio | Pts |
|---|---|
| `navigator.modelContext` con herramientas registradas | 3 |
| `llms.txt`, `/.well-known/` de agentes o feed estructurado de flota/rutas | 2 |

### Tiers

**Enmendado el 09-09-2026** — `docs/decisiones/2026-09-09-tiers-no-publicados.md`.

- **Tier absoluto por cuenta** (`0–29 Invisible` · `30–54 Parcial` · `55–74 Emergente` · `75–100 Líder GEO`, sobre el core): se calcula, vive en el JSON y el Markdown por cuenta, lo usan el histórico (RF-19, "caída de tier") y el funnel self-serve. **No se publica** en las páginas del panel sectorial.
- **Cuartil de ranking del panel** (Q1 cuarto superior … Q4 cuarto inferior, RF-22): relativo a las cuentas `medido`/`unverified` de la corrida. Va solo en la tabla comparativa Markdown, que es un **entregable interno** de prospección.
- **Páginas públicas del panel**: puntaje /100 + desglose por dimensión + evidencia + hallazgos. Ninguna etiqueta de tier ni de cuartil.

**Criterio de calibración (test de aceptación global):** es sobre el **puntaje**, no sobre la etiqueta — el scoring del motor reproduce el scoring manual del panel AR con desvío ≤ 8 pts (finalización §5 de `spec.md`), con los extremos del panel AR fijados en T0. La redacción rev. 4 (reproducir el orden de Fase 2, HeliAir Marbella y Modena en los extremos) queda superada: la calibración está acotada a Argentina (§9.5) y se evalúa por distancia de puntaje celda por celda, no por tier.

---

## 3. Requisitos funcionales (extracto en EARS)

**La spec completa vive en [`spec.md`](../spec.md)** (raíz del repo): RF-01…RF-21 de la Parte A y RR-01…RR-27 de la Parte B, en EARS, con sus criterios de finalización. Lo que sigue son los RF de anclaje de la Parte A, que se mantienen acá como contexto del plan; la versión vigente y completa es `spec.md`.

**Estados de una cuenta en una corrida** — enum del contrato JSON (RF-15):

| estado | cuándo | efecto |
|---|---|---|
| `medido` | se obtuvo crudo y render | puntaje real |
| `bloqueado` | 403/503 al cliente identificado | D2 acceso = 0 · hallazgo **crítico** |
| `inaccesible` | TLS inválido, bucle de redirects, DNS | D2 acceso = 0 · hallazgo **crítico**, con `motivo` |
| `unverified` | hay crudo pero no render | sub-criterios dependientes del DOM a mitad (principio 4) |
| `no_aplica` | la cuenta no tiene sitio web | sin puntaje ni tier; no entra en promedios |

`no_aplica` no lo determina el motor: es una anotación del panel (hoy, Baires Fly y Argentina Jets). En la tabla comparativa, una cuenta que no es `medido` nunca se promedia junto a las medidas sin decirlo en la misma línea.

**Adquisición**

- **RF-01** — CUANDO se solicita auditar una URL, EL SISTEMA obtiene el recurso dos veces: HTML crudo vía HTTP y DOM renderizado vía navegador headless, y persiste ambos con su timestamp UTC.
- **RF-02** — SI la obtención renderizada falla o excede 30 s, ENTONCES EL SISTEMA registra el fallo como evidencia, continúa con el HTML crudo y marca como `unverified` todo sub-criterio que dependa del render.
- **RF-03** — SI el servidor responde 403 o 503 al user-agent propio identificado, ENTONCES EL SISTEMA marca la cuenta `bloqueado`, puntúa 0 en el sub-criterio de acceso de D2 y emite un hallazgo de severidad crítica. SI el recurso no se puede obtener (certificado TLS inválido, bucle de redirecciones, fallo de DNS), la cuenta se marca `inaccesible` con `motivo` y el efecto es el mismo. EL SISTEMA no envía un user-agent de crawler de terceros para provocar esta respuesta (principio 6).
- **RF-04** — EL SISTEMA identifica siempre su user-agent y nunca ejecuta más de una petición concurrente contra el mismo dominio.
- **RF-05** — MIENTRAS exista una respuesta cacheada de menos de 24 h para una URL, EL SISTEMA la reutiliza en lugar de volver a pedirla, salvo `--no-cache` explícito.

**Evaluación**

- **RF-06 a RF-11** — Una por dimensión: CUANDO se evalúa la dimensión Dn sobre un recurso obtenido, EL SISTEMA emite un `DimensionResult` con puntaje, máximo, lista de sub-criterios y evidencia por cada uno.
- **RF-12** — SI un sub-criterio no puede comprobarse con los datos obtenidos, ENTONCES EL SISTEMA le asigna la mitad de su puntaje máximo y estado `unverified`. SI la causa es la ausencia de DOM renderizado y afecta a todos los sub-criterios dependientes del render, la cuenta entera se marca `unverified`.
- **RF-13** — SI el único schema presente es boilerplate sin `Organization` con datos, ENTONCES EL SISTEMA limita D1 a 10 puntos.
- **RF-14** — EL SISTEMA calcula el total como suma ponderada de D1–D5 más el bonus D6, acotado a 100, y le asigna su tier.

**Salida**

- **RF-15** — CUANDO termina una auditoría, EL SISTEMA emite un JSON con `schema_version`, identidad de la cuenta, timestamp, `estado` (`medido` | `bloqueado` | `inaccesible` | `unverified` | `no_aplica`), puntaje total, tier, las seis dimensiones con su evidencia y la lista de hallazgos ordenada por severidad.
- **RF-16** — CUANDO se solicita el informe de una cuenta, EL SISTEMA deriva un Markdown del JSON, sin recalcular nada.
- **RF-17** — CUANDO se audita un panel, EL SISTEMA emite una tabla comparativa Markdown ordenada por puntaje, con columna de grupo (A/B/C) y de tipo de flujo (corporativo-industrial / turismo VIP / sanitario).
- **RF-18** — EL SISTEMA reporta en sección aparte todos los sub-criterios `unverified` de la corrida.

**Histórico y aporte humano**

- **RF-19** — CUANDO termina una auditoría, EL SISTEMA la archiva bajo su cuenta y fecha, y MIENTRAS exista una corrida anterior de esa cuenta, calcula el delta de puntaje total y por dimensión respecto de la última.
- **RF-20** — EL SISTEMA permite anexar a una cuenta hallazgos redactados por el analista, con `origin: analyst`; aparecen en el informe junto a los automáticos y **no** modifican el puntaje.
- **RF-21** — MIENTRAS exista para una cuenta un resultado de la medición de tiempo de respuesta (Paso Cero), EL SISTEMA lo muestra en su ficha junto al Índice, marcado como `origin: analyst`, sin incorporarlo al puntaje. *El compromiso publicado (D5) y el tiempo realmente medido son datos distintos: el primero se audita, el segundo se mide enviando consultas, cosa que el principio 7 prohíbe al motor. La ficha los presenta juntos porque juntos son el argumento.*

**Fuera de alcance:** ficha o portal del operador, agentes autónomos, generación de texto outbound, envío de consultas a formularios, medición de tiempo de respuesta (eso es el Paso Cero, proceso humano), servidor MCP, cuentas de España.

---

## 4. Plan técnico

### Estructura del repositorio

```
jet-maria-motor/
├── constitution.md              # los 10 principios (extraído ✓)
├── AGENTS.md                    # contexto permanente del agente (extraído ✓)
├── spec.md                      # RF-01…RF-21 + RR-01…RR-27 en EARS (extraído ✓)
├── docs/plan.md                 # este documento
├── docs/decisiones/             # decisiones de rúbrica congeladas
├── .claude/skills/auditoria-geo/SKILL.md    # metodología propia, versionada (extraído ✓)
├── panels/panel-ar.yaml         # las 14 cuentas del Paso Cero / panel AR
├── tools/remote-chromium-server/            # Chromium remoto (notebook), ver §9.3
├── src/maria/
│   ├── models.py                # pydantic: Account, AuditRun, DimensionResult, Evidence, Finding
│   ├── store/  runs.py          # archivo de corridas por cuenta/fecha + cálculo de delta
│   ├── fetch/  static.py rendered.py cache.py robots.py
│   ├── probes/ d1_schema.py … d6_frontier.py
│   ├── scoring/ weights.py tiers.py
│   ├── report/  json_out.py markdown.py panel_table.py
│   └── cli.py                   # typer
├── tests/
│   ├── fixtures/                # HTML congelado de las 10 cuentas capturables + 2 sintéticos de fallo, con fecha
│   ├── golden/                  # JSON esperado por cuenta
│   └── test_rf*.py
└── out/runs/<cuenta>/<timestamp>.json        # el archivo de corridas (versionado en git)
```

### Decisiones justificadas

| Decisión | Elegido | Alternativa descartada | Por qué |
|---|---|---|---|
| Parser HTML | `selectolax` | `BeautifulSoup` | 10–20× más rápido en batch y suficiente para selectores CSS; BS4 solo aportaría tolerancia a HTML roto, que aquí es un dato a reportar, no a corregir |
| Renderizado | `playwright` (chromium), **remoto vía `connect()` — ver §9.3** | `requests-html`, servicio SaaS | Es el único camino que reproduce lo que vio el validador de Google en Fase 2; el SaaS mete costo por cuenta y opacidad en la evidencia. El hosting no puede correr Chromium local (límite de threads del jail), así que el browser corre en una notebook y el servidor se conecta por WebSocket — la decisión de fondo (Playwright vs SaaS) no cambia, solo dónde vive el proceso |
| Validación de datos | `pydantic` v2 | dataclasses | El JSON es el contrato público del Índice; necesita validación en el borde y `schema_version` |
| **Persistencia** | **Ficheros JSON en `out/runs/<cuenta>/<timestamp>.json`** | **SQLite** | *Corrección respecto de la rev. 2, donde se había elegido SQLite anticipando el portal y los agentes.* Con el alcance en el motor, una base no aporta nada: 12 cuentas con sitio y unas pocas corridas se recorren leyendo el directorio, y los ficheros son diffeables y auditables en git. **La migración posterior es barata precisamente por el principio 8**: el JSON es el contrato y los modelos pydantic son la fuente, así que un store SQLite sería una capa nueva que importa los mismos ficheros, no una reescritura del modelo ni de los tests |
| Concurrencia | `asyncio` con semáforo por dominio | multiproceso | El trabajo es I/O-bound y el principio 6 exige serializar por dominio |

### Estrategia de tests

- **Base (sin red):** cada probe contra fixtures congelados de las 10 cuentas capturables (ver nota de T7) más 2 fixtures sintéticos para los modos de fallo (`inaccesible-tls`, `inaccesible-bucle-redirects`). Un fixture real = HTML crudo + DOM renderizado + `robots.txt`, capturados una vez; el HTML no se versiona, solo el `MANIFEST.json` de la corrida (ver `jet-maria/README.md`).
- **Golden:** JSON esperado por cuenta; el diff del golden es la revisión de cualquier cambio de rúbrica. **El golden se siembra con el scoring manual del panel AR** (14 cuentas, registrado sub-criterio por sub-criterio en la planilla de T0) — ver T0.
- **Contrato:** validación del JSON de salida contra su esquema en cada corrida.
- **Calibración:** el test de aceptación de §2 (pendiente de fijar extremos concretos una vez cerrado T0).
- **Integración (`@pytest.mark.network`, fuera de CI):** una corrida real contra 2 dominios de control.

---

## 5. Desglose de tareas

Cada una < 30 min, ordenadas por dependencia, con criterio de cierre verificable.

**T0 · Prerrequisito, fuera del servidor y antes de la sesión CLI.** El scoring manual del panel AR ya está en curso. Registrarlo **sub-criterio por sub-criterio** con la rúbrica de §2 congelada —no solo el puntaje final— convierte ese trabajo en el conjunto golden del motor: las 14 cuentas del panel AR puntuadas a mano contra las que validar cada probe. *Formato: planilla "T0_Registro_Rubrica_IndiceVisibilidad" en Drive, junto a `PasoCero_Argentina_medicion_jets` (decidido, ver §9.2).* *Hecho cuando:* la hoja "Registro" tiene las 26 filas de sub-criterio × 14 columnas de cuenta completas, con el puntaje asignado, y la hoja "Evidencia" tiene la URL o cita de cada celda no trivial. Si el scoring manual usa una rúbrica distinta de la de §2, cuando el motor discrepe no vamos a poder saber si falló el motor o la planilla — por eso la rúbrica se congela antes, no después (hoja "Leyenda" de la misma planilla).

| # | Tarea | RF | Hecho cuando |
|---|---|---|---|
| T1 | Scaffolding, `pyproject`, pytest, CI local | — | `pytest` corre en verde con 0 tests y `maria --help` responde |
| T2 | Modelos pydantic + `schema_version` | RF-15 | Un `AuditRun` de ejemplo serializa y valida contra su esquema |
| T3 | Archivo de corridas por cuenta/fecha + cálculo de delta | RF-19 | Dos corridas de la misma cuenta se archivan, se recuperan ordenadas y el delta por dimensión es correcto |
| T4 | Fetch estático con caché y UA propio | RF-01, RF-04, RF-05 | Test: segunda llamada no toca la red y devuelve el mismo cuerpo |
| T5 | Fetch renderizado vía Playwright remoto (`connect()` a la notebook, §9.3) + timeout | RF-01, RF-02 | Test con timeout forzado: devuelve resultado degradado, no excepción. Test adicional: si no hay endpoint remoto disponible, degrada igual (no rompe la corrida) |
| T6 | Parser de `robots.txt` y detección de challenge | RF-03 | Test con fixture de Modena: emite hallazgo crítico |
| T7 | Captura de fixtures del panel | — | `tests/fixtures/<fecha>/` con 10 carpetas de cuentas capturadas + 2 fixtures sintéticos de modo de fallo + `MANIFEST.json` que lista las 12 cuentas con sitio (ver nota bajo la tabla) |
| T8 | Probe D1 · schema.org + tope de boilerplate | RF-06, RF-13 | Gestair > HeliAir > World Aviation en el test; HeliAir ≤ 10 |
| T9 | Probe D2 · accesibilidad crawlers IA | RF-07 | Modena puntúa 0 en acceso; el resto ≥ 8 en robots |
| T10 | Probe D3 · legibilidad sin JS | RF-08 | Ratio calculado y estable sobre los 10 fixtures capturados |
| T11 | Probe D4 · divulgación (con rastreo de footer) | RF-09, RF-12 | Sundown, American Jet y Modena → `unverified` documentado, no 0 |
| T12 | Probe D5 · fricción de leads + compromiso publicado | RF-10 | South American Jets 3/3 y las 9 argentinas 0/3 en el sub-criterio |
| T13 | Probe D6 · frontera WebMCP | RF-11 | 0 en las 10; 3/5 sobre el fixture de la demo propia |
| T14 | Scoring, ponderación y tiers | RF-14 | Test de calibración de §2 en verde (extremos fijados post-T0) |
| T15 | Anexo de hallazgos manuales del analista | RF-20 | Un hallazgo cargado a mano aparece en el informe con `origin: analyst` y no altera el puntaje |
| T16 | Salida JSON canónica | RF-15, RF-18 | Golden de una cuenta byte a byte reproducible |
| T17 | Informe Markdown por cuenta | RF-16 | Ficha derivada del JSON sin recálculo (test de mutación) |
| T18 | Batch de panel con semáforo por dominio | RF-04, RF-17 | 12 cuentas con sitio en una corrida (los 2 `no_aplica` no se piden), nunca 2 requests simultáneos al mismo host |
| T19 | Tabla comparativa A/B/C + tipo de flujo | RF-17 | Tabla ordenada, con las 5 extranjeras/referencia por encima de las locales con sitio (7; los 2 `no_aplica` de Grupo A quedan fuera de la comparación, no en 0) o explicación del porqué no — **regla de inclusión de `bloqueado`/`inaccesible` en el ranking pendiente de fijar** (ver nota T7) |
| T20 | Validación RF por RF y `README` de uso | todos | Recorrido completo de la spec con test y resultado por cada RF |

**Nota sobre T7 (corregida contra la corrida real del 29-08-2026).** El panel tiene 14 cuentas; 12 con sitio y 2 `no_aplica` (Baires Fly, sin sitio propio activo; Argentina Jets, sin web cargada en la hoja Objetivos — dato faltante en origen, no un hallazgo). De las 12 con sitio, **10 producen artefactos capturables**. Las otras dos no se pueden capturar y son los dos hallazgos críticos de D2:

- `tenilaviacion.com.ar` — bucle de redirecciones para clientes no-navegador;
- `avionesprivadossa.com.ar` — certificado TLS con hostname mismatch.

*Criterio de cierre para esas dos:* la captura escribe igual un artefacto de fallo (`meta.json` con `estado`, `motivo`, `status`, timestamp — sin `raw.html` ni `rendered.html`) y el `MANIFEST.json` lo registra. Además, para que el test de D2 (T9) corra sin red (principio 5), el repo lleva **un fixture sintético por modo de fallo**: `tests/fixtures/_sintetico/inaccesible-tls/` y `tests/fixtures/_sintetico/inaccesible-bucle-redirects/`, cada uno un `meta.json` de ~5 líneas con la forma de nuestro propio registro de error, sin contenido de terceros. El artefacto de corrida real no alcanza solo porque no se versiona (regla siguiente); el sintético es honesto porque no hay nada capturado que falsificar, solo la forma del error propio.

*Sobre "el HTML no va a git":* de cada corrida se versiona **solo** el `MANIFEST.json`. La consecuencia —un clon nuevo no puede correr la suite base sin recapturar— y el comando que regenera los fixtures están documentados en `jet-maria/README.md`.

---

## 6. El agente y la metodología propia

Tres archivos versionados en el repo, que son el activo de consultoría reutilizable.
**Los tres están creados** (2026-09-09); esta sección describe qué debe contener cada
uno y sigue siendo la referencia de su alcance.

**[`constitution.md`](../constitution.md)** — los 10 principios de §1.

**`AGENTS.md`** — contexto permanente: qué es MarIA, quién es el cliente ideal (C-levels, asistentes ejecutivos, family offices, directores de operaciones), la clasificación obligatoria por flujo operativo, la regla de argumentos/contraargumentos, y las tres lecciones ya pagadas del proyecto: (a) no confiar en fetch de solo-HTML para el `<head>`, (b) bloqueo de crawler ≠ ausencia de schema, (c) "cotizador" que no cotiza es un hallazgo de fricción, no de nomenclatura.

**[`.claude/skills/auditoria-geo/SKILL.md`](../.claude/skills/auditoria-geo/SKILL.md)** — el procedimiento de auditoría de una cuenta: orden de comprobaciones, herramientas por tipo de dato, formato de la ficha, y el checklist de verificación cruzada. Es lo que hace que la auditoría número 40 salga igual que la número 1, la haga quien la haga.

Estos tres archivos son el entregable más duradero del ciclo: el código puede reescribirse, el criterio versionado no.

---

## 7. Secuencia de la sesión en el servidor

Los ocho prompts del flujo de mouredev, ya adaptados. Uno por vez, parando en cada aprobación.

1. **Constitución** — "Leé `PLAN-JET-MARIA-SDD.md` §1 y escribí `constitution.md`. Máx. 15 líneas. Esperá mi aprobación."
2. **Spec (entrevista)** — "NO escribas código. Preguntame de a una (máx. 6) sobre casos límite, errores y alcance del motor del Índice; después generá `spec.md` con los RF en EARS, fuera de alcance y criterios de finalización. Solo el QUÉ y el POR QUÉ."
3. **Clarificación** — "Revisá la spec como QA profesional: ambigüedades, contradicciones, casos límite ausentes, conflictos con la constitución. Solo detectá, no resuelvas."
4. **Plan** — "Sin código: generá `plan.md` con módulos, modelo de datos, decisiones justificadas con su alternativa descartada, y estrategia de tests. Indicá qué RF cubre cada parte."
5. **Tareas** — "Dividí el plan en tareas de <30 min ordenadas por dependencia, cada una con sus RF y una línea 'Hecho cuando:' verificable, con checkboxes."
6. **Implementación** — "Implementá SOLO la tarea Tn. Tests primero. Ejecutá la suite, mostrame el resultado, marcá Tn como hecha y PARÁ." (×20)
7. **Validación** — "Recorré la spec RF por RF: qué test cubre cada uno y su resultado. Veredicto: ¿spec cumplida?"
8. **Cambio** — "Nuevo requisito: <X>. NO toques código: actualizá primero la spec y mostrame el diff."

**Pasos 1 a 5 antes de escribir una línea de código.** Es el punto entero del método y es donde se abandona.

### Requisitos del entorno del servidor

Antes de arrancar hay que confirmar, en la máquina, seis cosas. Estado real verificado el 28-08-2026 (ver §9.3 para el detalle):

| # | Requisito | Comprobación | Estado |
|---|---|---|---|
| 1 | Python ≥ 3.12 | `python3 --version` | ✅ Vía `/opt/alt/python312` (CloudLinux alt-python), sin sudo. El `python3` del sistema es 3.6.8 |
| 2 | git y repo remoto creado | `git --version`, origin configurado | ✅ git 2.48.2. Repo: subcarpeta `jet-maria/` en `mariarepo` existente, sin remoto por ahora |
| 3 | Salida a internet sin proxy corporativo | `curl -I https://americanjet.com.ar` | ✅ |
| 4 | Chromium de Playwright + libs de sistema | `playwright install --with-deps chromium` | ⚠️ Libs presentes, Chromium instala, pero **no arranca**: el hosting (CloudLinux LVE) limita threads y Chrome falla con `pthread_create: Resource temporarily unavailable`. Resuelto moviendo el render a una notebook local — ver §9.3 |
| 5 | RAM ≥ 2 GB libres | chromium headless por cuenta; con semáforo de 1, alcanza | ✅ 11GB disponibles (no aplica del todo: Chromium no corre acá) |
| 6 | Claude Code CLI instalado y autenticado | `claude --version` | ✅ 2.1.220 |

**El bloqueante de Chromium ya no es hipotético, es confirmado, y su solución está resuelta en la arquitectura** (Playwright `connect()` remoto — `tools/remote-chromium-server/`, ver §9.3), no pendiente.

---

## 8. Análisis crítico

### A favor

1. **La rúbrica ya existe y está validada contra 7 casos reales.** No estamos especificando en el aire: hay un rango conocido (26–73) que sirve de referencia. La mayoría de los proyectos SDD fracasan porque la spec se escribe sobre un dominio que nadie midió; acá el dominio está medido (aunque el test de aceptación formal se recalibra sobre el panel AR, ver §2).
2. **El error de la Fase 2 es el argumento comercial más fuerte del proyecto, y este motor lo institucionaliza.** Un competidor que audita con fetch simple publica los mismos falsos negativos. El doble fetch con reporte de la discrepancia es la diferencia entre un informe defendible frente al CTO del prospecto y uno que se cae en la primera objeción.
3. **El alcance está bien podado.** Fuera quedan las cuatro cosas que hunden un MVP de este tipo: generación por LLM, interfaz web, agentes y la medición de tiempos de respuesta. Lo que queda es I/O y parsing — todo testeable con fixtures.
4. **El batch de 14 cuentas produce el entregable comercial, no un demo.** Al terminar T19 hay una tabla que se puede llevar a una reunión.

### En contra

1. **El motor determinista mide lo verificable, no lo importante.** Los hallazgos que realmente venden del Paso Cero — "llama cotizador a un formulario que no cotiza", "promete despegar en 2 horas y no dice en cuánto contesta", "dos identidades de dominio en la misma página" — son juicios semánticos. El sub-criterio D5 de compromiso publicado captura uno; el resto se le escapa a cualquier regex. **Riesgo real de construir una herramienta rigurosa que produzca informes menos persuasivos que los escritos a mano.** Mitigado con RF-20 / T15: el analista anexa sus hallazgos y el informe los renderiza junto a los automáticos.
2. **La rúbrica de 100 puntos da una precisión que el método no tiene.** Decir "Modena 26, HeliAir 73" sugiere una escala calibrada; lo que hay son 22 sub-criterios con pesos elegidos por criterio experto. Un prospecto técnico puede preguntar por qué schema.org vale 25 y no 15, y no hay respuesta empírica. Mitigación: publicar la rúbrica completa como parte del entregable (la transparencia convierte la objeción en credibilidad) y presentar el **tier**, no el número, como conclusión.
3. ~~**Sin los niveles siguientes, 13 cuentas no justifican software.**~~ **Resuelto en rev. 4.** La objeción exigía saber si el panel se audita más de dos o tres veces. La respuesta es sí y ya está ocurriendo: a la primera auditoría manual de las 7 cuentas ES se suman ahora la medición de tiempo de respuesta AR y el scoring del Índice sobre las 14 cuentas AR. Son cuentas puntuadas a mano y una segunda ronda ya prevista para diciembre (Paso Cero, §Análisis crítico de la lista de sondeo). El motor entra a reemplazar un trabajo que se está pagando **hoy**, no uno hipotético. Queda el riesgo residual de siempre: que el motor termine y el panel deje de auditarse por razones comerciales, no técnicas.
4. **"Un gestor de tareas en un día" y "un motor de auditoría en 20 tareas" no son el mismo tipo de problema.** Un CRUD interno con un único usuario que sabe lo que quiere se construye rápido porque no tiene entorno hostil: no hay anti-bots, ni HTML roto, ni discrepancia entre DOM crudo y renderizado. Acá la mitad del trabajo es tolerar lo que el mundo devuelve. Conviene no importar del modelo de referencia la expectativa de velocidad.
5. ~~**Playwright es la dependencia frágil.**~~ **Confirmado y resuelto en esta revisión.** Chromium no corre en el hosting (§9.3): no es un riesgo teórico, ya pasó. La mitigación (Chromium remoto en notebook local vía `connect()`) introduce una dependencia nueva y real: sin la notebook prendida y el túnel activo, D1/D3 completos no se pueden auditar (degradan a `unverified` por RF-02, lo cual es correcto, pero limita cuándo se puede correr el panel).
6. **SDD tiene un costo fijo alto.** Los pasos 1–5 son fácilmente una sesión entera antes de la primera línea de código. Sobre 20 tareas se amortiza; sobre un script de 300 líneas, no.

### Síntesis

La conclusión más sólida no es "hay que automatizar la auditoría". Es que **el proyecto necesita convertir su criterio de auditoría en un artefacto que no dependa de quien lo ejecuta**, porque el activo que se vende es precisamente rigor reproducible y el incidente de Fase 2 demostró que hoy no lo hay. El código es el vehículo; la constitución, la spec y la skill de auditoría son el producto real del ciclo.

El criterio de decisión que quedaba abierto —¿el panel se audita más de dos o tres veces?— está respondido por los hechos: el scoring manual del Índice sobre las 14 cuentas AR y la medición de tiempo de respuesta están en curso ahora mismo. El motor sustituye trabajo que se está pagando, no trabajo imaginado.

Eso reordena la prioridad inmediata, y es el aporte principal de esta revisión: **lo urgente no es empezar a codear, es que el scoring manual en curso se registre sub-criterio por sub-criterio con la rúbrica de §2 congelada** (T0, ya con planilla creada — ver §9.2). Ese trabajo se está haciendo igual; si queda registrado con la granularidad correcta, el motor nace con 14 casos golden y la calibración deja de ser una apuesta.

| Resultado | Probabilidad estimada |
|---|---|
| Completar las 20 tareas con la suite en verde | ~75 % |
| Que el motor reproduzca el scoring manual con desvío ≤ 8 pts | ~65 % sin T0 · **~85 % con T0 bien hecho** — es el mayor retorno por unidad de esfuerzo de todo el plan |
| Que la tabla del panel AR sea presentable a un prospecto sin edición manual | ~45 % — el contraargumento 1 pesa acá |
| Que el motor se siga usando 3 meses después de terminado | ~70 % |

---

## 9. Puntos abiertos antes de aprobar

1. ~~Frecuencia de uso.~~ **Respondido:** medición de tiempo de respuesta AR + scoring del Índice sobre el panel AR, en curso. El ciclo se hace.
2. ~~T0 — congelar la rúbrica antes de seguir puntuando a mano.~~ **Respondido (28-08-2026):** planilla nueva junto a `PasoCero_Argentina_medicion_jets` en Drive — **"T0_Registro_Rubrica_IndiceVisibilidad"**, creada, misma carpeta. Cuatro hojas: Registro (matriz sub-criterio × cuenta), Evidencia (misma grilla, URL/cita), Objetivos (copia de la lista de cuentas), Leyenda (rúbrica de §2 congelada). Panel: 14 cuentas (9 Grupo A + 4 Grupo B + American Jet, Grupo C) — la misma lista que usa Paso Cero, hoja "Objetivos".
3. ~~El entorno del servidor.~~ **Respondido (28-08-2026):** las seis comprobaciones de §7 están hechas. Único punto real: Chromium **no arranca** en este hosting (límite de threads del jail CloudLinux LVE — confirmado con Playwright, con el binario de Chrome directo y con flags de `--single-process`, siempre el mismo `pthread_create: Resource temporarily unavailable`). Resuelto arquitectónicamente: el render corre en una notebook local (`playwright.chromium.launchServer()`) y el servidor se conecta por WebSocket a través de un túnel SSH reverso. Herramienta y guía en `jet-maria/tools/remote-chromium-server/`. Pendiente operativo (no de diseño): activar el túnel antes de cada corrida que necesite D1/D3 completos.
4. ~~Repositorio.~~ **Respondido:** subcarpeta `jet-maria/` dentro de `mariarepo` (repo existente del theme de maria.ar, pero repo Git independiente del tema en sí — no toca el sitio en producción). Sin remoto por ahora, solo local en el servidor.
5. ~~España.~~ **Respondido (28-08-2026):** NO se incluyen las cuentas españolas de Fase 2 en el set golden. La calibración queda **acotada a Argentina**: el panel de 14 cuentas de "Objetivos" (Paso Cero) es el único universo de calibración. Efecto colateral a resolver en el paso "Plan" de la sesión SDD: el criterio de aceptación de §2 citaba a "HeliAir Marbella" (España, ahora fuera de alcance) como uno de los extremos — hay que reemplazarlo por los extremos reales del panel AR, que solo se conocen al cerrar T0. Modena Air Service (Fase 2 Y panel AR) sigue siendo válido como punto de referencia porque está en ambos conjuntos.
