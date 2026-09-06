# Scoring del panel AR contra la rúbrica §2 — primera pasada

**Fecha:** 2026-09-01 · **Rúbrica:** §2 de `PLAN-JET-MARIA-SDD.md` con la enmienda de
[`2026-09-01-rubrica.md`](2026-09-01-rubrica.md) aplicada · **Método:** fetch estático
del HTML servido con el UA propio `MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)` desde
el servidor de maria.ar + datos de DOM renderizado reutilizados de
[`mediciones/panel_ar_run2.json`](mediciones/panel_ar_run2.json) (corrida del 29-08).

## Qué es esto y qué NO es

- Es una **primera pasada asistida, con evidencia por celda para validación humana**.
  No es el golden set independiente cerrado que pide T0: lo produjo Claude, no un
  analista. Cada celda no trivial va con su fuente para que se **verifique**, no se
  re-derive.
- El **ratio de D3** y todo sub-criterio que dependa del **DOM renderizado** salen de
  `panel_ar_run2.json` (29-08), no se remidieron hoy — no hay Chromium headless en
  esta sesión. Se marca la fecha en esas celdas.
- **Modena Air Service** no se pudo traer desde el servidor de maria.ar: Cloudflare
  devuelve **403 a la IP del hosting** (reputación de IP, **no** un bloqueo de
  contenido — `panel_ar_run2.json` desde la notebook obtuvo 200 limpio, y la enmienda
  §5 lo confirma). D1/D2/D3 mecánicos salen de run2; D4/D5 quedan mayormente
  `unverified`.
- **Baires Global Jets** es un SPA en GitHub Pages: el HTML servido trae solo
  `<head>` + JSON-LD, sin `<body>`, nav ni formularios. D1 se puntúa desde el JSON-LD
  (sólido); D3/D4/D5 quedan mayormente `unverified` (necesitan DOM renderizado).
- **tenilaviacion.com.ar** y **avionesprivadossa.com.ar** son `inaccesible`
  (bucle de redirecciones / certificado TLS con hostname mismatch). D2-acceso = 0 con
  hallazgo **crítico**; el resto no es medible. **Quedan fuera del ranking** (enmienda §4).
- **Baires Fly** y **Argentina Jets** son `no_aplica` (sin sitio) — sin puntaje.
- `navigator.modelContext` (D6.1) = 0 en todas: no se probó con JS en esta sesión,
  consistente con lo que ya anticipaba T13 del plan.

## Códigos de cuenta

| código | cuenta | URL | grupo | estado |
|---|---|---|---|---|
| SUN | Sundown Jet | sundownjet.com | A | medido |
| ROY | Royal Class | royalclass.com.ar | A | medido |
| MOD | Modena Air Service | modenaair.com | A | medido (D4/D5 parcial) |
| AFL | Argentina Fly | argentina-fly.com | A | medido |
| TEN | Tenil Aviación | tenilaviacion.com.ar | A | **inaccesible** |
| BGJ | Baires Global Jets | bairesglobaljets.com | A | medido (D3/D4/D5 parcial) |
| AVP | Aviones Privados SA | avionesprivadossa.com.ar | A | **inaccesible** |
| SAJ | South American Jets | southjets.com | B | medido |
| FLP | Flapper | flyflapper.com | B | medido |
| ACS | Air Charter Service AR | aircharterservice.com.ar | B | medido |
| LUN | LunaJets | lunajets.com | B | medido |
| AMJ | American Jet | americanjet.com.ar | C | medido |
| — | Baires Fly | — | A | **no_aplica** (sin sitio) |
| — | Argentina Jets | — | A | **no_aplica** (sin web en la hoja Objetivos) |

## Resumen — total y tier

