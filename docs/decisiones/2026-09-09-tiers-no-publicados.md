# Los tiers salen de las páginas públicas — decisión del 09-09-2026

**Alcance:** las cuatro páginas del panel sectorial que genera `tools/build_pages.py`
— Índice de Visibilidad GEO Técnico (`indice-GEO-tecnico`, `indice-GEO-tecnico-es`) e
Índice de Visibilidad en Respuestas (`indice-respuestas-ia`, `indice-respuestas-ia-ar`).
Toca la rúbrica congelada (`2026-09-01-rubrica.md` §Tiers, `2026-09-06-rubrica-respuestas.md`),
`spec.md` (RF-14, RF-15, RF-17, RR-12, RR-18 + nuevo RF-22) y `~/DECISIONES.md` §7.
**No** toca el funnel self-serve (decisión de alcance del 09-09).

Reemplaza el texto de §2 «Tiers» de `docs/plan.md` y la línea de tiers de
`2026-09-01-rubrica.md`.

---

## Qué cambia

### 1 · Las páginas del panel sectorial no muestran tier

La tabla de ranking y los acordeones por cuenta de las cuatro páginas públicas
muestran **puntaje /100, desglose por dimensión, evidencia y hallazgos**. Se saca la
columna «Tier», el `<span class="tier …">` de cada fila y de cada acordeón, y la
leyenda de tiers. La palabra «tiers» sale del texto de «Metodología».

*Por qué está en una decisión y no solo en el código:* cambia lo que un tercero con
nombre y apellido lee sobre sí mismo en una URL pública. «Invisible» es una palabra
editorial pegada a una empresa; un puntaje con desglose por dimensión es un dato
verificable contra la rúbrica publicada. La transparencia del método convierte la
objeción de un operador en credibilidad; una etiqueta de veredicto la convierte en
un agravio. Es el mismo argumento del contraargumento 2 del plan de los agentes
(`~/maria-agentes/docs/outbound-mitigaciones.md`).

### 2 · El tier absoluto sigue en el JSON por cuenta

`AuditRun.tier` (`Invisible/Parcial/Emergente/Líder GEO`, cortes 0–29/30–54/55–74/75–100
sobre el core) y `MarcaRun.tier` (`Ausente/Marginal/Presente/Referencia`) **no se
tocan**. Siguen en la salida JSON, en el Markdown por cuenta y en el histórico.

*Por qué:* tres consumidores dependen de él y ninguno es una página pública del panel:
el funnel self-serve lo muestra para el **sitio propio del visitante** (N=1, no es un
tercero); el delta del histórico usa «caída de tier» (RF-19); y el agente Triage lo
usa como señal de regresión (`~/maria-agentes` constitución §2, AG-05). Es un valor
absoluto, determinista y por cuenta — sacarlo del contrato rompería a los tres sin
resolver nada del problema, que es la **publicación**, no el cálculo.

### 3 · La tabla comparativa interna lleva un cuartil relativo al panel, no el tier absoluto

`maria panel` y `maria-respuestas` (la tabla comparativa Markdown, RF-17 / RR-18 —
**entregable interno**, no una página pública) reemplazan la columna de tier absoluto
por un **cuartil de ranking**:

- Las cuentas del panel en estado `medido` o `unverified` se ordenan por puntaje
  descendente, con desempate por `codigo` (misma regla que RR-13).
- Se reparten en cuatro bloques de ~25 % **por posición**, no por distancia de
  puntaje. Regla de corte determinista: la cuenta de rank *r* (1-indexado) sobre *n*
  cuentas cae en el cuartil `floor((r-1) · 4 / n) + 1`.
- Etiquetas neutras: **Q1 (cuarto superior)** … **Q4 (cuarto inferior)**. Los nombres
  editoriales (`Invisible`, …) no se usan en ningún contexto comparativo.
- `bloqueado`, `inaccesible` y `no_aplica` quedan fuera del cálculo (ya quedaban
  fuera del ranking, enmienda §4) y se listan aparte sin cuartil.

*Por qué el cuartil y no una normalización lineal min–máx:* el uso es de prospección
—«¿dónde cae este operador respecto de los demás?»— y ahí importa la posición, no la
distancia. El cuartil es insensible a un outlier (una cuenta que puntúa 12 no aplasta
la escala de las otras nueve) y no necesita fijar anclas. *(El pedido original hablaba
de «según el máximo y el mínimo»; se eligió el cuartil por ranking sobre las opciones
con preview el 09-09 — sirve mejor al caso de prospección.)*

*Por qué está en la decisión y no en el código:* define cómo la gente de prospección
prioriza a quién contactar. Un corte por ranking y un corte por puntaje dan listas de
objetivos distintas.

---

## En contra (el contraargumento más fuerte)

