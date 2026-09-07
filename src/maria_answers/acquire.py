"""Adquisición: del panel a una lista de `Captura`.

Frontera entre el carril no determinista (consultar un motor) y el determinista
(puntuar). Guarda cada respuesta cruda en disco antes de normalizarla: la
evidencia es la respuesta, no nuestra lectura de ella.

**La caché está apagada por defecto, al revés que en el Índice GEO Técnico.**
Allá la página es estable y cachear 24 h ahorra cortesía; acá *cada corrida es la
medición*, y servir una respuesta de ayer como el dato de hoy arruinaría la serie.
La caché existe solo para desarrollar sin gastar cuota (`--cache`).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .contract import Captura, PanelRespuestas
from .parse import desde_gemini
from .surfaces import obtener_superficie

DEFAULT_CACHE_DIR = Path("out/cache-respuestas")
DEFAULT_CRUDO_DIR = Path("out/crudo-respuestas")
CACHE_TTL_S = 6 * 3600


def _cache_path(cache_dir: Path, superficie: str, modelo: str, frase: str) -> Path:
    clave = hashlib.sha256(f"{superficie}|{modelo}|{frase}".encode("utf-8")).hexdigest()[:20]
    return cache_dir / superficie / f"{clave}.json"


def _leer_cache(path: Path, ttl: float) -> Optional[dict[str, Any]]:
    if not path.is_file() or time.time() - path.stat().st_mtime > ttl:
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:  # noqa: BLE001 — una caché ilegible es un miss
        return None


REPETICIONES_POR_DEFECTO = 3


def capturar_panel(
    panel: PanelRespuestas,
    *,
    repeticiones: int = REPETICIONES_POR_DEFECTO,
    usar_cache: bool = False,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    crudo_dir: Path | str | None = DEFAULT_CRUDO_DIR,
    pausa_s: float = 2.0,
    on_progress: Callable[[Captura], None] | None = None,
) -> list[Captura]:
    """Consulta las frases del panel y devuelve sus capturas.

    Cada frase se consulta `repeticiones` veces: una sola medición no alcanza,
    porque entre dos corridas idénticas solo reaparece el 60 % de las fuentes
    citadas (enmienda §7 de la rúbrica). `score` agrega las repeticiones por
    frecuencia.

    Secuencial a propósito: los límites de proceso de este host castigan las
    ráfagas, y el volumen no justifica concurrencia.
    """
    if repeticiones < 1:
        raise ValueError("repeticiones debe ser >= 1")

    superficie = obtener_superficie(panel.superficie, modelo=panel.modelo)
    cache_dir, capturas = Path(cache_dir), []
    crudo = Path(crudo_dir) if crudo_dir else None
    if crudo:
        crudo.mkdir(parents=True, exist_ok=True)

    total = len(panel.frases) * repeticiones
    hechas = 0
    for frase in panel.frases:
        for rep in range(1, repeticiones + 1):
            # La caché distingue repeticiones: si no, todas serían la misma.
            marca_cache = f"{frase.texto}#rep{rep}"
            cpath = _cache_path(cache_dir, superficie.nombre, superficie.modelo, marca_cache)
            data = _leer_cache(cpath, CACHE_TTL_S) if usar_cache else None
            desde_cache = data is not None

            if data is None:
                data = superficie.consultar(frase.texto)
                if usar_cache:
                    cpath.parent.mkdir(parents=True, exist_ok=True)
                    cpath.write_text(json.dumps(data, ensure_ascii=False), "utf-8")

            if crudo:
                nombre = f"{frase.id}.json" if repeticiones == 1 else f"{frase.id}.r{rep}.json"
                (crudo / nombre).write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

            cap = desde_gemini(data, frase_id=frase.id, frase_texto=frase.texto,
                               modelo=superficie.modelo)
            capturas.append(cap)
            if on_progress:
                on_progress(cap)

            hechas += 1
            if not desde_cache and hechas < total and pausa_s:
                time.sleep(pausa_s)

    return capturas


def capturas_desde_disco(panel: PanelRespuestas, crudo_dir: Path | str) -> list[Captura]:
    """Re-normaliza respuestas ya guardadas. Sin red — para recalcular sin pagar.

    Levanta tanto `<frase>.json` (una repetición) como `<frase>.rN.json` (varias).
    """
    crudo = Path(crudo_dir)
    capturas = []
    for frase in panel.frases:
        archivos = sorted(crudo.glob(f"{frase.id}.r*.json")) or (
            [crudo / f"{frase.id}.json"] if (crudo / f"{frase.id}.json").is_file() else []
        )
        for p in archivos:
            capturas.append(desde_gemini(
                json.loads(p.read_text("utf-8")),
                frase_id=frase.id, frase_texto=frase.texto, modelo=panel.modelo,
            ))
    return capturas