| # | cuenta | grupo | D1/25 | D2/20 | D3/20 | D4/15 | D5/15 | **/100** | +D6 | **/105** | **tier** |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Flapper (FLP) | B | 20.9 | 20 | 20.0 | 12.5 | 12.0 | **85.4** | +2 | 87.4 | Líder GEO |
| 2 | LunaJets (LUN) | B | 20.0 | 20 | 14.8 | 14.0 | 14.0 | **82.8** | 0 | 82.8 | Líder GEO |
| 3 | Argentina Fly (AFL) | A | 25.0 | 20 | 20.0 | 6.5 | 11.0 | **82.5** | +2 | 84.5 | Líder GEO |
| 4 | South American Jets (SAJ) | B | 11.7 | 20 | 13.2 | 10.5 | 10.0 | **65.4** | 0 | 65.4 | Emergente |
| 5 | Sundown Jet (SUN) | A | 13.4 | 18 | 18.0 | 3.0 | 7.0 | **59.4** | 0 | 59.4 | Emergente |
| 6 | Baires Global Jets (BGJ)* | A | 21.7 | 9 | 9.0 | 5.5u | 7.0u | **~52.2** | 0 | ~52.2 | Parcial* |
| 7 | Royal Class (ROY) | A | 0.0 | 20 | 20.0 | 2.0 | 10.0 | **52.0** | 0 | 52.0 | Parcial |
| 8 | Air Charter Service AR (ACS) | B | 0.0 | 9 | 20.0 | 11.5 | 8.0 | **48.5** | 0 | 48.5 | Parcial |
| 9 | Modena Air Service (MOD)* | A | 0.0 | 17 | 15.0 | 7.5u | 6.0u | **~45.5** | 0 | ~45.5 | Parcial* |
| 10 | American Jet (AMJ) | C | 0.0 | 20 | 15.0 | 3.0 | 5.5u | **43.5** | 0 | 43.5 | Parcial |
| — | Tenil Aviación (TEN) | A | — | 0 crít. | — | — | — | **no medible** | — | — | inaccesible |
| — | Aviones Privados SA (AVP) | A | — | 0 crít. | — | — | — | **no medible** | — | — | inaccesible |

Orden por total /100. FLP y AFL suman +2 de bonus D6 (`llms.txt`), lo que no altera
el orden del top-3 salvo que se cuente sobre /105 (ahí AFL pasa a LUN).

\* MOD y BGJ tienen sub-criterios `unverified` que pesan en el total; ver notas.
El total de MOD baja porque D1 = 0 (sin JSON-LD, dato firme de run2) y D4/D5 quedan a
mitad por no poder inspeccionar. El total de BGJ sube por D1 (JSON-LD rico) pero D2/D3
caen por no tener `robots.txt` y servir `<body>` vacío.

## Matriz — 26 sub-criterios × cuenta

Valores en puntos. `u` = `unverified` (mitad del máximo, principio 4). `—` = inaccesible.

### D1 · Estructura Semántica (25)

| sub-criterio | máx | SUN | ROY | MOD | AFL | BGJ | SAJ | FLP | ACS | LUN | AMJ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| D1.1 JSON-LD presente y parseable | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 5 | 0 | 5 | 0 |
| D1.2 `Organization`/`LocalBusiness` con name+url | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 5 | 0 | 5 | 0 |
| D1.3 `address` + `telephone` en el schema | 5 | 0 | 0 | 0 | 5 | 5 | 0 | 2.5 | 0 | 5 | 0 |
| D1.4 `Service`/`Offer`/`Product` del chárter | 5 | 0 | 0 | 0 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| D1.5 `sameAs`+`logo`+`aggregateRating` (1,7 c/u) | 5 | 3.4 | 0 | 0 | 5 | 1.7 | 1.7 | 3.4 | 0 | 5 | 0 |
| **D1 total** | 25 | **13.4** | **0** | **0** | **25.0** | **21.7** | **11.7** | **20.9** | **0** | **20.0** | **0** |

### D2 · Accesibilidad para Crawlers de IA (20)

| sub-criterio | máx | SUN | ROY | MOD | AFL | BGJ | SAJ | FLP | ACS | LUN | AMJ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| D2.1 `robots.txt` accesible sin `Disallow` para GPTBot/ClaudeBot/CCBot/PerplexityBot/Google-Extended | 8 | 8 | 8 | 8 | 8 | 0 | 8 | 8 | 0 | 8 | 8 |
| D2.2 Acceso para clientes no-navegador (200 al UA propio) | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 |
| D2.3 `sitemap.xml` presente y referenciado desde `robots.txt` | 3 | 1 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 3 | 3 |
| D2.4 HTTPS sin degradación en la cadena | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| **D2 total** | 20 | **18** | **20** | **17** | **20** | **9** | **20** | **20** | **9** | **20** | **20** |

### D3 · Legibilidad sin JavaScript (20) — *render de `panel_ar_run2.json` (29-08)*