1. **Un cuartil relativo no es reproducible por cuenta.** El cuartil de una cuenta
   cambia si entra o sale otra cuenta del panel, o si cualquiera se mueve de puesto
   entre dos corridas. Eso contradice el espíritu del principio 3 («misma entrada →
   mismo JSON»). *Mitigación:* el cuartil **no entra** en el JSON por cuenta ni en el
   histórico; vive solo en la tabla comparativa, que es función pura del conjunto de
   corridas del panel en esa fecha (determinismo a nivel panel, igual que RR-13). El
   dato reproducible por cuenta —el puntaje y el tier absoluto— no se toca.

2. **Sacar el tier debilita el gancho comercial.** «South American Jets: Emergente»
   entra por los ojos; «65,4 / 100» necesita contexto. Se pierde impacto en la
   página pública. *Contra-mitigación:* el impacto se recupera en el material que no
   es público — la ficha que la gente de prospección manda por privado, donde el
   cuartil y la comparación sí van (`~/maria-agentes/docs/outbound-mitigaciones.md`,
   mitigación 3). La página pública gana en defendibilidad lo que pierde en golpe.

3. **Dos escalas de tier para el mismo índice** (el absoluto por cuenta + el cuartil
   del panel) es una complejidad nueva y una fuente de confusión: alguien va a citar
   «Q4» y «Invisible» como si fueran lo mismo. *Mitigación:* etiquetas deliberadamente
   distintas (`Q1..Q4` vs. nombres), y el cuartil solo aparece en un artefacto
   —la tabla comparativa— que nunca se comparte fuera del equipo.

4. **El criterio de calibración de T0 apuntaba a los tiers.** `docs/plan.md` §2 pedía
   «qué dos cuentas del panel AR deben quedar en los extremos». Con un cuartil por
   ranking los extremos son Q1 y Q4 por definición y ese criterio se diluye.
   *Mitigación:* la calibración real (finalización §5 de `spec.md`) siempre fue sobre
   el **puntaje** (desvío ≤ 8 pts contra el scoring manual), no sobre la etiqueta.
   Ese criterio sobrevive intacto; se reescribe solo la frase de §2 que hablaba de
   «extremos» de tier.

---

## Lo que queda abierto

- El nombre exacto de la columna en el Markdown (`Cuartil`, `Q`, `Posición`).
- Si la ficha por cuenta del entregable interno muestra además la **posición
  numérica** (`#4 de 10`) junto al cuartil.
- Si el Índice de Respuestas, con menos cuentas por panel (a veces < 8), usa cuartiles
  o cae a terciles / mitades cuando `n` es chico. *Propuesta:* con `n < 8`, mitades
  (Q1–Q2 = mitad superior, Q3–Q4 = inferior); se decide al primer panel real chico.

---

## Cambios asociados

| Dónde | Qué |
|---|---|
| `spec.md` RF-14 | El tier absoluto se calcula pero **no se publica** en el panel sectorial. |
| `spec.md` RF-15 | El JSON por cuenta sigue llevando `tier` (sin cambio de `schema_version`). |
| `spec.md` RF-17 | La tabla comparativa lleva **cuartil de ranking**, no tier absoluto. |
| `spec.md` **RF-22** (nuevo) | Define la clasificación por cuartiles y su regla de corte determinista. |
| `spec.md` RR-12 | El tier de Respuestas sigue en el JSON por marca; no se publica en el panel. |
| `spec.md` RR-18 | La tabla de panel de Respuestas lleva el cuartil. |
| `docs/plan.md` §2 «Tiers» | Se reescribe: cortes absolutos (uso interno / funnel) + cuartil del panel (tabla interna) + nada en la página pública. |
| `src/maria/scoring/tiers.py` | Nueva función `cuartiles_panel(...)`; `TIERS`/`tier_for` quedan como están. |
| `src/maria/report/panel_table.py` | Columna cuartil en vez de `r.tier`. |
| `src/maria_answers/report.py` | Ídem para la tabla de Respuestas. |
| `tools/build_pages.py` | Se saca todo `<span class="tier">`, la columna «Tier», la leyenda y la palabra «tiers» del texto de Metodología — en las dos familias de página. |
| `~/DECISIONES.md` §7 | Entrada nueva (decisión que cruza motor + páginas LIVE + nota de re-sync al funnel). |
| Producción | Rebuild de las 4 páginas + copia a `public_html/` + `wp litespeed-purge all`. Paso aparte, con OK explícito (footgun 3 de `~/CLAUDE.md`). |
| `~/indice-de-posicionamiento-en-la-IA/VENDOR.md` | Nota: el próximo re-sync trae `scoring/tiers.py` y `report/panel_table.py` cambiados; el funnel no llama a `cuartiles_panel` y su `pages.py` es propio, así que el efecto es nulo — pero queda anotado.
