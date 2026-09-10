# El crawler manda headers de request estándar — decisión del 10-09-2026

**Alcance:** `src/maria/fetch/static.py`. Enmienda el **principio 6** de
`constitution.md` y **RF-04** de `spec.md`. No toca scoring, rúbrica ni
`schema_version`.

---

## El hallazgo

Un visitante del funnel GEO self-serve auditó `animalcargo.com` y obtuvo
`estado: bloqueado` — *"el servidor respondió 403 a un cliente identificado y
no-navegador"*. Se preguntó si convenía **suplantar** el user-agent de GPTBot /
Google-Extended para pasar ese bloqueo.

Investigación (10-09-2026, desde la misma máquina que corre el funnel):

| cliente | resultado |
|---|---|
| `curl` (UA propio de MarIA) | **200** |
| `wget` (UA propio de MarIA) | **200** |
| `httpx` + UA propio de MarIA | **403** |
| `httpx` + UA de navegador (Chrome), sin otros headers | **403** |
| `httpx` + UA propio + `Accept: text/html,…` | **200** |
| `httpx` + UA propio + `Accept-Language` | **200** |

- **No es la IP** (curl/wget entran desde la misma IP).
- **No es el user-agent** (httpx con UA de navegador también da 403).
- **Es la forma del request.** `fetch()` mandaba solo `User-Agent`; httpx completa
  con sus defaults (`accept: */*`, `accept-encoding: gzip, deflate`). El CDN de
  Hostinger (`server: hcdn`) tiene una regla cruda que marca **exactamente** ese
  perfil (sin `Accept` explícito ni `Accept-Language`) como bot. Cualquier header
  de negociación de contenido adicional lo desactiva.

Verificado que agregar `Accept` + `Accept-Language` **no cambia nada** en sitios
que ya respondían bien: `maria.ar`, `example.com`, `www.iana.org` devuelven el
mismo status y el mismo body byte a byte.

---

## Qué cambia

`fetch()` (y por herencia `fetch_text()`) manda siempre:

```
User-Agent:      MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)   (sin cambio)
Accept:          text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7
Accept-Language: es,en;q=0.8
```

El `Accept` cubre HTML + XML (sitemaps) + plain (robots.txt / llms.txt) + `*/*`,
así sirve igual para la página y para `fetch_text`.

El parámetro `ua=` sigue overrideando solo el `User-Agent`.

---

## Por qué NO es evasión de anti-bot (principio 6)

1. **La identidad no se toca.** El `User-Agent` sigue siendo `MarIA-GEO-Audit` con
   URL de contacto. No nos hacemos pasar por un navegador ni por el crawler de un
   tercero.
2. **Son headers que manda todo cliente HTTP real.** `curl`, `wget`, cualquier
   navegador, cualquier librería HTTP seria mandan `Accept`. No mandarlos es el
   error, no mandarlos es lo anómalo.
3. **No hay iteración contra el filtro.** Se manda un set fijo y estándar. No se
   prueban variantes hasta pasar, no se adapta al WAF de cada sitio.
4. **No se cruza ninguna otra línea:** no se resuelven challenges de JavaScript, no
   se rota IP, no se suplanta la firma TLS de un navegador (`curl_cffi` y similares
   quedan explícitamente fuera), no se mandan cookies de sesión.

El principio 6 pasa a decirlo con todas las letras: request **completo** e
identificado, y el límite explícito de qué NO se hace.

---

## En contra (el contraargumento más fuerte)

**"Cualquier tuneo de headers para pasar un filtro de bots es, por definición,
evasión."** Si el criterio es "medir exactamente lo que ve el request más
mínimo posible", entonces agregar `Accept` ya es demasiado.

*Mitigación:* el criterio no es ese. El objetivo del motor es medir **si un
cliente HTTP legítimo y bien comportado puede leer el sitio** — y un cliente
legítimo manda `Accept`. Un request sin `Accept` no es "más honesto", es
incompleto: modela mal al universo de clientes que importan (navegadores, curl,
y con alta probabilidad los crawlers de IA, que no son librerías Python
default). El costo de quedarse con el request pelado es concreto y ya se pagó:
un **falso `bloqueado`** que le dice al dueño de animalcargo.com "bloqueás a los
crawlers" cuando su sitio responde 200 a curl. Eso desinforma; es peor que el
riesgo de la enmienda.

---

## El límite del informe no cambia

Un 403/503 al request **completo** sigue siendo `estado: bloqueado`, D2.2 = 0/7,
hallazgo crítico. El informe sigue sin poder afirmar «bloquea a GPTBot» salvo
que `robots.txt` lo diga — puede decir «rechaza a un cliente HTTP identificado y
con request estándar».

---

## Cambios asociados

| Dónde | Qué |
|---|---|
| `src/maria/fetch/static.py` | `DEFAULT_HEADERS` (UA + Accept + Accept-Language); `fetch()` los manda. |
| `constitution.md` §6 | Enmienda: request completo estándar + límite explícito (sin challenges / IP / TLS). |
| `docs/plan.md` §6, rúbrica D2.2(b) | Espejo de la enmienda. |
| `spec.md` RF-03, RF-04 | "request completo e identificado"; RF-04 nombra `Accept`/`Accept-Language`. |
| `tests/test_rf01_04_05_fetch.py` | El request lleva `Accept` y `Accept-Language`; `ua=` sigue overrideando el UA. |
| Funnel (`~/indice-de-posicionamiento-en-la-IA`) | Re-sync de `static.py`; copia del estado `bloqueado` sin overclaim. Ver `~/DECISIONES.md`. |
| Paneles sectoriales | Modena y otros marcados `bloqueado`/`inaccesible` por esto podrían reclasificarse — rebuild aparte, con OK. |
