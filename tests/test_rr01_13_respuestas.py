"""Índice de Respuestas — RR-01 a RR-13.

Suite offline: sin red y sin LLM. Todo entra como dicts ya obtenidos, igual que
la suite del índice técnico entra con `raw.html` ya capturado.
"""
from __future__ import annotations

import json

import pytest

from maria_answers.contract import Captura, Fuente, Marca, PanelRespuestas
from maria_answers.match import (
    buscar_citas,
    buscar_mencion,
    coincide_dominio,
    normalizar_dominio,
)
from maria_answers.panel import load_panel
from maria_answers.parse import desde_gemini
from maria_answers.score import puntuar_marca, puntuar_panel

GESTAIR = Marca(codigo="GST", nombre="Gestair", dominios=["gestair.com"],
                alias=["Gestair Business Aviation"])
GLOBAL_ES = Marca(codigo="GCH", nombre="Global Charters",
                  dominios=["global-charters.com"])
AUREO = Marca(codigo="AUR", nombre="Áureo Jets", dominios=["aureojets.com"])


def cap(frase_id="G1", texto="", fuentes=(), estado="con_busqueda", motivo=None):
    return Captura(
        frase_id=frase_id, frase_texto="frase de prueba", estado=estado, motivo=motivo,
        texto=texto, fuentes=[Fuente(dominio=d) for d in fuentes],
        busquedas=["q"] if estado == "con_busqueda" else [],
    )


# --------------------------------------------------------------------------- #
# RR-01 · el panel se carga y se valida
# --------------------------------------------------------------------------- #

def test_rr01_panel_se_carga_desde_yaml(tmp_path):
    p = tmp_path / "panel.yaml"
    p.write_text(
        "industria: aviación ejecutiva\n"
        "mercado: {pais: ES, idioma: es}\n"
        "marcas:\n"
        "  - {codigo: GST, nombre: Gestair, dominios: [gestair.com]}\n"
        "frases:\n"
        "  - {id: G1, tipo: general, texto: alquiler de jet privado}\n",
        "utf-8",
    )
    panel = load_panel(p)
    assert panel.industria == "aviación ejecutiva"
    assert panel.mercado.pais == "ES"
    assert panel.marcas[0].codigo == "GST"
    assert panel.frases[0].tipo == "general"


def test_rr01_panel_sin_frases_es_error(tmp_path):
    p = tmp_path / "panel.yaml"
    p.write_text("industria: x\nmarcas:\n  - {codigo: A, nombre: A}\nfrases: []\n", "utf-8")
    with pytest.raises(ValueError, match="no tiene frases"):
        load_panel(p)


def test_rr01_panel_con_marca_duplicada_es_error(tmp_path):
    p = tmp_path / "panel.yaml"
    p.write_text(
        "industria: x\n"
        "marcas:\n  - {codigo: A, nombre: A}\n  - {codigo: A, nombre: B}\n"
        "frases:\n  - {id: G1, tipo: general, texto: t}\n", "utf-8")
    with pytest.raises(ValueError, match="duplicada"):
        load_panel(p)


# --------------------------------------------------------------------------- #
# RR-02 · una frase sin búsqueda sale del denominador, no puntúa cero
# --------------------------------------------------------------------------- #

def test_rr02_frase_sin_busqueda_no_entra_al_denominador():
    capturas = [
        cap("G1", texto="Gestair lidera el mercado.", fuentes=["gestair.com"]),
        cap("G2", estado="sin_busqueda", motivo="respondió de memoria"),
    ]
    run = puntuar_marca(GESTAIR, capturas)
    # Solo la frase con búsqueda aporta máximo: 4 + 4 + 2 = 10, no 20.
    assert run.puntos_alcanzables == 10.0
    assert run.frases_con_busqueda == 1
    assert run.frases_totales == 2
    # Perfecta en la única frase que contó.
    assert run.puntaje_total == 100.0


def test_rr02_sin_ninguna_busqueda_el_puntaje_es_none_no_cero():
    run = puntuar_marca(GESTAIR, [cap("G1", estado="sin_busqueda", motivo="x")])
    assert run.puntaje_total is None
    assert run.tier is None
    assert run.estado == "sin_cobertura"


# --------------------------------------------------------------------------- #
# RR-03 · el dominio de la fuente sale de web.title, nunca de la URI
# --------------------------------------------------------------------------- #

