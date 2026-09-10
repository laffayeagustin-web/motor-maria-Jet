# spec.md — Requisitos funcionales del motor

> El QUÉ y el POR QUÉ, en EARS. El CÓMO está en [`docs/plan.md`](docs/plan.md) §4.
> Los principios que ninguna implementación puede violar están en
> [`constitution.md`](constitution.md). Las decisiones de rúbrica congeladas están
> en [`docs/decisiones/`](docs/decisiones/).
>
> **Regla (constitución, principio 10):** cada RF/RR tiene un test que lo nombra
> (`test_rf07_…`, `test_rr19_…`). `tests/test_rf_todos.py` falla si se agrega un
> requisito acá sin su test. Para un requisito nuevo: se actualiza esta spec y se
> muestra el diff **antes** de tocar código (flujo SDD, `docs/plan.md` §7 paso 8).

Dos índices, dos bloques de requisitos. No comparten rúbrica, tiers ni panel.

---

## Parte A — Índice de Visibilidad GEO Técnico (`maria`, `maria-render`)

CLIs: `maria` (servidor: fetch estático, `robots.txt`, scoring determinista, salida)
y `maria-render` (notebook: render del DOM con Chromium → *render bundle*). Contrato
entre ambos: `render_schema_version`.

### Estados de una cuenta en una corrida (enum del contrato JSON, RF-15)

| estado | cuándo | efecto |
|---|---|---|
| `medido` | se obtuvo crudo y render | puntaje real |
| `bloqueado` | 403/503 al cliente identificado | D2 acceso = 0 · hallazgo **crítico** |
| `inaccesible` | TLS inválido, bucle de redirects, DNS | D2 acceso = 0 · hallazgo **crítico**, con `motivo` |
| `unverified` | hay crudo pero no render | sub-criterios dependientes del DOM a mitad (principio 4) |
| `no_aplica` | la cuenta no tiene sitio web | sin puntaje ni tier; no entra en promedios |

`no_aplica` no lo determina el motor: es una anotación del panel.

### Adquisición

- **RF-01** — CUANDO se solicita auditar una URL, EL SISTEMA obtiene el recurso dos
  veces: HTML crudo vía HTTP y DOM renderizado vía navegador headless, y persiste
  ambos con su timestamp UTC.
- **RF-02** — SI la obtención renderizada falla o excede 30 s, ENTONCES EL SISTEMA
  registra el fallo como evidencia, continúa con el HTML crudo y marca `unverified`
  todo sub-criterio que dependa del render. SI no hay endpoint de render disponible,
  la corrida degrada igual, no se rompe.
- **RF-03** — SI el servidor responde 403 o 503 al user-agent propio identificado,
  ENTONCES la cuenta se marca `bloqueado`, D2-acceso puntúa 0 y se emite hallazgo
  crítico. SI el recurso no se puede obtener (TLS inválido, bucle de redirects, DNS),
  la cuenta se marca `inaccesible` con `motivo` y el efecto es el mismo. EL SISTEMA
  **no** envía un user-agent de crawler de terceros para provocar esta respuesta
  (constitución, principio 6).
- **RF-04** — EL SISTEMA identifica siempre su user-agent
  (`MarIA-GEO-Audit/x.y (+https://maria.ar/bot)`) y nunca ejecuta más de una
  petición concurrente contra el mismo dominio.
- **RF-05** — MIENTRAS exista una respuesta cacheada de menos de 24 h para una URL,
  EL SISTEMA la reutiliza, salvo `--no-cache` explícito.

### Evaluación

- **RF-06 a RF-11** — Una por dimensión (D1 Estructura Semántica · D2 Accesibilidad
  para Crawlers de IA · D3 Legibilidad sin JS · D4 Divulgación y Confianza · D5
  Captura de Leads · D6 Frontera WebMCP/MCP): CUANDO se evalúa Dn sobre un recurso
  obtenido, EL SISTEMA emite un `DimensionResult` con puntaje, máximo, lista de
  sub-criterios y evidencia (URL + timestamp UTC + método) por cada uno. Pesos y
  sub-criterios: `docs/plan.md` §2 con las enmiendas de
  `docs/decisiones/2026-09-01-rubrica.md`.
- **RF-12** — SI un sub-criterio no puede comprobarse con los datos obtenidos,
  ENTONCES se le asigna la mitad de su puntaje máximo y estado `unverified`. SI la
  causa es la ausencia de DOM renderizado y afecta a todos los sub-criterios
  dependientes del render, la cuenta entera se marca `unverified`.
