"""T2b — helpers compartidos: jsonld y text dan el mismo resultado que el prototipo."""
from maria_common.jsonld import all_types, has_org_con_datos, parse_blocks
from maria_common.text import raw_text_content, text_sha256, words


def test_parse_blocks_recorre_graph():
    blob = '{"@graph":[{"@type":"Organization","name":"E"},{"@type":"WebSite"}]}'
    nodes, ok, total = parse_blocks([blob])
    assert (ok, total) == (1, 1)
    assert all_types(nodes) == {"Organization", "WebSite"}


def test_parse_blocks_cuenta_ilegibles():
    nodes, ok, total = parse_blocks(['{"@type":"Organization"}', "no-json", ""])
    assert (ok, total) == (1, 2)


def test_has_org_con_datos():
    con, _, _ = parse_blocks(['{"@type":"Organization","name":"E SA"}'])
    sin, _, _ = parse_blocks(['{"@type":"WebPage"}'])
    assert has_org_con_datos(con) is True
    assert has_org_con_datos(sin) is False


def test_words_simetria():
    assert words("uno dos tres") == 3
    assert words("") == 0


def test_raw_text_content_quita_script_y_conserva_oculto():
    html = '<body>visible <span style="display:none">oculto</span><script>x=1</script></body>'
    txt = raw_text_content(html)
    assert "visible" in txt and "oculto" in txt and "x=1" not in txt


def test_text_sha256_estable():
    assert text_sha256("  a  b ") == text_sha256("a b")
