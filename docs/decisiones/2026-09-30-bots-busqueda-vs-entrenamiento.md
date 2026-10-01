# Bots de búsqueda/uso en vivo aparte de los de entrenamiento en D2 — decisión del 30-09-2026

**Alcance:** `src/maria/fetch/robots.py`, `src/maria/probes/d2_access.py`.
Agrega **RF-23** a `spec.md`. No toca `RF-03`/`RF-04`/`RF-22`, no cambia el
puntaje de D2.1 ni `schema_version`.

---

## El hallazgo

Un review externo (otra IA) de la auditoría real de `bikeexplorer.bike`
(29-09-2026,
`https://maria.ar/auditoria-geo-tecnica/r/bikeexplorer-bike-9f5851/`) señaló
algo real: el veredicto INVISIBLE de esa corrida sale de un 403 al fetch
propio (D2.2) combinado con que `robots.txt` bloquea explícitamente a
GPTBot/ClaudeBot/CCBot/Google-Extended (D2.1). Pero esos cuatro (más
PerplexityBot) son bots de **entrenamiento/índice** — bloquearlos impide que
el contenido entre al próximo entrenamiento de un modelo, pero no dice nada
sobre si `ChatGPT-User`/`Claude-User`/`Perplexity-User`/`OAI-SearchBot`
(los que efectivamente buscan y responden *en vivo*, por pedido de un usuario
real) pueden leer el sitio ahora mismo. El review lo resumió bien: *"un
diagnóstico más preciso sería 'accesible para agentes de búsqueda y de
usuario, con bloqueo a crawlers de entrenamiento en robots.txt'"*.

`AI_CRAWLERS` en `fetch/robots.py` ya documentaba el rol de los 11 bots
conocidos en comentarios desde el 01-09-2026 (`docs/decisiones/2026-09-01-rubrica.md`),
pero `D2.1` solo puntuaba 5 (los de entrenamiento/índice: `D2_CORE_CRAWLERS`)
y el informe no decía nada de los otros 6.

## La segunda parte del review — evaluada y descartada

El review también sugería confirmar esto con un chequeo cruzado:
`curl -A "OAI-SearchBot"`, `curl -A "Claude-User"`, etc. — literalmente
mandar el request con el user-agent de esos bots. **Es la misma pregunta que
ya se resolvió el 10-09-2026 para `animalcargo.com`**
(`docs/decisiones/2026-09-10-headers-de-request.md`): ahí también se preguntó
si convenía suplantar el UA de GPTBot/Google-Extended para pasar un 403, y se
resolvió que no — el principio 6 no admite mandar un user-agent de un
crawler de terceros. Ese archivo queda como la referencia: si esto se vuelve
a preguntar, releerlo primero.

Se consultó con el usuario si quería reabrir el principio 6 para este caso
puntual, primero como herramienta de diagnóstico manual (uso interno, fuera
de la auditoría pública) y, al insistir, como **sonda dentro de la auditoría
pública** (correr en cada corrida, para cualquier visitante). Se explicó el
motivo del rechazo y **no se implementó ninguna de las dos**:

1. **Suplanta a terceros ante un cuarto.** Mandar `User-Agent: OAI-SearchBot`
   sin ser OpenAI es afirmarle una identidad falsa al sitio auditado — y, de
   rebote, a OpenAI/Anthropic/Perplexity, cuyo nombre se usa sin autorización.
2. **Ensucia los logs de un tercero que no consintió nada.** El dueño del
   sitio auditado (ni siquiera es cliente de maria.ar, muchas veces es un
   prospecto que llenó un formulario) termina con tráfico de maria.ar
   atribuido en sus logs de seguridad a otra empresa.
3. **No da una señal confiable.** Un WAF que verifica el bot por IP/reverse-DNS
   (Cloudflare, muchos hostings serios lo hacen) sigue bloqueando el UA
   falsificado igual que al UA propio — no prueba nada. Uno que no verifica
   nada y confía ciegamente en el string del User-Agent da un "sí entra" que
   tampoco certifica cómo se comporta el bot real. En ambos casos el
   resultado es ruido, no evidencia — lo que la rúbrica del motor exige
   evitar ("evidencia o silencio", constitution.md).
4. **A escala, no a mano.** Como sonda de cada auditoría pública, el efecto
   del punto 2 se multiplica por cada dominio que llegue al formulario del
   funnel self-serve — no es un experimento de una vez de Agustín, es una
   conducta del producto contra cualquier tercero.

**El principio 6 no se toca.** Sigue prohibiendo mandar un user-agent de un
crawler de terceros, sin excepción para este caso.

---

## Qué cambia (lo que sí se hace)

Puramente aditivo e informativo: usa el `robots.txt` que D2.1 **ya**
descarga, sin ningún request nuevo, sin tocar el puntaje.

- `fetch/robots.py`: `D2_LIVE_CRAWLERS = ["OAI-SearchBot", "ChatGPT-User",
  "Claude-User", "Perplexity-User"]`. `blocked_ai_crawlers()` gana un
  parámetro `crawlers` (default `D2_CORE_CRAWLERS`, retrocompatible) para
  reusarse con la lista nueva.
- `probes/d2_access.py`: cuando `robots.txt` se pudo leer (rama `else` de
  D2.1), se agrega un `Finding(severidad="informativa", dimension="D2", ...)`
  aparte, indicando si bloquea o no a los 4 bots de búsqueda/uso en vivo.
  `D2.1` sigue puntuando exactamente igual (8 pts, solo los 5 núcleo).

## Qué NO cambia

- El puntaje de D2.1/D2.2, el veredicto VISIBLE/INVISIBLE (GE-17 del funnel)
  y el tier absoluto: ningún número se mueve.
- `RF-03`/`RF-04`: la política de request sigue igual.
- No hay ningún request nuevo contra el sitio auditado — mismo `robots.txt`
  de siempre, un parseo más.

## Cambios asociados

| Dónde | Qué |
|---|---|
| `src/maria/fetch/robots.py` | `D2_LIVE_CRAWLERS`; `blocked_ai_crawlers(crawlers=...)`. |
| `src/maria/probes/d2_access.py` | Finding informativo nuevo, D2.1 sin cambios. |
| `spec.md` RF-23 | Este requisito. |
| `tests/test_rf23_bots_busqueda.py` | Bloqueo, no-bloqueo, y que D2.1 no se mueve. |
| `tests/test_rf06_13_probes.py` | `test_rf07_d2_robots_abierto_puntua_pleno` actualizado: ahora hay un finding informativo incluso con `robots.txt` totalmente abierto. |
| Funnel (`~/indice-de-posicionamiento-en-la-IA`) | Re-sync dirigido de los dos archivos (`VENDOR.md`); `pages.py::_politica_robots` extendido para mencionar esto en la caja de "bloqueado" (GE-20 del funnel). |
