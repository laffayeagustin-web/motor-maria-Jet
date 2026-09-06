"""Captura del DOM renderizado de una URL con Playwright/Chromium.

`playwright` es dependencia del perfil `[render]` — este módulo se importa solo en
la notebook. El servidor nunca lo toca.

Modo de captura (enmienda §1, D3): `wait_until="networkidle"`, timeout 45 s. El
momento de captura es parte de la definición del ratio, no un detalle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from maria_common.render_contract import (
    RENDER_SCHEMA_VERSION,
    FooterLink,
    FormInfo,
    ModelContextInfo,
    RenderBundleEntry,
)
from maria_common.text import text_sha256, words

from . import extract

UA_STRING = "MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)"
CAPTURE_TIMEOUT_MS = 45_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_one(url: str, *, browser, keep_html: bool = False,
                timeout_ms: int = CAPTURE_TIMEOUT_MS) -> tuple[RenderBundleEntry, Optional[str]]:
    """Renderiza `url` y devuelve (entry, rendered_html|None).

    `browser` es un `Browser` de Playwright ya conectado (local o remoto).
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    entry = RenderBundleEntry(
        render_schema_version=RENDER_SCHEMA_VERSION,
        url=url, captured_utc=_now(),
        capture_dom="networkidle", capture_timeout_ms=timeout_ms,
        playwright_chromium=getattr(browser, "version", None),
    )
    page = browser.new_page(user_agent=UA_STRING)
    rendered_html = None
    try:
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except PWTimeout:
            entry.status = "timeout"
            entry.error = f"networkidle no alcanzado en {timeout_ms} ms; se usa lo cargado"

        entry.final_url = page.url
        text = page.evaluate(extract.JS_TEXT_CONTENT) or ""
        entry.rendered_words = words(text)
        entry.rendered_text_sha256 = text_sha256(text)
        entry.ld_blocks = [b for b in (page.evaluate(extract.JS_LD_BLOCKS) or []) if b]
        entry.forms = [FormInfo(**f) for f in (page.evaluate(extract.JS_FORMS) or [])]
        entry.nav_links_internal = int(page.evaluate(extract.JS_NAV_LINKS_INTERNAL) or 0)
        entry.quote_link = bool(page.evaluate(extract.JS_QUOTE_LINK))
        entry.price_on_screen = bool(page.evaluate(extract.JS_PRICE_ON_SCREEN))
        entry.model_context = ModelContextInfo(**(page.evaluate(extract.JS_MODEL_CONTEXT) or {}))
        entry.footer_links = [FooterLink(**l) for l in (page.evaluate(extract.JS_FOOTER_LINKS) or [])][:40]
        if keep_html:
            rendered_html = page.content()
            entry.rendered_html_file = "rendered.html"
    except Exception as exc:  # noqa: BLE001
        entry.status = "error"
        entry.error = f"{type(exc).__name__}: {str(exc).splitlines()[0].strip()}"
    finally:
        page.close()
    return entry, rendered_html


def open_browser(playwright, ws_endpoint: Optional[str]):
    """Chromium local (default) o remoto vía `connect()` si se pasa `--ws`."""
    if ws_endpoint:
        return playwright.chromium.connect(ws_endpoint, timeout=15_000)
    return playwright.chromium.launch(headless=True, args=["--no-sandbox"])
