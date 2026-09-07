"""Índice de Respuestas — RR-14 a RR-18: adquisición, almacén y salida.

Offline: la superficie se reemplaza por una falsa que cuenta llamadas. Los tests
que sí tocan la API de Gemini van marcados `network` y quedan fuera de la suite
base, igual que en el índice técnico.
"""
from __future__ import annotations

import json

import pytest

from maria.store import runs as runstore
from maria_answers import acquire
from maria_answers.contract import Frase, Marca, MarcaRun, PanelRespuestas
from maria_answers.report import marca_report, panel_table, to_dict, to_json
from maria_answers.score import puntuar_marca, puntuar_panel
from maria_answers.surfaces import obtener_superficie

GESTAIR = Marca(codigo="GST", nombre="Gestair", dominios=["gestair.com"])


def respuesta_falsa(texto="Gestair opera desde Madrid.", dominio="gestair.com"):
    return {
        "candidates": [{
            "content": {"parts": [{"text": texto}]},
            "groundingMetadata": {
                "webSearchQueries": ["q"],
                "groundingChunks": [{"web": {"uri": "https://vertexaisearch.cloud.google.com/x",
                                             "title": dominio}}],
            },
        }]
    }


class SuperficieFalsa:
    nombre = "gemini"
    modelo = "modelo-de-prueba"

    def __init__(self):
        self.llamadas = 0

    def consultar(self, frase: str) -> dict:
        self.llamadas += 1
        return respuesta_falsa()


def panel_de_dos() -> PanelRespuestas:
    return PanelRespuestas(
        industria="aviación ejecutiva",
        marcas=[GESTAIR],
        frases=[Frase(id="G1", tipo="general", texto="uno"),
                Frase(id="G2", tipo="general", texto="dos")],
    )


# --------------------------------------------------------------------------- #
# RR-14 · la caché está apagada por defecto: cada corrida es la medición
# --------------------------------------------------------------------------- #

def test_rr14_cache_apagada_por_defecto_vuelve_a_consultar(tmp_path, monkeypatch):
    falsa = SuperficieFalsa()
    monkeypatch.setattr(acquire, "obtener_superficie", lambda *a, **k: falsa)
    p = panel_de_dos()

    acquire.capturar_panel(p, repeticiones=1, cache_dir=tmp_path / "c",
                           crudo_dir=tmp_path / "r", pausa_s=0)
    acquire.capturar_panel(p, repeticiones=1, cache_dir=tmp_path / "c",
                           crudo_dir=tmp_path / "r", pausa_s=0)

    # 2 frases × 2 corridas: nada se reusó.
    assert falsa.llamadas == 4


def test_rr14_con_cache_explicita_no_vuelve_a_consultar(tmp_path, monkeypatch):
    falsa = SuperficieFalsa()
    monkeypatch.setattr(acquire, "obtener_superficie", lambda *a, **k: falsa)
    p = panel_de_dos()

    acquire.capturar_panel(p, repeticiones=1, usar_cache=True, cache_dir=tmp_path / "c",
                           crudo_dir=tmp_path / "r", pausa_s=0)
    acquire.capturar_panel(p, repeticiones=1, usar_cache=True, cache_dir=tmp_path / "c",
                           crudo_dir=tmp_path / "r", pausa_s=0)

    assert falsa.llamadas == 2


def test_rr14_la_respuesta_cruda_se_guarda_como_evidencia(tmp_path, monkeypatch):
    falsa = SuperficieFalsa()
    monkeypatch.setattr(acquire, "obtener_superficie", lambda *a, **k: falsa)
    crudo = tmp_path / "crudo"

    acquire.capturar_panel(panel_de_dos(), repeticiones=1, cache_dir=tmp_path / "c",
                           crudo_dir=crudo, pausa_s=0)

    assert (crudo / "G1.json").is_file() and (crudo / "G2.json").is_file()
    guardado = json.loads((crudo / "G1.json").read_text("utf-8"))
    assert guardado["candidates"][0]["groundingMetadata"]["groundingChunks"]


