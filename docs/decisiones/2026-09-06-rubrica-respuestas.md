# Rúbrica del Índice de Visibilidad en Respuestas de IA — decisiones del 06-09-2026

Siete decisiones cerradas a partir de la sonda de Fase 0 sobre el panel de
aviación ejecutiva ES (10 frases, 1 corrida + 5 pasadas de varianza,
2026-09-06). **Esto es lo que se congela antes de escribir el motor.**

Índice distinto del Índice GEO Técnico: aquél audita el sitio, éste mide la
respuesta. No comparten rúbrica, ni tiers, ni panel.

Capturas crudas de la sonda: `out/fase0/` (10 respuestas + `varianza/`, 5 pasadas
de la misma frase).

---

## 1 · La superficie es Gemini con grounding, no AI Overviews

Se descartó medir AI Overviews con medios propios: se inyectan por JavaScript,
Chromium no arranca en este servidor (`docs/plan.md` §7,
`pthread_create: Resource temporarily unavailable`), la IP del hosting ya come 403
de sitios comunes, y sobre todo **scrapearlos exige la evasión de anti-bot que el
principio 6 prohíbe** — el mismo principio por el que se reescribió D2.2 para no
suplantar a GPTBot.

Se mide entonces la **API de Gemini con la herramienta `google_search` activada**:
es oficial, la clave ya existe en el servidor, y devuelve el texto de la respuesta
junto a las fuentes que la respaldan.

**Límite que el informe debe respetar.** Una marca ausente de las respuestas de
Gemini **no** es una marca ausente de ChatGPT, de Perplexity, de Copilot ni de los
AI Overviews de Google. El informe puede afirmar *"no aparece en las respuestas de
Gemini con búsqueda para estas 10 frases"*. Nada más amplio. Las propuestas
comerciales que prometen "menciones en ChatGPT, Perplexity, Gemini, Copilot y AI
Overviews" están cubiertas en **una** de las cinco superficies.

## 2 · El dominio de la fuente se lee de `web.title`, no de la URI

*Por qué está en la rúbrica y no en el código:* define qué cuenta como "una cita",
que es el 40 % del puntaje.

Todas las URIs de `groundingChunks[].web.uri` son redirecciones opacas de
`vertexaisearch.cloud.google.com/grounding-api-redirect/...`. Parsear el host de
esa URI devuelve siempre el dominio de Google y **cero citas para todo el panel**
— es exactamente el resultado que dio la primera pasada de la sonda: `0/15` marcas
con cita.

El dominio real de la fuente viene en `groundingChunks[].web.title`, literal:
`gestair.com`, `initium-aviation.com`, `lunajets.com`, `unitedaviation.es`.
Releyendo las mismas capturas con ese campo, el resultado pasó a `9/15`.

> **Definición de cita (R2):** una marca está citada en una frase cuando alguno de
> sus `dominios` declarados aparece en `groundingChunks[].web.title`, normalizado a
> minúsculas y sin `www.`, comparando por igualdad exacta o como sufijo de
> subdominio (`x == d` o `x.endswith("." + d)`).

## 3 · R1 y R2 se mantienen separadas, aunque a nivel panel converjan

Sobre las 10 frases, mención y cita dieron **el mismo conjunto de 9 marcas**. Se
mantienen igual separadas porque **por frase sí divergen**, y la puntuación se
calcula por frase:

| frase | mención | cita |
|---|---|---|
| G3 | AEA, LUN, FLP, GST | AEA, **ALB**, LUN, FLP, GST |
| G4 | — | LUN, FLP |
| L1 | — | LUN |
| L2 | — | AEA |
| L3 | — | AEA, LUN |

Cuatro frases citan marcas sin nombrarlas. Colapsar las dos señales perdería esas
cuatro observaciones y, con ellas, la distinción comercialmente interesante entre
"la IA te nombra" y "la IA se apoya en tu sitio".

**Consecuencia para el informe:** la discriminación entre marcas no viene de
*cuáles* aparecen —mención y cita coinciden— sino de *en cuántas frases*. El
informe no presenta R1 y R2 como si ordenaran distinto el panel.

## 4 · La cobertura se publica siempre, aunque hoy dé 10/10

Las 10 frases dispararon búsqueda real (`webSearchQueries` no vacío en las 10;
32 búsquedas ejecutadas en total, entre 2 y 5 por frase). Cero errores.

No se elimina el estado `sin_busqueda` ni el denominador variable: la cobertura es
propiedad del mercado y de la fecha, no del motor, y puede caer. Además vale por sí
sola como dato — dice cuánto de la industria se responde consultando la web.

