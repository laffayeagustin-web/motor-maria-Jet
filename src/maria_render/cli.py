"""CLI de la notebook: `maria-render`.

Captura el DOM renderizado de un conjunto de URLs y escribe el render bundle que
consume `maria` en el servidor. Handoff por artefacto: no hay conexión en vivo
con el servidor (salvo `--ws` a un Chromium remoto, que es conveniencia).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False, help="Captura de DOM renderizado para el Índice Jet MarIA (notebook).")


def _collect_urls(url, urls_file, panel) -> list[str]:
    urls: list[str] = list(url or [])
    if urls_file:
        urls += [l.strip() for l in Path(urls_file).read_text("utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
    if panel:
        import yaml
        data = yaml.safe_load(Path(panel).read_text("utf-8")) or {}
        urls += [c["url"] for c in data.get("cuentas", []) if c.get("url")]
    return list(dict.fromkeys(urls))


@app.command()
def run(
    url: Optional[list[str]] = typer.Option(None, "--url", help="URL suelta (repetible)"),
    urls_file: Optional[Path] = typer.Option(None, "--urls-file"),
    panel: Optional[Path] = typer.Option(None, "--panel", help="panels/panel-ar.yaml"),
    out: Path = typer.Option(..., "--out", help="directorio del bundle"),
    keep_html: bool = typer.Option(False, "--keep-html", help="guarda rendered.html por URL"),
    ws: Optional[str] = typer.Option(None, "--ws", help="Chromium remoto ws://... (opcional)"),
    concurrency: int = typer.Option(1, "--concurrency", help="páginas en paralelo (1 = cortés)"),
):
    """Renderiza las URLs y escribe el bundle en --out."""
    from playwright.sync_api import sync_playwright

    from .bundle import write_entry, write_manifest
    from .capture import capture_one, open_browser
    from maria_common.render_contract import RenderManifestAccount

    urls = _collect_urls(url, urls_file, panel)
    if not urls:
        raise typer.BadParameter("pasá --url, --urls-file o --panel")
    out.mkdir(parents=True, exist_ok=True)

    accounts: list[RenderManifestAccount] = []
    with sync_playwright() as p:
        browser = open_browser(p, ws)
        version = getattr(browser, "version", None)
        try:
            for u in urls:
                entry, html = capture_one(u, browser=browser, keep_html=keep_html)
                folder = write_entry(out, entry, html)
                accounts.append(RenderManifestAccount(url=u, status=entry.status, dir=folder,
                                                      error=entry.error))
                typer.echo(f"{entry.status:>8}  {u}  ({entry.rendered_words} palabras, {len(entry.ld_blocks)} JSON-LD)")
        finally:
            browser.close()
        write_manifest(out, accounts, version)

    ok = sum(1 for a in accounts if a.status == "ok")
    typer.echo(f"\nbundle -> {out}  ({ok}/{len(accounts)} ok)")


if __name__ == "__main__":
    app()