def test_rr14_recalcular_desde_crudo_no_consulta(tmp_path, monkeypatch):
    falsa = SuperficieFalsa()
    monkeypatch.setattr(acquire, "obtener_superficie", lambda *a, **k: falsa)
    p = panel_de_dos()
    crudo = tmp_path / "crudo"
    acquire.capturar_panel(p, repeticiones=1, cache_dir=tmp_path / "c",
                           crudo_dir=crudo, pausa_s=0)
    antes = falsa.llamadas

    capturas = acquire.capturas_desde_disco(p, crudo)

    assert falsa.llamadas == antes
    assert len(capturas) == 2
    assert all(c.estado == "con_busqueda" for c in capturas)


# --------------------------------------------------------------------------- #
# RR-15 · la superficie es intercambiable y se valida por nombre
# --------------------------------------------------------------------------- #

def test_rr15_superficie_desconocida_falla_con_mensaje_util():
    with pytest.raises(ValueError, match="superficie desconocida"):
        obtener_superficie("ai-overviews")


def test_rr15_gemini_se_resuelve_sin_consultar(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-de-prueba")
    s = obtener_superficie("gemini")
    assert s.nombre == "gemini"
    assert s.modelo == "gemini-de-prueba"


# --------------------------------------------------------------------------- #
# RR-16 · la clave se busca en orden y el error no revela el valor
# --------------------------------------------------------------------------- #

def test_rr16_la_variable_de_entorno_gana(monkeypatch):
    from maria_answers import config
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-entorno")
    assert config.gemini_api_key() == "clave-de-entorno"


def test_rr16_sin_clave_el_error_nombra_donde_busco(monkeypatch, tmp_path):
    from maria_answers import config
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "SECRET_ENV", tmp_path / "no-existe.env")
    monkeypatch.setattr(config, "CONFIG_PHP", tmp_path / "no-existe.php")
    with pytest.raises(RuntimeError) as exc:
        config.gemini_api_key()
    assert "GEMINI_API_KEY" in str(exc.value)


# --------------------------------------------------------------------------- #
# RR-17 · el almacén archiva y recupera un MarcaRun, y calcula el delta
# --------------------------------------------------------------------------- #

def test_rr17_store_archiva_y_recupera_un_marcarun(tmp_path):
    from maria_answers.contract import Captura, Fuente

    def cap(fid, texto, doms):
        return Captura(frase_id=fid, frase_texto="t", texto=texto,
                       fuentes=[Fuente(dominio=d) for d in doms], busquedas=["q"])

    ayer = puntuar_marca(GESTAIR, [cap("G1", "Nadie.", [])],
                         timestamp_utc="2026-09-06T00:00:00+00:00")
    hoy = puntuar_marca(GESTAIR, [cap("G1", "Gestair primero.", ["gestair.com"])],
                        timestamp_utc="2026-09-07T00:00:00+00:00")

    runstore.archive(ayer, tmp_path)
    prev = runstore.previous("GST", tmp_path, MarcaRun)
    assert prev is not None and prev.timestamp_utc == ayer.timestamp_utc

    runstore.archive(hoy, tmp_path)
    assert len(runstore.history("GST", tmp_path, MarcaRun)) == 2

    d = runstore.delta(hoy, prev)
    assert d["total"] > 0                      # la marca mejoró
    assert d["dimensiones"]["R1"] == 4.0
    assert d["dimensiones"]["R2"] == 4.0


def test_rr17_el_indice_tecnico_sigue_usando_el_store_sin_cambios(tmp_path):
    """La generalización del almacén no rompe al consumidor original."""
    from maria_common.models import Account, AuditRun, DimensionResult

    run = AuditRun(cuenta=Account(codigo="ZZZ", nombre="Prueba"),
                   dimensiones=[DimensionResult(id="D1", nombre="x", puntos_max=25.0)])
    runstore.archive(run, tmp_path)
    recuperado = runstore.previous("ZZZ", tmp_path)      # sin pasar modelo
    assert isinstance(recuperado, AuditRun)
    assert recuperado.cuenta.codigo == "ZZZ"


# --------------------------------------------------------------------------- #
# RR-18 · la salida deriva del JSON, no recalcula
# --------------------------------------------------------------------------- #

def test_rr18_json_determinista_y_con_propiedades_calculadas():
    from maria_answers.contract import Captura

    run = puntuar_marca(GESTAIR, [Captura(frase_id="G1", frase_texto="t",
                                          texto="Gestair.", busquedas=["q"])],
                        timestamp_utc="2026-09-07T00:00:00+00:00")
    d = to_dict(run)
    assert d["puntaje_total"] == run.puntaje_total
    assert d["tier"] == run.tier
    assert d["cobertura"] == "1/1"
    assert to_json(run) == to_json(run)