- **RF-13** — SI el único schema presente es boilerplate (`WebPage`/`WebSite`/
  `BreadcrumbList`) sin `Organization` con datos, ENTONCES D1 se limita a 10 puntos.
- **RF-14** — EL SISTEMA calcula el total como suma ponderada de D1–D5 (core = 95)
  más el bonus D6 (5), acotado a 100, y le asigna su **tier absoluto**
  (`0–29 Invisible · 30–54 Parcial · 55–74 Emergente · 75–100 Líder GEO`). Ese tier
  vive en el JSON y el Markdown por cuenta y lo consumen el histórico (RF-19) y el
  funnel self-serve; **no se publica** en las páginas del panel sectorial
  (`docs/decisiones/2026-09-09-tiers-no-publicados.md`).

### Salida

- **RF-15** — CUANDO termina una auditoría, EL SISTEMA emite un JSON con
  `schema_version`, identidad de la cuenta, timestamp, `estado`, puntaje total,
  tier, las seis dimensiones con su evidencia y la lista de hallazgos ordenada por
  severidad.
- **RF-16** — CUANDO se solicita el informe de una cuenta, EL SISTEMA deriva un
  Markdown del JSON, **sin recalcular nada** (constitución, principio 8).
- **RF-17** — CUANDO se audita un panel, EL SISTEMA emite una tabla comparativa
  Markdown ordenada por puntaje, con columna de grupo (A/B/C), de flujo operativo
  (corporativo-industrial / turismo VIP / sanitario) y de **cuartil de ranking**
  (RF-22). Es un entregable **interno** de prospección, no una página pública. Una
  cuenta que no es `medido` nunca se promedia junto a las medidas sin decirlo en la
  misma línea, y no recibe cuartil.
- **RF-18** — EL SISTEMA reporta en sección aparte todos los sub-criterios
  `unverified` de la corrida.
- **RF-22** — CUANDO emite la tabla comparativa de un panel, EL SISTEMA clasifica en
  cuartiles a las cuentas `medido` y `unverified`: las ordena por puntaje descendente
  con desempate por `codigo`, y la cuenta de posición *r* (1-indexado) sobre *n* cae
  en el cuartil `floor((r-1)·4/n) + 1` — Q1 (cuarto superior) … Q4 (cuarto inferior).
  El cuartil es **relativo al panel de esa corrida**: no entra en el JSON por cuenta
  ni en el histórico, usa etiquetas neutras (`Q1`…`Q4`) y nunca los nombres de tier.
  `bloqueado` / `inaccesible` / `no_aplica` quedan fuera del cálculo. *(Paneles chicos:
  `docs/decisiones/2026-09-09-tiers-no-publicados.md` §Lo que queda abierto.)*

### Histórico y aporte humano

- **RF-19** — CUANDO termina una auditoría, EL SISTEMA la archiva bajo su cuenta y
  fecha, y MIENTRAS exista una corrida anterior de esa cuenta, calcula el delta de
  puntaje total y por dimensión respecto de la última.
- **RF-20** — EL SISTEMA permite anexar a una cuenta hallazgos redactados por el
  analista, con `origin: analyst`; aparecen en el informe junto a los automáticos y
  **no** modifican el puntaje.
- **RF-21** — MIENTRAS exista para una cuenta un resultado de la medición de tiempo
  de respuesta (Paso Cero, proceso humano), EL SISTEMA lo muestra en su ficha junto
  al Índice, marcado `origin: analyst`, sin incorporarlo al puntaje. *(El compromiso
  publicado de D5 y el tiempo realmente medido son datos distintos: el primero se
  audita, el segundo se mide enviando consultas, cosa que el principio 7 prohíbe al
  motor. La ficha los presenta juntos porque juntos son el argumento.)*

### Fuera de alcance (Parte A)

Ficha o portal del operador, agentes autónomos, generación de texto outbound, envío
de consultas a formularios, medición del tiempo de respuesta, servidor MCP, cuentas
de España en el set golden de calibración.

---

## Parte B — Índice de Visibilidad en Respuestas (`maria-respuestas`)

Superficie: **API de Gemini con la herramienta `google_search` activada**. NO AI
Overviews, NO ChatGPT/Perplexity/Copilot (`docs/decisiones/2026-09-06-rubrica-respuestas.md`
§1). Rúbrica: R1 mención (4,0/frase) · R2 cita de dominio propio (4,0/frase) · R3
posición de la primera mención (0–2,0/frase). Suite offline: todo entra como dicts
ya obtenidos; el no determinismo vive solo en la adquisición.

