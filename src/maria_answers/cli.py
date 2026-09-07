"""CLI del Índice de Respuestas: `maria-respuestas`.

    maria-respuestas panel panels/respuestas-es-aviacion.yaml
    maria-respuestas panel <panel> --desde-crudo out/crudo-respuestas   # sin red
    maria-respuestas frase "alquiler de jet privado"

`panel` es el comando del cron: consulta, puntúa, archiva el histórico y escribe
los informes. `--desde-crudo` recalcula sobre respuestas ya guardadas, sin gastar
cuota — es lo que hay que usar cuando cambia la rúbrica y no la medición.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import typer

from maria.store import runs as runstore

from .acquire import REPETICIONES_POR_DEFECTO, capturar_panel, capturas_desde_disco
from .contract import Captura, MarcaRun
from .panel import load_panel
from .report import (
    cobertura_dict,
    marca_report,
    panel_table,
    resumen_capturas,
    to_dict,
    to_json,
)
from .score import puntuar_panel
from .serie import serie_dict
from .surfaces import obtener_superficie

app = typer.Typer(add_completion=False,
                  help="Índice de Visibilidad en Respuestas de IA.")


@app.callback()
def _setup(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")


@app.command()
def panel(
    panel_file: Path = typer.Argument(..., help="panels/respuestas-<slug>.yaml"),
    desde_crudo: Optional[Path] = typer.Option(
        None, "--desde-crudo", help="recalcula sobre respuestas guardadas, sin red"),
    repeticiones: int = typer.Option(
        REPETICIONES_POR_DEFECTO, "--repeticiones",
        help="consultas por frase; se agregan por frecuencia (§7 de la rúbrica)"),
    cache: bool = typer.Option(
        False, "--cache", help="reusa respuestas de menos de 6 h (solo para desarrollo)"),
    out_dir: Path = typer.Option(Path("out/runs-respuestas"), "--out-dir"),
    report_dir: Path = typer.Option(Path("out/report-respuestas"), "--report-dir"),
    crudo_dir: Path = typer.Option(Path("out/crudo-respuestas"), "--crudo-dir"),
    serie_n: int = typer.Option(
        30, "--serie-n", help="cuántas corridas del histórico se publican en la serie"),
) -> None:
    """Mide el panel completo, archiva el histórico y escribe los informes."""
    p = load_panel(panel_file)

    if desde_crudo:
        capturas = capturas_desde_disco(p, desde_crudo)
        if not capturas:
            raise typer.BadParameter(f"no hay respuestas guardadas en {desde_crudo}")
    else:
        def progreso(c: Captura) -> None:
            typer.echo(f"  {c.estado:>13}  {c.frase_id}  "
                       f"({len(c.fuentes)} fuentes, {len(c.busquedas)} búsquedas)")
        typer.echo(f"Consultando {len(p.frases)} frases × {repeticiones} "
                   f"repeticiones en {p.superficie} ({p.modelo})…")
        capturas = capturar_panel(p, repeticiones=repeticiones, usar_cache=cache,
                                  crudo_dir=crudo_dir, on_progress=progreso)

    resultados = puntuar_panel(p, capturas)

    report_dir.mkdir(parents=True, exist_ok=True)
    for run in resultados:
        prev = runstore.previous(run.cuenta.codigo, out_dir, MarcaRun)
        runstore.archive(run, out_dir)
        d = to_dict(run)
        d["delta"] = runstore.delta(run, prev)
        # Serie y media móvil de 7 días: la rúbrica (§7 bis) exige publicar el
        # promedio móvil junto al valor del día, porque un movimiento de una sola
        # corrida está dentro del ruido medido.
        d["serie"] = serie_dict(run.cuenta.codigo, out_dir, n=serie_n)
        d["media_movil_7d"] = d["serie"][-1]["media_movil_7d"] if d["serie"] else None
        (report_dir / f"{run.cuenta.codigo}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")
        (report_dir / f"{run.cuenta.codigo}.md").write_text(marca_report(run), "utf-8")

    tabla = panel_table(resultados)
    (report_dir / "panel.md").write_text(tabla, "utf-8")
    (report_dir / "frases.md").write_text(resumen_capturas(capturas), "utf-8")

    # Cobertura del panel, agregada por frase. Es propiedad de la corrida, no de
    # la marca: la página la publica junto al ranking.
    cobertura = cobertura_dict(
        p, capturas, repeticiones=repeticiones,
        medicion_utc=resultados[0].timestamp_utc if resultados else None,
    )
    (report_dir / "frases.json").write_text(
        json.dumps(cobertura, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")

    typer.echo("")
    typer.echo(tabla)


@app.command()
def frase(
    texto: str = typer.Argument(..., help="la frase a consultar"),
    superficie: str = typer.Option("gemini", "--superficie"),
    modelo: Optional[str] = typer.Option(None, "--modelo"),
    crudo: bool = typer.Option(False, "--crudo", help="imprime el JSON de la API"),
) -> None:
    """Consulta una sola frase y muestra qué devolvió la superficie."""
    from .parse import desde_gemini

    s = obtener_superficie(superficie, modelo=modelo)
    data = s.consultar(texto)
    if crudo:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    cap = desde_gemini(data, frase_id="AD-HOC", frase_texto=texto, modelo=s.modelo)
    typer.echo(f"estado    : {cap.estado}" + (f"  ({cap.motivo})" if cap.motivo else ""))
    typer.echo(f"modelo    : {cap.modelo}")
    typer.echo(f"búsquedas : {cap.busquedas}")
    typer.echo(f"fuentes   : {[f.dominio for f in cap.fuentes]}")
    typer.echo(f"palabras  : {len(cap.texto.split())}")


@app.command()
def informe(run_json: Path = typer.Argument(..., help="un <COD>.json ya calculado")) -> None:
    """Deriva el Markdown de una corrida guardada, sin recalcular."""
    run = MarcaRun.model_validate_json(run_json.read_text("utf-8"))
    typer.echo(marca_report(run))


def _escribir_propuesta(prop, destino_dir: Path, slug: str) -> dict:
    """Guarda el YAML propuesto (sin congelar) + la corrida de medición al toque."""
    import yaml

    destino_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = destino_dir / f"{slug}.yaml"
    yaml_path.write_text(
        "# PROPUESTA SIN CONGELAR — generada por `maria-respuestas proponer`.\n"
        "# Revisar a mano y mover a panels/ para que entre al cron diario.\n\n"
        + yaml.safe_dump(prop.to_yaml_dict(), allow_unicode=True, sort_keys=False),
        "utf-8")

    resultados = puntuar_panel(prop.panel, prop.capturas_semilla)
    tabla = panel_table(resultados)
    (destino_dir / f"{slug}-corrida.md").write_text(tabla, "utf-8")
    (destino_dir / f"{slug}-frases.md").write_text(
        resumen_capturas(prop.capturas_semilla), "utf-8")

    medidas = [r for r in resultados if r.puntaje_total is not None]
    return {
        "yaml": str(yaml_path),
        "marcas": len(prop.panel.marcas),
        "frases": len(prop.panel.frases),
        "dominios_citados": len(prop.dominios_citados),
        "medidas": len(medidas),
        "empresa_top": medidas[0].cuenta.nombre if medidas else None,
    }


@app.command()
def proponer(
    industria: str = typer.Option(..., "--industria"),
    empresa: str = typer.Option(..., "--empresa"),
    dominio: str = typer.Option(..., "--dominio"),
    pais: str = typer.Option("ES", "--pais"),
    idioma: str = typer.Option("es", "--idioma"),
    out_dir: Path = typer.Option(Path("out/propuestas"), "--out-dir"),
) -> None:
    """Industria + empresa + dominio → panel propuesto (sin congelar) + una corrida.

    Es el paso del formulario: Gemini arma 10 frases, se corren con grounding, y
    los competidores salen de los dominios que Google citó de hecho (rúbrica §6),
    no de la memoria del modelo. Un humano revisa y, si aprueba, mueve el YAML a
    `panels/`.
    """
    from .propose import proponer as _proponer

    slug = _slug(f"{pais}-{industria}-{empresa}")
    typer.echo(f"Proponiendo panel para {empresa} ({industria}, {pais})…")
    prop = _proponer(
        industria, empresa, dominio, pais=pais, idioma=idioma,
        on_progress=lambda c: typer.echo(f"  {c.estado:>13}  {c.frase_id}  "
                                         f"({len(c.fuentes)} fuentes)"))
    resumen = _escribir_propuesta(prop, out_dir, slug)

    typer.echo("")
    typer.echo(f"Propuesta escrita en {resumen['yaml']}")
    typer.echo(f"  {resumen['marcas']} marcas · {resumen['frases']} frases · "
               f"{resumen['dominios_citados']} dominios citados en la sonda")
    typer.echo("Revisá el YAML y movelo a panels/ para congelarlo y activar el cron.")


@app.command()
def cola(
    cola_dir: Path = typer.Option(Path("out/solicitudes"), "--cola-dir"),
    out_dir: Path = typer.Option(Path("out/propuestas"), "--out-dir"),
    tope_diario: int = typer.Option(15, "--tope-diario",
                                    help="máximo de propuestas nuevas por día (UTC)"),
    max_solicitudes: int = typer.Option(5, "--max", help="cuántas atender en esta pasada"),
    dry_run: bool = typer.Option(False, "--dry-run", help="no consulta a Gemini; solo valida"),
) -> None:
    """Procesa la cola del formulario: valida límites, genera la propuesta, mueve el archivo."""
    from datetime import datetime, timezone

    from .propose import proponer as _proponer
    from .solicitudes import ColaDisco, Rechazo, puede_procesarse

    cd = ColaDisco(cola_dir)
    pendientes = cd.pendientes()[:max_solicitudes]
    if not pendientes:
        typer.echo("cola vacía: nada pendiente de verificar y procesar")
        return

    for sol in pendientes:
        typer.echo(f"\n[{sol.id}] {sol.empresa} · {sol.industria} · {sol.dominio}")
        try:
            puede_procesarse(sol, cd, tope_diario=tope_diario)
        except Rechazo as r:
            typer.echo(f"  rechazada: {r.motivo}")
            sol.motivo_rechazo = r.motivo
            cd.mover(sol, "rechazada")
            continue

        if dry_run:
            typer.echo("  (dry-run) pasa los límites; no se consulta a Gemini")
            continue

        prop = _proponer(sol.industria, sol.empresa, sol.dominio_normalizado(),
                         pais="ES", idioma="es")
        resumen = _escribir_propuesta(prop, out_dir, _slug(f"{sol.id}-{sol.empresa}"))
        resumen["procesada_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        sol.resultado = resumen
        cd.mover(sol, "procesada")
        typer.echo(f"  propuesta lista: {resumen['yaml']}  "
                   f"({resumen['marcas']} marcas, {resumen['medidas']} medidas)")


def _slug(s: str) -> str:
    import re
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                if unicodedata.category(c) != "Mn")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:60] or "propuesta"


if __name__ == "__main__":
    app()
