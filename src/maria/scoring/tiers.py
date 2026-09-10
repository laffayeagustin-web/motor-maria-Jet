"""Tiers y pesos de la rúbrica (§2 de docs/plan.md). El cálculo del tier absoluto
vive en `maria_common.models.AuditRun`; acá quedan las constantes, el chequeo de
calibración para el test de aceptación global, y la clasificación por cuartiles
del panel (RF-22)."""
from __future__ import annotations

import math

TIERS = [
    (0, 29, "Invisible"),
    (30, 54, "Parcial"),
    (55, 74, "Emergente"),
    (75, 100, "Líder GEO"),
]

DIMENSION_MAX = {"D1": 25, "D2": 20, "D3": 20, "D4": 15, "D5": 15, "D6": 5}
CORE_MAX = 100  # D1..D5; D6 es bonus por encima


def tier_for(core_score: float) -> str:
    """Tier **absoluto** de una cuenta, sobre cortes fijos del core.

    Vive en el JSON por cuenta y lo consumen el histórico y el funnel self-serve;
    **no se publica** en las páginas del panel sectorial
    (`docs/decisiones/2026-09-09-tiers-no-publicados.md`).
    """
    for lo, hi, name in TIERS:
        if lo <= core_score <= hi:
            return name
    return "Líder GEO" if core_score > 100 else "Invisible"


def cuartiles_panel(items: list[tuple[str, float]]) -> dict[str, str]:
    """Clasificación por **cuartil de ranking** del panel (RF-22).

    `items` = pares `(clave, puntaje)` de las cuentas medibles (`medido` /
    `unverified`) del panel; el llamador ya filtró `bloqueado` / `inaccesible` /
    `no_aplica`. Se ordena por puntaje descendente con desempate por `clave`, y la
    cuenta de posición *r* (0-indexada) sobre *n* cae en `Q{floor(r·4/n)+1}` —
    Q1 (cuarto superior) … Q4 (cuarto inferior).

    Es relativo al panel de la corrida: **no** entra en el JSON por cuenta ni en el
    histórico. Etiquetas neutras (`Q1`…`Q4`), nunca los nombres de tier. Panel
    vacío → `{}`.

    Con `n < 8` la escala se vuelve gruesa (a veces salta un cuartil); el
    comportamiento definitivo para paneles chicos queda pendiente
    (`docs/decisiones/2026-09-09-tiers-no-publicados.md` §Lo que queda abierto).
    """
    if not items:
        return {}
    ordenados = sorted(items, key=lambda t: (-t[1], t[0]))
    n = len(ordenados)
    return {clave: f"Q{math.floor(r * 4 / n) + 1}"
            for r, (clave, _) in enumerate(ordenados)}
