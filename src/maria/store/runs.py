"""Archivo de corridas por cuenta/fecha + cálculo de delta (RF-19).

`out/runs/<codigo>/<timestamp>.json`. Ficheros JSON diffeables (decisión §4 del
plan: no SQLite mientras el alcance sea el motor).

El almacén es genérico sobre la *forma* de la corrida, no sobre `AuditRun`: le
alcanza con `cuenta.codigo`, `timestamp_utc`, `dimensiones` (con `id` y `puntos`)
y `puntaje_total`. Así lo comparten el Índice GEO Técnico y el Índice de
Respuestas sin duplicarlo. `history()` y `previous()` reciben el modelo a
deserializar; por defecto, `AuditRun`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from maria_common.models import AuditRun

DEFAULT_RUNS_DIR = Path("out/runs")


@runtime_checkable
class RunLike(Protocol):
    """Lo mínimo que el almacén necesita saber de una corrida."""
    timestamp_utc: str

    @property
    def puntaje_total(self) -> Optional[float]: ...


T = TypeVar("T", bound=BaseModel)


def _account_dir(runs_dir: Path, codigo: str) -> Path:
    return runs_dir / codigo


def stamp_archivo(timestamp_utc: str) -> str:
    """`2026-09-07T14:23:11+00:00` → `20260907T142311Z`.

    El offset UTC se normaliza a `Z` **antes** de quitar los `:`, en cualquiera
    de sus formas (`+00:00`, `+0000`, ya `Z`). Antes esto funcionaba de casualidad
    —el `.replace(":", "")` convertía `+00:00` en `+0000` y de ahí el último
    reemplazo lo alcanzaba—; si `isoformat()` cambiara el formato del offset el
    nombre de archivo quedaría con un `+00:00` literal adentro. Se hace explícito.
    """
    ts = timestamp_utc.strip()
    for suf in ("+00:00", "+0000", "-00:00", "-0000"):
        if ts.endswith(suf):
            ts = ts[: -len(suf)] + "Z"
            break
    return ts.replace("-", "").replace(":", "")


def archive(run: RunLike, runs_dir: Path | str = DEFAULT_RUNS_DIR) -> Path:
    runs_dir = Path(runs_dir)
    d = _account_dir(runs_dir, run.cuenta.codigo)
    d.mkdir(parents=True, exist_ok=True)
    stamp = stamp_archivo(run.timestamp_utc)
    path = d / f"{stamp}.json"
    path.write_text(run.model_dump_json(indent=2), "utf-8")
    return path


def history(
    codigo: str,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
    model: type[T] = AuditRun,
) -> list[T]:
    d = _account_dir(Path(runs_dir), codigo)
    if not d.is_dir():
        return []
    runs = []
    for p in sorted(d.glob("*.json")):
        try:
            runs.append(model.model_validate_json(p.read_text("utf-8")))
        except Exception:
            continue
    runs.sort(key=lambda r: r.timestamp_utc)
    return runs


def previous(
    codigo: str,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
    model: type[T] = AuditRun,
) -> Optional[T]:
    h = history(codigo, runs_dir, model)
    return h[-1] if h else None


def delta(current: RunLike, prior: Optional[RunLike]) -> dict:
    """Delta de puntaje total y por dimensión respecto de la corrida anterior."""
    if prior is None:
        return {"vs": None, "total": None, "dimensiones": {}}
    cur_dims = {d.id: d.puntos for d in current.dimensiones}
    old_dims = {d.id: d.puntos for d in prior.dimensiones}
    dims = {
        k: round(cur_dims.get(k, 0) - old_dims.get(k, 0), 2)
        for k in sorted(set(cur_dims) | set(old_dims))
    }
    ct, pt = current.puntaje_total, prior.puntaje_total
    return {
        "vs": prior.timestamp_utc,
        "total": None if (ct is None or pt is None) else round(ct - pt, 2),
        "dimensiones": dims,
    }