| sub-criterio | máx | SUN | ROY | MOD | AFL | BGJ | SAJ | FLP | ACS | LUN | AMJ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| D3.1 ratio de texto útil (escalado 0,40–0,80) | 8 | 8 | 8 | 8 | 8 | 0 | 1.2 | 8 | 8 | 6.8 | 8 |
| D3.2 `title` + `meta description` en HTML servido | 4 | 2 | 4 | 2 | 4 | 4 | 4 | 4 | 4 | 2 | 4 |
| D3.3 `canonical` en HTML servido | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 0 | 0 |
| D3.4 nav principal sin JS (≥5 enlaces internos) | 3 | 3 | 3 | 1.5u | 3 | 0 | 3 | 3 | 3 | 3 | 0 |
| D3.5 teléfono o email en HTML servido | 3 | 3 | 3 | 1.5u | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| **D3 total** | 20 | **18.0** | **20.0** | **15.0** | **20.0** | **9.0** | **13.2** | **20.0** | **20.0** | **14.8** | **15.0** |

### D4 · Divulgación y Confianza (15)

| sub-criterio | máx | SUN | ROY | MOD | AFL | BGJ | SAJ | FLP | ACS | LUN | AMJ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| D4.1 política de privacidad localizable | 4 | 0 | 0 | 2u | 2u | 2u | 4 | 4 | 4 | 4 | 0 |
| D4.2 política de cookies completa | 3 | 0 | 0 | 1.5u | 1.5u | 1.5u | 1.5u | 2 | 2.5u | 2.5u | 0 |
| D4.3 CMP presente y coherente con la analítica | 3 | 0 | 0 | 1.5u | 0 | 1.5u | 3 | 1.5u | 2 | 3 | 0 |
| D4.4 identidad legal (razón social + CUIT/CIF + domicilio) | 3 | 1 | 1 | 1.5u | 1 | 1.5u | 1.5 | 3 | 2 | 2.5 | 1 |
| D4.5 coherencia dominio web ↔ dominio email | 2 | 2 | 0 | 1u | 2 | 2 | 1u | 2 | 1 | 2 | 2 |
| **D4 total** | 15 | **3.0** | **2.0** | **~7.5u** | **~6.5** | **~5.5u** | **~10.5** | **12.5** | **~11.5** | **14.0** | **3.0** |

### D5 · Captura de Leads sin Fricción (15)

| sub-criterio | máx | SUN | ROY | MOD | AFL | BGJ | SAJ | FLP | ACS | LUN | AMJ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| D5.1 formulario de cotización ≤2 clics desde home | 4 | 4 | 4 | 2u | 4 | 2u | 4 | 4 | 4 | 4 | 1 |
| D5.2 campos requeridos ≤6 (escalado) | 3 | 0 | 3 | 1.5u | 3 | 1.5u | 0 | 3 | 3 | 3 | 1.5u |
| D5.3 canal directo `tel:` o `wa.me` clickable | 3 | 3 | 3 | 1.5u | 3 | 1.5u | 3 | 3 | 1 | 3 | 3 |
| D5.4 **compromiso de respuesta publicado** | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 3 | 0 |
| D5.5 cotizador con precio en pantalla | 2 | 0 | 0 | 1u | 1u | 1u | 0 | 2 | 0 | 1 | 0 |
| **D5 total** | 15 | **7** | **10** | **~6.0u** | **11** | **~7.0u** | **10** | **12** | **8** | **14** | **~5.5** |

### D6 · Frontera WebMCP/MCP (5 bonus)

| sub-criterio | máx | SUN | ROY | MOD | AFL | BGJ | SAJ | FLP | ACS | LUN | AMJ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| D6.1 `navigator.modelContext` con herramientas | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| D6.2 `llms.txt` / `/.well-known/` / feed de flota-rutas | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| **D6 bonus** | 5 | 0 | 0 | 0 | **2** | 0 | 0 | **2** | 0 | 0 | 0 |

---

## Evidencia por cuenta

### SUN · Sundown Jet — 59.4 (Emergente)

