"""Archivo de corridas por cuenta/fecha + cálculo de delta (RF-19).

`out/runs/<codigo>/<timestamp>.json`. Ficheros JSON diffeables (decisión §4 del
plan: no SQLite mientras el alcance sea el motor).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from maria_common.models import AuditRun

DEFAULT_RUNS_DIR = Path("out/runs")


def _account_dir(runs_dir: Path, codigo: str) -> Path:
    return runs_dir / codigo


def archive(run: AuditRun, runs_dir: Path | str = DEFAULT_RUNS_DIR) -> Path:
    runs_dir = Path(runs_dir)
    d = _account_dir(runs_dir, run.cuenta.codigo)
    d.mkdir(parents=True, exist_ok=True)
    stamp = run.timestamp_utc.replace(":", "").replace("-", "").replace("+0000", "Z")
    path = d / f"{stamp}.json"
    path.write_text(run.model_dump_json(indent=2), "utf-8")
    return path


def history(codigo: str, runs_dir: Path | str = DEFAULT_RUNS_DIR) -> list[AuditRun]:
    d = _account_dir(Path(runs_dir), codigo)
    if not d.is_dir():
        return []
    runs = []
    for p in sorted(d.glob("*.json")):
        try:
            runs.append(AuditRun.model_validate_json(p.read_text("utf-8")))
        except Exception:
            continue
    runs.sort(key=lambda r: r.timestamp_utc)
    return runs


def previous(codigo: str, runs_dir: Path | str = DEFAULT_RUNS_DIR) -> Optional[AuditRun]:
    h = history(codigo, runs_dir)
    return h[-1] if h else None


def delta(current: AuditRun, prior: Optional[AuditRun]) -> dict:
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
