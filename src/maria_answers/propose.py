"""Propuesta de panel: el ÚNICO módulo que le pide a un LLM que *genere*.

El resto del motor es determinista o normaliza un artefacto ya obtenido. Acá, y
solo acá, Gemini redacta. Aun así la regla de la rúbrica (§6) se respeta al pie:

> El paso `proponer` **no le pregunta a un LLM quiénes son los competidores.**
> Corre primero las frases y toma como candidatos los dominios más citados; el
> LLM solo **redacta y agrupa**, y un humano aprueba.

Flujo:

1. `generar_frases()` — el LLM propone 10 frases de la industria (5 generales +
   5 long-tail), sin nombres de marca. Sin grounding: es redacción.
2. se corren esas frases con grounding (la adquisición de siempre) y se cuentan
   los dominios efectivamente citados.
3. `nombrar_competidores()` — el LLM recibe los dominios más citados y les pone
   nombre y alias, y descarta los que no son operadores/brokers del rubro
   (directorios, prensa, agregadores). No inventa competidores: solo nombra los
   que la evidencia ya trajo.
4. se arma un `PanelRespuestas` **sin congelar**. No entra al cron hasta que un
   humano lo mueve a `panels/`.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections import Counter
from typing import Any, Optional

import httpx

from .acquire import capturar_panel
from .config import gemini_api_key, gemini_modelo
from .contract import Frase, Marca, Mercado, PanelRespuestas
from .match import normalizar_dominio
from .parse import desde_gemini  # noqa: F401  (mantiene la superficie como fuente única de forma)

log = logging.getLogger(__name__)

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
TIMEOUT_S = 60.0
CANDIDATOS_POR_DEFECTO = 8
MIN_CITAS_CANDIDATO = 2          # un dominio citado una sola vez es ruido


# --------------------------------------------------------------------------- #
# Llamada JSON a Gemini — sin grounding, es redacción. Portado de
# campus/extensions/growth-bot/src/GeminiClient.php::generateJson().
# --------------------------------------------------------------------------- #

def _gemini_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
    *,
    modelo: Optional[str] = None,
    timeout: float = TIMEOUT_S,
) -> Any:
    modelo = modelo or gemini_modelo()
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(ENDPOINT.format(modelo=modelo),
                        params={"key": gemini_api_key()}, json=payload)
    r.raise_for_status()
    data = r.json()
    try:
        texto = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Gemini no devolvió texto: {json.dumps(data)[:300]}") from exc
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini no devolvió JSON válido: {texto[:300]}") from exc


# --------------------------------------------------------------------------- #
# Paso 1 · frases
# --------------------------------------------------------------------------- #

_SCHEMA_FRASES = {
    "type": "object",
    "properties": {
        "frases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["general", "long-tail"]},
                    "texto": {"type": "string"},
                },
                "required": ["tipo", "texto"],
            },
        }
    },
    "required": ["frases"],
}


def generar_frases(
    industria: str,
    mercado: Mercado,
    *,
    modelo: Optional[str] = None,
    n_general: int = 5,
    n_long_tail: int = 5,
) -> list[Frase]:
    """10 frases que un cliente real escribiría en un buscador. Sin marcas."""
    system = (
        "Sos un analista de marketing. Devolvés consultas de búsqueda que una "
        "persona escribiría al contratar un servicio, en el idioma y el país "
        "indicados. NUNCA incluís nombres de empresas ni de marcas: son frases "
        "genéricas de intención. Las 'general' son cortas y de cabecera; las "
        "'long-tail' son preguntas concretas con detalle (ruta, precio, "
        "cantidad de pasajeros, trámite)."
    )
    user = (
        f"Industria: {industria}\n"
        f"País: {mercado.pais}\nIdioma: {mercado.idioma}\n"
        f"Devolvé exactamente {n_general} frases 'general' y {n_long_tail} "
        f"'long-tail'."
    )
    data = _gemini_json(system, user, _SCHEMA_FRASES, modelo=modelo)
    crudas = data.get("frases", []) if isinstance(data, dict) else []

    frases: list[Frase] = []
    n_g = n_l = 0
    for item in crudas:
        tipo = item.get("tipo")
        texto = (item.get("texto") or "").strip()
        if not texto or tipo not in ("general", "long-tail"):
            continue
        if tipo == "general" and n_g < n_general:
            n_g += 1
            frases.append(Frase(id=f"G{n_g}", tipo="general", texto=texto))
        elif tipo == "long-tail" and n_l < n_long_tail:
            n_l += 1
            frases.append(Frase(id=f"L{n_l}", tipo="long-tail", texto=texto))
    if n_g < n_general or n_l < n_long_tail:
        raise RuntimeError(
            f"Gemini devolvió {n_g}/{n_general} generales y {n_l}/{n_long_tail} "
            f"long-tail; se esperaban {n_general}+{n_long_tail}.")
    return frases


# --------------------------------------------------------------------------- #
# Paso 2 · contar dominios citados  (determinista, sin LLM)
# --------------------------------------------------------------------------- #

def contar_dominios(capturas, *, excluir_dominios: list[str]) -> list[tuple[str, int]]:
    """Dominios citados por frecuencia de frases que los citan, descendente.

    Cuenta una vez por frase (no por repetición): que un dominio salga en las 3
    repeticiones de una frase es una cita, no tres.
    """
    excl = {normalizar_dominio(d) for d in excluir_dominios}
    por_frase: dict[str, set[str]] = {}
    for cap in capturas:
        vistos = por_frase.setdefault(cap.frase_id, set())
        for f in cap.fuentes:
            d = normalizar_dominio(f.dominio)
            if d and d not in excl:
                vistos.add(d)
    tally: Counter[str] = Counter()
    for dominios in por_frase.values():
        tally.update(dominios)
    return tally.most_common()


# --------------------------------------------------------------------------- #
# Paso 3 · nombrar los dominios  (el LLM agrupa, no elige)
# --------------------------------------------------------------------------- #

_SCHEMA_MARCAS = {
    "type": "object",
    "properties": {
        "marcas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dominio": {"type": "string"},
                    "nombre": {"type": "string"},
                    "alias": {"type": "array", "items": {"type": "string"}},
                    "es_competidor": {"type": "boolean"},
                    "motivo_descarte": {"type": "string"},
                },
                "required": ["dominio", "nombre", "es_competidor"],
            },
        }
    },
    "required": ["marcas"],
}


def _codigo_de(nombre: str, usados: set[str]) -> str:
    base = "".join(c for c in unicodedata.normalize("NFD", nombre.upper())
                   if unicodedata.category(c) != "Mn")
    letras = re.sub(r"[^A-Z0-9]", "", base) or "MRC"
    cod = letras[:3]
    i = 1
    while cod in usados:
        i += 1
        cod = (letras[:2] + str(i))[:3]
    usados.add(cod)
    return cod


def nombrar_competidores(
    industria: str,
    empresa: str,
    dominios_candidatos: list[str],
    *,
    modelo: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Le pone nombre a cada dominio y marca cuáles NO son competidores del rubro."""
    if not dominios_candidatos:
        return []
    system = (
        "Recibís una lista de dominios que un buscador citó al responder sobre "
        "una industria. Para cada uno devolvés el nombre comercial de la marca y "
        "sus alias frecuentes. Marcás es_competidor=false cuando el dominio NO "
        "es un operador, broker o proveedor del rubro: directorios, prensa, "
        "Wikipedia, foros, agregadores, reguladores. No agregues dominios que no "
        "estén en la lista."
    )
    user = (
        f"Industria: {industria}\nEmpresa que pide el informe: {empresa}\n"
        f"Dominios citados:\n" + "\n".join(f"- {d}" for d in dominios_candidatos)
    )
    data = _gemini_json(system, user, _SCHEMA_MARCAS, modelo=modelo)
    return data.get("marcas", []) if isinstance(data, dict) else []


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #

