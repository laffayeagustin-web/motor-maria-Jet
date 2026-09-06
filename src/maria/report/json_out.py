"""Salida JSON canónica (RF-15) + sección de `unverified` de la corrida (RF-18).

El JSON es la fuente (principio 8): Markdown y tabla se derivan de acá, nunca al
revés. `to_dict()` es determinista — dos corridas sobre el mismo fixture dan el
mismo dict.
"""
from __future__ import annotations

import json

from maria_common.models import AuditRun


def to_dict(run: AuditRun) -> dict:
    d = json.loads(run.model_dump_json())
    d["puntaje_total"] = run.puntaje_total
    d["tier"] = run.tier
    for dim, dm in zip(d["dimensiones"], run.dimensiones):
        dim["puntos"] = dm.puntos
        for sub, sm in zip(dim["sub_criterios"], dm.sub_criterios):
            sub["puntos_efectivos"] = sm.puntos_efectivos
    d["unverified"] = [
        {"id": s.id, "nombre": s.nombre, "puntos_max": s.puntos_max, "motivo": s.motivo}
        for s in run.unverified
    ]
    d["hallazgos"] = sorted(
        d["hallazgos"], key=lambda h: _sev_rank(h["severidad"])
    )
    return d


def _sev_rank(sev: str) -> int:
    return {"critica": 0, "alta": 1, "media": 2, "informativa": 3}.get(sev, 4)


def to_json(run: AuditRun, *, indent: int = 2) -> str:
    return json.dumps(to_dict(run), ensure_ascii=False, indent=indent, sort_keys=False)
