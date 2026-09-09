---
name: auditoria-geo
description: Procedimiento para auditar una cuenta con el Índice de Visibilidad GEO Técnico — orden de comprobaciones, herramientas por tipo de dato, formato de la ficha y checklist de verificación cruzada. Usar cuando haya que correr o revisar una auditoría de un sitio del panel de aviación ejecutiva.
---

# Auditoría GEO de una cuenta

El objetivo de esta skill es que **la auditoría número 40 salga igual que la número 1**,
la corra quien la corra. El criterio versionado (esta skill + `constitution.md` +
`docs/decisiones/`) es el producto real; el código es el vehículo.

Antes de empezar: leé `constitution.md` entera y `AGENTS.md`. El scoring es
determinista y vive solo en `maria` — no lo "ajustes" a ojo.

## 1 · Orden de comprobaciones

Siempre en este orden. No saltear pasos aunque parezcan redundantes.

1. **Acceso primero.** ¿El sitio responde al UA propio
   (`MarIA-GEO-Audit/x.y (+https://maria.ar/bot)`)? Un 403/503 → estado `bloqueado`,
   hallazgo crítico, y **se termina la auditoría de puntaje** (D2-acceso = 0, el
   resto queda como está). TLS roto / bucle de redirects / DNS → `inaccesible` con
   `motivo`. Nunca cambiar de UA para "esquivar" el bloqueo: el bloqueo **es** el
   hallazgo (constitución, principio 6).
2. **Doble fetch.** HTML crudo (servidor) + DOM renderizado (bundle de
   `maria-render`, notebook). Si no hay bundle: la corrida sigue, pero todo
   sub-criterio dependiente del DOM va a `unverified` (mitad de puntos), no a 0.
3. **`robots.txt` y Content Signals.** Política declarada para GPTBot, ClaudeBot,
   CCBot, PerplexityBot, Google-Extended. Una Content Signal explícita en `no` para
   `ai-train`/`ai-input` cuenta como bloqueo en D2. La **ausencia** de señal es
   neutra. Un `robots.txt` que solo trae el preámbulo de Content Signals sin una
   sola directiva **no declara política** (caso Modena, verificado 01-09-2026).
4. **Las seis dimensiones**, en orden D1 → D6. Pesos y sub-criterios: `docs/plan.md`
   §2 con las enmiendas de `docs/decisiones/2026-09-01-rubrica.md`.
5. **Clasificación por flujo operativo** (corporativo-industrial / turismo VIP /
   sanitario) — va en la ficha y en la tabla; nunca se compara entre flujos sin
   decirlo.
6. **Hallazgos del analista** (`--analyst-notes`), si los hay: entran con
   `origin: analyst`, aparecen en el informe, **no** mueven el puntaje.

## 2 · Herramientas por tipo de dato

| Dato | Cómo se obtiene | Nunca |
|---|---|---|
| HTML servido, `title`/`meta`/`canonical` crudos | `maria` (fetch estático `httpx`) | inferir del render |
| JSON-LD, nav sin JS, ratio de texto útil | DOM renderizado del bundle, capturado con `wait_until="networkidle"`, timeout 45 s | leer el DOM apenas termina la navegación (cambia el ratio) |
| Política de crawlers de IA | `robots.txt` + Content Signals (dato público) | mandar UA de GPTBot para "probar" |
| Respuesta real al cliente no-navegador | 1 request con el UA propio | repetir hasta que dé 200 |
| Compromiso de respuesta publicado (D5) | regex multiidioma sobre el texto | confundirlo con el tiempo real medido (eso es Paso Cero, RF-21) |

Comando base:

```bash
.venv/bin/maria audit https://ejemplo.com --codigo XXX --nombre "Ejemplo" \
  --render-bundle out/bundles/2026-09-09/            # omitir si no hay notebook
.venv/bin/maria audit ... --md                       # ficha Markdown en vez de JSON
```

## 3 · Formato de la ficha

Se deriva del JSON con `maria report <run.json>` o `maria audit --md` (RF-16, sin
recálculo). La ficha lleva, en este orden:

1. Identidad + `estado` + puntaje total + **tier** (el tier es la conclusión, no el
   número — `docs/plan.md` §8 contra #2).
2. Las seis dimensiones con puntaje/máximo y la evidencia por sub-criterio (URL +
   timestamp UTC + método).
3. Sección **"Sin verificar"** con todos los `unverified` de la corrida (RF-18).
4. Hallazgos ordenados por severidad; los `origin: analyst` intercalados y marcados.
5. Si existe medición de Paso Cero para la cuenta: bloque aparte con el tiempo de
   respuesta real, marcado `origin: analyst`, fuera del puntaje.

## 4 · Checklist de verificación cruzada

Antes de dar una auditoría por buena:

- [ ] `estado` coherente con la evidencia: ningún `medido` sin bundle de render;
      ningún `bloqueado`/`inaccesible` sin hallazgo crítico y `motivo`.
- [ ] `title`/`meta`/`canonical`: si crudo y render **difieren**, la ficha reporta
      **los dos** valores (constitución, principio 2 — la lección de la Fase 2).
- [ ] D1 ≤ 10 si el único schema es boilerplate sin `Organization` con datos (RF-13).
- [ ] Ratio de texto útil > 1,10 → informado como **anomalía**, no como puntaje.
- [ ] Ningún sub-criterio no comprobable puntuado 0: debe ser mitad + `unverified`.
- [ ] La tabla del panel no promedia una cuenta no-`medido` junto a las medidas sin
      decirlo en la misma línea (RF-17).
- [ ] Dos corridas sobre el mismo input → mismo JSON byte a byte. Si no, hay
      no-determinismo colado (constitución, principio 3).
- [ ] Lenguaje del informe: "declara tal política" / "rechaza clientes no-navegador",
      nunca "bloquea a GPTBot" salvo que la política declarada lo diga.
