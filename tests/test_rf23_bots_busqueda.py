"""RF-23 — hallazgo informativo aparte para bots de "fetch en vivo"/búsqueda
(OAI-SearchBot, ChatGPT-User, Claude-User, Perplexity-User), distinto del
puntaje de D2.1 (que es solo entrenamiento/índice: GPTBot/ClaudeBot/CCBot/
PerplexityBot/Google-Extended). Puramente informativo: no manda ningún
request nuevo, no suplanta a nadie, no cambia el puntaje de D2.1.
"""
from tests.conftest import make_ctx

from maria.probes import d2_access


def _informativos_busqueda(findings):
    return [f for f in findings if "bots de búsqueda/uso en vivo" in f.detalle]


def test_rf23_reporta_bloqueo_a_bots_de_busqueda():
    robots = "User-agent: ChatGPT-User\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    dim, findings = d2_access.run(make_ctx(robots_txt=robots))
    d21 = next(s for s in dim.sub_criterios if s.id == "D2.1")
    # D2.1 no se entera: ChatGPT-User no es uno de los 5 núcleo.
    assert d21.puntos == 8

    [f] = _informativos_busqueda(findings)
    assert f.severidad == "informativa"
    assert f.dimension == "D2"
    assert "ChatGPT-User" in f.detalle
    assert "bloquea bots de búsqueda/uso en vivo:" in f.detalle


def test_rf23_reporta_sin_bloqueo_a_bots_de_busqueda():
    robots = "User-agent: *\nDisallow:\n"
    dim, findings = d2_access.run(make_ctx(robots_txt=robots))

    [f] = _informativos_busqueda(findings)
    assert f.severidad == "informativa"
    assert "no bloquea bots de búsqueda/uso en vivo:" in f.detalle
    for bot in ("OAI-SearchBot", "ChatGPT-User", "Claude-User", "Perplexity-User"):
        assert bot in f.detalle


def test_rf23_no_cambia_puntaje_d21_cuando_bloquea_los_5_nucleo():
    # robots.txt bloquea los 5 núcleo de D2.1 Y a un bot de búsqueda/uso en vivo
    # a la vez — el finding nuevo no debe mover el puntaje de D2.1 ni pisar el
    # finding "alta" que ya existía para el bloqueo núcleo.
    robots = (
        "User-agent: GPTBot\nDisallow: /\n"
        "User-agent: ClaudeBot\nDisallow: /\n"
        "User-agent: CCBot\nDisallow: /\n"
        "User-agent: PerplexityBot\nDisallow: /\n"
        "User-agent: Google-Extended\nDisallow: /\n"
        "User-agent: Claude-User\nDisallow: /\n"
        "User-agent: *\nDisallow:\n"
    )
    dim, findings = d2_access.run(make_ctx(robots_txt=robots))
    d21 = next(s for s in dim.sub_criterios if s.id == "D2.1")
    assert d21.puntos == 0  # bloqueados los 5 núcleo → D2.1 sigue en 0, sin cambios

    alta = [f for f in findings if f.severidad == "alta" and "robots.txt bloquea crawlers de IA:" in f.detalle]
    assert len(alta) == 1
    assert "GPTBot" in alta[0].detalle

    [informativo] = _informativos_busqueda(findings)
    assert "Claude-User" in informativo.detalle
