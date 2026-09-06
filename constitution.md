# Constitución — Motor del Índice de Visibilidad IA (Jet MarIA)

Diez principios cortos y verificables. Derivados de §1 de `docs/plan.md`, con los
ajustes que trae la arquitectura de dos herramientas (`maria` en el servidor,
`maria-render` en la notebook, contrato de artefacto entre medio).

1. **Evidencia o silencio.** Ningún puntaje se emite sin al menos un ítem de
   evidencia con URL, timestamp UTC y método (`static` | `rendered` | `robots` |
   `manual`).

2. **Nada del `<head>` sin renderizado real.** `title`, `meta description`,
   `canonical` y `JSON-LD` se leen del HTML crudo (servidor) y del DOM renderizado
   (bundle de `maria-render`); si difieren, se reportan **ambos**.

3. **El núcleo es determinista.** Ningún LLM participa del cálculo del puntaje. El
   scoring vive solo en `maria` (servidor). Dos ejecuciones sobre el mismo fixture
   dan byte a byte el mismo JSON.

4. **Lo no verificado se marca, no se infiere.** Un sub-criterio no comprobable se
   puntúa neutro (mitad del máximo) y se etiqueta `status: unverified`. Enum de
   estado de cuenta: `medido` · `bloqueado` · `inaccesible` · `unverified` ·
   `no_aplica`.

5. **Tests primero, y con fixture congelado.** Ninguna dimensión se implementa
   antes que su test. La suite base de `maria` corre **sin red y sin Playwright**,
   contra `raw.html + robots.txt + render.json` en disco. Los tests que necesitan
   navegador llevan `@pytest.mark.render`; los que tocan la red, `@pytest.mark.network`.
   Ninguno de los dos entra en el CI base.

6. **Rastreo cortés y sin suplantación.** User-agent identificable
   (`MarIA-GEO-Audit/x.y (+https://maria.ar/bot)`), máximo 1 request concurrente
   por dominio, respeto del `Crawl-delay`, sin autenticación ni evasión de
   anti-bot. No se suplanta el crawler de un tercero: la política declarada para
   GPTBot, ClaudeBot, CCBot, PerplexityBot y Google-Extended se lee de `robots.txt`;
   la respuesta real se mide una sola vez, con el UA propio.

7. **Solo datos públicos.** No se almacenan datos personales, no se envían
   formularios, no se guardan cookies de sesión de terceros.

8. **El JSON es la fuente.** Salida canónica versionada con `schema_version`. El
   Markdown y la tabla comparativa se derivan del JSON; nunca al revés. El
   contrato entre las dos herramientas es `render_schema_version`.

9. **Stack acotado.** Python 3.12, `httpx`, `selectolax`, `pydantic`, `typer`,
   `pytest` para `maria`. `playwright` es dependencia **opcional** del perfil
   `render` (notebook) — el servidor no puede correr Chromium (jail LVE) y con
   esta arquitectura no lo necesita. Toda dependencia nueva se justifica.

10. **Un RF, un test que lo nombra.** El identificador del requisito aparece en el
    nombre del test (`test_rf07_...`). La validación final recorre la spec RF por RF.