- **D1** JSON-LD Yoast (1 bloque, parsea). `Organization` `#organization`: name "Sundown Jet S.A.", url, `logo` ImageObject, `sameAs` [instagram, linkedin]. **Sin** `address`/`telephone` en el schema, **sin** `Service`/`Offer`, **sin** `aggregateRating`. Tipos: BreadcrumbList, Organization, WebPage, WebSite → **no** aplica el tope por boilerplate (hay Organization con datos). → 5+5+0+0+3.4 = **13.4**.
- **D2** `robots.txt` presente: solo lista agentes Google (`Disallow:` vacío), sin bloque `User-agent: *`, sin `Disallow` de contenido → GPTBot/ClaudeBot/etc. permitidos (8). `run2`: 200 al UA propio (7). Sitemap: `/sitemap_index.xml` responde 200 **pero** las líneas `Sitemap:` del `robots.txt` apuntan a **otros dominios** (`sundownjetsa.com`, `sundownjetsa.ar/index.html`) — referencia rota → **1/3**. HTTPS sin degradación (2). → **18**.
- **D3** (run2) ratio 1,003 → 8. `title` sí, `meta description` **no** → 2/4. `canonical` sí (2). 30 enlaces internos en HTML servido (3). `tel:`/email en el servido (3). → **18.0**.
- **D4** Sin enlace a política de privacidad en home ni en `/contacto/` (0/4). Sin política de cookies (0/3). Sin CMP y con GA4 cargando → incoherente (0/3). Identidad legal: razón social "Sundown Jet S.A." + ubicación (San Fernando) pero **sin CUIT** → 1/3. Email `ventas@sundownjet.com` ↔ dominio `sundownjet.com` ✓ (2/2). → **3.0**.
- **D5** Cotizador en `/cotizador-de-vuelo-privado/`, 1 clic desde el botón "COTIZÁ TU VUELO" (4/4). El form tiene **11 campos, 9 requeridos** (>6) → 0/3. `tel:` + widget WhatsApp (3/3). Sin compromiso de respuesta (0/3). Contact Form 7, sin precio en pantalla (0/2). → **7**.
- **D6** Sin `llms.txt` (404), sin `/.well-known/` real. → **0**.

### ROY · Royal Class — 52.0 (Parcial)

- **D1** **0 bloques JSON-LD**. → **0/25**.
- **D2** `robots.txt`: `User-agent: *` con `Disallow` solo de rutas técnicas de WordPress/WooCommerce, contenido abierto → 8. `run2` 200 al UA propio (7). `Sitemap: https://royalclass.com.ar/wp-sitemap.xml` referenciado (3). HTTPS ok (2). → **20**.
- **D3** (run2) ratio 1,024 → 8. `title` + `meta description` sí (4). `canonical` sí (2). 29 enlaces internos (3). `wa.me` + email en el servido (3). → **20.0**.
- **D4** Sin política de privacidad ni de cookies visible (0+0). Sin CMP; tampoco se detecta analítica → 0/3. Identidad: "Royal Class" sin forma societaria explícita, dirección de hangar en Aeroparque, sin CUIT → 1/3. Emails `info@royalclass.global` / `comercial@royalclass.global` ↔ sitio `royalclass.com.ar` → **dominio de email distinto** (0/2). → **2.0**.
- **D5** Form de cotización en el home: **10 campos, 6 requeridos** (= 6, en el límite) → 3/3. `wa.me` ×2 (3/3). "Servicio H24 con capacidad de despegue en 2hs" es capacidad operativa, **no** un compromiso de respuesta a consultas → 0/3. Sin precio (0/2). Alcance ≤2 clics (4/4). → **10**.
- **D6** Sin `llms.txt`. → **0**.

### MOD · Modena Air Service — ~45.5 (Parcial, parcialmente unverified)

- **No fetcheable desde el servidor de maria.ar** (Cloudflare 403 a la IP del hosting). D1/D2/D3 desde `panel_ar_run2.json` (notebook, 200 limpio). D4/D5 `unverified`.
- **D1** run2: **sin JSON-LD** (raw ni renderizado). → **0/25**.
- **D2** `robots.txt` presente (1248 chars) = **solo el preámbulo de Content Signals de Cloudflare, cero directivas** → no declara política pero tampoco bloquea; sin `Disallow` para AI crawlers (8). run2: **200 limpio al UA propio, sin challenge** (7) — el 403 que veo desde acá es reputación de IP, no bloqueo (enmienda §5). Sin `Sitemap:` en robots y `/sitemap.xml` → 403 (0/3). HTTPS ok (2). → **17**.
- **D3** (run2) ratio 1,061 → 8. `title` sí, `meta description` **no** → 2/4. `canonical` sí (2). Nav / contacto en HTML servido: `unverified` (1,5 + 1,5). → **15.0**.
- **D4** `unverified` — no inspeccionable en esta sesión. Estimado a mitad: ~7.5. **Pendiente de revisión en navegador.**
- **D5** `unverified`. Estimado ~6. Sin evidencia de compromiso de respuesta (D5.4 = 0).
- **D6** Sin `llms.txt` (404). → **0**.
- **Nota:** el hallazgo real de Modena (enmienda §5 / `2026-09-01-hallazgos.md` §4) es que publica un `robots.txt` que **parece** una política y está vacío — **no** que bloquee. La hoja del panel decía "riesgo real de estar bloqueando crawlers de IA"; esta corrida **no lo reproduce**.

### AFL · Argentina Fly — 82.5 + 2 bonus (Líder GEO)

