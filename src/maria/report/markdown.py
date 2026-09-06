"""Informe Markdown por cuenta (RF-16). Se deriva del dict de `json_out`, sin
recalcular nada."""
from __future__ import annotations

from .json_out import to_dict


def account_report(run) -> str:
    d = to_dict(run)
    c = d["cuenta"]
    out: list[str] = []
    total = d["puntaje_total"]
    tier = d["tier"]
    head = f"# {c['nombre']} ({c['codigo']}) — "
    head += f"{total} · {tier}" if total is not None else f"estado: {d['estado']}"
    out.append(head)
    out.append("")
    out.append(f"- **URL:** {c['url'] or '—'}")
    out.append(f"- **Grupo:** {c['grupo']} · **Flujo:** {c['flujo']}")
    out.append(f"- **Estado:** {d['estado']}" + (f" — {d['motivo']}" if d.get("motivo") else ""))
    if d.get("render_bundle_ref"):
        out.append(f"- **Render bundle:** {d['render_bundle_ref']}")
    out.append("")

    for dim in d["dimensiones"]:
        out.append(f"## {dim['id']} · {dim['nombre']} — {dim['puntos']}/{dim['puntos_max']}")
        if dim.get("tope_aplicado"):
            out.append(f"> ⚠ {dim['tope_aplicado']}")
        out.append("")
        out.append("| sub | pts | estado | evidencia |")
        out.append("|---|---:|---|---|")
        for s in dim["sub_criterios"]:
            pts = s["puntos_efectivos"]
            ev = "; ".join(e["detail"] for e in s["evidencia"]) or (s.get("motivo") or "")
            out.append(f"| {s['id']} {s['nombre']} | {pts}/{s['puntos_max']} | {s['status']} | {ev} |")
        out.append("")

    if d["unverified"]:
        out.append("## Sub-criterios sin verificar")
        out.append("")
        for u in d["unverified"]:
            out.append(f"- **{u['id']}** {u['nombre']} ({u['puntos_max']} pts máx) — {u['motivo']}")
        out.append("")

    if d["hallazgos"]:
        out.append("## Hallazgos")
        out.append("")
        for h in d["hallazgos"]:
            tag = f"[{h['severidad']}]"
            origin = "" if h["origin"] == "motor" else " _(analyst)_"
            out.append(f"- {tag} {h.get('dimension') or ''} {h['detalle']}{origin}")
        out.append("")

    if d["anomalias"]:
        out.append("## Anomalías")
        out.append("")
        for a in d["anomalias"]:
            out.append(f"- {a}")
        out.append("")

    return "\n".join(out)
