"""Contrato de una superficie y su registro."""
from __future__ import annotations

from typing import Any, Protocol


class Superficie(Protocol):
    """Consulta un motor y devuelve la respuesta cruda, sin interpretarla.

    Toda la interpretación es de `parse`: así una superficie nueva no puede
    cambiar la rúbrica sin querer.
    """

    nombre: str
    modelo: str

    def consultar(self, frase: str) -> dict[str, Any]:
        """Devuelve el dict crudo del motor. No lanza por errores de la API:
        los devuelve para que `parse` los registre como estado `error`."""
        ...


def obtener_superficie(nombre: str, *, modelo: str | None = None) -> Superficie:
    if nombre == "gemini":
        from .gemini import SuperficieGemini
        return SuperficieGemini(modelo=modelo)
    raise ValueError(
        f"superficie desconocida: {nombre!r}. Disponibles: 'gemini'."
    )