### Panel y matching

- **RR-01** — CUANDO se carga un panel desde YAML, EL SISTEMA valida industria,
  mercado, marcas y frases. SI el panel no tiene frases, o tiene un `codigo` de
  marca duplicado, ENTONCES falla con un `ValueError` que nombra la causa.
- **RR-02** — SI una frase no disparó búsqueda (`sin_busqueda`), ENTONCES **sale
  del denominador**, no puntúa cero. SI ninguna frase de una marca disparó
  búsqueda, su `puntaje_total` es `None` (estado `sin_cobertura`), nunca 0.
- **RR-03** — CUANDO se parsea una respuesta de Gemini, EL SISTEMA lee el dominio de
  cada fuente de `groundingChunks[].web.title`, **nunca** del host de
  `groundingChunks[].web.uri` (es siempre un redirect opaco de
  `vertexaisearch.cloud.google.com`). SI no hay `webSearchQueries` ni fuentes, la
  captura es `sin_busqueda`. SI la API devuelve `error`, la captura es `error` con
  `motivo`.
- **RR-04** — EL SISTEMA busca la mención del nombre sobre texto normalizado
  (minúsculas, sin acentos) y **con límites de palabra** (`\b`): "Gestair" no
  matchea dentro de "Gestairways". EL SISTEMA reconoce los `alias` declarados.
- **RR-05** — EL SISTEMA considera citada a una marca cuando un `dominio` declarado
  coincide con el de una fuente por **igualdad exacta o sufijo de subdominio**
  (`x == d` o `x.endswith("." + d)`), normalizando esquema y `www.`. **Nunca
  subcadena** (`globalcharter.com` no matchea `global-charters.com`).
- **RR-06** — SI un match de nombre cae dentro de un patrón de la lista `excluir` de
  la marca, ENTONCES no cuenta (p. ej. "air txt de terceros" para la marca `Air TXT`).

### Señales y puntaje

- **RR-07** — CUANDO una marca es nombrada en la respuesta de una frase, EL SISTEMA
  le otorga R1 (4,0 por frase).
- **RR-08** — CUANDO un dominio propio es citado como fuente, EL SISTEMA le otorga
  R2 (4,0 por frase) **aunque la marca no sea nombrada** — R1 y R2 son señales
  independientes.
- **RR-09** — EL SISTEMA otorga R3 en escala lineal según la posición relativa de la
  primera mención en el texto: al inicio ~2,0, al final ~0. *(Escala pendiente de
  confirmación empírica tras la primera semana de serie.)*
- **RR-10** — EL SISTEMA normaliza el puntaje a 100 sobre los puntos alcanzables en
  las **frases con búsqueda** (`100 × obtenidos / alcanzables`), no sobre todas.
- **RR-11** — EL SISTEMA reporta siempre la cobertura como `frases_con_busqueda /
  frases_totales`, aunque hoy dé 10/10.
- **RR-12** — EL SISTEMA asigna un tier propio del índice de respuestas
  (`Ausente` … `Referencia`; umbrales exactos en `contract.py`), **disjunto** de los
  tiers del índice técnico (`Invisible`/`Parcial`/`Emergente`/`Líder GEO`). Vive en
  el JSON y el Markdown por marca; **no se publica** en la página del panel
  (`docs/decisiones/2026-09-09-tiers-no-publicados.md`). La tabla comparativa de
  panel usa el cuartil de ranking (RF-22).
- **RR-13** — Dos corridas de `puntuar_panel` sobre las mismas capturas producen el
  mismo JSON byte a byte. El panel sale ordenado por ranking (puntaje desc., luego
  `codigo`).

### Adquisición, almacén y salida

- **RR-14** — La caché está **apagada por defecto**: cada corrida vuelve a consultar
  (es *la medición*). SI se pasa `--cache` explícito, ENTONCES reutiliza. La
  respuesta cruda de cada frase se guarda como evidencia (`G1.json` /
  `G1.r1.json`…), y recalcular desde el crudo no consulta.
- **RR-15** — La superficie es intercambiable y se valida por nombre. SI el nombre
  es desconocido (`ai-overviews`), ENTONCES falla con "superficie desconocida". La
  superficie `gemini` se resuelve sin consultar (respeta `GEMINI_MODEL`).
