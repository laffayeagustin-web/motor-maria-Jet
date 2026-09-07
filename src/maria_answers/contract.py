"""Modelos de dominio del Índice de Respuestas. El JSON de salida es su serialización.

`RESPUESTAS_SCHEMA_VERSION` versiona este contrato, distinto del `SCHEMA_VERSION`
del Índice GEO Técnico: son dos productos con dos rúbricas.

Los modelos de puntaje replican deliberadamente la *forma* de
`maria_common.models` (`id` + `puntos` + `puntos_max` por dimensión) para que
`maria.store.runs` archive y calcule deltas sin saber de qué índice se trata. No
se reusan las clases porque los estados y la regla de puntos efectivos son otros:
acá una frase sin búsqueda **sale del denominador**, no puntúa a la mitad.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

RESPUESTAS_SCHEMA_VERSION = "1.0"

# Tipo de frase del panel: 5 generales + 5 long-tail sin marca.
FraseTipo = Literal["general", "long-tail"]

# Estado de una frase en una corrida (rúbrica §4).
FraseEstado = Literal["con_busqueda", "sin_busqueda", "error"]

# Estado de una marca en una corrida.
MarcaEstado = Literal["medida", "sin_cobertura"]

# Cómo se obtuvo un dato de evidencia.
MetodoEvidencia = Literal["respuesta", "fuente", "regla"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #

class Marca(BaseModel):
    codigo: str                                   # "GST"
    nombre: str                                   # "Gestair"
    dominios: list[str] = Field(default_factory=list)
    alias: list[str] = Field(default_factory=list)
    # Trampas conocidas de falso positivo (rúbrica §5): si el texto que rodea al
    # match contiene una de estas, no cuenta. Ej. "Air TXT" vs "air taxi".
    excluir: list[str] = Field(default_factory=list)


class Frase(BaseModel):
    id: str                                       # "G1" / "L1"
    tipo: FraseTipo
    texto: str


class Mercado(BaseModel):
    pais: str = "ES"
    idioma: str = "es"


class PanelRespuestas(BaseModel):
    industria: str
    superficie: str = "gemini"
    modelo: str = "gemini-2.5-flash"
    mercado: Mercado = Field(default_factory=Mercado)
    empresa_auditada: Optional[str] = None
    marcas: list[Marca] = Field(default_factory=list)
    frases: list[Frase] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Adquisición — el artefacto que separa el carril no determinista del determinista
# --------------------------------------------------------------------------- #

class Fuente(BaseModel):
    """Una fuente citada. `dominio` sale de `groundingChunks[].web.title` (rúbrica §2)."""
    dominio: str
    titulo_crudo: str = ""
    uri: Optional[str] = None                     # redirect opaco de vertexaisearch


class Captura(BaseModel):
    """Lo que la superficie devolvió para una frase. Se guarda verbatim como evidencia."""
    schema_version: str = RESPUESTAS_SCHEMA_VERSION
    frase_id: str
    frase_texto: str
    superficie: str = "gemini"
    modelo: str = "gemini-2.5-flash"
    captured_utc: str = Field(default_factory=_utc_now)

    estado: FraseEstado = "con_busqueda"
    motivo: Optional[str] = None                  # para sin_busqueda / error

    texto: str = ""
    fuentes: list[Fuente] = Field(default_factory=list)
    busquedas: list[str] = Field(default_factory=list)   # webSearchQueries

    @property
    def cuenta_para_el_denominador(self) -> bool:
        return self.estado == "con_busqueda"


# --------------------------------------------------------------------------- #
# Puntaje
# --------------------------------------------------------------------------- #

class Evidencia(BaseModel):
    metodo: MetodoEvidencia
    detalle: str
    captured_utc: str = Field(default_factory=_utc_now)


class SubSenal(BaseModel):
    """Una frase evaluada bajo una señal. `puntos_max` es 0 si la frase no cuenta."""
    frase_id: str
    puntos: float = 0.0
    puntos_max: float = 0.0
    estado: FraseEstado = "con_busqueda"
    evidencia: list[Evidencia] = Field(default_factory=list)


class SenalResult(BaseModel):
    id: str                                       # "R1" | "R2" | "R3"
    nombre: str
    por_frase: list[SubSenal] = Field(default_factory=list)

    @property
    def puntos(self) -> float:
        return round(sum(s.puntos for s in self.por_frase), 2)

    @property
    def puntos_max(self) -> float:
        return round(sum(s.puntos_max for s in self.por_frase), 2)


class MarcaRun(BaseModel):
    """Una marca, una corrida. Forma compatible con `maria.store.runs`.

    El campo se llama `cuenta` a propósito: es la clave que `store.runs.archive()`
    usa para elegir el directorio del histórico.
    """
    schema_version: str = RESPUESTAS_SCHEMA_VERSION
    cuenta: Marca
    timestamp_utc: str = Field(default_factory=_utc_now)
    superficie: str = "gemini"
    modelo: str = "gemini-2.5-flash"
    estado: MarcaEstado = "medida"

    dimensiones: list[SenalResult] = Field(default_factory=list)
    frases_con_busqueda: int = 0
    frases_totales: int = 0

    @property
    def cobertura(self) -> str:
        return f"{self.frases_con_busqueda}/{self.frases_totales}"

    @property
    def puntos_alcanzables(self) -> float:
        return round(sum(d.puntos_max for d in self.dimensiones), 2)

    @property
    def puntaje_total(self) -> Optional[float]:
        """Normalizado a 100 sobre las frases con búsqueda (rúbrica §4).

        `None` cuando ninguna frase disparó búsqueda: no es un cero, es la
        ausencia de denominador.
        """
        alcanzable = self.puntos_alcanzables
        if not alcanzable:
            return None
        obtenido = sum(d.puntos for d in self.dimensiones)
        return round(100 * obtenido / alcanzable, 2)

    @property
    def tier(self) -> Optional[str]:
        t = self.puntaje_total
        if t is None:
            return None
        if t < 25:
            return "Ausente"
        if t < 50:
            return "Marginal"
        if t < 75:
            return "Presente"
        return "Referencia"
