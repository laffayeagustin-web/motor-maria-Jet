"""D5 · Captura de Leads sin Fricción — 15 pts.

D5.1, D5.2 y D5.5 necesitan el DOM renderizado (formularios, precio en pantalla) →
vienen del bundle. D5.3 (tel:/wa.me) y D5.4 (compromiso publicado) son del HTML
servido.

D5.4 es un juicio semántico que el motor solo aproxima: el scoring manual dio 3/3
solo a cuentas con "recibirá ayuda en 15 minutos" / "tailored quote within
minutes"; NO a "24/7" (disponibilidad) ni "despegue en 2hs" (capacidad
operativa). La regex exige un sustantivo de respuesta cerca de un plazo. Lo que se
le escape lo cierra el analista con RF-20.
"""
from __future__ import annotations

import re

from maria_common.models import DimensionResult

from ._base import RENDER_MISSING, ProbeContext, dimension, ev_rendered, ev_static, scored, unverified

# plazo: "15 minutos", "en 2 horas", "within minutes", "en el día"
_PLAZO = r"(?:\d+\s*(?:min(?:uto)?s?|h(?:ora)?s?|hs)|(?:unos?\s+)?minutos|el mismo d[ií]a|within\s+(?:minutes|\d+\s*(?:min|hours?)))"
# respuesta: se compromete a responder / contestar / presupuesto / cotización / quote / get back
_RESPUESTA = r"(?:respond|contest|te contactamos|nos comunicamos|recibir[aá]s?\s+(?:tu|su|ayuda|respuesta|presupuesto|cotizaci[oó]n)|(?:tu|su)\s+(?:presupuesto|cotizaci[oó]n|quote)|get back to you|reply|tailored quote|price estimate)"
COMPROMISO_RE = re.compile(rf"{_RESPUESTA}[^.\n]{{0,60}}{_PLAZO}|{_PLAZO}[^.\n]{{0,40}}{_RESPUESTA}", re.I)

TEL_RE = re.compile(r'href=["\']tel:', re.I)
WA_RE = re.compile(r"wa\.me/|api\.whatsapp\.com|whatsapp://", re.I)


def run(ctx: ProbeContext) -> DimensionResult:
    subs = []
    r = ctx.render

    # --- D5.1 formulario de cotización alcanzable en ≤ 2 clics desde el home (4) ---
    if r is None:
        subs.append(unverified("D5.1", "Formulario de cotización alcanzable en ≤ 2 clics desde el home", 4, RENDER_MISSING))
        subs.append(unverified("D5.2", "Campos requeridos ≤ 6", 3, RENDER_MISSING))
    else:
        alcanzable = bool(r.forms) or r.quote_link
        subs.append(scored("D5.1", "Formulario de cotización alcanzable en ≤ 2 clics desde el home", 4,
                           4 if alcanzable else 0,
                           [ev_rendered(f"{len(r.forms)} form(s) en el home; enlace a cotización/contacto: {r.quote_link}")],
                           status="rendered"))
        # --- D5.2 campos requeridos ≤ 6 (escalado) ---
        if r.forms:
            min_req = min(f.required for f in r.forms)
            pts = 3.0 if min_req <= 6 else max(0.0, 3.0 - (min_req - 6) * 0.5)
            subs.append(scored("D5.2", "Campos requeridos ≤ 6", 3, pts,
                               [ev_rendered(f"campos requeridos por form: {[f.required for f in r.forms]}")],
                               status="rendered"))
        else:
            subs.append(unverified("D5.2", "Campos requeridos ≤ 6", 3,
                                   "sin formulario en el home para inspeccionar"))

    # --- D5.3 canal directo: tel: o wa.me clickable (3) ---
    has_tel = bool(TEL_RE.search(ctx.raw_html))
    has_wa = bool(WA_RE.search(ctx.raw_html))
    subs.append(scored("D5.3", "Canal directo: tel: o wa.me clickable", 3,
                       3 if (has_tel or has_wa) else 0,
                       [ev_static(f"tel:={has_tel}, whatsapp={has_wa}")]))

    # --- D5.4 compromiso de respuesta publicado (3) ---
    from maria_common.text import raw_text_content, normalize_ws

    visible = normalize_ws(raw_text_content(ctx.raw_html))
    m = COMPROMISO_RE.search(visible)
    subs.append(scored("D5.4", "Compromiso de respuesta publicado", 3, 3 if m else 0,
                       [ev_static(f'"{m.group(0)[:120]}"' if m else
                                  "no se encontró un compromiso de plazo de respuesta (24/7 y capacidad operativa no cuentan)")]))

    # --- D5.5 cotizador con precio en pantalla (2) ---
    if r is None:
        subs.append(unverified("D5.5", "Cotizador con precio en pantalla (no formulario disfrazado)", 2, RENDER_MISSING))
    else:
        subs.append(scored("D5.5", "Cotizador con precio en pantalla (no formulario disfrazado)", 2,
                           2 if r.price_on_screen else 0,
                           [ev_rendered(f"patrón de precio visible en el DOM: {r.price_on_screen}")],
                           status="rendered"))

    return dimension("D5", "Captura de Leads sin Fricción", 15, subs)