class Propuesta:
    """Lo que devuelve `proponer`: un panel sin congelar + la evidencia que lo armó."""

    def __init__(self, panel: PanelRespuestas, capturas, dominios_citados):
        self.panel = panel
        self.capturas_semilla = capturas
        self.dominios_citados = dominios_citados      # [(dominio, n_frases)]

    def to_yaml_dict(self) -> dict[str, Any]:
        p = self.panel
        return {
            "industria": p.industria,
            "superficie": p.superficie,
            "modelo": p.modelo,
            "mercado": {"pais": p.mercado.pais, "idioma": p.mercado.idioma},
            "empresa_auditada": p.empresa_auditada,
            "_propuesta": {
                "generada_por": "maria-respuestas proponer",
                "congelar": "revisar a mano y mover este archivo a panels/ para que entre al cron",
                "dominios_citados": [{"dominio": d, "frases": n}
                                     for d, n in self.dominios_citados],
            },
            "marcas": [
                {k: v for k, v in {
                    "codigo": m.codigo, "nombre": m.nombre,
                    "dominios": m.dominios, "alias": m.alias, "excluir": m.excluir,
                }.items() if v or k in ("codigo", "nombre", "dominios")}
                for m in p.marcas
            ],
            "frases": [{"id": f.id, "tipo": f.tipo, "texto": f.texto} for f in p.frases],
        }


