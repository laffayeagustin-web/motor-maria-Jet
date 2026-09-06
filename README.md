# Jet MarIA — Motor del Índice de Visibilidad IA

Motor de auditoría GEO para el panel de aviación ejecutiva (Argentina), partido en
**dos herramientas** con un contrato de artefacto entre medio:

| Herramienta | Dónde corre | Qué hace |
|---|---|---|
| **`maria`** | servidor (cPanel/CloudLinux) | fetch estático, `robots.txt`, Content Signals, scoring determinista, salida JSON/Markdown/tabla. **No abre navegador.** |
| **`maria-render`** | notebook | renderiza el DOM con Chromium y extrae todo lo que necesita un navegador (JSON-LD renderizado, ratio de texto, formularios, precio en pantalla, `navigator.modelContext`, enlaces del footer). Escribe un *render bundle*. |

El plan completo está en [`docs/plan.md`](docs/plan.md); la rúbrica congelada y las
decisiones, en [`docs/decisiones/`](docs/decisiones/); la constitución del proyecto
en [`constitution.md`](constitution.md).

## Instalación

```bash
python3.12 -m venv .venv

# servidor: NO instala Playwright
.venv/bin/pip install -e .

# notebook: agrega Playwright + Chromium
.venv/bin/pip install -e '.[render]'
.venv/bin/playwright install chromium
```

## Flujo notebook → servidor (handoff por artefacto)

```bash
# 1) NOTEBOOK — capturar el render bundle
maria-render --panel panels/panel-ar.yaml --out bundle/2026-09-05/ --keep-html --concurrency 1

# 2) mover bundle/2026-09-05/ al servidor (scp, git, carpeta compartida)

# 3) SERVIDOR — auditar
maria panel panels/panel-ar.yaml --render-bundle bundle/2026-09-05/
#   -> out/report/<COD>.json + <COD>.md + panel.md
#   -> out/runs/<COD>/<timestamp>.json  (histórico, para el delta de RF-19)
```

Sin `--render-bundle`, o con un bundle parcial, las cuentas sin entry quedan
`unverified` y los sub-criterios que dependen del DOM se puntúan a mitad (RF-02 /
principio 4). La corrida nunca rompe por falta de render.

### Una sola URL

```bash
maria audit https://argentina-fly.com --codigo AFL --render-bundle bundle/2026-09-05/
maria audit https://argentina-fly.com --codigo AFL --md          # informe Markdown
```

### Hallazgos del analista (RF-20)

```bash
maria panel panels/panel-ar.yaml --analyst-notes notas.yaml
```

```yaml
# notas.yaml
cuentas:
  AFL:
    hallazgos:
      - severidad: alta
        dimension: D5
        detalle: "El 'cotizador' es un formulario de contacto, no cotiza."
    tiempo_respuesta_pasocero: "3 min"   # RF-21, no entra al puntaje
```

## Modo alternativo: Chromium remoto (sin mover archivos)

`maria-render --ws ws://127.0.0.1:9223/jet-maria` usa un Chromium remoto en vez de
uno local y escribe el mismo bundle. Requiere un `chromium.launchServer()` en la
notebook + túnel SSH reverso. El flujo por defecto y el de CI es el handoff por
archivo.

## Tests

```bash
.venv/bin/pytest                       # suite base: sin red, sin Playwright
.venv/bin/pytest -m render             # captura real (notebook, con Chromium)
.venv/bin/pytest -m network            # integración contra dominios de control
```

## Fixtures fuera de git

El `.gitignore` deja fuera `raw.html`, `rendered.html`, `robots.txt` y
`render.json` (contenido de terceros). Se versiona solo el `MANIFEST.json` de cada
corrida. **Un clon nuevo recaptura antes de correr la suite base contra fixtures
reales.** Los fixtures sintéticos de modo de fallo (`tests/fixtures/_sintetico/`) sí
se versionan: son la forma de nuestro propio registro de error, sin contenido ajeno.

## Nota sobre el máximo de la rúbrica

Los sub-criterios de §2 suman **95** en el core (D1 25 + D2 20 + D3 20 + D4 15 +
D5 15), no 100 — el texto del plan dice "100 + 5 de bonus" pero la suma real es 95
+ 5. El motor respeta la suma de los sub-criterios (igual que el scoring manual de
`docs/decisiones/2026-09-01-scoring-panel.md`). Los tiers se aplican sobre el core.
