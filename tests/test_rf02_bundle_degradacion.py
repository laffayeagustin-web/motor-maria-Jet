"""RF-02 / RF-12 — sin entry de bundle, los sub-criterios de render van a
`unverified` (mitad del máximo) y la corrida no rompe."""
from tests.conftest import make_ctx, make_render

from maria.probes import d1_schema, d3_nojs, d5_leads, d6_frontier


def test_rf02_d1_sin_render_marca_unverified():
    dim = d1_schema.run(make_ctx(render=None, raw_html='<html><body></body></html>'))
    unv = {s.id for s in dim.sub_criterios if s.status == "unverified"}
    assert unv == {"D1.2", "D1.3", "D1.4", "D1.5"}
    # mitad del máximo
    assert dim.sub_criterios[1].puntos_efectivos == 2.5


def test_d3_ratio_sin_render_es_unverified():
    dim, _ = d3_nojs.run(make_ctx(render=None))
    d31 = next(s for s in dim.sub_criterios if s.id == "D3.1")
    assert d31.status == "unverified"
    assert d31.puntos_efectivos == 4.0


def test_d5_forms_sin_render_unverified_pero_estaticos_no():
    dim = d5_leads.run(make_ctx(render=None, raw_html='<a href="tel:+5411">t</a>'))
    by_id = {s.id: s for s in dim.sub_criterios}
    assert by_id["D5.1"].status == "unverified"
    assert by_id["D5.3"].status == "static"  # tel: se ve en el HTML servido


def test_d6_modelcontext_sin_render_unverified():
    dim = d6_frontier.run(make_ctx(render=None))
    assert next(s for s in dim.sub_criterios if s.id == "D6.1").status == "unverified"


def test_con_render_no_hay_unverified_de_render():
    r = make_render(rendered_words=120, ld_blocks=['{"@type":"Organization","name":"E","url":"u"}'],
                    forms=[{"fields": 3, "required": 2}])
    dim = d1_schema.run(make_ctx(render=r))
    assert all(s.status != "unverified" for s in dim.sub_criterios)
