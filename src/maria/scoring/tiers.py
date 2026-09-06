"""Tiers y pesos de la rúbrica (§2 de docs/plan.md). El cálculo vive en
`maria_common.models.AuditRun`; acá quedan las constantes y el chequeo de
calibración para el test de aceptación global."""
from __future__ import annotations

TIERS = [
    (0, 29, "Invisible"),
    (30, 54, "Parcial"),
    (55, 74, "Emergente"),
    (75, 100, "Líder GEO"),
]

DIMENSION_MAX = {"D1": 25, "D2": 20, "D3": 20, "D4": 15, "D5": 15, "D6": 5}
CORE_MAX = 100  # D1..D5; D6 es bonus por encima


def tier_for(core_score: float) -> str:
    for lo, hi, name in TIERS:
        if lo <= core_score <= hi:
            return name
    return "Líder GEO" if core_score > 100 else "Invisible"
