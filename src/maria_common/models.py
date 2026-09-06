"""Modelos de dominio del motor. El JSON de salida (RF-15) es su serialización.

`SCHEMA_VERSION` versiona el contrato JSON público del Índice (principio 8),
distinto de `RENDER_SCHEMA_VERSION` (contrato del bundle entre herramientas).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

# Estados de una cuenta en una corrida (enmienda §4 de docs/decisiones/2026-09-01-rubrica.md).
AccountState = Literal["medido", "bloqueado", "inaccesible", "unverified", "no_aplica"]

# Método de obtención de un ítem de evidencia (principio 1).
EvidenceMethod = Literal["static", "rendered", "robots", "manual"]

Severity = Literal["critica", "alta", "media", "informativa"]
SubStatus = Literal["static", "rendered", "unverified", "regla"]
FindingOrigin = Literal["motor", "analyst"]

Grupo = Literal["A", "B", "C"]
FlujoOperativo = Literal["corporativo-industrial", "turismo-vip", "sanitario", "mixto"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Evidence(BaseModel):
    method: EvidenceMethod
    url: Optional[str] = None
    detail: str
    captured_utc: str = Field(default_factory=_utc_now)


class SubCriterion(BaseModel):
    id: str                      # "D1.1"
    nombre: str
    puntos_max: float
    puntos: Optional[float] = None      # None mientras el status sea unverified
    status: SubStatus = "static"
    evidencia: list[Evidence] = Field(default_factory=list)
    motivo: Optional[str] = None        # por qué quedó unverified / regla

    @property
    def puntos_efectivos(self) -> float:
        """Puntos que suman al total: reales, o la mitad del máximo si unverified (RF-12)."""
        if self.status == "unverified":
            return round(self.puntos_max / 2, 2)
        return self.puntos or 0.0


class DimensionResult(BaseModel):
    id: str                      # "D1"
    nombre: str
    puntos_max: float
    sub_criterios: list[SubCriterion] = Field(default_factory=list)
    tope_aplicado: Optional[str] = None   # RF-13 u otra regla que limitó la dimensión
    cap: Optional[float] = None            # límite duro < puntos_max (RF-13: D1 ≤ 10)

    @property
    def puntos(self) -> float:
        bruto = sum(s.puntos_efectivos for s in self.sub_criterios)
        limite = min(self.puntos_max, self.cap) if self.cap is not None else self.puntos_max
        return round(min(bruto, limite), 2)

    @property
    def unverified(self) -> list[SubCriterion]:
        return [s for s in self.sub_criterios if s.status == "unverified"]


class Finding(BaseModel):
    severidad: Severity
    dimension: Optional[str] = None
    detalle: str
    origin: FindingOrigin = "motor"


class Account(BaseModel):
    codigo: str                  # "AFL"
    nombre: str                  # "Argentina Fly"
    url: Optional[str] = None
    grupo: Grupo = "A"
    flujo: FlujoOperativo = "mixto"
    # anotación del panel, no la decide el motor (enmienda §4)
    no_aplica_motivo: Optional[str] = None


class AuditRun(BaseModel):
    schema_version: str = SCHEMA_VERSION
    cuenta: Account
    timestamp_utc: str = Field(default_factory=_utc_now)
    estado: AccountState = "medido"
    motivo: Optional[str] = None          # para bloqueado / inaccesible

    dimensiones: list[DimensionResult] = Field(default_factory=list)
    hallazgos: list[Finding] = Field(default_factory=list)
    anomalias: list[str] = Field(default_factory=list)

    render_bundle_ref: Optional[str] = None   # dir del bundle usado, o None

    @property
    def puntaje_total(self) -> Optional[float]:
        if self.estado == "no_aplica":
            return None
        core = sum(d.puntos for d in self.dimensiones if not d.id.startswith("D6"))
        bonus = sum(d.puntos for d in self.dimensiones if d.id.startswith("D6"))
        return round(min(core, 100) + bonus, 2)

    @property
    def tier(self) -> Optional[str]:
        total = self.puntaje_total
        if total is None:
            return None
        core = min(total, 100)
        if core < 30:
            return "Invisible"
        if core < 55:
            return "Parcial"
        if core < 75:
            return "Emergente"
        return "Líder GEO"

    @property
    def unverified(self) -> list[SubCriterion]:
        return [s for d in self.dimensiones for s in d.unverified]