- **D1** 2 bloques JSON-LD. `LocalBusiness`: name "Argentina Fly", url, `telephone` "+5491130807775", `email`, `address` PostalAddress (Buenos Aires / AR), `sameAs` [instagram, facebook, google], `logo`, **`aggregateRating`** 5/28, `priceRange` "$$", **`hasOfferCatalog`** con 9 `Offer`→`Service` (Private flights, Air taxi, Charter, Executive aviation, Empty legs, Helicopter tours, Baptism flights, Aerial experiences). → 5+5+5+5+5 = **25/25**. *(Revisar: el `address` es solo localidad+país, sin `streetAddress`; el `aggregateRating` de 28 reseñas conviene validar si es sustantivo.)*
- **D2** **El mejor `robots.txt` del panel.** Bloque explícito `User-agent: GPTBot / ChatGPT-User / ClaudeBot / anthropic-ai / PerplexityBot / Google-Extended / …` con `Disallow` solo de rutas de desarrollo, `Allow: /llms.txt`, comentario "Crawlers de IA — indexación permitida para visibilidad en búsqueda con IA" (8). run2 200 (7). `Sitemap: https://argentina-fly.com/sitemap.xml` referenciado (3). HTTPS ok (2). → **20**.
- **D3** (run2) ratio 0,927 → 8. `title` + `meta description` (4). `canonical` (2). 6 enlaces internos en el servido (≥5 → 3). tel + wa + email (3). → **20.0**.
- **D4** Sin enlace visible a política de privacidad en el HTML servido → `unverified` 2/4. Cookies `unverified` 1,5. Sin CMP + GA4 → 0/3. Identidad: sin razón social ni CUIT, solo "Buenos Aires / AR" del schema → 1/3. `info@argentina-fly.com` ↔ `argentina-fly.com` ✓ (2/2). → **~6.5** *(D4.1/D4.2 pendientes de revisión).*
- **D5** Form de contacto en home (5 campos, 0 requeridos → 3/3). El `llms.txt` afirma "instant price estimates" → probable cotizador con precio, `unverified` 1/2. tel + wa (3/3). "24/7" es disponibilidad, **no** compromiso de respuesta → 0/3. Alcance ≤2 clics (4/4). → **11** *(D5.5 pendiente de confirmar el cotizador).*
- **D6** **`llms.txt` presente y real** (EN + `/llms-es.txt`), declara rol de intermediario, servicios, y está referenciado desde `robots.txt`. → **2/2**.
- **Hallazgo:** una cuenta de **Grupo A** (prospecto argentino) hizo trabajo GEO deliberado y queda **#2 del panel**. Rompe el patrón "las extranjeras arriba". Candidata a extremo alto de la calibración de T0.

### BGJ · Baires Global Jets — ~52.2 (Parcial, parcialmente unverified)

- **SPA en GitHub Pages** — el HTML servido trae solo `<head>` + JSON-LD, sin `<body>`, nav ni formularios. run2: `raw_words` = 0.
- **D1** 1 bloque JSON-LD. `TravelAgency` `#organization`: name "Baires Global Jets", url, `telephone` "+54-11-5272-1234", `email`, **`address` PostalAddress completa** (Bolívar 753, B1704BKO, Ramos Mejía, Prov. Buenos Aires, AR), `logo`, `priceRange` "$$$", **`hasOfferCatalog`** con `Offer`→`Service` detallados (Light/Medium/Heavy Jets con descripción). `sameAs` **vacío** `[]`, **sin** `aggregateRating`. → 5+5+5+5+1.7 = **21.7/25**. *(La mejor `address` del panel.)*
- **D2** **Sin `robots.txt`** (GitHub Pages devuelve 404 HTML) → 0/8. 200 al UA propio (7). Sin sitemap (0/3). HTTPS ok (2). → **9**.
- **D3** (run2) ratio **0,0** (raw_words = 0, todo el texto es JS) → 0/8. `title` + `meta description` en el servido (4). `canonical` (2). Nav: 0 enlaces en el servido → 0/3. email en el servido (dentro del JSON-LD) (3). → **9.0**.
- **D4** `unverified` (SPA). `address` legal en JSON-LD sin razón social/CUIT → D4.4 1,5u. `info@bairesglobaljets.com` ↔ `bairesglobaljets.com` ✓ (2/2). Resto `unverified`. → **~5.5**.
- **D5** `unverified` (SPA). → **~7.0**.
- **D6** Sin `llms.txt`. → **0**.

### SAJ · South American Jets — 65.4 (Emergente)