def test_rr03_dominio_sale_de_web_title_no_de_la_uri():
    crudo = {
        "candidates": [{
            "content": {"parts": [{"text": "Gestair es un operador español."}]},
            "groundingMetadata": {
                "webSearchQueries": ["operadores españa"],
                "groundingChunks": [
                    {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZ123",
                             "title": "gestair.com"}},
                    {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZ456",
                             "title": "unitedaviation.es"}},
                ],
            },
        }]
    }
    c = desde_gemini(crudo, frase_id="G1", frase_texto="t")
    assert c.estado == "con_busqueda"
    assert [f.dominio for f in c.fuentes] == ["gestair.com", "unitedaviation.es"]
    # El host de la URI jamás debe filtrarse como dominio de la fuente.
    assert all("vertexaisearch" not in f.dominio for f in c.fuentes)


def test_rr03_sin_busquedas_ni_fuentes_es_sin_busqueda():
    crudo = {"candidates": [{"content": {"parts": [{"text": "respuesta de memoria"}]}}]}
    c = desde_gemini(crudo, frase_id="G1", frase_texto="t")
    assert c.estado == "sin_busqueda"
    assert c.cuenta_para_el_denominador is False


def test_rr03_error_de_api_se_registra_con_motivo():
    c = desde_gemini({"error": {"message": "quota exceeded"}}, frase_id="G1", frase_texto="t")
    assert c.estado == "error"
    assert "quota" in c.motivo


# --------------------------------------------------------------------------- #
# RR-04 · el match de nombre usa límites de palabra y normaliza acentos
# --------------------------------------------------------------------------- #

def test_rr04_mencion_normaliza_acentos():
    variante, off = buscar_mencion("Aureo Jets opera desde Madrid.", AUREO)
    assert variante == "Áureo Jets"
    assert off == 0


def test_rr04_mencion_respeta_limites_de_palabra():
    # "Gestair" no debe hacer match dentro de otra palabra.
    variante, _ = buscar_mencion("La empresa Gestairways no es del panel.", GESTAIR)
    assert variante is None


def test_rr04_mencion_encuentra_alias():
    variante, off = buscar_mencion("Hablamos de Gestair Business Aviation hoy.", GESTAIR)
    assert variante in ("Gestair", "Gestair Business Aviation")
    assert off is not None


# --------------------------------------------------------------------------- #
# RR-05 · el match de dominio es exacto o subdominio, nunca subcadena
# --------------------------------------------------------------------------- #

def test_rr05_dominio_globalcharter_no_es_global_charters():
    """Caso real de la sonda: dos empresas distintas, nombres casi iguales."""
    assert coincide_dominio("global-charters.com", "global-charters.com") is True
    assert coincide_dominio("globalcharter.com", "global-charters.com") is False
    fuentes = [Fuente(dominio="globalcharter.com")]
    assert buscar_citas(fuentes, GLOBAL_ES) == []


def test_rr05_dominio_acepta_subdominio_pero_no_sufijo_pegado():
    assert coincide_dominio("www.gestair.com", "gestair.com") is True
    assert coincide_dominio("charter.gestair.com", "gestair.com") is True
    assert coincide_dominio("notgestair.com", "gestair.com") is False


def test_rr05_normalizar_dominio_saca_esquema_y_www():
    assert normalizar_dominio("https://www.Gestair.com/vuelos") == "gestair.com"


# --------------------------------------------------------------------------- #
# RR-06 · la lista `excluir` invalida un match
# --------------------------------------------------------------------------- #

def test_rr06_excluir_bloquea_el_falso_positivo():
    marca = Marca(codigo="ATX", nombre="Air TXT", dominios=["airtxt.es"],
                  excluir=["air txt de terceros"])
    variante, _ = buscar_mencion("Hablamos de air txt de terceros, no de la marca.", marca)
    assert variante is None
    # Fuera de la exclusión sí cuenta.
    variante2, _ = buscar_mencion("Air TXT vuela desde Ibiza.", marca)
    assert variante2 == "Air TXT"


# --------------------------------------------------------------------------- #
# RR-07 / RR-08 / RR-09 · las tres señales
# --------------------------------------------------------------------------- #

def test_rr07_mencion_otorga_cuatro_puntos():
    run = puntuar_marca(GESTAIR, [cap("G1", texto="Gestair opera en Madrid.")])
    r1 = next(d for d in run.dimensiones if d.id == "R1")
    assert r1.puntos == 4.0 and r1.puntos_max == 4.0