def test_rr18_markdown_usa_los_puntos_del_json():
    """Mutar el modelo después de renderizar no cambia el Markdown ya emitido."""
    from maria_answers.contract import Captura

    run = puntuar_marca(GESTAIR, [Captura(frase_id="G1", frase_texto="t",
                                          texto="Gestair.", busquedas=["q"])])
    md = marca_report(run)
    run.dimensiones[0].por_frase[0].puntos = 999.0
    assert "999" not in md


def test_rr18_la_tabla_separa_las_marcas_sin_cobertura():
    from maria_answers.contract import Captura

    p = PanelRespuestas(industria="x", marcas=[GESTAIR], frases=[])
    sin = [Captura(frase_id="G1", frase_texto="t", estado="sin_busqueda",
                   motivo="de memoria")]
    tabla = panel_table(puntuar_panel(p, sin))
    assert "Sin cobertura" in tabla
    assert "Gestair" in tabla


# --------------------------------------------------------------------------- #
# RR-19 · las repeticiones se agregan por frecuencia (enmienda §7 bis)
# --------------------------------------------------------------------------- #

def test_rr19_repeticiones_se_agregan_por_frecuencia():
    """Nombrada en 2 de 3 repeticiones vale dos tercios de R1, no todo ni nada."""
    from maria_answers.contract import Captura, Fuente

    def rep(texto, doms=()):
        return Captura(frase_id="G1", frase_texto="t", texto=texto,
                       fuentes=[Fuente(dominio=d) for d in doms], busquedas=["q"])

    reps = [rep("Gestair primero.", ["gestair.com"]),
            rep("Gestair otra vez.", []),
            rep("Nadie del panel.", [])]
    run = puntuar_marca(GESTAIR, reps)

    r1 = next(d for d in run.dimensiones if d.id == "R1")
    r2 = next(d for d in run.dimensiones if d.id == "R2")
    assert r1.puntos == pytest.approx(4 * 2 / 3, abs=0.01)   # 2 de 3 menciones
    assert r2.puntos == pytest.approx(4 * 1 / 3, abs=0.01)   # 1 de 3 citas
    # Sigue siendo UNA frase: el denominador no se triplica.
    assert run.frases_totales == 1
    assert run.frases_con_busqueda == 1
    assert run.puntos_alcanzables == 10.0


def test_rr19_una_sola_repeticion_da_el_binario_de_siempre():
    from maria_answers.contract import Captura, Fuente

    una = [Captura(frase_id="G1", frase_texto="t", texto="Gestair.",
                   fuentes=[Fuente(dominio="gestair.com")], busquedas=["q"])]
    run = puntuar_marca(GESTAIR, una)
    assert next(d for d in run.dimensiones if d.id == "R1").puntos == 4.0
    assert next(d for d in run.dimensiones if d.id == "R2").puntos == 4.0


def test_rr19_la_evidencia_dice_en_cuantas_repeticiones_aparecio():
    from maria_answers.contract import Captura

    reps = [Captura(frase_id="G1", frase_texto="t", texto="Gestair.", busquedas=["q"]),
            Captura(frase_id="G1", frase_texto="t", texto="nadie", busquedas=["q"])]
    run = puntuar_marca(GESTAIR, reps)
    detalle = next(d for d in run.dimensiones if d.id == "R1").por_frase[0].evidencia[0].detalle
    assert "1/2 repeticiones" in detalle


def test_rr19_capturar_panel_consulta_n_veces_por_frase(tmp_path, monkeypatch):
    falsa = SuperficieFalsa()
    monkeypatch.setattr(acquire, "obtener_superficie", lambda *a, **k: falsa)

    caps = acquire.capturar_panel(panel_de_dos(), repeticiones=3, pausa_s=0,
                                  cache_dir=tmp_path / "c", crudo_dir=tmp_path / "r")

    assert falsa.llamadas == 6              # 2 frases × 3
    assert len(caps) == 6
    assert (tmp_path / "r" / "G1.r1.json").is_file()
    assert (tmp_path / "r" / "G1.r3.json").is_file()
    # Y al recalcular desde disco vuelven las 6.
    assert len(acquire.capturas_desde_disco(panel_de_dos(), tmp_path / "r")) == 6
