"""Anexo de hallazgos redactados por el analista (RF-20).

Se cargan de un YAML, aparecen en el informe con `origin: analyst` y **no**
modifican el puntaje. RF-21: si el YAML trae una medición de tiempo de respuesta
del Paso Cero, se anexa como hallazgo informativo, también sin tocar el puntaje.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from maria_common.models import AuditRun, Finding


def apply_analyst_notes(runs: list[AuditRun], path: Path | str | None) -> None:
    if path is None:
        return
    data = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    by_code: dict[str, list[Finding]] = {}
    for codigo, notas in (data.get("cuentas") or {}).items():
        items = []
        for h in notas.get("hallazgos", []):
            items.append(Finding(
                severidad=h.get("severidad", "media"),
                dimension=h.get("dimension"),
                detalle=h["detalle"],
                origin="analyst",
            ))
        if notas.get("tiempo_respuesta_pasocero"):
            items.append(Finding(
                severidad="informativa", dimension=None,
                detalle=f"Paso Cero — tiempo de respuesta medido: {notas['tiempo_respuesta_pasocero']} "
                        "(dato del analista, no entra al puntaje).",
                origin="analyst",
            ))
        by_code[codigo] = items

    for run in runs:
        extra = by_code.get(run.cuenta.codigo)
        if extra:
            run.hallazgos.extend(extra)