def proponer(
    industria: str,
    empresa: str,
    dominio: str,
    *,
    pais: str = "ES",
    idioma: str = "es",
    superficie: str = "gemini",
    modelo: Optional[str] = None,
    repeticiones: int = 1,
    max_candidatos: int = CANDIDATOS_POR_DEFECTO,
    crudo_dir: Optional[Any] = None,
    on_progress=None,
) -> Propuesta:
    """Industria + empresa + dominio → panel propuesto (sin congelar) + una corrida.

    `repeticiones=1` a propósito: la propuesta es exploración, no la serie. La
    corrida de medición "al toque" que ve el que pide el informe se calcula sobre
    estas capturas; el panel definitivo se vuelve a medir con N=3 recién cuando
    se aprueba.
    """
    modelo = modelo or gemini_modelo()
    mercado = Mercado(pais=pais, idioma=idioma)
    dominio_propio = normalizar_dominio(dominio)

    log.info("proponer: generando frases semilla para %r", industria)
    frases = generar_frases(industria, mercado, modelo=modelo)

    semilla = PanelRespuestas(
        industria=industria, superficie=superficie, modelo=modelo, mercado=mercado,
        empresa_auditada=None,
        marcas=[Marca(codigo="REQ", nombre=empresa,
                      dominios=[dominio_propio] if dominio_propio else [])],
        frases=frases,
    )

    log.info("proponer: corriendo %d frases con grounding", len(frases))
    capturas = capturar_panel(semilla, repeticiones=repeticiones, usar_cache=False,
                              crudo_dir=crudo_dir, on_progress=on_progress)

    citados = contar_dominios(capturas, excluir_dominios=[dominio_propio] if dominio_propio else [])
    candidatos = [d for d, n in citados if n >= MIN_CITAS_CANDIDATO][:max_candidatos]
    log.info("proponer: %d dominios citados, %d candidatos sobre el umbral",
             len(citados), len(candidatos))

    nombradas = nombrar_competidores(industria, empresa, candidatos, modelo=modelo)
    por_dominio = {normalizar_dominio(m.get("dominio", "")): m for m in nombradas}

    usados: set[str] = set()
    marcas: list[Marca] = []

    # La empresa que pide el informe va primera y con código propio.
    cod_req = _codigo_de(empresa, usados)
    marcas.append(Marca(codigo=cod_req, nombre=empresa,
                        dominios=[dominio_propio] if dominio_propio else []))

    for dom in candidatos:
        m = por_dominio.get(dom)
        if not m or not m.get("es_competidor", False):
            log.info("proponer: descartado %s (%s)", dom,
                     (m or {}).get("motivo_descarte", "no es competidor"))
            continue
        nombre = (m.get("nombre") or dom).strip()
        marcas.append(Marca(
            codigo=_codigo_de(nombre, usados),
            nombre=nombre,
            dominios=[dom],
            alias=[a.strip() for a in (m.get("alias") or []) if a.strip()],
        ))

    panel = PanelRespuestas(
        industria=industria, superficie=superficie, modelo=modelo, mercado=mercado,
        empresa_auditada=cod_req, marcas=marcas, frases=frases,
    )
    return Propuesta(panel, capturas, citados)
