"""Tabla comparativa del panel (RF-17), ordenada por puntaje, con grupo y flujo.

Regla (enmienda §4): una cuenta que no es `medido` nunca se promedia con las
medidas sin decirlo. `inaccesible` / `bloqueado` / `no_aplica` quedan fuera del
ranking, listadas aparte.
"""
from __future__ import annotations

from maria_common.models import AuditRun


def panel_table(runs: list[AuditRun]) -> str:
    medibles = [r for r in runs if r.estado in ("medido", "unverified")]
    aparte = [r for r in runs if r.estado in ("bloqueado", "inaccesible", "no_aplica")]
    medibles.sort(key=lambda r: r.puntaje_total or 0, reverse=True)

    out: list[str] = []
    out.append("# Panel — tabla comparativa")
    out.append("")
    out.append("| # | cuenta | grupo | flujo | D1 | D2 | D3 | D4 | D5 | /100 | +D6 | tier | estado |")
    out.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for i, r in enumerate(medibles, 1):
        dims = {d.id: d.puntos for d in r.dimensiones}
        core = sum(v for k, v in dims.items() if not k.startswith("D6"))
        out.append(
            f"| {i} | {r.cuenta.nombre} ({r.cuenta.codigo}) | {r.cuenta.grupo} | {r.cuenta.flujo} | "
            f"{dims.get('D1', 0):g} | {dims.get('D2', 0):g} | {dims.get('D3', 0):g} | "
            f"{dims.get('D4', 0):g} | {dims.get('D5', 0):g} | {round(min(core,100),1):g} | "
            f"{dims.get('D6', 0):g} | {r.tier} | {r.estado} |"
        )
    out.append("")

    if aparte:
        out.append("## Fuera del ranking")
        out.append("")
        for r in aparte:
            out.append(f"- **{r.cuenta.nombre} ({r.cuenta.codigo})** — {r.estado}"
                       + (f": {r.motivo}" if r.motivo else ""))
        out.append("")

    total_unv = sum(len(r.unverified) for r in medibles)
    if total_unv:
        out.append(f"_{total_unv} sub-criterios `unverified` en la corrida (ver informes por cuenta)._")
        out.append("")
    return "\n".join(out)
