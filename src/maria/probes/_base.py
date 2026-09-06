"""Contexto y helpers compartidos por los seis probes.

Cada probe recibe un `ProbeContext` y devuelve un `DimensionResult`. El probe
nunca abre un navegador ni toca la red directamente: el HTML crudo, el
`robots.txt` y el bundle ya vienen resueltos por el orquestador (`maria.audit`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from selectolax.lexbor import LexborHTMLParser

from maria_common.models import DimensionResult, Evidence, SubCriterion
from maria_common.render_contract import RenderBundleEntry


@dataclass
class ProbeContext:
    url: str
    # lado servido (siempre presente salvo bloqueado/inaccesible)
    raw_html: str = ""
    raw_tree: Optional[LexborHTMLParser] = None
    status: Optional[int] = None
    final_url: Optional[str] = None
    headers: dict = field(default_factory=dict)
    https_sin_degradacion: bool = True
    estado_fetch: Optional[str] = None       # None | "bloqueado" | "inaccesible"
    motivo_fetch: Optional[str] = None
    # robots
    robots_txt: Optional[str] = None
    # lado renderizado (None si no hay bundle usable para esta URL — RF-02)
    render: Optional[RenderBundleEntry] = None
    # descubrimientos que el orquestador resuelve por red para D4
    footer_pages: dict[str, int] = field(default_factory=dict)   # url -> status
    llms_txt_present: bool = False
    well_known: list[str] = field(default_factory=list)
    sitemap_ok: bool = False

    def tree(self) -> LexborHTMLParser:
        if self.raw_tree is None:
            self.raw_tree = LexborHTMLParser(self.raw_html or "")
        return self.raw_tree


def ev_static(detail: str, url: Optional[str] = None) -> Evidence:
    return Evidence(method="static", detail=detail, url=url)


def ev_rendered(detail: str, url: Optional[str] = None) -> Evidence:
    return Evidence(method="rendered", detail=detail, url=url)


def ev_robots(detail: str, url: Optional[str] = None) -> Evidence:
    return Evidence(method="robots", detail=detail, url=url)


def scored(
    sub_id: str, nombre: str, puntos_max: float, puntos: float,
    evidencia: list[Evidence], status: str = "static",
) -> SubCriterion:
    return SubCriterion(
        id=sub_id, nombre=nombre, puntos_max=puntos_max,
        puntos=round(puntos, 2), status=status, evidencia=evidencia,
    )


def unverified(sub_id: str, nombre: str, puntos_max: float, motivo: str) -> SubCriterion:
    return SubCriterion(
        id=sub_id, nombre=nombre, puntos_max=puntos_max,
        puntos=None, status="unverified", motivo=motivo,
    )


def dimension(dim_id: str, nombre: str, puntos_max: float, subs: list[SubCriterion]) -> DimensionResult:
    return DimensionResult(id=dim_id, nombre=nombre, puntos_max=puntos_max, sub_criterios=subs)


RENDER_MISSING = "sin DOM renderizado disponible para esta URL (no hay entry en el render bundle)"
