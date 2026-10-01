"""Orquestación completa: `audit_account` / `audit_panel` sin red.

Se parchea `maria.fetch.static.fetch` y `fetch_text` para devolver HTML sintético.
Cubre RF-01/02 (estado de cuenta según fetch + bundle), RF-17/18 (panel), y el
semáforo por dominio de RF-04 (T18).
"""
import threading

import pytest

from maria import audit as auditmod
from maria.fetch.static import FetchResult
from maria_common.models import Account
from maria_common.render_contract import RenderBundleEntry

HTML_OK = """<html><head><title>Ejemplo</title><meta name="description" content="d">
<link rel="canonical" href="https://e.com/"></head><body>
<a href="/a">a</a><a href="/b">b</a><a href="/c">c</a><a href="/d">d</a><a href="/e">e</a>
<a href="tel:+541150000000">tel</a> info@e.com</body></html>"""


@pytest.fixture
def patched_net(monkeypatch):
    def fake_fetch(url, **kw):
        if url.rstrip("/") in ("https://e.com", "https://e.com"):
            return FetchResult(url=url, ok=True, status=200, final_url="https://e.com/",
                               body=HTML_OK, headers={"content-type": "text/html"})
        # robots, sitemap, footer, llms, well-known: 404
        return FetchResult(url=url, ok=True, status=404, final_url=url, body="")

    def fake_fetch_text(url, **kw):
        if url.endswith("/robots.txt"):
            return "User-agent: *\nDisallow:\nSitemap: https://e.com/sitemap.xml\n"
        return None

    monkeypatch.setattr(auditmod.fetchmod, "fetch", fake_fetch)
    monkeypatch.setattr(auditmod.fetchmod, "fetch_text", fake_fetch_text)


def test_rf01_cuenta_sin_render_queda_unverified(patched_net):
    run = auditmod.audit_account(Account(codigo="E", nombre="E", url="https://e.com"))
    assert run.estado == "unverified"
    assert run.puntaje_total is not None  # la corrida no rompe
    assert len(run.unverified) > 0


def test_rf01_cuenta_con_render_queda_medido(patched_net, tmp_bundle_dir):
    entry = RenderBundleEntry(
        url="https://e.com", captured_utc="2026-09-05T00:00:00+00:00", rendered_words=40,
        ld_blocks=['{"@type":"Organization","name":"E SA","url":"https://e.com"}'],
    )
    d = tmp_bundle_dir([entry])
    run = auditmod.audit_account(Account(codigo="E", nombre="E", url="https://e.com"),
                                 bundle=auditmod.load_bundle(d))
    assert run.estado == "medido"


def test_no_aplica_sin_url():
    run = auditmod.audit_account(
        Account(codigo="BFL", nombre="Baires Fly", url=None, no_aplica_motivo="sin sitio")
    )
    assert run.estado == "no_aplica" and run.puntaje_total is None


def test_rf04_semaforo_serializa_por_dominio(monkeypatch):
    activos: dict[str, int] = {}
    max_simultaneo = {"n": 0}
    lock = threading.Lock()

    def fake_fetch(url, **kw):
        import time
        host = url.split("/")[2]
        with lock:
            activos[host] = activos.get(host, 0) + 1
            max_simultaneo["n"] = max(max_simultaneo["n"], max(activos.values()))
        time.sleep(0.01)
        with lock:
            activos[host] -= 1
        return FetchResult(url=url, ok=True, status=404, final_url=url, body="")

    monkeypatch.setattr(auditmod.fetchmod, "fetch", fake_fetch)
    monkeypatch.setattr(auditmod.fetchmod, "fetch_text", lambda url, **kw: None)

    accounts = [Account(codigo=f"C{i}", nombre="x", url="https://mismo.com") for i in range(4)]
    auditmod.audit_panel(accounts, workers=4)
    assert max_simultaneo["n"] == 1  # nunca 2 requests simultáneos al mismo host