- **D1** 1 bloque JSON-LD. `Organization` `#Organization`: name "South American Jets", url, `logo` ImageObject. `sameAs` **vacío** `[]`, **sin** `address`/`telephone` en el schema, **sin** `Service`/`Offer`, **sin** `aggregateRating`. También `SiteNavigationElement` + `WebSite`. → 5+5+0+0+1.7 = **11.7/25**. *(Grupo B, "vara de medir", y su schema es pobre — hallazgo.)*
- **D2** `robots.txt` Yoast: `User-agent: * / Disallow:` (permite todo) + `Sitemap: .../sitemap_index.xml` (8 + 3). run2 200 (7). HTTPS ok (2). → **20**.
- **D3** (run2) ratio **0,46** → **1,19/8** (más de la mitad del contenido depende de JS — el caso testigo de la enmienda §1). `title` + `meta description` (4). `canonical` (2). 49 enlaces internos en el servido (3). `tel:` (números US) en el servido (3). → **13.2**.
- **D4** Footer "Política de privacidad" + página `/es/politica-de-privacidad/` responde 200 (4/4). Cookies: CookieYes presente, completitud `unverified` 1,5. **CookieYes CMP + GTM** → coherente (3/3). Identidad: "South American Jets, LLC" (EE.UU.) + direcciones US/AR/ES + "TEKOA VIAJES 3G TOURS SRL" (entidad AR en el HTML) — sin CUIT/RUC → 1,5/3. Email ofuscado, no verificable → 1u/2. → **~10.5**.
- **D5** Form de cotización en el home: **9 campos, 7 requeridos** (>6) → 0/3. "**Recibirá ayuda de nuestro equipo en 15 minutos, 24 horas al día, 7 días a la semana**" → **compromiso de respuesta publicado, 3/3**. `tel:` + WhatsApp (vía bit.ly) (3/3). Sin precio (0/2). Alcance ≤2 clics (4/4). → **10**. *(Confirma el "3/3 en D5.4" que anticipaba el plan §2 D5.)*
- **D6** Sin `llms.txt` (404). → **0**.

### FLP · Flapper — 85.4 + 2 bonus (Líder GEO)

- **D1** 1 bloque JSON-LD grande. `Organization` `#organization`: name "Flapper", url, `logo`, **`sameAs` con 8 entradas** (LinkedIn, IG, FB, YouTube, X, Wikipedia PT/EN, Crunchbase), `taxID` "27.028.507/0001-00", `founder` (Person), `description`, `contactPoint` con `telephone` "+551132303710", **`hasOfferCatalog`** con 7 `Service` con descripción (Alquiler de aeronaves, Propiedad compartida, Taxi aéreo, Ambulancia aérea, Chárter para grupos, Chárter de carga, Empty legs). **Sin `PostalAddress`** (telephone sí, vía contactPoint), **sin `aggregateRating`**. → 5+5+2.5+5+3.4 = **20.9/25**.
- **D2** `robots.txt`: `User-agent: * / Allow: / / Sitemap: .../sitemap.xml / Host:` (8 + 3). run2 200 (7). HTTPS ok (2). → **20**.
- **D3** (run2) ratio 1,076 → 8. `title` + `meta description` (4). `canonical` (2). 37 enlaces internos (3). tel + wa + email (3). → **20.0**.
- **D4** Footer "Política de privacidad" → página 200 ("Sus datos son gestionados por la empresa con sede en Brasil"); "Fly Legal" (4/4). Cookies mencionadas en la política (~2/3). CMP/analítica no detectables en el servido → `unverified` 1,5. Identidad: **"FLAPPER TECNOLOGIA S.A." + `taxID` (CNPJ) 27.028.507/0001-00 + sede Brasil** → **3/3**. `support@flyflapper.com` ↔ `flyflapper.com` ✓ (2/2). → **12.5**.
- **D5** Flujo de reserva/app desde el home (4/4). Forms tipo búsqueda, mínimos (3/3). tel + wa (3/3). Sin compromiso de respuesta a consultas claro ("15 minutos" = despegue) → 0/3. **Precios reales en pantalla** (tarjetas de ruta $2.000, $4.500, $12.000…) + pricing instantáneo en la app → **2/2**. → **12**.
- **D6** **`llms.txt` presente y real** (`/llms.txt`, "Guidance for AI/LLM and AI-search crawlers", lista feeds de datos JSON: `aeronaves.index.json`, `faq.json`, `stories.json`) → **2/2**.

### ACS · Air Charter Service AR — 48.5 (Parcial)

