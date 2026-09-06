"""D6 · Frontera WebMCP/MCP — 5 pts bonus.

D6.1 (`navigator.modelContext`) necesita ejecutar JS → viene del bundle. D6.2
(`llms.txt` / `/.well-known/` de agentes / feed estructurado) lo resuelve el
orquestador con fetch estático y lo deja en `ctx.llms_txt_present` /
`ctx.well_known`.
"""
from __future__ import annotations

from maria_common.models import DimensionResult

from ._base import RENDER_MISSING, ProbeContext, dimension, ev_rendered, ev_static, scored, unverified


def run(ctx: ProbeContext) -> DimensionResult:
    subs = []

    # --- D6.1 navigator.modelContext con herramientas registradas (3) ---
    if ctx.render is None:
        subs.append(unverified("D6.1", "navigator.modelContext con herramientas registradas", 3, RENDER_MISSING))
    else:
        mc = ctx.render.model_context
        ok = mc.present and mc.tools > 0
        subs.append(scored("D6.1", "navigator.modelContext con herramientas registradas", 3, 3 if ok else 0,
                           [ev_rendered(f"modelContext presente={mc.present}, herramientas={mc.tools}")],
                           status="rendered"))

    # --- D6.2 llms.txt / .well-known de agentes / feed estructurado (2) ---
    señales = []
    if ctx.llms_txt_present:
        señales.append("/llms.txt")
    señales += ctx.well_known
    subs.append(scored("D6.2", "llms.txt, /.well-known/ de agentes o feed estructurado", 2,
                       2 if señales else 0,
                       [ev_static(f"encontrados: {señales or 'ninguno'}")]))

    return dimension("D6", "Frontera WebMCP/MCP", 5, subs)