def test_rf17_panel_table_desde_audit_panel(patched_net):
    accounts = [
        Account(codigo="E", nombre="E", url="https://e.com"),
        Account(codigo="BFL", nombre="Baires Fly", url=None, no_aplica_motivo="sin sitio"),
    ]
    runs = auditmod.audit_panel(accounts, workers=2)
    from maria.report.panel_table import panel_table

    table = panel_table(runs)
    assert "Fuera del ranking" in table and "Baires Fly" in table


# ---- RF-24 · fallback www./sin-www. cuando el DNS no resuelve -------------

def _dns_fail(url):
    return FetchResult(url=url, ok=False, estado="inaccesible",
                       motivo="el DNS no resuelve", error="fetch crudo: dns fail")


def test_rf24_dns_no_resuelve_reintenta_con_www(monkeypatch):
    llamadas = []

    def fake_fetch(url, **kw):
        llamadas.append(url)
        if url.rstrip("/") == "https://e.com":
            return _dns_fail(url)
        return FetchResult(url=url, ok=True, status=200, final_url=url, body=HTML_OK,
                           headers={"content-type": "text/html"})

    monkeypatch.setattr(auditmod.fetchmod, "fetch", fake_fetch)
    monkeypatch.setattr(auditmod.fetchmod, "fetch_text", lambda url, **kw: None)

    run = auditmod.audit_account(Account(codigo="E", nombre="E", url="https://e.com"))
    assert run.estado != "inaccesible"
    assert "https://e.com" in llamadas and "https://www.e.com" in llamadas
    swap = [h for h in run.hallazgos if "no resuelve por DNS" in h.detalle]
    assert len(swap) == 1
    assert "www.e.com" in swap[0].detalle and swap[0].severidad == "informativa"


def test_rf24_www_no_resuelve_reintenta_sin_www(monkeypatch):
    def fake_fetch(url, **kw):
        if url.rstrip("/") == "https://www.e.com":
            return _dns_fail(url)
        return FetchResult(url=url, ok=True, status=200, final_url=url, body=HTML_OK,
                           headers={"content-type": "text/html"})

    monkeypatch.setattr(auditmod.fetchmod, "fetch", fake_fetch)
    monkeypatch.setattr(auditmod.fetchmod, "fetch_text", lambda url, **kw: None)

    run = auditmod.audit_account(Account(codigo="E", nombre="E", url="https://www.e.com"))
    assert run.estado != "inaccesible"
    swap = [h for h in run.hallazgos if "no resuelve por DNS" in h.detalle]
    assert len(swap) == 1 and "se usó https://e.com" in swap[0].detalle


def test_rf24_dns_no_resuelve_en_ambas_variantes_no_esconde_el_error(monkeypatch):
    monkeypatch.setattr(auditmod.fetchmod, "fetch", lambda url, **kw: _dns_fail(url))
    monkeypatch.setattr(auditmod.fetchmod, "fetch_text", lambda url, **kw: None)

    run = auditmod.audit_account(Account(codigo="E", nombre="E", url="https://e.com"))
    assert run.estado == "inaccesible" and run.motivo == "el DNS no resuelve"
    assert not any("no resuelve por DNS; se usó" in h.detalle for h in run.hallazgos)


def test_rf24_bloqueado_no_reintenta(monkeypatch):
    llamadas = []

    def fake_fetch(url, **kw):
        llamadas.append(url)
        return FetchResult(url=url, ok=True, status=403, final_url=url, body="",
                           estado="bloqueado", motivo="403 al UA propio")

    monkeypatch.setattr(auditmod.fetchmod, "fetch", fake_fetch)
    monkeypatch.setattr(auditmod.fetchmod, "fetch_text", lambda url, **kw: None)

    auditmod.audit_account(Account(codigo="E", nombre="E", url="https://e.com"))
    assert llamadas.count("https://e.com") == 1   # sin segundo intento
