"""T6 / T7 — fixtures sintéticos de modo de fallo (los únicos fixtures versionados).

`tests/fixtures/_sintetico/*/meta.json` modela la forma de nuestro propio registro
de error, sin contenido de terceros.
"""
import json
from pathlib import Path

import pytest

SINT = Path(__file__).parent / "fixtures" / "_sintetico"


@pytest.mark.parametrize("caso,estado", [
    ("inaccesible-tls", "inaccesible"),
    ("inaccesible-bucle-redirects", "inaccesible"),
])
def test_fixture_sintetico_tiene_forma_de_registro_propio(caso, estado):
    meta = json.loads((SINT / caso / "meta.json").read_text("utf-8"))
    assert meta["estado"] == estado
    assert meta["motivo"] and meta["user_agent"].startswith("MarIA-GEO-Audit")
    # no hay contenido capturado de terceros
    assert not (SINT / caso / "raw.html").exists()
    assert not (SINT / caso / "rendered.html").exists()


def test_clasificacion_de_error_reproduce_los_sinteticos():
    from maria.fetch.static import classify_error

    tls = json.loads((SINT / "inaccesible-tls" / "meta.json").read_text("utf-8"))
    bucle = json.loads((SINT / "inaccesible-bucle-redirects" / "meta.json").read_text("utf-8"))
    assert classify_error(tls["error"]) == ("inaccesible", "certificado TLS inválido para este dominio")
    assert classify_error(bucle["error"]) == (
        "inaccesible", "bucle de redirecciones para un cliente que no es navegador",
    )
