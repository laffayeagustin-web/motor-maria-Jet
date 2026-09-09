# CLAUDE.md — jet-maria-motor

Motor de auditoría **GEO** determinista para el panel de aviación ejecutiva
(Argentina). Dado un sitio, emite un JSON con puntaje, tier y evidencia citada por
sub-criterio. Es el **motor canónico** del ecosistema (ver `~/CLAUDE.md`).

## Arquitectura: dos herramientas + contrato de artefacto

| CLI | Dónde corre | Qué hace |
|---|---|---|
| `maria` | servidor (cPanel) | fetch estático, `robots.txt`, Content Signals, **scoring determinista**, salida JSON/MD/tabla. No abre navegador. |
| `maria-render` | notebook | renderiza el DOM con Chromium, escribe un *render bundle* que se mueve al servidor y se pasa con `maria panel … --render-bundle`. |
| `maria-respuestas` | servidor | Índice de Visibilidad en **Respuestas** de IA: mide cuánto nombra/cita Gemini (con grounding de Google) a las marcas del panel en frases de la industria. Serie diaria. |

Entry points en `pyproject.toml [project.scripts]`: `maria = maria.cli:app`,
`maria-render = maria_render.cli:app`, `maria-respuestas = maria_answers.cli:app`.

## Setup y tests

```bash
.venv/bin/pip install -e .            # servidor: sin Playwright
.venv/bin/pip install -e '.[render]'  # notebook: + Playwright/Chromium
.venv/bin/pytest                      # suite base: OFFLINE, sin navegador
.venv/bin/pytest -m render            # captura real (notebook)
.venv/bin/pytest -m network           # integración contra dominios de control
```

`addopts = -m 'not render and not network'` — la suite base nunca toca red ni
Chromium.

## Artefactos SDD

`constitution.md` (principios) · `spec.md` (RF-01…RF-21 + RR-01…RR-27 en EARS) ·
`AGENTS.md` (contexto permanente) · `docs/plan.md` (plan + rúbrica + tareas) ·
`docs/decisiones/` (decisiones de rúbrica congeladas) ·
`.claude/skills/auditoria-geo/SKILL.md` (procedimiento de auditoría). Requisito
nuevo → se actualiza `spec.md` y se muestra el diff **antes** de tocar código.
Decisiones que cruzan repos: `~/DECISIONES.md`.

## Reglas del proyecto (de `constitution.md` — leerla entera antes de tocar scoring)

- **Evidencia o silencio:** ningún puntaje sin URL + timestamp UTC + método.
- **Núcleo determinista:** ningún LLM en el cálculo del puntaje; el scoring vive
  solo en `maria`; misma fixture → mismo JSON byte a byte.
- **Lo no verificado se marca, no se infiere:** sub-criterio no comprobable →
  puntaje neutro (mitad) + `status: unverified`. Estados de cuenta: `medido` ·
  `bloqueado` · `inaccesible` · `unverified` · `no_aplica`.
- **Tests primero, fixture congelado.**
- **Crawling cortés:** UA `MarIA-GEO-Audit/x.y (+https://maria.ar/bot)`, 1 request
  concurrente por dominio, respeta `Crawl-delay`, sin evasión de anti-bot, **sin
  suplantar** a GPTBot/ClaudeBot/CCBot/etc.
- **El JSON es la fuente:** el Markdown y la tabla se derivan del JSON, nunca al revés.
- **Stack acotado:** Python 3.12 + `httpx`, `selectolax`, `pydantic`, `typer`,
  `pytest`. Playwright solo en el perfil `render`. Toda dependencia nueva se justifica.
- **Un RF, un test que lo nombra:** el ID del requisito va en el nombre del test
  (`test_rf07_…`).

## Cosas a saber

- **Fixtures fuera de git:** `raw.html`, `rendered.html`, `robots.txt`, `render.json`
  están gitignoreados (contenido de terceros). Se versiona solo `MANIFEST.json`. Un
  clon nuevo **recaptura antes** de correr la suite base. **No** "arreglar" tests
  commiteando HTML ajeno.
- **La rúbrica core suma 95 (+5 de bonus), no 100** — es intencional (D1 25 + D2 20
  + D3 20 + D4 15 + D5 15). Los tiers se aplican sobre el core.
- `docs/prototipo/` (`geo_probe.py`, etc.) **no es el motor**.
- `~/mariarepo/jet-maria/` es un intento viejo — **no usar**, este repo es el vigente.
- `tools/cron-respuestas.sh` **no está instalado** en el crontab hasta congelar el
  panel y medir el costo real de Gemini. No instalarlo sin OK explícito.
- Decisiones congeladas en `docs/decisiones/` (`2026-09-01-rubrica.md`,
  `2026-09-01-scoring-panel.md`, `2026-09-06-rubrica-respuestas.md`, …).

## Relación con otros repos

`src/` de este repo se copia (vendoriza) a
`~/indice-de-posicionamiento-en-la-IA/src/{maria,maria_answers,maria_common}`. Los
dos divergen a propósito — ver `VENDOR.md` en ese repo. Un fix acá **no** se
propaga solo.
