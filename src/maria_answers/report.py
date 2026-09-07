"""Salida del Índice de Respuestas: JSON canónico, y Markdown derivado de él.

Principio 8 del proyecto: el JSON es la fuente. El Markdown y la tabla no
recalculan nada — leen el dict que ya produjo `to_dict`.
"""
from __future__ import annotations

import json

from .contract import Captura, MarcaRun, PanelRespuestas


def to_dict(run: MarcaRun) -> dict:
    """Serialización canónica: el dump de pydantic más las propiedades calculadas."""
    d = json.loads(run.model_dump_json())
    d["puntaje_total"] = run.puntaje_total
    d["tier"] = run.tier
    d["cobertura"] = run.cobertura
    d["puntos_alcanzables"] = run.puntos_alcanzables
    for dim, señal in zip(d.get("dimensiones", []), run.dimensiones):
        dim["puntos"] = señal.puntos
        dim["puntos_max"] = señal.puntos_max
    return d


def to_json(run: MarcaRun, *, indent: int = 2) -> str:
    return json.dumps(to_dict(run), ensure_ascii=False, indent=indent, sort_keys=True)


def marca_report(run: MarcaRun) -> str:
    """Informe Markdown de una marca, derivado del JSON."""
    d = to_dict(run)
    total = d["puntaje_total"]
    cab = f"{d['cuenta']['nombre']} ({d['cuenta']['codigo']})"
    encabezado = (f"# {cab} — {total:g} · {d['tier']}" if total is not None
                  else f"# {cab} — sin cobertura")

    out = [encabezado, ""]
    out.append(f"- **Superficie:** {d['superficie']} · modelo `{d['modelo']}`")
    out.append(f"- **Cobertura:** {d['cobertura']} frases con búsqueda")
    out.append(f"- **Medición:** {d['timestamp_utc']}")
    if d["cuenta"].get("dominios"):
        out.append(f"- **Dominios propios:** {', '.join(d['cuenta']['dominios'])}")
    out.append("")

    if total is None:
        out.append("> Ninguna frase disparó búsqueda web. No es un cero: no hay "
                   "denominador para normalizar.")
        out.append("")
        return "\n".join(out)

    for dim in d["dimensiones"]:
        out.append(f"## {dim['id']} · {dim['nombre']} — {dim['puntos']:g}/{dim['puntos_max']:g}")
        out.append("")
        out.append("| frase | pts | estado | evidencia |")
        out.append("|---|---:|---|---|")
        for sub in dim["por_frase"]:
            ev = " · ".join(e["detalle"] for e in sub["evidencia"])
            out.append(f"| {sub['frase_id']} | {sub['puntos']:g}/{sub['puntos_max']:g} "
                       f"| {sub['estado']} | {ev} |")
        out.append("")
    return "\n".join(out)


def panel_table(runs: list[MarcaRun]) -> str:
    """Tabla comparativa del panel. Las marcas sin cobertura van aparte."""
    medidas = [r for r in runs if r.puntaje_total is not None]
    sin_cob = [r for r in runs if r.puntaje_total is None]

    out = ["# Panel de Respuestas — tabla comparativa", ""]
    if medidas:
        sup, mod = medidas[0].superficie, medidas[0].modelo
        out.append(f"_Superficie: {sup} · modelo `{mod}`. "
                   f"Puntaje sobre 100, normalizado a las frases con búsqueda._")
        out.append("")
    out.append("| # | marca | R1 mención | R2 cita | R3 posición | /100 | cobertura | tier |")
    out.append("|---|---|---:|---:|---:|---:|---|---|")
    for i, r in enumerate(medidas, 1):
        dims = {x.id: x for x in r.dimensiones}
        out.append(
            f"| {i} | {r.cuenta.nombre} ({r.cuenta.codigo}) "
            f"| {dims['R1'].puntos:g} | {dims['R2'].puntos:g} | {dims['R3'].puntos:g} "
            f"| {r.puntaje_total:g} | {r.cobertura} | {r.tier} |"
        )

    if sin_cob:
        out += ["", "## Sin cobertura", ""]
        for r in sin_cob:
            out.append(f"- **{r.cuenta.nombre} ({r.cuenta.codigo})** — ninguna frase "
                       "disparó búsqueda web")
    return "\n".join(out)


def cobertura_dict(
    panel: PanelRespuestas,
    capturas: list[Captura],
    *,
    repeticiones: int,
    medicion_utc: str | None,
) -> dict:
    """Cobertura de la corrida agregada por frase.

    Es propiedad de la corrida, no de la marca: la página la publica junto al
    ranking. Una frase cuenta como `con_busqueda` si alguna de sus repeticiones
    disparó búsqueda; si ninguna lo hizo pero hubo respuesta, `sin_busqueda`; si
    solo hubo errores de API, `error`.
    """
    frases_txt = {f.id: f.texto for f in panel.frases}
    frases_tipo = {f.id: f.tipo for f in panel.frases}
    por_frase: dict[str, dict] = {}
    for cap in capturas:
        e = por_frase.setdefault(cap.frase_id, {
            "id": cap.frase_id, "texto": frases_txt.get(cap.frase_id, cap.frase_texto),
            "tipo": frases_tipo.get(cap.frase_id, "general"),
            "estado": "error", "repeticiones": 0, "con_busqueda": 0, "motivo": None,
        })
        e["repeticiones"] += 1
        if cap.estado == "con_busqueda":
            e["con_busqueda"] += 1
        elif e["motivo"] is None:
            e["motivo"] = cap.motivo
    for e in por_frase.values():
        e["estado"] = "con_busqueda" if e["con_busqueda"] else (
            "sin_busqueda" if e["motivo"] else "error")
    frases_lista = [por_frase[f.id] for f in panel.frases if f.id in por_frase]
    return {
        "con_busqueda": sum(1 for e in frases_lista if e["estado"] == "con_busqueda"),
        "total": len(frases_lista),
        "modelo": panel.modelo,
        "superficie": panel.superficie,
        "repeticiones": repeticiones,
        "medicion_utc": medicion_utc,
        "frases": frases_lista,
    }


def resumen_capturas(capturas: list[Captura]) -> str:
    """Estado de las frases de la corrida: qué se pudo medir y qué no."""
    con = [c for c in capturas if c.estado == "con_busqueda"]
    out = ["# Frases de la corrida", "",
           f"Cobertura: **{len(con)}/{len(capturas)}** con búsqueda web.", "",
           "| frase | estado | fuentes | búsquedas | motivo |", "|---|---|---:|---:|---|"]
    for c in capturas:
        out.append(f"| {c.frase_id} | {c.estado} | {len(c.fuentes)} | "
                   f"{len(c.busquedas)} | {c.motivo or ''} |")
    return "\n".join(out)
