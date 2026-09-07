"""Emparejar una marca con el texto de una respuesta y con sus fuentes.

Es el módulo donde este índice puede producir un número falso con toda la
apariencia de ser correcto, así que las reglas están congeladas en la rúbrica
(`docs/decisiones/2026-09-06-rubrica-respuestas.md` §5) y no se relajan acá:

- **Dominio (RR-05):** igualdad exacta o sufijo de subdominio. Nunca subcadena.
  Caso real: `globalcharter.com` (compañía británica) no es `global-charters.com`
  (el broker español del panel).
- **Nombre (RR-04):** sobre texto normalizado —minúsculas, sin acentos— y con
  límites de palabra. Nunca subcadena.
- **Exclusiones (RR-06):** una aparición que cae dentro de una frase declarada en
  `excluir` no cuenta, y se sigue buscando la siguiente.

Sin red, sin LLM: entra texto, salen posiciones.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .contract import Fuente, Marca


def normalizar(s: str) -> str:
    """Minúsculas y sin diacríticos. La base de todo match de nombre."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def normalizar_dominio(s: str) -> str:
    """Un `web.title` de Gemini ya viene como dominio; se limpia por las dudas."""
    d = (s or "").strip().lower()
    d = d.removeprefix("http://").removeprefix("https://")
    d = d.split("/", 1)[0].split("?", 1)[0]
    return d.removeprefix("www.")


def _spans_excluidos(texto_norm: str, excluir: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for frase in excluir:
        f = normalizar(frase)
        if not f:
            continue
        for m in re.finditer(re.escape(f), texto_norm):
            spans.append((m.start(), m.end()))
    return spans


def buscar_mencion(texto: str, marca: Marca) -> tuple[Optional[str], Optional[int]]:
    """Primera mención válida de la marca. Devuelve `(variante, offset)`.

    Prueba el nombre y luego cada alias; se queda con la aparición más temprana
    que no caiga dentro de una exclusión. `(None, None)` si no hay ninguna.
    """
    tnorm = normalizar(texto)
    excl = _spans_excluidos(tnorm, marca.excluir)

    mejor: tuple[Optional[str], Optional[int]] = (None, None)
    for variante in [marca.nombre, *marca.alias]:
        v = normalizar(variante)
        if not v:
            continue
        for m in re.finditer(r"\b" + re.escape(v) + r"\b", tnorm):
            if any(ini <= m.start() and m.end() <= fin for ini, fin in excl):
                continue                      # cae dentro de una trampa declarada
            if mejor[1] is None or m.start() < mejor[1]:
                mejor = (variante, m.start())
            break                             # la primera válida de esta variante alcanza
    return mejor


def posicion_relativa(texto: str, offset: int) -> float:
    """Offset de la mención sobre el largo del texto normalizado, en [0, 1]."""
    largo = max(len(normalizar(texto)), 1)
    return round(min(max(offset / largo, 0.0), 1.0), 4)


def coincide_dominio(candidato: str, propio: str) -> bool:
    """Igualdad exacta o subdominio de `propio`. Nunca subcadena (RR-05)."""
    c, p = normalizar_dominio(candidato), normalizar_dominio(propio)
    if not c or not p:
        return False
    return c == p or c.endswith("." + p)


def buscar_citas(fuentes: list[Fuente], marca: Marca) -> list[str]:
    """Dominios de la marca presentes entre las fuentes citadas, ordenados."""
    vistos = {
        normalizar_dominio(f.dominio)
        for f in fuentes
        if any(coincide_dominio(f.dominio, propio) for propio in marca.dominios)
    }
    return sorted(vistos)
