"""D4 · Divulgación y Confianza — 15 pts.

D4.1–D4.3 dependen de rastreo multi-página del footer. El descubrimiento de
enlaces del footer lo aporta el bundle (`footer_links`); el orquestador fetchea
esas URLs + rutas comunes con fetch estático y deja el resultado en
`ctx.footer_pages`. Si no hay footer sin JS y no hay bundle, van a `unverified`
(principio 4). D4.4 y D4.5 salen de datos estáticos + JSON-LD.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from maria_common.jsonld import parse_blocks
from maria_common.models import DimensionResult

from ._base import RENDER_MISSING, ProbeContext, dimension, ev_static, scored, unverified

PRIVACY_RE = re.compile(r"priv(?:acy|acidad)|datos-personales|proteccion-de-datos", re.I)
COOKIES_RE = re.compile(r"cookies?", re.I)
LEGAL_RE = re.compile(r"aviso-?legal|legal-?notice|terminos|terms|impressum", re.I)
CUIT_RE = re.compile(r"\b(?:CUIT|CIF|C\.U\.I\.T|RUC|NIF)\b[\s:.\-]*[\d./\-]{6,}", re.I)
RAZON_SOCIAL_RE = re.compile(r"\b(?:S\.?A\.?|S\.?R\.?L\.?|S\.?A\.?S\.?|LLC|Ltd\.?|GmbH|Inc\.?)\b")
# `logo@2x.png`, `img@3x.jpg` en srcset no son emails
_NOT_EMAIL_TLD = {"png", "jpg", "jpeg", "gif", "webp", "svg", "css", "js", "avif", "ico"}


def _real_emails(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"([\w.\-]+)@([\w.\-]+\.([A-Za-z]{2,}))", text):
        if m.group(3).lower() in _NOT_EMAIL_TLD:
            continue
        if m.group(1).lower() in ("", "2x", "3x", "1x"):
            continue
        out.append(m.group(2).lower())
    return out


def _found(ctx: ProbeContext, rx: re.Pattern) -> str | None:
    for url, status in ctx.footer_pages.items():
        if rx.search(url) and status == 200:
            return url
    return None


def _footer_conocido(ctx: ProbeContext) -> bool:
    return bool(ctx.footer_pages) or (ctx.render is not None and bool(ctx.render.footer_links))


def run(ctx: ProbeContext) -> DimensionResult:
    subs = []
    footer_ok = _footer_conocido(ctx)

    # --- D4.1 política de privacidad localizable (4) ---
    priv = _found(ctx, PRIVACY_RE)
    if priv:
        subs.append(scored("D4.1", "Política de privacidad localizable", 4, 4,
                           [ev_static("página de privacidad responde 200", url=priv)]))
    elif footer_ok:
        subs.append(scored("D4.1", "Política de privacidad localizable", 4, 0,
                           [ev_static("footer conocido, sin enlace a política de privacidad accesible")]))
    else:
        subs.append(unverified("D4.1", "Política de privacidad localizable", 4,
                               "sin footer sin JS y sin bundle: no se pudo rastrear " + RENDER_MISSING))

    # --- D4.2 política de cookies completa (3) ---
    cook = _found(ctx, COOKIES_RE)
    if cook:
        subs.append(scored("D4.2", "Política de cookies completa", 3, 2,
                           [ev_static("página de cookies responde 200; completitud de la tabla no verificada", url=cook)]))
    elif footer_ok:
        subs.append(scored("D4.2", "Política de cookies completa", 3, 0,
                           [ev_static("footer conocido, sin política de cookies accesible")]))
    else:
        subs.append(unverified("D4.2", "Política de cookies completa", 3, "requiere rastreo de footer"))

    # --- D4.3 CMP presente y coherente con la analítica (3) ---
    cmp_presente = bool(re.search(r"cookieyes|cookiebot|onetrust|osano|iubenda|complianz|borlabs",
                                  ctx.raw_html, re.I))
    analitica = bool(re.search(r"googletagmanager\.com|gtag\(|google-analytics\.com|/gtag/js",
                               ctx.raw_html, re.I))
    if cmp_presente and analitica:
        subs.append(scored("D4.3", "CMP presente y coherente con la analítica cargada", 3, 3,
                           [ev_static("CMP conocido + analítica detectados en el HTML servido")]))
    elif cmp_presente or not analitica:
        subs.append(scored("D4.3", "CMP presente y coherente con la analítica cargada", 3, 1.5 if cmp_presente else 3,
                           [ev_static(f"CMP={cmp_presente}, analítica={analitica}")]))
    else:
        subs.append(scored("D4.3", "CMP presente y coherente con la analítica cargada", 3, 0,
                           [ev_static("analítica cargada sin CMP detectable — incoherente")]))

    # --- D4.4 identidad legal publicada (3) ---
    text_all = ctx.raw_html
    ld_nodes, _, _ = parse_blocks([n.text() for n in ctx.tree().css('script[type="application/ld+json"]')])
    if ctx.render is not None:
        rn, _, _ = parse_blocks(ctx.render.ld_blocks)
        ld_nodes = rn or ld_nodes
    schema_address = any(n.get("address") for n in ld_nodes)
    tiene_cuit = bool(CUIT_RE.search(text_all))
    tiene_razon = bool(RAZON_SOCIAL_RE.search(text_all)) or any(
        RAZON_SOCIAL_RE.search(str(n.get("name") or "")) for n in ld_nodes
    )
    pts44 = (1 if tiene_razon else 0) + (1 if tiene_cuit else 0) + (1 if schema_address else 0)
    subs.append(scored("D4.4", "Identidad legal publicada (razón social, CUIT/CIF, domicilio)", 3, pts44,
                       [ev_static(f"razón social={tiene_razon}, CUIT/CIF={tiene_cuit}, domicilio en schema={schema_address}")]))

    # --- D4.5 coherencia dominio web ↔ dominio de email (2) ---
    site_host = urlparse(ctx.final_url or ctx.url).netloc.lower().removeprefix("www.")
    site_root = ".".join(site_host.split(".")[-2:]) if site_host else ""
    emails = _real_emails(text_all)
    if not emails:
        subs.append(unverified("D4.5", "Coherencia dominio web ↔ dominio de email de contacto", 2,
                               "sin email de contacto visible en el HTML servido"))
    else:
        coherente = any(site_root and site_root in e for e in emails)
        subs.append(scored("D4.5", "Coherencia dominio web ↔ dominio de email de contacto", 2,
                           2 if coherente else 0,
                           [ev_static(f"dominios de email: {sorted(set(emails))[:3]}; raíz del sitio: {site_root}")]))

    return dimension("D4", "Divulgación y Confianza", 15, subs)
