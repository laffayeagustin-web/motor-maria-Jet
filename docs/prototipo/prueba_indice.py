"""
PRUEBA DE HUMO — no es el motor real (eso se construye vía SDD, ver PLAN-JET-MARIA-SDD.md §7).

Corre las sub-dimensiones computables con fetch estático Y, si el túnel de Chromium
remoto está activo (tools/remote-chromium-server/), también las que necesitan DOM
renderizado (D1 schema completo, D3 ratio de texto, D5 formularios, D6 WebMCP).

Si el túnel está caído o el render falla/expira (30 s), esos sub-criterios degradan a
status "unverified" con el motivo real del fallo — es la degradación de RF-02, no un bug.

Endpoint del túnel: env CHROMIUM_WS_ENDPOINT (default ws://127.0.0.1:9223/jet-maria).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

UA = "MarIA-GEO-Audit/0.1-prueba (+https://maria.ar/bot)"
AI_BOTS = ["GPTBot", "ClaudeBot", "CCBot", "PerplexityBot", "Google-Extended"]

WS_ENDPOINT_DEFAULT = "ws://127.0.0.1:9223/jet-maria"
RENDER_TIMEOUT_MS = 30_000


def ws_endpoint():
    return os.environ.get("CHROMIUM_WS_ENDPOINT", WS_ENDPOINT_DEFAULT)


def sub(nombre, pts_max, puntos, evidencia, status="static"):
    return {
        "sub_criterio": nombre,
        "puntos_max": pts_max,
        "puntos": puntos,
        "status": status,
        "evidencia": evidencia,
    }


def unver(nombre, pts_max, motivo):
    return {
        "sub_criterio": nombre,
        "puntos_max": pts_max,
        "puntos": None,
        "status": "unverified",
        "motivo": motivo,
    }


def fetch(url, timeout=10):
    return httpx.get(url, headers={"User-Agent": UA}, timeout=timeout, follow_redirects=True)


# --------------------------------------------------------------------------- #
# Render pass — Chromium remoto vía túnel (tools/remote-chromium-server/)
# --------------------------------------------------------------------------- #

def render(url, endpoint, timeout_ms=RENDER_TIMEOUT_MS):
    """Conecta al Chromium remoto y devuelve los datos del DOM renderizado.

    Levanta excepción si no se puede conectar (túnel caído). Si la navegación
    expira, devuelve lo que haya cargado hasta ese momento.
    """
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PWTimeout

    with sync_playwright() as p:
        browser = p.chromium.connect(endpoint, timeout=10_000)
        try:
            page = browser.new_page(user_agent=UA)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except PWTimeout:
                    pass
            except PWTimeout:
                pass  # seguimos con lo cargado — degradación parcial, no fallo

            html = page.content()
            inner_text = page.evaluate("() => document.body ? document.body.innerText : ''")
            ld_blocks = page.evaluate(
                "() => [...document.querySelectorAll('script[type=\"application/ld+json\"]')]"
                ".map(s => s.textContent)"
            )
            has_model_context = page.evaluate(
                "() => typeof navigator !== 'undefined' && typeof navigator.modelContext !== 'undefined'"
            )
            mc_tools = page.evaluate(
                """() => {
                    try {
                        const mc = navigator.modelContext;
                        if (!mc) return 0;
                        if (Array.isArray(mc.tools)) return mc.tools.length;
                        if (typeof mc.listTools === 'function') {
                            const t = mc.listTools();
                            return Array.isArray(t) ? t.length : 0;
                        }
                        return 0;
                    } catch (e) { return 0; }
                }"""
            )
            forms = page.evaluate(
                """() => [...document.querySelectorAll('form')].map(f => ({
                    required: f.querySelectorAll('[required]').length,
                    fields: f.querySelectorAll(
                        'input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea'
                    ).length
                }))"""
            )
            quote_link = page.evaluate(
                r"""() => {
                    const rx = /cotiz|presupuest|quote|reserv[aá]|solicit|contact/i;
                    return [...document.querySelectorAll('a[href]')].some(
                        a => rx.test(a.textContent || '') || rx.test(a.getAttribute('href') || '')
                    );
                }"""
            )
            price_on_screen = page.evaluate(
                r"""() => {
                    const t = document.body ? document.body.innerText : '';
                    return /(US\$|U\$S|USD|EUR|€|\$)\s?\d{2,}/.test(t);
                }"""
            )
            return {
                "html": html,
                "inner_text": inner_text or "",
                "ld_blocks": ld_blocks or [],
                "has_model_context": bool(has_model_context),
                "mc_tools": int(mc_tools or 0),
                "forms": forms or [],
                "quote_link": bool(quote_link),
                "price_on_screen": bool(price_on_screen),
            }
        finally:
            browser.close()


# --------------------------------------------------------------------------- #
# Utilidades de JSON-LD y texto
# --------------------------------------------------------------------------- #

def _iter_ld_nodes(obj):
    if isinstance(obj, dict):
        graph = obj.get("@graph")
        if isinstance(graph, list):
            for n in graph:
                yield from _iter_ld_nodes(n)
            return
        yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from _iter_ld_nodes(v)
    elif isinstance(obj, list):
        for n in obj:
            yield from _iter_ld_nodes(n)


def _types(node):
    t = node.get("@type") if isinstance(node, dict) else None
    if isinstance(t, list):
        return {str(x) for x in t}
    if isinstance(t, str):
        return {t}
    return set()


def _parse_ld(blocks):
    """blocks: lista de strings ld+json. Devuelve (nodos, bloques_parseables, bloques_totales)."""
    nodes, ok = [], 0
    for b in blocks or []:
        try:
            data = json.loads(b)
        except Exception:
            continue
        ok += 1
        nodes.extend(_iter_ld_nodes(data))
    return nodes, ok, len(blocks or [])


def _ld_types(nodes):
    return {t for n in nodes for t in _types(n)}


ORG_TYPES = {"Organization", "LocalBusiness"}
BOILERPLATE_TYPES = {"WebPage", "WebSite", "BreadcrumbList", "SearchAction", "ListItem", "ImageObject", "SiteNavigationElement"}


def _visible_text(html):
    tree = HTMLParser(html)
    tree.strip_tags(["script", "style", "noscript", "template", "svg"])
    return re.sub(r"\s+", " ", (tree.text() or "")).strip()


def _has_org_con_datos(nodes):
    for n in nodes:
        if _types(n) & ORG_TYPES and (n.get("name") or n.get("address") or n.get("telephone")):
            return True
    return False


# --------------------------------------------------------------------------- #
# Dimensiones
# --------------------------------------------------------------------------- #

def d1(raw_tree, raw_html, rd, rerr):
    subs = []

    raw_ld_nodes, raw_ok, raw_total = _parse_ld(
        [n.text() for n in raw_tree.css("script[type='application/ld+json']")]
    )

    if rerr:
        # JSON-LD parseable lo evaluamos con lo que hay (HTML crudo), pero avisando.
        subs.append(sub(
            "JSON-LD presente y parseable (solo HTML crudo — sin render para comparar, principio 2)",
            5, 5 if raw_ok else 0,
            f"crudo: {raw_total} bloques, {raw_ok} parseables. Render no disponible: {rerr}",
            status="static",
        ))
        for nombre, pts in [
            ("Organization/LocalBusiness con name+url", 5),
            ("address + telephone dentro del schema", 5),
            ("Service/Offer/Product describiendo el chárter", 5),
            ("sameAs + logo + aggregateRating", 5),
        ]:
            subs.append(unver(nombre, pts, rerr))
        return subs

    ren_ld_nodes, ren_ok, ren_total = _parse_ld(rd["ld_blocks"])
    raw_t, ren_t = _ld_types(raw_ld_nodes), _ld_types(ren_ld_nodes)
    discrepancia = raw_t != ren_t
    ev_p2 = (
        f"crudo: {raw_total} bloques/{sorted(raw_t)}; renderizado: {ren_total} bloques/{sorted(ren_t)}"
        + ("  ⚠ DIFIEREN (principio 2: se reportan ambos)" if discrepancia else "")
    )
    subs.append(sub(
        "JSON-LD presente y parseable (crudo + DOM renderizado, principio 2)",
        5, 5 if ren_ok else 0, ev_p2, status="rendered",
    ))

    orgs = [n for n in ren_ld_nodes if _types(n) & ORG_TYPES]
    org_name_url = any(n.get("name") and n.get("url") for n in orgs)
    subs.append(sub(
        "Nodo Organization/LocalBusiness con name + url", 5,
        5 if org_name_url else 0,
        f"{len(orgs)} nodos Organization/LocalBusiness; con name+url: {org_name_url}",
        status="rendered",
    ))

    addr_tel = any(n.get("address") and n.get("telephone") for n in ren_ld_nodes)
    subs.append(sub(
        "address + telephone dentro del schema", 5,
        5 if addr_tel else 0,
        f"algún nodo con address+telephone: {addr_tel}",
        status="rendered",
    ))

    charter = any(_types(n) & {"Service", "Offer", "Product"} for n in ren_ld_nodes)
    subs.append(sub(
        "Service / Offer / Product describiendo el chárter", 5,
        5 if charter else 0,
        f"tipos presentes: {sorted(_ld_types(ren_ld_nodes) & {'Service', 'Offer', 'Product'}) or 'ninguno'}",
        status="rendered",
    ))

    has_sameas = any(n.get("sameAs") for n in orgs)
    has_logo = any(n.get("logo") for n in orgs)
    has_rating = any(n.get("aggregateRating") for n in ren_ld_nodes)
    pts_extra = round((has_sameas + has_logo + has_rating) * (5 / 3), 2)
    subs.append(sub(
        "sameAs + logo + aggregateRating (1,67 pts c/u)", 5, pts_extra,
        f"sameAs={has_sameas}, logo={has_logo}, aggregateRating={has_rating}",
        status="rendered",
    ))
    return subs


def d2_static(base_url):
    subs = []
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        r = fetch(robots_url)
        robots_txt = r.text if r.status_code == 200 else ""
    except Exception:
        robots_txt = ""
        r = None

    blocked = [
        b for b in AI_BOTS
        if re.search(rf"User-agent:\s*{b}\b.*?Disallow:\s*/\s*$", robots_txt, re.I | re.M | re.S)
    ]
    ok_robots = bool(robots_txt) and not blocked
    subs.append(sub(
        "robots.txt accesible y sin Disallow para bots IA",
        8, 8 if ok_robots else 0,
        f"HTTP {r.status_code if r else 'sin respuesta'} en /robots.txt; bloqueados: {blocked or 'ninguno'}",
    ))

    try:
        r2 = fetch(base_url)
        ok_200 = r2.status_code == 200
    except Exception:
        r2 = None
        ok_200 = False
    subs.append(sub(
        "HTTP 200 real (UA de prueba, no UA de crawler IA real — aproximado)",
        7, 7 if ok_200 else 0,
        f"HTTP {r2.status_code if r2 else 'error'} con UA {UA}",
    ))

    sitemap_ref = "sitemap" in robots_txt.lower()
    subs.append(sub(
        "sitemap.xml referenciado desde robots.txt",
        3, 3 if sitemap_ref else 0,
        "Encontrado 'sitemap' en robots.txt" if sitemap_ref else "No se menciona sitemap en robots.txt",
    ))

    degrada = False
    if r2 is not None:
        for h in r2.history:
            if h.url.scheme == "https" and r2.url.scheme != "https":
                degrada = True
    subs.append(sub(
        "HTTPS sin degradación a HTTP en redirects",
        2, 0 if degrada else 2,
        f"Cadena final: {r2.url if r2 else 'sin respuesta'}",
    ))
    return subs


def d3(raw_tree, raw_html, rd, rerr):
    subs = []

    if rerr:
        subs.append(unver(
            "Ratio texto útil crudo/renderizado ≥0,80 (necesita el render para comparar)", 8, rerr))
    else:
        raw_text = _visible_text(raw_html)
        ren_text = re.sub(r"\s+", " ", rd["inner_text"]).strip()
        ratio = len(raw_text) / max(len(ren_text), 1)
        ratio_efectivo = min(ratio, 1.0)
        pts = max(0.0, min(8.0, (ratio_efectivo - 0.40) / 0.40 * 8))
        subs.append(sub(
            "Ratio de texto útil (HTML crudo ÷ DOM renderizado) ≥ 0,80", 8, round(pts, 2),
            f"crudo {len(raw_text)} car. ÷ renderizado {len(ren_text)} car. = {ratio:.2f}",
            status="rendered",
        ))

    title = raw_tree.css_first("title")
    meta_desc = raw_tree.css_first("meta[name='description']")
    ok_tm = bool(title and title.text(strip=True)) and bool(meta_desc and meta_desc.attributes.get("content"))
    subs.append(sub("title + meta description en HTML servido", 4, 4 if ok_tm else 0,
                    f"title={'sí' if title else 'no'}, meta description={'sí' if meta_desc else 'no'}"))

    canonical = raw_tree.css_first("link[rel='canonical']")
    subs.append(sub("canonical en HTML servido", 2, 2 if canonical else 0,
                    canonical.attributes.get("href") if canonical else "no encontrado"))

    links = raw_tree.css("a[href]")
    subs.append(sub(
        "Navegación principal sin JS (≥5 enlaces internos, aprox: total <a> en HTML crudo)", 3,
        3 if len(links) >= 5 else 0, f"{len(links)} enlaces <a> en HTML crudo"))

    tel_match = re.search(r"\+?\d[\d\s\-\(\)]{7,}\d", raw_html)
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_html)
    subs.append(sub("Teléfono o email presentes en HTML servido", 3,
                    3 if (tel_match or email_match) else 0,
                    f"tel={'sí' if tel_match else 'no'}, email={'sí' if email_match else 'no'}"))
    return subs


def d5(raw_tree, raw_html, rd, rerr):
    subs = []

    tel_links = raw_tree.css("a[href^='tel:']")
    wa_links = [a for a in raw_tree.css("a[href]") if "wa.me" in (a.attributes.get("href") or "")]
    subs.append(sub("Canal directo: tel: o wa.me clickable", 3,
                    3 if (tel_links or wa_links) else 0,
                    f"{len(tel_links)} enlaces tel:, {len(wa_links)} enlaces wa.me"))

    compromiso = re.search(r"\b(\d+\s*(hora|hs|h\b|minuto|min)s?|24\s*/\s*7|24hs?)\b", raw_html, re.I)
    subs.append(sub("Compromiso de respuesta publicado (regex simple, sin multiidioma completo)", 3,
                    3 if compromiso else 0,
                    compromiso.group(0) if compromiso else "no se encontró patrón de plazo"))

    if rerr:
        subs.append(unver("Formulario de cotización alcanzable en ≤2 clics desde home", 4, rerr))
        subs.append(unver("Campos requeridos ≤ 6", 3, rerr))
        subs.append(unver("Cotizador con precio en pantalla (no formulario disfrazado)", 2, rerr))
        return subs

    forms = rd["forms"]
    alcanzable = bool(forms) or rd["quote_link"]
    subs.append(sub(
        "Formulario de cotización alcanzable en ≤2 clics desde home "
        "(aprox: form en home = 0-1 clic, o link cotiz/presupuesto/contacto = ~2)", 4,
        4 if alcanzable else 0,
        f"{len(forms)} form(s) en home, link a cotización/contacto: {rd['quote_link']}",
        status="rendered",
    ))

    if forms:
        min_req = min(f["required"] for f in forms)
        pts_req = 3.0 if min_req <= 6 else max(0.0, 3.0 - (min_req - 6) * 0.5)
        subs.append(sub("Campos requeridos ≤ 6 (mínimo entre los forms del home)", 3, round(pts_req, 2),
                        f"forms con campos requeridos: {[f['required'] for f in forms]}", status="rendered"))
    else:
        subs.append(unver("Campos requeridos ≤ 6", 3, "sin formulario en el home para inspeccionar"))

    subs.append(sub("Cotizador con precio en pantalla (no formulario disfrazado)", 2,
                    2 if rd["price_on_screen"] else 0,
                    f"patrón de precio visible en el DOM: {rd['price_on_screen']}", status="rendered"))
    return subs


def d6(base_url, rd, rerr):
    subs = []

    if rerr:
        subs.append(unver("navigator.modelContext con herramientas (requiere ejecutar JS)", 3, rerr))
    else:
        n = rd["mc_tools"]
        ok = rd["has_model_context"] and n > 0
        subs.append(sub("navigator.modelContext con herramientas registradas", 3, 3 if ok else 0,
                        f"modelContext={'sí' if rd['has_model_context'] else 'no'}, herramientas={n}",
                        status="rendered"))

    parsed = urlparse(base_url)
    found = []
    for path in ("/llms.txt", "/.well-known/ai-plugin.json", "/.well-known/mcp.json"):
        try:
            rr = fetch(f"{parsed.scheme}://{parsed.netloc}{path}")
            if rr.status_code == 200:
                found.append(path)
        except Exception:
            pass
    subs.append(sub("llms.txt / .well-known de agentes o feed estructurado", 2, 2 if found else 0,
                    f"encontrados: {found or 'ninguno'}"))
    return subs


# --------------------------------------------------------------------------- #

def run(cuenta, url, endpoint=None, skip_render=False):
    endpoint = endpoint or ws_endpoint()

    r = fetch(url)
    raw_html = r.text
    raw_tree = HTMLParser(raw_html)

    render_data, render_error = None, None
    if skip_render:
        render_error = "render omitido (túnel caído en el preflight del panel)"
    else:
        try:
            render_data = render(url, endpoint)
        except Exception as e:
            render_error = f"{type(e).__name__}: {str(e).splitlines()[0].strip()}"
            print(f"      render no disponible ({cuenta}): {render_error}", file=sys.stderr)

    dims = {
        "D1_estructura_semantica": d1(raw_tree, raw_html, render_data, render_error),
        "D2_accesibilidad_crawlers_ia": d2_static(url),
        "D3_legibilidad_sin_js": d3(raw_tree, raw_html, render_data, render_error),
        "D4_divulgacion_confianza": [
            unver("requiere rastreo multi-página (footer), fuera de alcance de la prueba de humo", 15,
                  "no implementado (rastreo multi-página)")
        ],
        "D5_captura_leads": d5(raw_tree, raw_html, render_data, render_error),
        "D6_frontera_webmcp": d6(url, render_data, render_error),
    }

    # Tope por boilerplate (RF-13): si no hay Organization/LocalBusiness con datos,
    # D1 no supera 10/25.
    d1_subs = dims["D1_estructura_semantica"]
    ren_ld_nodes = []
    if render_data is not None:
        ren_ld_nodes, _, _ = _parse_ld(render_data["ld_blocks"])
    raw_ld_nodes, _, _ = _parse_ld(
        [n.text() for n in raw_tree.css("script[type='application/ld+json']")]
    )
    hay_org = _has_org_con_datos(ren_ld_nodes or raw_ld_nodes)
    d1_bruto = sum((s["puntos"] or 0) for s in d1_subs if s["status"] not in ("unverified", "regla"))
    if not hay_org and d1_bruto > 10:
        exceso = round(d1_bruto - 10, 2)
        d1_subs.append({
            "sub_criterio": "TOPE por boilerplate (RF-13): schema solo WebPage/WebSite sin Organization con datos",
            "puntos_max": 0,
            "puntos": -exceso,
            "status": "regla",
            "evidencia": f"D1 bruto {d1_bruto} → limitado a 10",
        })

    total = 0
    total_max = 0
    n_unverified = 0
    for subs in dims.values():
        for s in subs:
            total_max += s["puntos_max"]
            if s["status"] == "unverified":
                n_unverified += 1
            else:
                total += s["puntos"] or 0

    return {
        "schema_version": "prueba-0.2",
        "cuenta": cuenta,
        "url": url,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "render": {
            "endpoint": endpoint,
            "ok": render_error is None,
            "motivo": render_error,
        },
        "nota": "PRUEBA DE HUMO, no el motor final. Sub-criterios 'unverified' con motivo "
                "de conexión requieren el Chromium remoto (tools/remote-chromium-server).",
        "dimensiones": dims,
        "resumen": {
            "puntos_obtenidos": round(total, 2),
            "puntos_max_totales_de_la_rubrica": total_max,
            "sub_criterios_unverified": n_unverified,
            "sub_criterios_totales": sum(len(v) for v in dims.values()),
        },
    }


if __name__ == "__main__":
    cuenta = sys.argv[1] if len(sys.argv) > 1 else "American Jet"
    url = sys.argv[2] if len(sys.argv) > 2 else "https://americanjet.com.ar"
    print(json.dumps(run(cuenta, url), indent=2, ensure_ascii=False))