```
puntaje = 100 × (puntos obtenidos / puntos alcanzables en frases con_busqueda)
```

## 5 · El matching es por dominio exacto y el nombre necesita lista de exclusión

*Por qué está en la rúbrica:* es el único lugar donde este índice puede producir un
número falso con toda la apariencia de ser correcto.

**Caso real encontrado en la sonda.** El dominio más citado fuera del panel fue
`globalcharter.com` (4 de 10 frases). El panel tiene `global-charters.com`. Se
verificaron los dos:

| dominio | title | qué es |
|---|---|---|
| `global-charters.com` | "Broker aéreo. Alquiler de aviones, jets y helicópteros" | el broker **español** del panel |
| `globalcharter.com` | "Private Jet Charter \| Luxury Jet Hire \| Global Charter" | una compañía **británica distinta** |

Un matching laxo por nombre ("Global Charter") le habría acreditado a la marca
española 4 frases que en realidad citan a una competidora británica.

Reglas que se congelan:

- **Dominio:** igualdad exacta o sufijo de subdominio. Nunca subcadena.
- **Nombre:** sobre texto normalizado (minúsculas, sin acentos) y **con límites de
  palabra** (`\b`). Nunca subcadena.
- Cada marca declara `alias` (variantes legítimas) y `excluir` (trampas conocidas).
- Trampa ya identificada y pendiente de excluir: **`Air TXT` contra el texto "air
  taxi"**, que normalizado colisiona.

## 6 · El panel de respuestas se siembra desde las citas reales, no desde el panel técnico

El panel ES del Índice GEO Técnico **no sirve tal cual** para este índice. La sonda
lo demuestra dos veces:

- **6 de 15 marcas del panel son invisibles** en las 10 frases, ni mención ni cita:
  `ATX`, `AUR`, `EEJ`, `GCH`, `IJE`, `JFE`.
- Se citaron **49 dominios distintos**, y los más frecuentes no están en el panel:
  `globalcharter.com` (4), `europair.com` (3), `aircharterservice.es` (3),
  `elgaviation.com` (3), `unitedaviation.es` (2), `jetapp.es` (2),
  `netjets.com` (1).

Decisión: el paso `proponer` **no le pregunta a un LLM quiénes son los
competidores**. Corre primero las 10 frases y toma como candidatos los dominios más
citados; el LLM solo redacta y agrupa, y un humano aprueba. Los competidores salen
de la evidencia, no de la memoria del modelo.

Los dos paneles pueden compartir marcas, pero son listas distintas y se mantienen
por separado.

## 7 · Margen de ruido declarado: la señal del panel es estable, la cola no

Cinco pasadas de la misma frase (`"operadores de aviación ejecutiva en España"`),
`temperature: 0`, seguidas:

| | pasada 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| palabras | 367 | 272 | 289 | 326 | 333 |
| chunks | 8 | 7 | 7 | 8 | 9 |
| mención | CLJ, GST | CLJ, GST | CLJ, GST | CLJ, GST | CLJ, GST |
| cita | CLJ, GST | CLJ, GST | CLJ, GST | CLJ, GST | CLJ, GST |

**Las marcas del panel salieron idénticas en las 5 pasadas.** La varianza vive en
lo que no se puntúa: la prosa (272–367 palabras) y la cola de fuentes (solo 4 de 9
dominios aparecieron en las 5).

Eso hace creíble una serie diaria. Pero la muestra es **una frase y dos marcas
fuertes**: una marca al margen puede parpadear. Por lo tanto se congela igual:

- Se publica **media móvil de 7 días** junto al valor del día.
- **No se interpreta el delta de una sola corrida** — el informe no puede atribuir
  un movimiento de un día a una causa.
- La varianza se vuelve a medir cuando cambie el modelo (hoy `gemini-2.5-flash`).

**El modelo y su versión son parte de la definición de la métrica**, igual que
`networkidle` lo es de D3 en el índice técnico: la serie solo es comparable
mientras no cambien. Un cambio de modelo se registra como corte de serie.

---

## Lo que queda abierto

- El costo real por corrida diaria. La sonda ejecutó 32 búsquedas para 10 frases
  (facturables), pero no se confirmó contra el saldo de la cuenta.
- El umbral de `pos_rel` para R3 está definido como escala lineal, sin evidencia
  todavía de que discrimine. Revisar tras la primera semana de serie.
- Las 10 frases de la sonda son un borrador propio, no salieron del paso
  `proponer`. El panel piloto definitivo se arma con la decisión 6.
