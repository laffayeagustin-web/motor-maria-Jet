"""Carga de un panel YAML a `list[Account]`."""
from __future__ import annotations

from pathlib import Path

import yaml

from maria_common.models import Account


def load_panel(path: Path | str) -> list[Account]:
    data = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    cuentas = data.get("cuentas", data if isinstance(data, list) else [])
    return [Account.model_validate(c) for c in cuentas]
