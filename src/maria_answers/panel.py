"""Carga de un panel de respuestas YAML a `PanelRespuestas` (RR-01).

Mismo patrón que `maria.panel.load_panel`, con validación propia: un panel sin
frases o sin marcas es un error de configuración, no una corrida vacía.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .contract import PanelRespuestas


def load_panel(path: Path | str) -> PanelRespuestas:
    data = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    panel = PanelRespuestas.model_validate(data)

    if not panel.marcas:
        raise ValueError(f"{path}: el panel no tiene marcas")
    if not panel.frases:
        raise ValueError(f"{path}: el panel no tiene frases")

    for lista, etiqueta in ((panel.marcas, "marca"), (panel.frases, "frase")):
        vistos: set[str] = set()
        for item in lista:
            clave = item.codigo if etiqueta == "marca" else item.id
            if clave in vistos:
                raise ValueError(f"{path}: {etiqueta} duplicada: {clave}")
            vistos.add(clave)

    return panel
