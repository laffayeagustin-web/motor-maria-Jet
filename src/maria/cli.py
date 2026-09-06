"""CLI del servidor: `maria audit` / `maria report` / `maria panel`.

No importa `playwright` en ningún camino. El render llega solo como bundle.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from .analyst import apply_analyst_notes
from .audit import audit_account, audit_panel
from .panel import load_panel
from .report import json_out, markdown, panel_table
from .store import runs as runstore

app = typer.Typer(add_completion=False, help="Motor del Índice de Visibilidad IA — herramienta del servidor.")


@app.callback()
def _setup(verbose: bool = typer.Option(False, "--verbose", "-v")):
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def audit(
    url: str = typer.Argument(..., help="URL a auditar"),
    codigo: str = typer.Option("ADHOC", help="código de cuenta"),
    nombre: Optional[str] = typer.Option(None),
    render_bundle: Optional[Path] = typer.Option(None, "--render-bundle", help="dir del render bundle"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    out_dir: Path = typer.Option(Path("out/runs"), "--out-dir"),
    md: bool = typer.Option(False, "--md", help="imprime el informe Markdown en vez del JSON"),
):
    """Audita una sola URL."""
    from maria_common.models import Account

    from .render_bundle import load_bundle

    acc = Account(codigo=codigo, nombre=nombre or url, url=url)
    run = audit_account(acc, bundle=load_bundle(render_bundle), no_cache=no_cache)
    prev = runstore.previous(acc.codigo, out_dir)
    runstore.archive(run, out_dir)
    if md:
        typer.echo(markdown.account_report(run))
    else:
        d = json_out.to_dict(run)
        d["delta"] = runstore.delta(run, prev)
        typer.echo(json_out.json.dumps(d, ensure_ascii=False, indent=2))


@app.command()
def panel(
    panel_file: Path = typer.Argument(..., help="panels/panel-ar.yaml"),
    render_bundle: Optional[Path] = typer.Option(None, "--render-bundle"),
    analyst_notes: Optional[Path] = typer.Option(None, "--analyst-notes"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    workers: int = typer.Option(4, "--workers"),
    out_dir: Path = typer.Option(Path("out/runs"), "--out-dir"),
    report_dir: Path = typer.Option(Path("out/report"), "--report-dir"),
):
    """Audita el panel completo y escribe informes + tabla comparativa."""
    accounts = load_panel(panel_file)
    results = audit_panel(accounts, bundle_dir=render_bundle, no_cache=no_cache, workers=workers)
    apply_analyst_notes(results, analyst_notes)

    report_dir.mkdir(parents=True, exist_ok=True)
    for run in results:
        runstore.archive(run, out_dir)
        (report_dir / f"{run.cuenta.codigo}.json").write_text(json_out.to_json(run), "utf-8")
        (report_dir / f"{run.cuenta.codigo}.md").write_text(markdown.account_report(run), "utf-8")
    table = panel_table.panel_table(results)
    (report_dir / "panel.md").write_text(table, "utf-8")
    typer.echo(table)


@app.command()
def report(
    run_json: Path = typer.Argument(..., help="un JSON de out/runs/<cod>/<ts>.json"),
):
    """Deriva el informe Markdown de un JSON ya calculado (RF-16, sin recálculo)."""
    from maria_common.models import AuditRun

    run = AuditRun.model_validate_json(run_json.read_text("utf-8"))
    typer.echo(markdown.account_report(run))


if __name__ == "__main__":
    app()
