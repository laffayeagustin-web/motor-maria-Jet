"""Índice de Respuestas — RR-20 a RR-27: serie diaria, página y propuesta.

Fases 4–5 del plan. Offline: la superficie y las llamadas generativas de Gemini
se reemplazan por dobles. Nada acá toca la red.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from maria.store import runs as runstore
from maria_answers import propose, serie, solicitudes
from maria_answers.contract import Captura, Fuente, Marca, MarcaRun, Mercado
from maria_answers.score import puntuar_marca

GST = Marca(codigo="GST", nombre="Gestair", dominios=["gestair.com"])


def _run(fecha: str, texto: str, doms=()) -> MarcaRun:
    cap = Captura(frase_id="G1", frase_texto="t", texto=texto,
                  fuentes=[Fuente(dominio=d) for d in doms], busquedas=["q"])
    return puntuar_marca(GST, [cap], timestamp_utc=fecha)


# --------------------------------------------------------------------------- #
# RR-20 · el nombre de archivo del histórico normaliza el offset UTC a Z
# --------------------------------------------------------------------------- #

def test_rr20_stamp_normaliza_offset_utc_en_cualquier_forma():
    for ts in ("2026-09-07T14:23:11+00:00", "2026-09-07T14:23:11+0000",
               "2026-09-07T14:23:11Z"):
        assert runstore.stamp_archivo(ts) == "20260907T142311Z"


def test_rr20_archive_no_deja_mas_00_00_en_el_nombre(tmp_path):
    run = _run("2026-09-07T14:23:11+00:00", "Gestair.")
    p = runstore.archive(run, tmp_path)
    assert "+00:00" not in p.name and "+0000" not in p.name
    assert p.name == "20260907T142311Z.json"


# --------------------------------------------------------------------------- #
# RR-21 · la serie devuelve las últimas N corridas en orden cronológico
# --------------------------------------------------------------------------- #

def test_rr21_serie_ordena_y_recorta(tmp_path):
    for fecha, texto, doms in [
        ("2026-09-01T00:00:00+00:00", "Nadie.", []),
        ("2026-09-02T00:00:00+00:00", "Gestair.", []),
        ("2026-09-03T00:00:00+00:00", "Gestair primero.", ["gestair.com"]),
    ]:
        runstore.archive(_run(fecha, texto, doms), tmp_path)

    puntos = serie.serie("GST", tmp_path, n=2)
    assert [p.fecha[:10] for p in puntos] == ["2026-09-02", "2026-09-03"]
    assert puntos[-1].puntaje > puntos[0].puntaje       # mejoró


# --------------------------------------------------------------------------- #
# RR-22 · la media móvil de 7 días acompaña al valor del día (rúbrica §7 bis)
# --------------------------------------------------------------------------- #

def test_rr22_media_movil_salta_las_corridas_sin_cobertura():
    # None = corrida sin cobertura: no es un cero, se saltea.
    assert serie.media_movil([None, None]) is None
    assert serie.media_movil([100.0, None, 50.0]) == 75.0


def test_rr22_media_movil_solo_mira_hacia_atras(tmp_path):
    for i, p in enumerate([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0], 1):
        cap = Captura(frase_id="G1", frase_texto="t",
                      texto=("Gestair " * 0) + "Gestair.", busquedas=["q"])
        run = MarcaRun(cuenta=GST, timestamp_utc=f"2026-09-{i:02d}T00:00:00+00:00")
        # puntaje sintético: se arma el run directo para fijar el valor
        from maria_answers.contract import SenalResult, SubSenal
        run.dimensiones = [SenalResult(id="R1", nombre="x", por_frase=[
            SubSenal(frase_id="G1", puntos=p / 10, puntos_max=10.0)])]
        run.frases_con_busqueda = 1
        run.frases_totales = 1
        runstore.archive(run, tmp_path)

    puntos = serie.serie("GST", tmp_path, n=8)
    # El día 7 ve los días 1..7; el día 8 ve 2..8. La MM7 del día 7 no cambia después.
    assert puntos[6].media_movil_7d == pytest.approx(
        sum([10, 20, 30, 40, 50, 60, 70]) / 7, abs=0.01)
    assert puntos[7].media_movil_7d == pytest.approx(
        sum([20, 30, 40, 50, 60, 70, 80]) / 7, abs=0.01)


# --------------------------------------------------------------------------- #
# RR-23 · build_pages genera la página de Respuestas desde el JSON, sin recalcular
# --------------------------------------------------------------------------- #

def _cargar_build_pages():
    ruta = Path(__file__).parents[1] / "tools" / "build_pages.py"
    spec = importlib.util.spec_from_file_location("build_pages", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rr23_pagina_respuestas_sale_del_report_dir(tmp_path):
    bp = _cargar_build_pages()
    report = tmp_path / "report-respuestas"
    report.mkdir()
    (report / "GST.json").write_text(json.dumps({
        "cuenta": {"codigo": "GST", "nombre": "Gestair", "dominios": ["gestair.com"],
                   "alias": [], "excluir": []},
        "puntaje_total": 62.5, "tier": "Presente", "cobertura": "8/10",
        "timestamp_utc": "2026-09-07T04:17:00+00:00", "superficie": "gemini",
        "modelo": "gemini-2.5-flash", "media_movil_7d": 60.0,
        "delta": {"vs": "ayer", "total": 3.0, "dimensiones": {}},
        "serie": [{"fecha": "2026-09-06T04:17:00+00:00", "puntaje": 59.5,
                   "cobertura": "8/10", "media_movil_7d": 59.5},
                  {"fecha": "2026-09-07T04:17:00+00:00", "puntaje": 62.5,
                   "cobertura": "8/10", "media_movil_7d": 61.0}],
        "dimensiones": [
            {"id": "R1", "nombre": "Mención", "puntos": 24.0, "puntos_max": 32.0,
             "por_frase": [{"frase_id": "G1", "puntos": 4.0, "puntos_max": 4.0,
                            "estado": "con_busqueda",
                            "evidencia": [{"detalle": "nombrada como Gestair"}]}]},
            {"id": "R2", "nombre": "Cita", "puntos": 16.0, "puntos_max": 32.0,
             "por_frase": []},
            {"id": "R3", "nombre": "Posición", "puntos": 6.0, "puntos_max": 16.0,
             "por_frase": []},
        ],
    }, ensure_ascii=False), "utf-8")
    (report / "frases.json").write_text(json.dumps({
        "con_busqueda": 8, "total": 10, "repeticiones": 3, "modelo": "gemini-2.5-flash",
        "superficie": "gemini", "medicion_utc": "2026-09-07T04:17:00+00:00",
        "frases": [{"id": "G1", "texto": "alquiler de jet privado", "tipo": "general",
                    "estado": "con_busqueda", "repeticiones": 3, "con_busqueda": 3,
                    "motivo": None}],
    }, ensure_ascii=False), "utf-8")

    out = tmp_path / "pub" / "index.html"
    bp.build_respuestas(dict(slug="respuestas", report_dir=str(report), out=str(out),
                             title="T", h1="H", meta_desc="d",
                             industria="aviación ejecutiva"))
    html = out.read_text("utf-8")
    assert "Gestair" in html
    assert "Presente" not in html     # el tier no se publica (decisión 09-09-2026)
    assert "62.5" in html
    assert "ChatGPT" in html          # el límite del informe está en la página
    # Δ de 3 pts está dentro del ruido (§7 bis): se muestra en gris, no como flecha.
    assert "±3" in html
    assert "dentro del ruido medido" in html


# --------------------------------------------------------------------------- #
# RR-24 · `proponer` toma los competidores de las citas reales, no de la memoria
# --------------------------------------------------------------------------- #

def test_rr24_contar_dominios_cuenta_por_frase_no_por_repeticion():
    caps = [
        Captura(frase_id="G1", frase_texto="t", fuentes=[Fuente(dominio="lunajets.com")]),
        Captura(frase_id="G1", frase_texto="t", fuentes=[Fuente(dominio="lunajets.com")]),
        Captura(frase_id="G2", frase_texto="t", fuentes=[Fuente(dominio="lunajets.com")]),
        Captura(frase_id="G2", frase_texto="t", fuentes=[Fuente(dominio="gestair.com")]),
    ]
    tally = dict(propose.contar_dominios(caps, excluir_dominios=["gestair.com"]))
    assert tally == {"lunajets.com": 2}       # 2 frases, no 3 capturas; propio excluido


def test_rr24_codigo_de_marca_no_colisiona():
    usados: set[str] = set()
    assert propose._codigo_de("Gestair", usados) == "GES"
    assert propose._codigo_de("Gestair", usados) != "GES"   # dedup


# --------------------------------------------------------------------------- #
# RR-25 · `proponer` arma un panel sin congelar: empresa primero, no-competidores fuera
# --------------------------------------------------------------------------- #

def test_rr25_proponer_ensambla_el_panel_desde_la_evidencia(monkeypatch):
    frases_falsas = [
        {"tipo": "general", "texto": f"g{i}"} for i in range(1, 6)
    ] + [{"tipo": "long-tail", "texto": f"l{i}"} for i in range(1, 6)]

    def fake_gemini_json(system, user, schema, **kw):
        if "frases" in schema["properties"]:
            return {"frases": frases_falsas}
        return {"marcas": [
            {"dominio": "lunajets.com", "nombre": "LunaJets", "alias": ["Luna Jets"],
             "es_competidor": True},
            {"dominio": "wikipedia.org", "nombre": "Wikipedia", "es_competidor": False,
             "motivo_descarte": "enciclopedia"},
        ]}

    def fake_capturar_panel(panel, **kw):
        # dos dominios citados en >=2 frases: uno competidor, uno no
        caps = []
        for fid in ("G1", "G2", "G3"):
            caps.append(Captura(frase_id=fid, frase_texto="t", busquedas=["q"],
                                fuentes=[Fuente(dominio="lunajets.com"),
                                         Fuente(dominio="wikipedia.org")]))
        return caps

    monkeypatch.setattr(propose, "_gemini_json", fake_gemini_json)
    monkeypatch.setattr(propose, "capturar_panel", fake_capturar_panel)
    monkeypatch.setattr(propose, "gemini_modelo", lambda: "gemini-de-prueba")

    prop = propose.proponer("aviación ejecutiva", "Gestair", "https://www.gestair.com/")

    codigos = [m.codigo for m in prop.panel.marcas]
    nombres = [m.nombre for m in prop.panel.marcas]
    assert nombres[0] == "Gestair"                     # la empresa que pide, primero
    assert "LunaJets" in nombres                       # competidor citado, adentro
    assert "Wikipedia" not in nombres                  # no-competidor, afuera
    assert len(prop.panel.frases) == 10
    assert prop.panel.empresa_auditada == codigos[0]

    y = prop.to_yaml_dict()
    assert "_propuesta" in y and "congelar" in y["_propuesta"]


# --------------------------------------------------------------------------- #
# RR-26 · la cola en disco: encolar, verificar, mover
# --------------------------------------------------------------------------- #

def test_rr26_cola_mueve_la_solicitud_entre_estados(tmp_path):
    cd = solicitudes.ColaDisco(tmp_path)
    sol = solicitudes.Solicitud(id="X1", industria="aviación ejecutiva",
                                empresa="Gestair", dominio="gestair.com",
                                email="a@b.com")
    cd.guardar(sol)
    assert [s.id for s in cd.pendientes()] == []            # aún sin verificar

    sol.verificada_utc = "2026-09-07T00:00:00+00:00"
    cd.mover(sol, "pendiente")
    assert [s.id for s in cd.pendientes()] == ["X1"]
    assert not (tmp_path / "pendientes_verificacion" / "X1.json").exists()

    sol.resultado = {"procesada_utc": "2026-09-07T01:00:00+00:00", "yaml": "x"}
    cd.mover(sol, "procesada")
    assert [s.id for s in cd.pendientes()] == []
    assert [s.id for s in cd.procesadas()] == ["X1"]


# --------------------------------------------------------------------------- #
# RR-27 · control de gasto: fuera de límites ⇒ rechazo, sin consultar a Gemini
# --------------------------------------------------------------------------- #

def test_rr27_industria_fuera_de_la_lista_blanca_se_rechaza(tmp_path):
    cd = solicitudes.ColaDisco(tmp_path)
    sol = solicitudes.Solicitud(id="X2", industria="peluquería", empresa="X",
                                dominio="x.com", email="a@b.com",
                                verificada_utc="2026-09-07T00:00:00+00:00",
                                estado="pendiente")
    with pytest.raises(solicitudes.Rechazo, match="lista blanca"):
        solicitudes.puede_procesarse(sol, cd)


def test_rr27_email_sin_verificar_se_rechaza(tmp_path):
    cd = solicitudes.ColaDisco(tmp_path)
    sol = solicitudes.Solicitud(id="X3", industria="aviación ejecutiva", empresa="X",
                                dominio="x.com", email="a@b.com")
    with pytest.raises(solicitudes.Rechazo, match="verificad"):
        solicitudes.puede_procesarse(sol, cd)


def test_rr27_tope_diario_corta(tmp_path, monkeypatch):
    cd = solicitudes.ColaDisco(tmp_path)
    monkeypatch.setattr(cd, "procesadas_hoy", lambda *a, **k: 15)
    sol = solicitudes.Solicitud(id="X4", industria="aviación ejecutiva", empresa="X",
                                dominio="x.com", email="a@b.com",
                                verificada_utc="2026-09-07T00:00:00+00:00",
                                estado="pendiente")
    with pytest.raises(solicitudes.Rechazo, match="tope diario"):
        solicitudes.puede_procesarse(sol, cd, tope_diario=15)
