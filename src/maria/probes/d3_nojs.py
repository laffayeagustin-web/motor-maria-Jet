"""D3 · Legibilidad sin JavaScript — 20 pts.

D3.1 (ratio) necesita el DOM renderizado del bundle (`rendered_words`); sin él
queda unverified. D3.2–D3.5 son del HTML servido.

Definición normativa del ratio (enmienda §1): ambos lados con `textContent` tras
remover script/style/noscript/template, texto oculto por CSS incluido, DOM
capturado con `networkidle`. `rendered_words` viene ya contado del bundle con ese
criterio; el crudo lo cuenta el servidor con `maria_common.text`.
"""
from __future__ import annotations

import re

from maria_common.models import DimensionResult
from maria_common.text import raw_text_content, words

from ._base import RENDER_MISSING, ProbeContext, dimension, ev_rendered, ev_static, scored, unverified

D3_MIN, D3_MAX, D3_PTS = 0.40, 0.80, 8
ANOMALIA_RATIO = 1.10

TEL_RE = re.compile(r"(?:tel:|\+?\d[\d\s\-().]{7,}\d)")
EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+\.\w{2,}")


def score_ratio(ratio: float) -> float:
    r = min(ratio, 1.0)
    if r >= D3_MAX:
        return float(D3_PTS)
    if r <= D3_MIN:
        return 0.0
    return round(D3_PTS * (r - D3_MIN) / (D3_MAX - D3_MIN), 2)


def run(ctx: ProbeContext) -> tuple[DimensionResult, list[str]]:
    subs = []
    anomalias: list[str] = []
    tree = ctx.tree()
    raw_words = words(raw_text_content(ctx.raw_html))

    # --- D3.1 ratio de texto útil ---
    if ctx.render is None or ctx.render.rendered_words is None:
        subs.append(unverified("D3.1", "Ratio de texto útil (HTML crudo ÷ DOM renderizado) ≥ 0,80", 8, RENDER_MISSING))
    else:
        ren_words = ctx.render.rendered_words
        ratio = raw_words / ren_words if ren_words else 0.0
        subs.append(scored("D3.1", "Ratio de texto útil (HTML crudo ÷ DOM renderizado) ≥ 0,80", 8,
                           score_ratio(ratio),
                           [ev_rendered(f"crudo {raw_words} palabras ÷ renderizado {ren_words} = {ratio:.3f}")],
                           status="rendered"))
        if ratio > ANOMALIA_RATIO:
            anomalias.append(f"ratio {ratio:.3f} > {ANOMALIA_RATIO}: el HTML servido tiene bastante más "
                             "texto que el DOM renderizado — revisar extracción o contenido que el JS elimina.")

    # --- D3.2 title + meta description en el HTML servido ---
    title = tree.css_first("title")
    meta_desc = tree.css_first('meta[name="description"]')
    has_title = bool(title and title.text(strip=True))
    has_desc = bool(meta_desc and (meta_desc.attributes.get("content") or "").strip())
    pts = (2 if has_title else 0) + (2 if has_desc else 0)
    subs.append(scored("D3.2", "title + meta description en el HTML servido", 4, pts,
                       [ev_static(f"title={'sí' if has_title else 'no'}, meta description={'sí' if has_desc else 'no'}")]))

    # --- D3.3 canonical en el HTML servido ---
    canonical = tree.css_first('link[rel="canonical"]')
    href = canonical.attributes.get("href") if canonical else None
    subs.append(scored("D3.3", "canonical en el HTML servido", 2, 2 if href else 0,
                       [ev_static(href or "no encontrado")]))

    # --- D3.4 navegación principal sin JS (≥ 5 enlaces internos) ---
    internal = _internal_links(ctx)
    subs.append(scored("D3.4", "Navegación principal presente sin JS (≥ 5 enlaces internos)", 3,
                       3 if internal >= 5 else 0,
                       [ev_static(f"{internal} enlaces internos en el HTML servido")]))

    # --- D3.5 teléfono o email en el HTML servido ---
    has_tel = bool(TEL_RE.search(ctx.raw_html))
    has_email = bool(EMAIL_RE.search(ctx.raw_html))
    subs.append(scored("D3.5", "Teléfono o email presentes en el HTML servido", 3,
                       3 if (has_tel or has_email) else 0,
                       [ev_static(f"tel={'sí' if has_tel else 'no'}, email={'sí' if has_email else 'no'}")]))

    return dimension("D3", "Legibilidad sin JavaScript", 20, subs), anomalias


def _internal_links(ctx: ProbeContext) -> int:
    from urllib.parse import urlparse

    host = urlparse(ctx.final_url or ctx.url).netloc.lower().removeprefix("www.")
    count = 0
    for a in ctx.tree().css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if href.startswith("/") or host in href:
            count += 1
    return count
