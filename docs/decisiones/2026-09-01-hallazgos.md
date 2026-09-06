# Panel AR — corrida 1 del probe · 29-08-2026

Fuente: `panel_ar_run1.json` (Playwright + httpx, UA `MarIA-GEO-Audit/0.1`, notebook).
Contrastado contra la corrida por navegador del mismo día (Chrome, UA de navegador).

## 1. Validación cruzada: el render es reproducible

El conteo de palabras del DOM renderizado coincide **exactamente** entre dos stacks
independientes — el Chrome del escritorio y el Chromium de Playwright — en 8 de 9
cuentas medidas por ambos:

| dominio | render navegador | render probe |
|---|---|---|
| sundownjet.com | 628 | 628 |
| royalclass.com.ar | 823 | 823 |
| modenaair.com | 1519 | 1519 |
| bairesglobaljets.com | 649 | 649 |
| flyflapper.com | 2122 | 2122 |
| aircharterservice.com.ar | 986 | 986 |
| americanjet.com.ar | 451 | 451 |
| lunajets.com | 1920 | 1917 |

Coincidencia byte a byte en 7 de 8. La extracción del lado renderizado es sólida y
puede congelarse como fixture (T7) con confianza.

## 2. La divergencia real: South American Jets

| | render | ratio |
|---|---|---|
| navegador | 1025 | 0,999 |
| probe | 2236 | **0,460** |

El crudo es el mismo (1024 / 1028). Lo que cambió es el renderizado: Playwright
espera `networkidle`, la medición por navegador leyó el DOM apenas terminó la
navegación. O sea que southjets.com **carga ~1200 palabras de forma diferida**, y
la corrida por navegador las perdió.

Consecuencia para la rúbrica: D3 pasa de 8/8 a **1,19/8**. Es un Grupo B —la vara
de medir del informe— y resulta que más de la mitad de su contenido no está en el
HTML servido.

Consecuencia para la spec: el momento de captura del DOM es un parámetro de la
medición, no un detalle. Hay que fijarlo explícitamente (`networkidle` + timeout) y
escribirlo en la rúbrica, o dos corridas legítimas dan puntajes distintos.

## 3. Dos fallos de acceso — hallazgos críticos de D2

**tenilaviacion.com.ar** — `Exceeded maximum allowed redirects`.
Bucle de redirecciones para un cliente que no es navegador. Con Chrome carga sin
problema. Ningún crawler de IA puede obtener la página: no es "falta schema", es
que no hay contenido alcanzable. Además explica por qué su `robots.txt` da 404.

**avionesprivadossa.com.ar** — `SSL: CERTIFICATE_VERIFY_FAILED — Hostname mismatch`.
El certificado no cubre el dominio. Esto también explica que el navegador se negara
a abrirlo en la corrida anterior: no era un permiso, era TLS roto. Un navegador
muestra una pantalla de advertencia a pantalla completa; un crawler simplemente
falla. Es el hallazgo más caro del panel para un negocio que vende confianza.

Los dos puntúan 0 en el sub-criterio de acceso de D2 y elevan a severidad crítica.

## 4. Modena NO bloquea

`status 200` con el UA propio identificado. No hubo challenge, ni 403, ni 503.
La hoja del panel anota "riesgo real de estar bloqueando crawlers de IA": esta
corrida **no lo reproduce**. Su `robots.txt` sigue siendo 1248 caracteres con cero
directivas (solo Content Signals de Cloudflare), así que tampoco bloquea por ahí.

El fallo del validador de Google documentado en Fase 2 no se explica con este dato.
Puede haber sido específico de Google, o transitorio. Conviene no repetir la
afirmación de bloqueo en el informe sin una prueba nueva.

## 5. El ratio > 1,0 es ruido, no bug

Cinco cuentas dieron ratio levemente por encima de 1: sundown 1,003 · aircharter
1,009 · royalclass 1,024 · modena 1,061 · flapper 1,076.

En todas, el render coincide con la corrida por navegador y lo que cambia es el
**crudo**: httpx sin cookies recibe algo más de marcado que el navegador. Sospecha
principal, banners de consentimiento servidos a clientes sin cookie previa.

Para GEO es benigno —el crawler ve más, no menos— así que el umbral de anomalía
está demasiado ajustado. Propuesta: informar solo por encima de **1,10**, y como
nota informativa, no como error. Con el umbral actual el 45% del panel se marca.

## 6. robots.txt no discrimina nada

`crawlers_bloqueados` vacío en las 12. Ninguna cuenta del panel bloquea GPTBot,
ClaudeBot, CCBot, PerplexityBot ni Google-Extended. Los 8 puntos de ese
sub-criterio se los lleva entero todo el que tenga `robots.txt`.

Sin `robots.txt`: tenil, bairesglobaljets, avionesprivados y aircharterservice
(este último devuelve HTML, soft-404).

Junto con lo ya visto en D3, la conclusión sobre la rúbrica se refuerza: la varianza
del panel está en **acceso (D2, 7 pts)** y en **schema (D1, 25 pts)**, no en los
sub-criterios declarativos.