def test_rr08_cita_otorga_cuatro_puntos_aunque_no_haya_mencion():
    """Señales independientes: la IA puede apoyarse en el sitio sin nombrar la marca."""
    run = puntuar_marca(GESTAIR, [cap("G1", texto="Hay varios operadores.",
                                      fuentes=["gestair.com"])])
    r1 = next(d for d in run.dimensiones if d.id == "R1")
    r2 = next(d for d in run.dimensiones if d.id == "R2")
    assert r1.puntos == 0.0
    assert r2.puntos == 4.0


def test_rr09_posicion_puntua_mas_temprano_que_tarde():
    temprano = puntuar_marca(GESTAIR, [cap("G1", texto="Gestair" + " x" * 200)])
    tardio = puntuar_marca(GESTAIR, [cap("G1", texto="x " * 200 + "Gestair")])
    p_temprano = next(d for d in temprano.dimensiones if d.id == "R3").puntos
    p_tardio = next(d for d in tardio.dimensiones if d.id == "R3").puntos
    assert p_temprano > p_tardio
    assert p_temprano == pytest.approx(2.0, abs=0.05)
    assert p_tardio == pytest.approx(0.0, abs=0.05)


# --------------------------------------------------------------------------- #
# RR-10 / RR-11 · normalización a 100 y cobertura
# --------------------------------------------------------------------------- #

def test_rr10_puntaje_se_normaliza_sobre_las_frases_con_busqueda():
    capturas = [
        cap("G1", texto="Gestair primero.", fuentes=["gestair.com"]),   # 4+4+~2
        cap("G2", texto="Nadie del panel."),                            # 0+0+0
        cap("G3", estado="sin_busqueda", motivo="de memoria"),          # fuera
    ]
    run = puntuar_marca(GESTAIR, capturas)
    assert run.frases_con_busqueda == 2
    assert run.puntos_alcanzables == 20.0            # 2 frases × 10, no 3 × 10
    assert 45.0 <= run.puntaje_total <= 50.0         # ~la mitad


def test_rr11_cobertura_se_reporta_siempre():
    capturas = [cap("G1", texto="Gestair."), cap("G2", estado="sin_busqueda", motivo="x")]
    run = puntuar_marca(GESTAIR, capturas)
    assert run.cobertura == "1/2"


# --------------------------------------------------------------------------- #
# RR-12 · tiers propios, distintos de los del índice técnico
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("texto,fuentes,tier_esperado", [
    ("Gestair al inicio.", ["gestair.com"], "Referencia"),   # 10/10
    ("Nada de nada.", [], "Ausente"),                        # 0/10
])
def test_rr12_tiers_ausente_marginal_presente_referencia(texto, fuentes, tier_esperado):
    run = puntuar_marca(GESTAIR, [cap("G1", texto=texto, fuentes=fuentes)])
    assert run.tier == tier_esperado


def test_rr12_los_tiers_no_son_los_del_indice_tecnico():
    nombres = set()
    for texto, fuentes in [("Gestair.", ["gestair.com"]), ("nada", [])]:
        nombres.add(puntuar_marca(GESTAIR, [cap("G1", texto=texto, fuentes=fuentes)]).tier)
    assert nombres.isdisjoint({"Invisible", "Parcial", "Emergente", "Líder GEO"})


# --------------------------------------------------------------------------- #
# RR-13 · el scoring es determinista
# --------------------------------------------------------------------------- #

def test_rr13_scoring_determinista_byte_a_byte():
    panel = PanelRespuestas(
        industria="aviación ejecutiva",
        marcas=[GESTAIR, GLOBAL_ES, AUREO],
        frases=[],
    )
    capturas = [
        cap("G1", texto="Gestair y Áureo Jets compiten.", fuentes=["gestair.com"]),
        cap("G2", texto="Otra respuesta.", fuentes=["global-charters.com"]),
    ]
    ts = "2026-09-06T12:00:00+00:00"
    a = puntuar_panel(panel, capturas, timestamp_utc=ts)
    b = puntuar_panel(panel, capturas, timestamp_utc=ts)
    ja = json.dumps([json.loads(r.model_dump_json()) for r in a], sort_keys=True)
    jb = json.dumps([json.loads(r.model_dump_json()) for r in b], sort_keys=True)
    assert ja == jb


def test_rr13_el_panel_sale_ordenado_por_ranking():
    panel = PanelRespuestas(industria="x", marcas=[AUREO, GESTAIR], frases=[])
    capturas = [cap("G1", texto="Gestair manda.", fuentes=["gestair.com"])]
    orden = [r.cuenta.codigo for r in puntuar_panel(panel, capturas)]
    assert orden[0] == "GST"
