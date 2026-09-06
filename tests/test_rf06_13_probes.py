"""RF-06..RF-13 — cada probe contra HTML sintético.

Un RF por bloque; el nombre del test lo nombra (principio 10).
"""
from tests.conftest import make_ctx, make_render

from maria.probes import d1_schema, d2_access, d3_nojs, d4_trust, d5_leads, d6_frontier

ORG_LD = ('{"@type":"Organization","name":"Ejemplo SA","url":"https://e.com",'
          '"telephone":"+54 11 5555","address":{"@type":"PostalAddress","addressLocality":"BA"},'
          '"logo":"https://e.com/l.png","sameAs":["https://ig.com/e"],"aggregateRating":{"ratingValue":5}}')
OFFER_LD = '{"@type":"Service","name":"Charter"}'
BOILERPLATE_LD = '{"@type":"WebPage","name":"Home"}'


# ---- RF-06 / RF-13 · D1 ----

def test_rf06_d1_schema_completo_puntua_alto():
    r = make_render(ld_blocks=[ORG_LD, OFFER_LD], rendered_words=100)
    dim = d1_schema.run(make_ctx(render=r))
    assert dim.puntos >= 23


def test_rf13_d1_solo_boilerplate_se_topa_en_10():
    # schema que puntúa > 10 (Service + sameAs/logo/rating) pero sin Organization con datos
    ld = [
        BOILERPLATE_LD,
        '{"@type":"Service","name":"Charter"}',
        '{"@type":"Organization","logo":"l","sameAs":["x"],"aggregateRating":{"ratingValue":5}}',
    ]
    r = make_render(ld_blocks=ld, rendered_words=100)
    dim = d1_schema.run(make_ctx(render=r))
    assert dim.cap == 10
    assert dim.puntos <= 10
    assert dim.tope_aplicado is not None


def test_rf13_boilerplate_que_ya_puntua_bajo_no_necesita_tope():
    r = make_render(ld_blocks=[BOILERPLATE_LD], rendered_words=100)
    dim = d1_schema.run(make_ctx(render=r))
    assert dim.cap is None and dim.puntos <= 10


# ---- RF-07 · D2 ----

def test_rf07_d2_robots_abierto_puntua_pleno():
    robots = "User-agent: *\nDisallow:\nSitemap: https://e.com/sitemap.xml\n"
    dim, findings = d2_access.run(make_ctx(robots_txt=robots, sitemap_ok=True))
    assert dim.puntos == 20
    assert findings == []


def test_rf07_d2_robots_bloquea_gptbot():
    robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    dim, findings = d2_access.run(make_ctx(robots_txt=robots))
    d21 = next(s for s in dim.sub_criterios if s.id == "D2.1")
    assert d21.puntos == 0
    assert any("GPTBot" in f.detalle for f in findings)


def test_rf03_d2_bloqueado_es_hallazgo_critico():
    dim, findings = d2_access.run(make_ctx(estado_fetch="bloqueado", motivo_fetch="403 al UA propio"))
    d22 = next(s for s in dim.sub_criterios if s.id == "D2.2")
    assert d22.puntos == 0
    assert any(f.severidad == "critica" for f in findings)


def test_rf03_d2_content_signal_no_cuenta_como_bloqueo():
    robots = "# preambulo\ncontent-signal: ai-train=no, search=yes\nUser-agent: *\nDisallow:\n"
    dim, findings = d2_access.run(make_ctx(robots_txt=robots))
    d22 = next(s for s in dim.sub_criterios if s.id == "D2.2")
    assert d22.puntos == 0
    assert any("Content Signals" in f.detalle for f in findings)


def test_d2_robots_solo_preambulo_no_penaliza_pero_avisa():
    # caso Modena: preámbulo de Content Signals, cero directivas
    robots = "# Content Signals preamble bla bla\n# more text\n"
    dim, findings = d2_access.run(make_ctx(robots_txt=robots, status=200))
    d21 = next(s for s in dim.sub_criterios if s.id == "D2.1")
    assert d21.puntos == 8  # accesible, sin Disallow
    assert any("no declara política" in f.detalle for f in findings)


# ---- RF-08 · D3 ----

def test_rf08_d3_ratio_bajo_puntua_poco():
    r = make_render(rendered_words=1000)
    html = "<html><head><title>t</title></head><body>" + "palabra " * 100 + "</body></html>"
    dim, anomalias = d3_nojs.run(make_ctx(raw_html=html, render=r))
    d31 = next(s for s in dim.sub_criterios if s.id == "D3.1")
    assert d31.puntos < 2  # ratio ~0.1


def test_rf08_d3_ratio_alto_es_anomalia():
    r = make_render(rendered_words=10)
    html = "<html><body>" + "palabra " * 100 + "</body></html>"
    dim, anomalias = d3_nojs.run(make_ctx(raw_html=html, render=r))
    assert anomalias and "> 1.1" in anomalias[0]


# ---- RF-09 / RF-12 · D4 ----

def test_rf12_d4_sin_footer_es_unverified_no_cero():
    dim = d4_trust.run(make_ctx(render=None, footer_pages={}))
    d41 = next(s for s in dim.sub_criterios if s.id == "D4.1")
    assert d41.status == "unverified"


def test_rf09_d4_privacidad_encontrada_puntua():
    ctx = make_ctx(footer_pages={"https://e.com/politica-de-privacidad": 200})
    dim = d4_trust.run(ctx)
    d41 = next(s for s in dim.sub_criterios if s.id == "D4.1")
    assert d41.puntos == 4


# ---- RF-10 · D5 ----

def test_rf10_d5_compromiso_publicado_matchea_plazo_de_respuesta():
    html = "<body>Recibirás tu presupuesto en 15 minutos, 24/7</body>"
    dim = d5_leads.run(make_ctx(raw_html=html, render=make_render()))
    d54 = next(s for s in dim.sub_criterios if s.id == "D5.4")
    assert d54.puntos == 3


def test_rf10_d5_24_7_solo_no_cuenta():
    html = "<body>Disponibilidad 24/7 para vuelos sanitarios. Despegue en 2 horas.</body>"
    dim = d5_leads.run(make_ctx(raw_html=html, render=make_render()))
    d54 = next(s for s in dim.sub_criterios if s.id == "D5.4")
    assert d54.puntos == 0


def test_rf10_d5_forms_del_bundle_alimentan_d52():
    r = make_render(forms=[{"fields": 12, "required": 10}])
    dim = d5_leads.run(make_ctx(render=r))
    d52 = next(s for s in dim.sub_criterios if s.id == "D5.2")
    assert d52.puntos < 3  # 10 requeridos > 6


# ---- RF-11 · D6 ----

def test_rf11_d6_llms_txt_da_bonus():
    dim = d6_frontier.run(make_ctx(llms_txt_present=True, render=make_render()))
    d62 = next(s for s in dim.sub_criterios if s.id == "D6.2")
    assert d62.puntos == 2


def test_rf11_d6_model_context_cero_sin_tools():
    r = make_render(model_context={"present": True, "tools": 0})
    dim = d6_frontier.run(make_ctx(render=r))
    d61 = next(s for s in dim.sub_criterios if s.id == "D6.1")
    assert d61.puntos == 0
