"""D1 · Estructura Semántica — 25 pts.

JSON-LD del DOM renderizado (principio 2: se compara con el crudo y si difieren se
reportan ambos). RF-13: si el único schema es boilerplate sin Organization con
datos, la dimensión no supera 10/25.
"""
from __future__ import annotations

from maria_common.jsonld import (
    all_types,
    has_org_con_datos,
    node_types,
    parse_blocks,
    ORG_TYPES,
    CHARTER_TYPES,
)
from maria_common.models import DimensionResult

from ._base import (
    RENDER_MISSING,
    ProbeContext,
    dimension,
    ev_rendered,
    ev_static,
    scored,
    unverified,
)


def _raw_ld_blocks(ctx: ProbeContext) -> list[str]:
    return [n.text() for n in ctx.tree().css('script[type="application/ld+json"]')]


def run(ctx: ProbeContext) -> DimensionResult:
    subs = []
    raw_blocks = _raw_ld_blocks(ctx)
    raw_nodes, raw_ok, raw_total = parse_blocks(raw_blocks)
    raw_types = all_types(raw_nodes)

    if ctx.render is None:
        # Principio 2: sin render no se puede confirmar el <head>. Se evalúa
        # D1.1 con el crudo (avisando) y el resto queda unverified.
        subs.append(scored(
            "D1.1", "JSON-LD presente y parseable (solo HTML crudo — sin render, principio 2)",
            5, 5 if raw_ok else 0,
            [ev_static(f"crudo: {raw_total} bloques, {raw_ok} parseables; tipos {sorted(raw_types)}")],
        ))
        for sid, nombre in [
            ("D1.2", "Organization/LocalBusiness con name + url"),
            ("D1.3", "address + telephone dentro del schema"),
            ("D1.4", "Service/Offer/Product describiendo el chárter"),
            ("D1.5", "sameAs + logo + aggregateRating"),
        ]:
            subs.append(unverified(sid, nombre, 5, RENDER_MISSING))
        return _cap(ctx, dimension("D1", "Estructura Semántica", 25, subs), raw_nodes, [])

    ren_nodes, ren_ok, ren_total = parse_blocks(ctx.render.ld_blocks)
    ren_types = all_types(ren_nodes)
    difieren = raw_types != ren_types
    ev_p2 = ev_rendered(
        f"crudo {raw_total} bloques/{sorted(raw_types)}; renderizado {ren_total} bloques/{sorted(ren_types)}"
        + ("  ⚠ DIFIEREN (principio 2: se reportan ambos)" if difieren else "")
    )
    subs.append(scored("D1.1", "JSON-LD presente y parseable (crudo + DOM renderizado, principio 2)",
                       5, 5 if ren_ok else 0, [ev_p2], status="rendered"))

    orgs = [n for n in ren_nodes if node_types(n) & ORG_TYPES]
    org_name_url = any(n.get("name") and n.get("url") for n in orgs)
    subs.append(scored("D1.2", "Nodo Organization/LocalBusiness con name + url", 5,
                       5 if org_name_url else 0,
                       [ev_rendered(f"{len(orgs)} nodos Organization/LocalBusiness; con name+url: {org_name_url}")],
                       status="rendered"))

    addr_tel = any(
        n.get("address") is not None and n.get("telephone") not in (None, "")
        for n in ren_nodes
    )
    subs.append(scored("D1.3", "address + telephone dentro del schema", 5,
                       5 if addr_tel else 0,
                       [ev_rendered(f"algún nodo con address+telephone: {addr_tel}")],
                       status="rendered"))

    charter = sorted(all_types(ren_nodes) & CHARTER_TYPES)
    subs.append(scored("D1.4", "Service / Offer / Product describiendo el chárter", 5,
                       5 if charter else 0,
                       [ev_rendered(f"tipos presentes: {charter or 'ninguno'}")],
                       status="rendered"))

    has_sameas = any(n.get("sameAs") for n in orgs)
    has_logo = any(n.get("logo") for n in orgs)
    has_rating = any(n.get("aggregateRating") for n in ren_nodes)
    pts = round((has_sameas + has_logo + has_rating) * (5 / 3), 2)
    subs.append(scored("D1.5", "sameAs + logo + aggregateRating (1,67 pts c/u)", 5, pts,
                       [ev_rendered(f"sameAs={has_sameas}, logo={has_logo}, aggregateRating={has_rating}")],
                       status="rendered"))

    return _cap(ctx, dimension("D1", "Estructura Semántica", 25, subs), raw_nodes, ren_nodes)


def _cap(ctx: ProbeContext, dim: DimensionResult, raw_nodes, ren_nodes) -> DimensionResult:
    """RF-13: solo boilerplate sin Organization con datos → D1 ≤ 10."""
    nodes = ren_nodes or raw_nodes
    if has_org_con_datos(nodes):
        return dim
    bruto = sum(s.puntos_efectivos for s in dim.sub_criterios)
    if bruto > 10:
        dim.tope_aplicado = (
            f"RF-13: schema solo {sorted(all_types(nodes)) or 'ausente'} sin Organization "
            f"con datos → D1 limitado de {round(bruto, 2)} a 10"
        )
        dim.cap = 10
    return dim
