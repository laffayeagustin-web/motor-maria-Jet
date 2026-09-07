"""Credenciales del Índice de Respuestas.

Orden de búsqueda de la clave, del más explícito al más implícito:

1. la variable de entorno `GEMINI_API_KEY`;
2. `~/.secrets/gemini.env` (modo 600) — el lugar canónico, compartido con el
   growth-bot del campus;
3. el `config.php` del growth-bot, como respaldo mientras dure la migración.

Nunca se registra el valor: los errores nombran dónde se buscó, no qué se
encontró.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

SECRET_ENV = Path(os.path.expanduser("~/.secrets/gemini.env"))
CONFIG_PHP = Path(os.path.expanduser(
    "~/public_html/campus/extensions/growth-bot/config.php"))
MODELO_POR_DEFECTO = "gemini-2.5-flash"


def _de_env_file(path: Path, clave: str) -> str | None:
    if not path.is_file():
        return None
    for linea in path.read_text("utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, _, v = linea.partition("=")
        if k.strip() == clave:
            return v.strip().strip("'\"") or None
    return None


def _de_config_php(clave_php: str) -> str | None:
    if not CONFIG_PHP.is_file():
        return None
    m = re.search(rf"'{clave_php}'\s*=>\s*'([^']+)'", CONFIG_PHP.read_text("utf-8"))
    return m.group(1) if m else None


def gemini_api_key() -> str:
    for valor in (
        os.environ.get("GEMINI_API_KEY"),
        _de_env_file(SECRET_ENV, "GEMINI_API_KEY"),
        _de_config_php("gemini_api_key"),
    ):
        if valor:
            return valor
    raise RuntimeError(
        "no se encontró la clave de Gemini. Se buscó en: la variable de entorno "
        f"GEMINI_API_KEY, {SECRET_ENV} y {CONFIG_PHP}."
    )


def gemini_modelo() -> str:
    return (
        os.environ.get("GEMINI_MODEL")
        or _de_env_file(SECRET_ENV, "GEMINI_MODEL")
        or _de_config_php("gemini_model")
        or MODELO_POR_DEFECTO
    )
