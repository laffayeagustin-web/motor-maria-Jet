"""Orquestador: de una URL (o un panel) a un `AuditRun`.

Hace el fetch estático fresco, resuelve `robots.txt`, el sitemap, `llms.txt`, las
páginas del footer para D4, y corre los seis probes con el entry del render
bundle (o `None` → RF-02). El scoring lo calculan los modelos.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser

from maria_common.models import Account, AuditRun, Finding

from .fetch import static as fetchmod
from .fetch.robots import parse_robots
from .probes import _base, d1_schema, d2_access, d3_nojs, d4_trust, d5_leads, d6_frontier
from .render_bundle import RenderBundle, load_bundle

log = logging.getLogger("maria.audit")

# Rutas de respaldo, solo si el bundle no trae enlaces de footer. Se mantiene
# corto para no golpear cada dominio con decenas de requests especulativos.
COMMON_FOOTER_ROUTES = [
    "/politica-de-privacidad", "/privacy-policy", "/cookie-policy", "/aviso-legal",
]
WELL_KNOWN = ["/.well-known/ai-plugin.json", "/.well-known/mcp.json", "/.well-known/agent.json"]


def _variante_www(url: str) -> str | None:
    """La otra forma del mismo host: agrega o saca `www.`. `None` si no hay
    host que parsear. RF-24: usada solo como fallback de un DNS que no
    resuelve — misma identidad (UA/headers), la misma URL que cualquier
    visitante hubiera tipeado con o sin el prefijo. No es una excepción al
    principio 6 (sin suplantación): es una variante de host, no de identidad.
    """
    p = urlparse(url)
    if not p.netloc:
        return None
    nuevo = p.netloc[4:] if p.netloc.startswith("www.") else "www." + p.netloc
    return p._replace(netloc=nuevo).geturl()


def audit_account(
    account: Account,
    *,
    bundle: RenderBundle | None = None,
    cache_dir: Path | str = fetchmod.DEFAULT_CACHE_DIR,
    no_cache: bool = False,
) -> AuditRun:
    bundle = bundle or load_bundle(None)

    if account.url is None:
        return AuditRun(
            cuenta=account, estado="no_aplica",
            motivo=account.no_aplica_motivo or "la cuenta no tiene sitio web cargado",
        )

    url = account.url
    fr = fetchmod.fetch(url, cache_dir=cache_dir, no_cache=no_cache)

    # RF-24: un DNS que no resuelve suele ser un apex sin registro A con todo
    # servido en `www.` vía CDN (o al revés) — configuración común, no un
    # error del sitio. Un solo reintento con la otra variante del mismo host,
    # misma identidad, antes de darlo por inaccesible.
    swap_finding: Optional[Finding] = None
    if fr.estado == "inaccesible" and fr.motivo == "el DNS no resuelve":
        alt_url = _variante_www(url)
        if alt_url:
            fr_alt = fetchmod.fetch(alt_url, cache_dir=cache_dir, no_cache=no_cache)
            if fr_alt.estado != "inaccesible":
                swap_finding = Finding(
                    severidad="informativa", dimension="D2",
                    detalle=f"{url} no resuelve por DNS; se usó {alt_url} en su lugar "
                            "(misma identidad, sin cambios de UA/IP).")
                url, fr = alt_url, fr_alt

    origin = fetchmod.origin_of(fr.final_url or url)

    robots_txt = fetchmod.fetch_text(fetchmod.robots_url(url), cache_dir=cache_dir, no_cache=no_cache)

    ctx = _base.ProbeContext(
        url=url,
        raw_html=fr.body,
        status=fr.status,
        final_url=fr.final_url,
        headers=fr.headers,
        https_sin_degradacion=fr.https_sin_degradacion,
        estado_fetch=fr.estado,
        motivo_fetch=fr.motivo,
        robots_txt=robots_txt,
        render=bundle.entry_for(url),
    )
    if fr.body:
        ctx.raw_tree = LexborHTMLParser(fr.body)

    # sitemap
    ctx.sitemap_ok = _probe_url(origin, "/sitemap.xml", cache_dir, no_cache) or \
        _probe_url(origin, "/sitemap_index.xml", cache_dir, no_cache)
    # llms.txt / well-known para D6
    ctx.llms_txt_present = fetchmod.fetch_text(urljoin(origin + "/", "/llms.txt"),
                                               cache_dir=cache_dir, no_cache=no_cache) is not None
    ctx.well_known = [w for w in WELL_KNOWN
                      if _probe_url(origin, w, cache_dir, no_cache)]
    # footer para D4
    ctx.footer_pages = _resolve_footer(ctx, origin, cache_dir, no_cache)

    # --- estado de la cuenta ---
    if fr.estado == "bloqueado":
        estado, motivo = "bloqueado", fr.motivo
    elif fr.estado == "inaccesible":
        estado, motivo = "inaccesible", fr.motivo
    elif ctx.render is None:
        estado, motivo = "unverified", _base.RENDER_MISSING
    else:
        estado, motivo = "medido", None

    run = AuditRun(
        cuenta=account, estado=estado, motivo=motivo,
        render_bundle_ref=str(bundle.directory) if bundle.loaded else None,
    )

    if fr.estado in ("bloqueado", "inaccesible"):
        # solo D2 es medible; el resto no hay contenido que puntuar
        d2, f2 = d2_access.run(ctx)
        run.dimensiones = [d2]
        run.hallazgos = ([swap_finding] if swap_finding else []) + list(f2)
        return run

    d1 = d1_schema.run(ctx)
    d2, f2 = d2_access.run(ctx)
    d3, anomalias = d3_nojs.run(ctx)
    d4 = d4_trust.run(ctx)
    d5 = d5_leads.run(ctx)
    d6 = d6_frontier.run(ctx)
    run.dimensiones = [d1, d2, d3, d4, d5, d6]
    run.hallazgos = ([swap_finding] if swap_finding else []) + list(f2)
    run.anomalias = anomalias
    return run


def _probe_url(origin: str, path: str, cache_dir, no_cache) -> bool:
    r = fetchmod.fetch(urljoin(origin + "/", path), cache_dir=cache_dir, no_cache=no_cache)
    return bool(r.ok and r.status == 200)


def _resolve_footer(ctx: _base.ProbeContext, origin: str, cache_dir, no_cache) -> dict[str, int]:
    """URLs candidatas de política: enlaces del footer del bundle + rutas comunes."""
    candidates: list[str] = []
    if ctx.render is not None and ctx.render.footer_links:
        for fl in ctx.render.footer_links:
            if fl.href:
                candidates.append(urljoin(origin + "/", fl.href))
    else:
        # sin footer del bundle: probamos solo un puñado de rutas de respaldo
        for route in COMMON_FOOTER_ROUTES:
            candidates.append(urljoin(origin + "/", route))

    seen: dict[str, int] = {}
    for c in dict.fromkeys(candidates):
        if urlparse(c).netloc.lower().removeprefix("www.") != urlparse(origin).netloc.lower().removeprefix("www."):
            continue
        r = fetchmod.fetch(c, cache_dir=cache_dir, no_cache=no_cache)
        if r.ok and r.status:
            seen[c] = r.status
    return seen


# --------------------------------------------------------------------------- #
# Batch de panel — semáforo por dominio (RF-04)
# --------------------------------------------------------------------------- #

def audit_panel(
    accounts: list[Account],
    *,
    bundle_dir: Optional[Path | str] = None,
    cache_dir: Path | str = fetchmod.DEFAULT_CACHE_DIR,
    no_cache: bool = False,
    workers: int = 4,
) -> list[AuditRun]:
    bundle = load_bundle(bundle_dir)
    locks: dict[str, threading.Lock] = {}
    locks_guard = threading.Lock()

    def domain_lock(url: Optional[str]) -> threading.Lock:
        host = urlparse(url or "").netloc or "_"
        with locks_guard:
            return locks.setdefault(host, threading.Lock())

    def one(acc: Account) -> AuditRun:
        with domain_lock(acc.url):
            return audit_account(acc, bundle=bundle, cache_dir=cache_dir, no_cache=no_cache)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, accounts))
