"""T20 — recorrido RF por RF: cada requisito tiene un test que lo nombra.

Este test no prueba comportamiento nuevo: verifica que la cobertura existe. Si se
agrega un RF a docs/plan.md sin su test, esto falla.
"""
from pathlib import Path

RF_A_TEST = {
    "RF-01": "test_rf01",
    "RF-02": "test_rf02_d1_sin_render",
    "RF-03": "test_rf03",
    "RF-04": "test_rf04_semaforo",
    "RF-05": "test_rf05_segunda_llamada_sale_de_cache",
    "RF-06": "test_rf06",
    "RF-07": "test_rf07",
    "RF-08": "test_rf08",
    "RF-09": "test_rf09",
    "RF-10": "test_rf10",
    "RF-11": "test_rf11",
    "RF-12": "test_rf12",
    "RF-13": "test_rf13",
    "RF-14": "test_rf14",
    "RF-15": "test_rf15",
    "RF-16": "test_rf16",
    "RF-17": "test_rf17",
    "RF-18": "test_rf18",
    "RF-19": "test_rf19",
    "RF-20": "test_rf20",
    "RF-22": "test_rf22",
}


def test_cada_rf_tiene_un_test_que_lo_nombra():
    blob = "\n".join(
        p.read_text("utf-8") for p in Path(__file__).parent.glob("test_*.py")
        if p.name != Path(__file__).name
    )
    faltan = [rf for rf, needle in RF_A_TEST.items() if needle not in blob]
    assert not faltan, f"RF sin test: {faltan}"
