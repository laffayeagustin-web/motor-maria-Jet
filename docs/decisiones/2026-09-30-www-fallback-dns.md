# Fallback a la variante `www.`/sin `www.` cuando el DNS no resuelve — decisión del 30-09-2026

**Alcance:** `src/maria/audit.py` (`_variante_www`, `audit_account`). Agrega
**RF-24** a `spec.md`. No toca `RF-03`/`RF-04` (sigue sin enviar UA de
terceros ni resolver challenges), no cambia scoring ni `schema_version`.

---

## El hallazgo

`https://maria.ar/auditoria-geo-tecnica/r/bellmuntgolf-com-792e04/` marcó a
`bellmuntgolf.com` como INVISIBLE, pero el usuario mostró una búsqueda de
Google (AI Mode) citando el sitio sin problema — claramente accesible y bien
indexado. El JSON de esa corrida decía `estado: inaccesible`, `motivo: "el
DNS no resuelve"`.

Investigación (30-09-2026):

```
nslookup bellmuntgolf.com 8.8.8.8      → Can't find bellmuntgolf.com: No answer
nslookup bellmuntgolf.com 1.1.1.1      → Can't find bellmuntgolf.com: No answer
dig @8.8.8.8 bellmuntgolf.com ANY      → solo NS + SOA (GoDaddy), sin registro A
nslookup www.bellmuntgolf.com 8.8.8.8  → CNAME a d3a8vx5uqxskzu.cloudfront.net (resuelve OK)
```

El apex (`bellmuntgolf.com` pelado) **genuinamente no tiene registro A/AAAA**
— la zona existe (delegada, con NS y SOA), pero nadie configuró el apex. El
sitio real vive entero en `www.bellmuntgolf.com`, detrás de CloudFront. Es
una configuración de DNS/hosting perfectamente común (y perfectamente
funcional desde cualquier browser o crawler real), no un error del sitio.

**Causa, del lado nuestro:** `geoserv/run.py::generar_geo()` (funnel, no
motor) arma `Account(url=f"https://{dom}")` con
`dom = maria_answers.match.normalizar_dominio(web)`, que **le saca el
`www.` incondicionalmente** — esa función está pensada para comparar
dominios citados en el motor de Respuestas (`www.x.com` y `x.com` son "la
misma marca" para contar menciones), no para elegir qué URL auditar. El
resultado: sin importar qué haya tipeado el visitante, siempre auditamos el
apex pelado. Contra un sitio con esta configuración, eso da DNS-fail
siempre, aunque el sitio esté perfectamente vivo.

## Qué cambia

`audit_account()` (el orquestador, usado por **todo** lo que llama al motor —
GEO self-serve, funnel de visibilidad, paneles sectoriales, no solo
`geoserv`) gana un fallback puntual: si el fetch inicial da `inaccesible` con
motivo **exactamente** "el DNS no resuelve", reintenta **una sola vez** con
la variante complementaria del mismo host (agrega `www.` si no lo tenía, lo
saca si lo tenía). Si esa variante no es también `inaccesible`, se usa para
el resto de la auditoría — robots.txt, sitemap, footer, los seis probes —
todo lo que sigue en `audit_account` ya usa `url`/`fr` como variables
locales, así que reasignarlas antes de continuar alcanza. Se agrega un
`Finding` informativo documentando el swap, para que quede evidencia de qué
pasó (principio "evidencia o silencio") en vez de un cambio silencioso.

**No se tocó `geoserv/run.py` ni `normalizar_dominio()`.** El fallback vive
enteramente en el orquestador canónico y es transparente para todo
llamador — `geoserv` sigue armando `Account(url=f"https://{dom}")` con el
dominio pelado exactamente igual que antes; si ese pelado no resuelve,
`audit_account` prueba `www.` por su cuenta.

## Por qué esto NO reabre el principio 6

El principio 6 (`docs/decisiones/2026-09-10-headers-de-request.md`, mismo
tema discutido dos veces hoy para el veredicto GE-17 del funnel) prohíbe
suplantar la **identidad** de un crawler de terceros, resolver challenges,
rotar IP o falsificar la firma TLS de un navegador — todo eso es intentar
parecer alguien que no somos para conseguir trato preferencial. Esto es
categóricamente distinto:

1. **La identidad no cambia.** Mismo UA, mismos headers, mismo cliente. Lo
   único que cambia es el *host* al que apunta la URL.
2. **Es la misma URL que un humano hubiera tipeado.** `www.bellmuntgolf.com`
   y `bellmuntgolf.com` son, para cualquier visitante, "el mismo sitio" —
   agregar o sacar `www.` es la corrección de dominio más aburrida y
   estándar que existe, no una variante de infraestructura.
3. **Gate estrecho, no una forma general de "reintentar hasta que ande".**
   Solo dispara con el motivo exacto "el DNS no resuelve" — un 403
   (`bloqueado`, hay un servidor real respondiendo que decidió rechazarnos)
   NO reintenta con otra variante; ahí sí seguiría aplicando el límite de
   RF-03 tal cual. TLS inválido o bucle de redirects tampoco disparan esto
   (no son el problema que esta variante resuelve).
4. **Sin este fallback, `bellmuntgolf.com` no se podía auditar en absoluto** —
   con o sin bots de por medio. No es una forma de "conseguir mejor
   resultado", es la diferencia entre medir algo real y no medir nada.

## Cambios asociados

| Dónde | Qué |
|---|---|
| `src/maria/audit.py` | `_variante_www()`; el reintento gateado en `audit_account()`; `Finding` informativo del swap en ambas ramas de retorno. |
| `spec.md` RF-24 | Este requisito. |
| `tests/test_rf15_18_orchestration.py` | 4 tests: swap con `www.`, swap sin `www.`, ambas variantes fallan (no esconde el error), `bloqueado` no reintenta. |
| Funnel (`~/indice-de-posicionamiento-en-la-IA`) | Re-sync dirigido de `audit.py` (`VENDOR.md`). `geoserv/run.py`/`server.py` sin cambios — el fallback es transparente. |
