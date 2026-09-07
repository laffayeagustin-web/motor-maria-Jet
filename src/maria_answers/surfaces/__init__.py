"""Superficies de IA que se pueden consultar.

Cada superficie sabe pedirle una respuesta a un motor y devolver el dict crudo.
La normalización a `Captura` vive en `parse`, y el puntaje en `score`: una
superficie nueva no toca la rúbrica.

Hoy hay una sola (`gemini`). AI Overviews entraría acá, con un proveedor de SERP,
sin mover nada más.
"""
from .base import Superficie, obtener_superficie

__all__ = ["Superficie", "obtener_superficie"]
