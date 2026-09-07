"""Cola en disco de solicitudes del formulario público.

Sin base de datos: para un piloto, archivos JSON son la elección de la casa y
este repo ya rechazó SQLite con fundamento (`docs/plan.md` §4). El endpoint PHP
solo escribe un archivo de trabajo; nada le pega a Gemini por request.

    out/solicitudes/
      pendientes_verificacion/  <id>.json   escrito por el endpoint, falta clic en el email
      pendientes/               <id>.json   verificado, esperando al consumidor
      procesadas/               <id>.json   ya se generó la propuesta
      rechazadas/               <id>.json   fuera de límites (industria, tope, abuso)

**Control de gasto y de abuso** (plan, "El formulario público"): la industria
tiene que estar en la lista blanca, hay un tope duro de propuestas por día, y el
email se verifica antes de gastar cuota. El límite por IP y por día lo aplica el
endpoint PHP (cuenta más barata ahí); acá se vuelve a chequear la industria y el
tope global, que son plata.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

DEFAULT_COLA_DIR = Path("out/solicitudes")

SUBDIRS = ("pendientes_verificacion", "pendientes", "procesadas", "rechazadas")

# Lista blanca de industrias de la v1. El formulario es un <select>, no un texto
# libre: cualquier valor fuera de esto se rechaza sin consultar a Gemini.
INDUSTRIAS_BLANCAS = {
    "aviación ejecutiva",
}

# Tope duro de propuestas nuevas por día (UTC). Cada propuesta = 10 frases con
# grounding + 2 llamadas de redacción. Configurable por el consumidor.
TOPE_DIARIO_POR_DEFECTO = 15

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOMINIO_RE = re.compile(r"^(?:https?://)?(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", re.I)

EstadoSolicitud = Literal[
    "pendiente_verificacion", "pendiente", "procesada", "rechazada"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Solicitud(BaseModel):
    id: str
    industria: str
    empresa: str
    dominio: str
    email: str
    ip: str = ""
    creada_utc: str = Field(default_factory=_utc_now)
    verificada_utc: Optional[str] = None
    estado: EstadoSolicitud = "pendiente_verificacion"
    token: Optional[str] = None            # el que viaja en el link del email
    motivo_rechazo: Optional[str] = None
    resultado: Optional[dict] = None       # ruta del YAML propuesto, resumen de la corrida

    def dominio_normalizado(self) -> str:
        m = _DOMINIO_RE.match(self.dominio.strip())
        return (m.group(1) if m else self.dominio.strip()).lower()


class ColaDisco:
    def __init__(self, raiz: Path | str = DEFAULT_COLA_DIR):
        self.raiz = Path(raiz)
        for sub in SUBDIRS:
            (self.raiz / sub).mkdir(parents=True, exist_ok=True)

    def _ruta(self, estado: str, sid: str) -> Path:
        return self.raiz / estado / f"{sid}.json"

    def _dir_de(self, estado: EstadoSolicitud) -> str:
        return "pendientes_verificacion" if estado == "pendiente_verificacion" else {
            "pendiente": "pendientes",
            "procesada": "procesadas",
            "rechazada": "rechazadas",
        }[estado]

    def guardar(self, sol: Solicitud) -> Path:
        p = self._ruta(self._dir_de(sol.estado), sol.id)
        p.write_text(sol.model_dump_json(indent=2), "utf-8")
        return p

    def _leer_dir(self, sub: str) -> list[Solicitud]:
        d = self.raiz / sub
        out = []
        for f in sorted(d.glob("*.json")):
            try:
                out.append(Solicitud.model_validate_json(f.read_text("utf-8")))
            except Exception:
                continue
        return out

    def pendientes(self) -> list[Solicitud]:
        return self._leer_dir("pendientes")

    def procesadas(self) -> list[Solicitud]:
        return self._leer_dir("procesadas")

    def buscar(self, sid: str) -> Optional[tuple[str, Solicitud]]:
        for sub in SUBDIRS:
            p = self.raiz / sub / f"{sid}.json"
            if p.is_file():
                return sub, Solicitud.model_validate_json(p.read_text("utf-8"))
        return None

    def mover(self, sol: Solicitud, nuevo_estado: EstadoSolicitud) -> Path:
        """Reescribe la solicitud en el subdir del nuevo estado y borra el viejo."""
        prev = self.buscar(sol.id)
        sol.estado = nuevo_estado
        destino = self.guardar(sol)
        if prev and prev[0] != self._dir_de(nuevo_estado):
            (self.raiz / prev[0] / f"{sol.id}.json").unlink(missing_ok=True)
        return destino

    def procesadas_hoy(self, ref_utc: Optional[str] = None) -> int:
        hoy = (ref_utc or _utc_now())[:10]
        n = 0
        for s in self.procesadas():
            fecha = (s.resultado or {}).get("procesada_utc", s.creada_utc)
            if str(fecha)[:10] == hoy:
                n += 1
        return n


# --------------------------------------------------------------------------- #
# Validación y límites — lo que se chequea ANTES de gastar cuota
# --------------------------------------------------------------------------- #

class Rechazo(Exception):
    """La solicitud no puede procesarse. `.motivo` es apto para mostrar."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def validar_forma(industria: str, empresa: str, dominio: str, email: str) -> None:
    if industria.strip().lower() not in {i.lower() for i in INDUSTRIAS_BLANCAS}:
        raise Rechazo(f"industria fuera de la lista blanca de la v1: {industria!r}")
    if not empresa.strip():
        raise Rechazo("falta el nombre de la empresa")
    if not _DOMINIO_RE.match(dominio.strip()):
        raise Rechazo(f"dominio no parece un dominio: {dominio!r}")
    if not _EMAIL_RE.match(email.strip()):
        raise Rechazo(f"email inválido: {email!r}")


def puede_procesarse(
    sol: Solicitud,
    cola: ColaDisco,
    *,
    tope_diario: int = TOPE_DIARIO_POR_DEFECTO,
) -> None:
    """Lanza `Rechazo` si la solicitud no debe consumir cuota. Silencio = adelante."""
    validar_forma(sol.industria, sol.empresa, sol.dominio, sol.email)
    if sol.estado == "pendiente_verificacion" or not sol.verificada_utc:
        raise Rechazo("el email todavía no fue verificado")
    if cola.procesadas_hoy() >= tope_diario:
        raise Rechazo(f"tope diario de propuestas alcanzado ({tope_diario})")
