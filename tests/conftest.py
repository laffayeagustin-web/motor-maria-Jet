"""Helpers para construir contextos de probe y bundles sin tocar la red ni Playwright.

Principio 5: la suite base corre offline. El HTML es sintético y mínimo — no es
contenido de terceros, es la forma que el probe necesita ver.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from maria.probes._base import ProbeContext
from maria_common.render_contract import RenderBundleEntry


def make_ctx(
    *,
    url: str = "https://ejemplo.com",
    raw_html: str = "<html><head><title>x</title></head><body></body></html>",
    status: int = 200,
    robots_txt: str | None = "User-agent: *\nDisallow:\n",
    render: RenderBundleEntry | None = None,
    estado_fetch: str | None = None,
    motivo_fetch: str | None = None,
    **kw,
) -> ProbeContext:
    ctx = ProbeContext(
        url=url, raw_html=raw_html, raw_tree=LexborHTMLParser(raw_html),
        status=status, final_url=kw.pop("final_url", url), robots_txt=robots_txt,
        render=render, estado_fetch=estado_fetch, motivo_fetch=motivo_fetch,
    )
    for k, v in kw.items():
        setattr(ctx, k, v)
    return ctx


def make_render(**kw) -> RenderBundleEntry:
    base = dict(url="https://ejemplo.com", captured_utc="2026-09-05T00:00:00+00:00")
    base.update(kw)
    return RenderBundleEntry(**base)


@pytest.fixture
def ctx_factory():
    return make_ctx


@pytest.fixture
def render_factory():
    return make_render


@pytest.fixture
def tmp_bundle_dir(tmp_path: Path):
    """Crea un dir de bundle con MANIFEST y N entries."""
    def _build(entries: list[RenderBundleEntry], manifest_version: str = "1.0") -> Path:
        from urllib.parse import urlparse

        d = tmp_path / "bundle"
        d.mkdir()
        cuentas = []
        for e in entries:
            folder = d / (urlparse(e.url).netloc.replace(":", "_") + "__home")
            folder.mkdir()
            (folder / "render.json").write_text(e.model_dump_json(indent=2), "utf-8")
            cuentas.append({"url": e.url, "status": e.status, "dir": folder.name})
        manifest = {
            "render_schema_version": manifest_version,
            "captured_utc": "2026-09-05T00:00:00+00:00",
            "user_agent": "MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)",
            "capture_dom": "networkidle",
            "cuentas": cuentas,
        }
        import json
        (d / "MANIFEST.json").write_text(json.dumps(manifest), "utf-8")
        return d
    return _build
