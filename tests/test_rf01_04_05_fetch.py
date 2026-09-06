"""RF-01 / RF-04 / RF-05 — fetch estático: UA propio, caché de 24 h.

Sin red: se parchea `httpx.Client.get`. El test de integración real contra
dominios de control va con `@pytest.mark.network`, fuera del CI base.
"""
import httpx
import pytest

from maria.fetch import static as fetchmod


class _FakeResp:
    def __init__(self, status=200, text="<html>ok</html>", url="https://e.com/"):
        self.status_code = status
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html"}
        self.history = []


def test_rf01_rf04_fetch_usa_ua_propio(monkeypatch, tmp_path):
    seen = {}

    def fake_get(self, url):
        seen["ua"] = self.headers.get("User-Agent")
        return _FakeResp()

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    r = fetchmod.fetch("https://e.com", cache_dir=tmp_path, no_cache=True)
    assert r.ok and r.status == 200
    assert seen["ua"] == fetchmod.UA_STRING


def test_rf05_segunda_llamada_sale_de_cache(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_get(self, url):
        calls["n"] += 1
        return _FakeResp(text=f"cuerpo-{calls['n']}")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    a = fetchmod.fetch("https://e.com/x", cache_dir=tmp_path)
    b = fetchmod.fetch("https://e.com/x", cache_dir=tmp_path)
    assert calls["n"] == 1
    assert b.from_cache is True and b.body == a.body


def test_rf05_no_cache_fuerza_red(monkeypatch, tmp_path):
    calls = {"n": 0}
    monkeypatch.setattr(httpx.Client, "get",
                        lambda self, url: (calls.__setitem__("n", calls["n"] + 1) or _FakeResp()))
    fetchmod.fetch("https://e.com/y", cache_dir=tmp_path)
    fetchmod.fetch("https://e.com/y", cache_dir=tmp_path, no_cache=True)
    assert calls["n"] == 2


def test_rf03_clasifica_tls_como_inaccesible(monkeypatch, tmp_path):
    def boom(self, url):
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] hostname mismatch")

    monkeypatch.setattr(httpx.Client, "get", boom)
    r = fetchmod.fetch("https://avionesprivadossa.com.ar", cache_dir=tmp_path, no_cache=True)
    assert r.ok is False and r.estado == "inaccesible"
    assert "TLS" in r.motivo


def test_rf03_403_es_bloqueado(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx.Client, "get", lambda self, url: _FakeResp(status=403))
    r = fetchmod.fetch("https://e.com", cache_dir=tmp_path, no_cache=True)
    assert r.estado == "bloqueado"
