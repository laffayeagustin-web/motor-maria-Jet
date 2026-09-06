"""D2 · Accesibilidad para Crawlers de IA — 20 pts.

Todo del lado servido: `robots.txt`, Content Signals y la respuesta real al UA
propio. No usa el bundle. Un 403/503/fallo de obtención puntúa 0 en D2.2 y eleva
un hallazgo crítico (RF-03).
"""
from __future__ import annotations

from maria_common.models import DimensionResult, Finding

from ..fetch.robots import (
    blocked_ai_crawlers,
    declara_politica,
    parse_content_signals,
    parse_robots,
    sitemap_referenciado,
    SENALES_QUE_BLOQUEAN,
)
from ._base import ProbeContext, dimension, ev_robots, ev_static, scored


def run(ctx: ProbeContext) -> tuple[DimensionResult, list[Finding]]:
    subs = []
    findings: list[Finding] = []
    robots_txt = ctx.robots_txt or ""
    groups = parse_robots(robots_txt)
    senales, senales_bloquean = parse_content_signals(robots_txt)

    # --- D2.1 robots.txt accesible y sin Disallow para los 5 crawlers núcleo ---
    if not ctx.robots_txt:
        subs.append(scored("D2.1", "robots.txt accesible y sin Disallow para GPTBot/ClaudeBot/CCBot/PerplexityBot/Google-Extended",
                           8, 0, [ev_robots("no hay robots.txt accesible (404 o HTML)")], status="static"))
    else:
        bloqueados = blocked_ai_crawlers(groups)
        pts = 8 if not bloqueados else 0
        subs.append(scored("D2.1", "robots.txt accesible y sin Disallow para GPTBot/ClaudeBot/CCBot/PerplexityBot/Google-Extended",
                           8, pts,
                           [ev_robots(f"robots.txt {len(robots_txt)} chars; bloqueados: {bloqueados or 'ninguno'}")],
                           status="static"))
        if bloqueados:
            findings.append(Finding(severidad="alta", dimension="D2",
                                    detalle=f"robots.txt bloquea crawlers de IA: {', '.join(bloqueados)}"))
        if not declara_politica(robots_txt):
            findings.append(Finding(severidad="informativa", dimension="D2",
                                    detalle="robots.txt presente pero sin ninguna directiva ni Content Signal: "
                                            "no declara política (cláusula (c) de Content Signals)."))

    # --- D2.2 acceso para clientes no-navegador (7 pts) ---
    if ctx.estado_fetch in ("bloqueado", "inaccesible"):
        subs.append(scored("D2.2", "Acceso para clientes no-navegador (respuesta real al UA propio)", 7, 0,
                           [ev_static(f"{ctx.estado_fetch}: {ctx.motivo_fetch}")], status="static"))
        findings.append(Finding(severidad="critica", dimension="D2",
                                detalle=f"Acceso bloqueado, no falta de estructura: {ctx.motivo_fetch}. "
                                        "Ningún crawler de IA puede obtener la página."))
    elif senales_bloquean:
        cuales = ", ".join(u for u in SENALES_QUE_BLOQUEAN if senales.get(u) == "no")
        subs.append(scored("D2.2", "Acceso para clientes no-navegador (respuesta real al UA propio)", 7, 0,
                           [ev_robots(f"Content Signals declara 'no' para {cuales}")], status="static"))
        findings.append(Finding(severidad="alta", dimension="D2",
                                detalle=f"Content Signals declara 'no' para {cuales}: reserva expresa de derechos, "
                                        "cuenta como bloqueo (enmienda §5)."))
    else:
        ok200 = ctx.status == 200
        subs.append(scored("D2.2", "Acceso para clientes no-navegador (respuesta real al UA propio)", 7,
                           7 if ok200 else 0,
                           [ev_static(f"HTTP {ctx.status} al UA propio; política declarada: "
                                      f"{'sin bloqueos' if not blocked_ai_crawlers(groups) else 'con bloqueos'}")],
                           status="static"))
        if not ok200:
            findings.append(Finding(severidad="alta", dimension="D2",
                                    detalle=f"HTTP {ctx.status} al UA propio (no 200)."))

    # --- D2.3 sitemap.xml presente y referenciado desde robots.txt ---
    ref = sitemap_referenciado(robots_txt)
    if ref and ctx.sitemap_ok:
        pts, det = 3, "sitemap referenciado en robots.txt y accesible"
    elif ctx.sitemap_ok:
        pts, det = 1, "sitemap accesible pero no referenciado desde robots.txt"
    elif ref:
        pts, det = 1, "sitemap referenciado en robots.txt pero no accesible / roto"
    else:
        pts, det = 0, "sin sitemap referenciado ni accesible"
    subs.append(scored("D2.3", "sitemap.xml presente y referenciado desde robots.txt", 3, pts,
                       [ev_robots(det)], status="static"))

    # --- D2.4 HTTPS sin degradación en la cadena de redirects ---
    degrada = not ctx.https_sin_degradacion
    subs.append(scored("D2.4", "HTTPS sin degradación a HTTP en la cadena de redirects", 2,
                       0 if degrada else 2,
                       [ev_static(f"cadena final: {ctx.final_url or ctx.url}")], status="static"))

    return dimension("D2", "Accesibilidad para Crawlers de IA", 20, subs), findings