- **D1** **0 bloques JSON-LD** en la versión `.com.ar` (el sitio global tiene schema; esta localización ccTLD no). → **0/25**.
- **D2** **Sin `robots.txt`** — `/robots.txt` devuelve el HTML de "Page Not Found" (soft-404). Idem `/sitemap.xml`, `/llms.txt`, `/.well-known/` (todos sirven el 404 del sitio) → 0/8, 0/3. run2 200 al UA propio (7). HTTPS ok (2). → **9**.
- **D3** (run2) ratio 1,009 → 8. `title` + `meta description` (4). `canonical` (2). 70 enlaces internos (3). emails regionales en el servido (3). → **20.0**.
- **D4** Footer con `/legal-and-privacy-policy` y `/cookie-policy` (ambos responden 200) → 4/4. Página de cookies dedicada, contenido JS → `unverified` 2,5. Banner de cookies detectado + GTM/UA → coherencia parcial 2/3. Identidad: "Air Charter Service Ltd" (UK) visible; sin CUIT local (es un `.com.ar` de una entidad británica) → 2/3. Emails `lonpax@aircharterservice.com` (el `.com`, no `.com.ar`) → mismatch parcial, misma marca 1/2. → **~11.5**.
- **D5** `/forms/fast-quote/` enlazado desde el home (4/4). Form de 5 campos, 5 requeridos (≤6 → 3/3). Sin `tel:`/`wa.me` en el servido, solo emails + texto "DISPONIBLE 24/7" → 1/3. Sin compromiso de respuesta (0/3). Fast-quote es contacto, sin precio (0/2). → **8**.
- **D6** Sin `llms.txt` real. → **0**.

### LUN · LunaJets — 82.8 (Líder GEO)

- **D1** **9 bloques JSON-LD.** 8 `LocalBusiness` (sucursales Ginebra, Londres, Zúrich, París, Dubái, Madrid, Riga…) cada una con `PostalAddress` completa + `telephone` + `email`. `Organization` padre "LunaJets": `logo`, `sameAs` (Google Maps, IG, YouTube, LinkedIn), **`aggregateRating` 4,8 / 2302 reseñas**, `contactPoint`. **Sin** `Service`/`Offer`/`Product` (hay `ReserveAction`, no `Offer`). → 5+5+5+0+5 = **20/25**.
- **D2** `robots.txt`: `User-agent: * / Allow: / / Sitemap: .../sitemap.xml` (8 + 3). run2 200 (7). HTTPS ok (2). → **20**.
- **D3** (run2) ratio **0,742** → **6,83/8** (parte del contenido depende de JS). `title` sí, `meta description` **no** → 2/4. `canonical` **no** → 0/2. 73 enlaces internos (3). tel + email (3). → **14.8**.
- **D4** Footer "Política de privacidad" + "Aviso legal" + "Términos y condiciones" (4/4). Política menciona cookies utilizadas (~2,5/3, `unverified` tabla). **CookieYes CMP + GA4 + GTM** → coherente (3/3). Identidad: **"LunaJets S.A." + "domicilio social en Rue Lect 29, 1217 Meyrin, Ginebra (Suiza)"** → 2,5/3 (sin nº de registro visible). `lunajets@lunajets.com` ↔ `lunajets.com` ✓ (2/2). → **14.0**.
- **D5** CTA "Solicitar presupuesto" desde el home + página `/es/precios` (4/4). Captura por email en el home, forms mínimos (3/3). Muchos `tel:` + WhatsApp API (3/3). "**receive your tailored quote within minutes, 24/7**" → **compromiso de respuesta, 3/3**. `/es/precios` con precios indicativos, no un cotizador en vivo → 1/2. → **14**.
- **D6** Sin `llms.txt` (404). → **0**.

### AMJ · American Jet — 43.5 (Parcial)

- **D1** **0 bloques JSON-LD.** → **0/25**. *(Grupo C, "referencia del mercado argentino", el operador ejecutivo más grande del país — y es GEO-invisible en estructura.)*
- **D2** `robots.txt`: `User-agent:* / Disallow:` (permite todo) + `Sitemap:` referenciado, `/sitemap.xml` responde 200 (8 + 3). run2 200 (7). HTTPS ok (2). → **20**.
- **D3** (run2) ratio 1,0 → 8. `title` + `meta description` (4). `canonical` **no** → 0/2. Solo 3 enlaces internos en el servido (menú JS) → 0/3. tel + wa + email en el servido (3). → **15.0**.
- **D4** **Sin ningún enlace legal en el footer** (WebFetch lo confirma) → 0 + 0. Sin CMP/banner + GA4 → incoherente 0/3. Identidad: "American Jet S.A." (fundada 1983), sin CUIT ni domicilio → 1/3. `comercial@americanjet.com.ar` ↔ `americanjet.com.ar` ✓ (2/2). → **3.0**.
- **D5** Sin formulario de cotización; "Contacto" en el menú lleva a una página de contacto, no a un cotizador → 1/4. Campos `unverified` 1,5. `tel:` + `wa.me` (3/3). "Atención las 24 hs" es para vuelos sanitarios, no un compromiso de respuesta comercial → 0/3. Sin precio (0/2). → **~5.5**.
- **D6** Sin `llms.txt`; `/.well-known/` devuelve 300 (MultiViews de Apache, no un recurso real). → **0**.