- **RR-16** — La clave de Gemini se busca en orden (`GEMINI_API_KEY` →
  `.secrets/gemini.env` → `config.php` del growth-bot). SI no hay clave, el error
  nombra dónde se buscó y **nunca revela el valor**.
- **RR-17** — El almacén (`maria.store.runs`, compartido con el índice técnico)
  archiva y recupera un `MarcaRun`, calcula el delta total y por dimensión, y **no
  rompe** al consumidor original (`AuditRun` se sigue recuperando sin pasar modelo).
- **RR-18** — La salida (JSON, Markdown de marca, tabla de panel) deriva del modelo
  puntuado y **no recalcula**: mutar el modelo después de renderizar no cambia el
  Markdown ya emitido. La tabla de panel (entregable **interno**) lleva el cuartil de
  ranking (RF-22) en vez del tier absoluto, y separa las marcas `sin_cobertura`.

### Serie diaria, página y propuesta (rúbrica §7 bis)

- **RR-19** — Varias capturas con el mismo `frase_id` son **repeticiones** (N = 3
  por defecto) y se agregan por frecuencia: nombrada en 2 de 3 vale ⅔ de R1; citada
  en 3 de 3 vale R2 entera; R3 es la media sobre las N. El denominador **no** se
  triplica (sigue siendo una frase). Con N = 1, el resultado es el binario de
  siempre. La evidencia dice en cuántas repeticiones apareció.
- **RR-20** — El nombre de archivo del histórico normaliza cualquier forma del
  offset UTC a `Z` (`20260907T142311Z.json`).
- **RR-21** — `serie(codigo, n)` devuelve las últimas N corridas en orden
  cronológico ascendente.
- **RR-22** — Cada punto de la serie lleva la **media móvil de 7 días** mirando solo
  hacia atrás; las corridas `sin_cobertura` (`None`) se saltean, no cuentan como 0.
- **RR-23** — `build_pages` genera la página pública de Respuestas desde el
  `report_dir`, sin recalcular. La página muestra puntaje y desglose por señal,
  **sin etiqueta de tier** (`docs/decisiones/2026-09-09-tiers-no-publicados.md`).
  Incluye el límite del informe (nombra ChatGPT/Perplexity/etc. como superficies
  **no** medidas) y un movimiento menor a ~5 pts entre días se muestra "dentro del
  ruido medido", no como flecha.
- **RR-24** — `proponer` cuenta los dominios citados **por frase, no por
  repetición**, y excluye los dominios propios. Los códigos de marca generados no
  colisionan.
- **RR-25** — `proponer` arma un panel **sin congelar** desde la evidencia: la
  empresa que pide el análisis va primera, los competidores citados entran, los
  no-competidores (Wikipedia, directorios) quedan fuera; 10 frases (5 general +
  5 long-tail); el YAML lleva un bloque `_propuesta` con instrucciones de congelado.
  El LLM solo redacta y agrupa; **los candidatos salen de las citas reales, no de la
  memoria del modelo** (`docs/decisiones/2026-09-06-rubrica-respuestas.md` §6).
- **RR-26** — La cola en disco mueve una `Solicitud` entre estados
  (`pendientes_verificacion` → `pendiente` → `procesada`); una solicitud sin
  `verificada_utc` no aparece en `pendientes()`.
- **RR-27** — ANTES de consultar a Gemini, EL SISTEMA rechaza (`Rechazo`, sin gastar
  créditos) una solicitud si: la industria no está en la lista blanca, el email no
  está verificado, o se alcanzó el tope diario de corridas.

### Fuera de alcance (Parte B)

Medir AI Overviews o cualquier superficie que no sea la API de Gemini; interpretar
el delta de una sola corrida; preguntarle a un LLM quiénes son los competidores;
matching de marca por subcadena o por nombre sin límite de palabra.

---

## Criterios de finalización

1. `.venv/bin/pytest` (suite base, offline, sin Chromium) en verde.
2. `tests/test_rf_todos.py` en verde: cada RF de la Parte A tiene su test.
3. Cada RR de la Parte B tiene su test en `tests/test_rr*.py`.
4. Un golden de cuenta reproducible byte a byte entre dos corridas (RF-15/RF-16).
5. El scoring del motor reproduce el scoring manual del panel AR con desvío ≤ 8 pts
   (calibración de `docs/plan.md` §2, extremos fijados en T0).
