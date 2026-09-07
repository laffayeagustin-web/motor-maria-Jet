"""Superficie Gemini: `generateContent` con la herramienta `google_search`.

`temperature: 0` no es una preferencia de estilo, es parte de la métrica: baja la
varianza al mínimo que la API permite, y la varianza de la señal es lo que hace
—o no— creíble a una serie diaria (rúbrica §7).

El modelo y su versión también son parte de la métrica: cambiarlos es un corte de
serie, no una mejora silenciosa. Por eso viajan en cada `Captura`.
"""
from __future__ import annotations

from typing import Any

import httpx

from ..config import gemini_api_key, gemini_modelo

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
TIMEOUT_S = 90.0


class SuperficieGemini:
    nombre = "gemini"

    def __init__(self, *, modelo: str | None = None, timeout: float = TIMEOUT_S):
        self.modelo = modelo or gemini_modelo()
        self._timeout = timeout

    def consultar(self, frase: str) -> dict[str, Any]:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": frase}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0},
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(
                    ENDPOINT.format(modelo=self.modelo),
                    params={"key": gemini_api_key()},
                    json=payload,
                )
        except Exception as exc:  # noqa: BLE001 — todo fallo es un dato a reportar
            return {"error": {"message": f"{type(exc).__name__}: {exc}"}}

        if r.status_code != 200:
            # El cuerpo de error de Gemini ya trae {"error": {...}}; si no, se arma.
            try:
                cuerpo = r.json()
            except Exception:  # noqa: BLE001
                cuerpo = {}
            if isinstance(cuerpo, dict) and cuerpo.get("error"):
                return cuerpo
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:300]}"}}

        try:
            return r.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": {"message": f"respuesta no es JSON: {exc}"}}