### TEN · Tenil Aviación — inaccesible (fuera del ranking)

- `https://tenilaviacion.com.ar` entra en **bucle de redirecciones** para un cliente que no es navegador (`curl`: "Maximum (10) redirects followed"; run2: "Exceeded maximum allowed redirects"). Con Chrome carga; ningún crawler de IA puede obtener la página.
- `robots.txt` → 404. **D2.2 (acceso) = 0 · hallazgo CRÍTICO.** D1/D3/D4/D5/D6: **no medible** (no hay contenido alcanzable).

### AVP · Aviones Privados SA — inaccesible (fuera del ranking)

- `https://avionesprivadossa.com.ar`: **certificado TLS con hostname mismatch** (`SSL: no alternative certificate subject name matches target host name` / `CERTIFICATE_VERIFY_FAILED`). Un navegador muestra una advertencia a pantalla completa; un crawler simplemente falla.
- `robots.txt` → no alcanzable. **D2.2 (acceso) = 0 · hallazgo CRÍTICO** (y D2.4 HTTPS = 0, cadena TLS rota). D1/D3/D4/D5/D6: **no medible**.
- Es el hallazgo más caro del panel para un negocio que vende confianza (`2026-09-01-hallazgos.md` §3).

---

## Lecturas para T0 / calibración

1. **El orden no es "extranjeras arriba, locales abajo".** El top-3 (Flapper, **Argentina Fly**, LunaJets) incluye una cuenta de Grupo A. Argentina Fly hizo GEO deliberado (robots.txt que nombra a los crawlers de IA, `llms.txt` bilingüe, `LocalBusiness` completo con `OfferCatalog` y `aggregateRating`). Esto contradice el criterio de T19 tal como está redactado; conviene fijar la regla de comparación **después** de validar este scoring a mano.
2. **El operador más grande del país (American Jet, Grupo C) queda último.** Cero schema, sin política de privacidad, nav sólo-JS, sin cotizador. Titular potencial del informe: *la referencia del mercado es invisible para los motores de IA.*
3. **Candidatos a extremos de la calibración (§9.5 / criterio de aceptación):**
   - **Alto:** Flapper (~85) o Argentina Fly (~82,5) — ambas del panel AR.
   - **Bajo (medible):** American Jet (~43,5) o Air Charter Service AR (~48,5).
   - Los dos `inaccesible` (Tenil, Aviones Privados) son el piso absoluto pero **no** entran en el rango de calibración porque no son `medido`.
4. **D3 no discrimina** (confirmado: 8/10 con ratio ≥ 0,92; solo SAJ y BGJ caen). Va como control negativo, no como diferenciador — como dice la enmienda §2.
5. **D1 es el mayor diferenciador**, junto con el acceso de D2: 5 cuentas con 0/25 en D1 (ROY, MOD, ACS-ar, AMJ) frente a AFL 25, BGJ 21,7, FLP 20,9, LUN 20.
6. **Compromiso de respuesta publicado (D5.4):** 3/3 solo en South American Jets y LunaJets; **0/3 en las 6 cuentas argentinas medibles**. Es la fila que conecta con el Paso Cero, y el contraste es exactamente el que anticipaba el plan.
7. **Celdas que un humano tiene que cerrar antes de que esto sea golden:**
   - **MOD**: D4/D5 completos (no fetcheable desde el server — abrir en navegador).
   - **BGJ**: D3/D4/D5 sobre el DOM renderizado (SPA).
   - **AFL**: confirmar el cotizador con precio (D5.5) y las políticas de privacidad/cookies (D4.1/D4.2).
   - **SAJ / ACS / LUN / FLP**: completitud de las políticas de cookies (tablas) sobre el contenido renderizado.
   - Todo D3 y sub-criterios de render: remedir con `geo_probe.py` + Chromium remoto para tener fecha de hoy, no del 29-08.
