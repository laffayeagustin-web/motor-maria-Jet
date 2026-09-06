"""T5a — `maria_render` captura el DOM y escribe un bundle válido.

Marcado `render`: necesita Playwright + Chromium, fuera del CI base. Se salta
solo si `playwright` no está instalado (perfil servidor).
"""
import pytest

pytest.importorskip("playwright", reason="perfil servidor: playwright no instalado")
pytestmark = pytest.mark.render


def test_captura_escribe_render_json_valido(tmp_path):
    from playwright.sync_api import sync_playwright

    from maria_render.bundle import write_entry, write_manifest
    from maria_render.capture import capture_one, open_browser
    from maria_common.render_contract import RenderBundleEntry, RenderManifestAccount

    html = tmp_path / "page.html"
    html.write_text(
        '<html><head><title>T</title>'
        '<script type="application/ld+json">{"@type":"Organization","name":"T"}</script>'
        '</head><body><form><input required><input></form>'
        '<footer><a href="/privacidad">Privacidad</a></footer></body></html>',
        "utf-8",
    )
    url = html.as_uri()

    with sync_playwright() as p:
        browser = open_browser(p, None)
        try:
            entry, rendered = capture_one(url, browser=browser, keep_html=True)
        finally:
            browser.close()

    out = tmp_path / "bundle"
    out.mkdir()
    folder = write_entry(out, entry, rendered)
    write_manifest(out, [RenderManifestAccount(url=url, status=entry.status, dir=folder)], None)

    reloaded = RenderBundleEntry.model_validate_json((out / folder / "render.json").read_text("utf-8"))
    assert reloaded.usable
    assert reloaded.rendered_words and reloaded.ld_blocks
    assert reloaded.forms and reloaded.forms[0].required == 1
    assert any("privacidad" in fl.href for fl in reloaded.footer_links)
