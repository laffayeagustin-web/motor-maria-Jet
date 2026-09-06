"""Extracción de texto útil con criterio simétrico crudo/renderizado.

Portado de `docs/prototipo/geo_probe.py`. La métrica de D3 exige que ambos lados
del ratio se midan con el MISMO criterio:

  * `textContent`, no `innerText` (se incluye el texto oculto por CSS);
  * se quitan `script`, `style`, `noscript`, `template`.

`raw_text_content()` cubre el lado servido. El lado renderizado lo produce
`maria_render` con el mismo criterio (ver `maria_render/extract.py`,
`JS_TEXT_CONTENT`) y llega al servidor ya contado en `render.json`
(`rendered_words`).
"""
from __future__ import annotations

import hashlib
import re

from selectolax.lexbor import LexborHTMLParser

STRIP_TAGS = ["script", "style", "noscript", "template"]
WORD_RE = re.compile(r"[^\W_][\w'’-]*", re.UNICODE)


def words(text: str) -> int:
    """Cantidad de palabras, con el mismo tokenizador en los dos lados del ratio."""
    return len(WORD_RE.findall(text or ""))


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def raw_text_content(html: str) -> str:
    """`textContent` del `<body>` del HTML servido. Incluye texto oculto por CSS."""
    tree = LexborHTMLParser(html or "")
    tree.strip_tags(STRIP_TAGS)
    if not tree.body:
        return ""
    return tree.body.text(deep=True, separator=" ", strip=True)


def text_sha256(text: str) -> str:
    """Hash del texto normalizado — para evidencia y reproducibilidad del ratio."""
    return hashlib.sha256(normalize_ws(text).encode("utf-8")).hexdigest()
