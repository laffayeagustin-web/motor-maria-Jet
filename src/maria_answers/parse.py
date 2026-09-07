"""Normaliza la respuesta cruda de una superficie a una `Captura`.

Frontera del carril determinista: de acá para abajo nadie sabe que existió una
API. Sin red — entra un dict ya obtenido, sale el artefacto que puntúa `score`.

Regla congelada (rúbrica §2, RR-03): **el dominio de la fuente se lee de
`groundingChunks[].web.title`.** La `web.uri` es siempre un redirect opaco de
`vertexaisearch.cloud.google.com`; parsearla de ahí da cero citas para todo el
panel, que es exactamente lo que pasó en la primera pasada de la sonda.
"""
from __future__ import annotations

from typing import Any

from .contract import Captura, Fuente
from .match import normalizar_dominio


def _texto_de(candidato: dict[str, Any]) -> str:
    partes = ((candidato.get("content") or {}).get("parts")) or []
    return "".join(p.get("text", "") for p in partes if isinstance(p, dict))


def _fuentes_de(gm: dict[str, Any]) -> list[Fuente]:
    fuentes: list[Fuente] = []
    for chunk in (gm.get("groundingChunks") or []):
        web = (chunk or {}).get("web") or {}
        titulo = (web.get("title") or "").strip()
        dominio = normalizar_dominio(titulo)
        if not dominio:
            continue
        fuentes.append(Fuente(dominio=dominio, titulo_crudo=titulo, uri=web.get("uri")))
    return fuentes


def desde_gemini(
    data: dict[str, Any],
    *,
    frase_id: str,
    frase_texto: str,
    modelo: str = "gemini-2.5-flash",
) -> Captura:
    """Construye la `Captura` de una respuesta de `generateContent` con `google_search`."""
    base = dict(frase_id=frase_id, frase_texto=frase_texto,
                superficie="gemini", modelo=modelo)

    if not isinstance(data, dict) or data.get("error"):
        detalle = ((data or {}).get("error") or {}).get("message") or "respuesta ilegible"
        return Captura(**base, estado="error", motivo=str(detalle)[:300])

    candidatos = data.get("candidates") or []
    if not candidatos:
        motivo = "la API no devolvió candidatos (posible filtro de contenido)"
        return Captura(**base, estado="error", motivo=motivo)

    cand = candidatos[0] or {}
    texto = _texto_de(cand)
    gm = cand.get("groundingMetadata") or {}
    busquedas = [q for q in (gm.get("webSearchQueries") or []) if q]
    fuentes = _fuentes_de(gm)

    if not busquedas and not fuentes:
        # El modelo contestó de memoria. No es un cero: sale del denominador.
        return Captura(**base, estado="sin_busqueda", texto=texto,
                       motivo="el modelo respondió sin ejecutar búsqueda web")

    return Captura(**base, estado="con_busqueda", texto=texto,
                   fuentes=fuentes, busquedas=busquedas)
