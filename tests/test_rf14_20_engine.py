"""RF-14..RF-20 — scoring, salida, histórico, analista."""
import json

from maria_common.models import (
    Account, AuditRun, DimensionResult, Evidence, Finding, SubCriterion,
)
from maria.report import json_out, markdown, panel_table
from maria.scoring.tiers import cuartiles_panel, tier_for
from maria.store import runs as runstore


def _dim(dim_id, nombre, pmax, pts):
    return DimensionResult(
        id=dim_id, nombre=nombre, puntos_max=pmax,
        sub_criterios=[SubCriterion(id=f"{dim_id}.1", nombre="x", puntos_max=pmax, puntos=pts,
                                    evidencia=[Evidence(method="static", detail="ok")])],
    )


def _run(codigo="T", pts=(20, 18, 16, 10, 12, 2), estado="medido"):
    dims = [
        _dim("D1", "Estructura", 25, pts[0]), _dim("D2", "Acceso", 20, pts[1]),
        _dim("D3", "Legibilidad", 20, pts[2]), _dim("D4", "Divulgación", 15, pts[3]),
        _dim("D5", "Leads", 15, pts[4]), _dim("D6", "Frontera", 5, pts[5]),
    ]
    return AuditRun(cuenta=Account(codigo=codigo, nombre=codigo, url="https://e.com"),
                    estado=estado, dimensiones=dims, timestamp_utc="2026-09-05T00:00:00+00:00")


# ---- RF-14 · scoring y tiers ----

def test_rf14_total_es_suma_core_mas_bonus_acotado():
    # OJO: la rúbrica de §2 suma 95 en core (25+20+20+15+15), no 100 — el texto
    # del plan dice "100 + 5" pero los sub-criterios suman 95. Se respeta la suma
    # real (como hizo el scoring manual de docs/decisiones/2026-09-01-scoring-panel.md).
    run = _run(pts=(25, 20, 20, 15, 15, 5))
    assert run.puntaje_total == 95 + 5
    assert run.tier == "Líder GEO"


def test_rf14_tiers_por_rango():
    assert tier_for(10) == "Invisible"
    assert tier_for(40) == "Parcial"
    assert tier_for(60) == "Emergente"
    assert tier_for(90) == "Líder GEO"


def test_rf14_no_aplica_sin_puntaje():
    run = _run(estado="no_aplica")
    run.cuenta.url = None
    assert run.puntaje_total is None and run.tier is None


# ---- RF-15 · JSON canónico determinista ----

def test_rf15_json_determinista():
    a, b = json_out.to_json(_run()), json_out.to_json(_run())
    assert a == b
    d = json.loads(a)
    assert d["schema_version"] and d["puntaje_total"] is not None


def test_rf15_hallazgos_ordenados_por_severidad():
    run = _run()
    run.hallazgos = [Finding(severidad="informativa", detalle="i"),
                     Finding(severidad="critica", detalle="c")]
    d = json_out.to_dict(run)
    assert [h["severidad"] for h in d["hallazgos"]] == ["critica", "informativa"]


# ---- RF-16 · Markdown derivado sin recálculo ----

def test_rf16_markdown_usa_los_puntos_del_json():
    run = _run(pts=(13, 20, 18, 3, 7, 0))
    md = markdown.account_report(run)
    assert "D1 · Estructura — 13" in md
    # mutar el modelo NO cambia lo ya escrito: se re-deriva del run, no se recalcula aparte
    assert str(run.puntaje_total) in md


# ---- RF-18 · sección unverified ----

def test_rf18_unverified_en_seccion_aparte():
    run = _run()
    run.dimensiones[3].sub_criterios.append(
        SubCriterion(id="D4.2", nombre="cookies", puntos_max=3, puntos=None,
                     status="unverified", motivo="sin footer")
    )
    d = json_out.to_dict(run)
    assert any(u["id"] == "D4.2" for u in d["unverified"])
    assert "Sub-criterios sin verificar" in markdown.account_report(run)


# ---- RF-19 · histórico y delta ----

def test_rf19_delta_por_dimension(tmp_path):
    r1 = _run(pts=(10, 10, 10, 10, 10, 0))
    r1.timestamp_utc = "2026-09-01T00:00:00+00:00"
    r2 = _run(pts=(20, 10, 12, 10, 10, 2))
    r2.timestamp_utc = "2026-09-05T00:00:00+00:00"
    runstore.archive(r1, tmp_path)
    runstore.archive(r2, tmp_path)
    hist = runstore.history("T", tmp_path)
    assert len(hist) == 2
    d = runstore.delta(r2, runstore.history("T", tmp_path)[0])
    assert d["dimensiones"]["D1"] == 10.0
    assert d["dimensiones"]["D3"] == 2.0


# ---- RF-17 · tabla comparativa ----

def test_rf17_panel_table_ordena_y_separa_no_medidos():
    runs = [
        _run("HI", pts=(25, 20, 20, 15, 15, 2)),
        _run("LO", pts=(0, 5, 10, 0, 3, 0)),
        _run("INA", estado="inaccesible"),
    ]
    runs[2].motivo = "TLS roto"
    table = panel_table.panel_table(runs)
    hi_idx, lo_idx = table.index("HI"), table.index("LO")
    assert hi_idx < lo_idx
    assert "Fuera del ranking" in table and "INA" in table.split("Fuera del ranking")[1]
    # la tabla comparativa lleva cuartil, no el tier absoluto (decisión 09-09-2026)
    assert "cuartil" in table and "Q1" in table
    assert "Invisible" not in table and "Líder GEO" not in table


# ---- RF-22 · cuartiles de ranking del panel ----

def test_rf22_cuartiles_reparte_por_posicion():
    # 10 cuentas, puntajes distintos → Q1×3, Q2×2, Q3×3, Q4×2
    items = [(f"C{i}", float(100 - i * 5)) for i in range(10)]
    q = cuartiles_panel(items)
    from collections import Counter
    assert Counter(q.values()) == {"Q1": 3, "Q2": 2, "Q3": 3, "Q4": 2}
    assert q["C0"] == "Q1"   # el mejor
    assert q["C9"] == "Q4"   # el peor


def test_rf22_orden_por_puntaje_desc_desempate_por_clave():
    q = cuartiles_panel([("b", 50.0), ("a", 50.0), ("z", 90.0), ("y", 10.0)])
    assert q == {"z": "Q1", "a": "Q2", "b": "Q3", "y": "Q4"}


def test_rf22_panel_vacio():
    assert cuartiles_panel([]) == {}


def test_rf22_no_entra_en_el_json_por_cuenta():
    d = json_out.to_dict(_run())
    assert "cuartil" not in d and "Q1" not in json_out.to_json(_run())


# ---- RF-20 · hallazgos del analista no cambian el puntaje ----

def test_rf20_analyst_notes_no_alteran_puntaje(tmp_path):
    from maria.analyst import apply_analyst_notes

    run = _run("AFL")
    total_antes = run.puntaje_total
    notes = tmp_path / "notes.yaml"
    notes.write_text(
        "cuentas:\n  AFL:\n    hallazgos:\n      - severidad: alta\n        detalle: 'cotizador que no cotiza'\n"
        "    tiempo_respuesta_pasocero: '3 min'\n", "utf-8",
    )
    apply_analyst_notes([run], notes)
    assert run.puntaje_total == total_antes
    assert any(h.origin == "analyst" for h in run.hallazgos)
    assert any("Paso Cero" in h.detalle for h in run.hallazgos)
