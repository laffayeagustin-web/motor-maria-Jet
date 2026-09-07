"""Serie temporal de una marca: qué mostrar de las últimas N corridas.

`maria.store.runs.history()` ya guarda y ordena las corridas; acá se las lee como
lo que la tabla diaria necesita — un punto por día con puntaje y cobertura — y se
calcula la **media móvil de 7 días** que la rúbrica (§7 bis) exige publicar junto
al valor del día, porque con N=3 repeticiones un movimiento menor a ~5 puntos
entre días sigue dentro del ruido medido y no se comenta.

Determinista y sin red: entra el histórico en disco, sale la vista.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

from maria.store import runs as runstore

from .contract import MarcaRun

VENTANA_MEDIA_MOVIL = 7


class PuntoSerie(NamedTuple):
    fecha: str                       # timestamp_utc de la corrida
    puntaje: Optional[float]         # None = esa corrida no tuvo cobertura
    cobertura: str                   # "8/10"
    media_movil_7d: Optional[float]  # media de los puntajes de hasta 7 corridas hasta ésta


def media_movil(valores: list[Optional[float]], ventana: int = VENTANA_MEDIA_MOVIL) -> Optional[float]:
    """Media de los últimos `ventana` valores no nulos. `None` si no hay ninguno.

    Las corridas sin cobertura (`puntaje` None) no son ceros: se saltan, igual que
    una frase `sin_busqueda` sale del denominador.
    """
    reales = [v for v in valores[-ventana:] if v is not None]
    if not reales:
        return None
    return round(sum(reales) / len(reales), 2)


def serie(
    codigo: str,
    runs_dir: Path | str,
    *,
    n: int = 30,
) -> list[PuntoSerie]:
    """Las últimas `n` corridas de la marca, en orden cronológico, con su media móvil.

    La media móvil de cada punto mira hasta 7 corridas **hasta ese punto** —no
    hacia adelante—, para que el valor publicado un día no cambie al día siguiente.
    """
    historia: list[MarcaRun] = runstore.history(codigo, runs_dir, MarcaRun)
    if not historia:
        return []

    puntajes_acum: list[Optional[float]] = []
    puntos: list[PuntoSerie] = []
    for run in historia:
        puntajes_acum.append(run.puntaje_total)
        puntos.append(PuntoSerie(
            fecha=run.timestamp_utc,
            puntaje=run.puntaje_total,
            cobertura=run.cobertura,
            media_movil_7d=media_movil(puntajes_acum),
        ))
    return puntos[-n:]


def serie_dict(codigo: str, runs_dir: Path | str, *, n: int = 30) -> list[dict]:
    """Igual que `serie()` pero como lista de dicts, para el JSON del informe."""
    return [p._asdict() for p in serie(codigo, runs_dir, n=n)]
