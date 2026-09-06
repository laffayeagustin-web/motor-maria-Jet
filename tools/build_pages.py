#!/usr/bin/env python3
"""Genera la página del Índice GEO Técnico para un panel del motor Jet MarIA."""
import json, glob, html, os, sys, datetime

def esc(s):
    return html.escape(str(s), quote=True)

GRUPO_LABEL_AR = {
    "A": "Grupo A · prospecto AR",
    "B": "Grupo B · extranjero que capta demanda AR",
    "C": "Grupo C · referencia de mercado",
}
GRUPO_LABEL_ES = {
    "A": "Grupo A · operador/broker con base en España",
    "B": "Grupo B · extranjero que capta demanda española",
    "C": "Grupo C · referencia de mercado",
}

TIER_CLASS = {
    "Consolidado": "tier-consolidado",
    "Emergente": "tier-emergente",
    "Parcial": "tier-parcial",
    "Invisible": "tier-invisible",
}

STATUS_LABEL = {
    "static": ("verificado (HTML crudo)", "st-ok"),
    "robots": ("verificado (robots.txt)", "st-ok"),
    "unverified": ("sin verificar (falta render DOM)", "st-warn"),
    "medido": ("medido", "st-ok"),
    "bloqueado": ("bloqueado por el servidor", "st-bad"),
    "inaccesible": ("inaccesible", "st-bad"),
    "no_aplica": ("no aplica", "st-na"),
}

def score_color(pct):
    if pct >= 0.70: return "var(--g-green)"
    if pct >= 0.45: return "var(--g-yellow)"
    if pct >= 0.20: return "#F29900"
    return "var(--g-red)"


def build(cfg):
    reports = {}
    for f in glob.glob(os.path.join(cfg["report_dir"], "*.json")):
        d = json.load(open(f))
        reports[d["cuenta"]["codigo"]] = d

    GRUPO_LABEL = cfg["grupo_label"]

    ranked = sorted(
        [c for c, d in reports.items() if d["estado"] in ("medido", "unverified")],
        key=lambda c: -reports[c]["puntaje_total"],
    )
    out_rank = sorted(
        [c for c in reports if c not in ranked],
        key=lambda c: (reports[c]["estado"], c),
    )

    def dim_block(dim):
        rows = []
        for s in (dim.get("sub_criterios") or []):
            st_label, st_cls = STATUS_LABEL.get(s["status"], (s["status"], ""))
            pts, pe, pmax = s.get("puntos"), s.get("puntos_efectivos"), s.get("puntos_max")
            if pts is None:
                pts_txt = f'<span class="prov">{pe:g}</span> <span class="muted">/ {pmax:g} · prov.</span>'
            else:
                pts_txt = f'{pts:g} <span class="muted">/ {pmax:g}</span>'
            eviden = s.get("evidencia") or []
            if eviden:
                ev = "<br>".join(esc(e.get("detail") or "") for e in eviden)
            elif s.get("motivo"):
                ev = f'<em class="muted">{esc(s["motivo"])}</em>'
            else:
                ev = ""
            rows.append(
                f'<tr><td class="sub-id">{esc(s["id"])}</td>'
                f'<td class="sub-name">{esc(s["nombre"])}<span class="st {st_cls}">{esc(st_label)}</span></td>'
                f'<td class="sub-pts">{pts_txt}</td><td class="sub-ev">{ev}</td></tr>'
            )
        dp, dmax = dim.get("puntos"), dim.get("puntos_max")
        dpct = (dp / dmax) if (dp is not None and dmax) else 0
        return f"""<div class="dim">
      <div class="dim-head">
        <h4>{esc(dim['id'])} · {esc(dim['nombre'])}</h4>
        <span class="dim-score" style="color:{score_color(dpct)}">{(f'{dp:g}' if dp is not None else '—')} / {dmax:g}</span>
      </div>
      <div class="table-wrap"><table class="subs">
        <thead><tr><th>#</th><th>Sub-criterio</th><th>Puntos</th><th>Evidencia</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table></div>
    </div>"""

    def accordion(code, rank=None):
        d = reports[code]
        c = d["cuenta"]
        estado, total, tier = d.get("estado"), d.get("puntaje_total"), d.get("tier")
        st_label, st_cls = STATUS_LABEL.get(estado, (estado, ""))
        n_unv = len(d.get("unverified") or [])

        rank_badge = f'<span class="rank">#{rank}</span>' if rank else '<span class="rank rank-out">—</span>'
        if total is not None:
            pct = total / 100.0
            score_html = f'<span class="acc-score" style="color:{score_color(pct)}">{total:g}<small>/100</small></span>'
            bar = f'<span class="bar"><span class="bar-fill" style="width:{max(pct*100,2):.0f}%;background:{score_color(pct)}"></span></span>'
        else:
            score_html = '<span class="acc-score muted">s/d</span>'
            bar = '<span class="bar"></span>'
        tier_html = f'<span class="tier {TIER_CLASS.get(tier,"")}">{esc(tier)}</span>' if tier else ""

        body = []
        url = c.get("url")
        bits = [GRUPO_LABEL.get(c.get("grupo"), c.get("grupo") or "")]
        if c.get("flujo"):
            bits.append(f'flujo: {esc(c["flujo"])}')
        if url:
            bits.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(url.replace("https://",""))}</a>')
        body.append(f'<p class="acc-meta">{" · ".join(bits)}</p>')

        if estado not in ("medido", "unverified") and d.get("motivo"):
            body.append(f'<div class="st-box {st_cls}"><strong>{esc(st_label)}.</strong> {esc(d["motivo"])}</div>')

        for a in (d.get("anomalias") or []):
            body.append(f'<div class="st-box st-warn"><strong>Anomalía registrada.</strong> {esc(a)}</div>')

        if estado == "unverified" and n_unv:
            body.append(
                f'<p class="note">⚠️ {n_unv} sub-criterios quedaron <strong>sin verificar</strong>: la corrida fue '
                f'solo estática (sin DOM renderizado). Sus puntos figuran como <span class="prov">provisionales</span> '
                f'— mitad del máximo, por regla RF-02.</p>'
            )

        for dim in (d.get("dimensiones") or []):
            body.append(dim_block(dim))

        if c.get("no_aplica_motivo"):
            body.append(f'<p class="note">{esc(c["no_aplica_motivo"])}</p>')
        if d.get("timestamp_utc"):
            body.append(f'<p class="ts">Medición: {esc(d["timestamp_utc"])}</p>')

        return f"""<details class="acc">
      <summary><span class="acc-top">{rank_badge}
          <span class="acc-name"><strong>{esc(c['nombre'])}</strong> <span class="code">{esc(code)}</span></span>
          {tier_html}{score_html}<span class="chev" aria-hidden="true">›</span></span>{bar}
      </summary>
      <div class="acc-body">{''.join(body)}</div>
    </details>"""

    def trow(code, i):
        d = reports[code]; c = d["cuenta"]
        dims = {dd["id"]: dd.get("puntos") for dd in (d.get("dimensiones") or [])}
        g = lambda k: (f"{dims[k]:g}" if dims.get(k) is not None else "—")
        total = d["puntaje_total"]
        return (f'<tr><td>{i}</td><td class="tl"><strong>{esc(c["nombre"])}</strong> '
                f'<span class="code">{esc(code)}</span></td><td>{esc(c["grupo"])}</td>'
                f'<td>{g("D1")}</td><td>{g("D2")}</td><td>{g("D3")}</td><td>{g("D4")}</td>'
                f'<td>{g("D5")}</td><td>{g("D6")}</td>'
                f'<td class="tot" style="color:{score_color(total/100)}"><strong>{total:g}</strong></td>'
                f'<td><span class="tier {TIER_CLASS.get(d["tier"],"")}">{esc(d["tier"])}</span></td></tr>')

    scores = [reports[c]["puntaje_total"] for c in ranked]
    prom = sum(scores) / len(scores)
    total_unv = sum(len(reports[c].get("unverified") or []) for c in reports)
    n_total = len(reports)
    best = reports[ranked[0]]["cuenta"]["nombre"]

    rank_rows = "\n".join(trow(c, i + 1) for i, c in enumerate(ranked))
    acc_ranked = "\n".join(accordion(c, i + 1) for i, c in enumerate(ranked))
    acc_out = "\n".join(accordion(c) for c in out_rank)

    out_section = ""
    if out_rank:
        out_section = f"""
  <h2 class="sec">Fuera del ranking</h2>
  <p class="sec-note">{cfg['out_note']}</p>
  {acc_out}"""

    HTML = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(cfg['title'])} · marIA.ar</title>
<meta name="description" content="{esc(cfg['meta_desc'])}">
<meta name="robots" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;800&display=swap" rel="stylesheet">
<style>
:root {{
  --g-blue:#4285F4; --g-red:#EA4335; --g-yellow:#FBBC05; --g-green:#34A853;
  --g-dark:#202124; --g-gray:#F8F9FA; --white:#FFFFFF;
  --gradient-primary:linear-gradient(135deg,#4285F4 0%,#1A73E8 100%);
  --border:#E8EAED;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  font-family:'Poppins',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  background:linear-gradient(180deg,#fff 0%,var(--g-gray) 100%);
  color:var(--g-dark); margin:0; -webkit-font-smoothing:antialiased; line-height:1.6;
}}
a {{ color:var(--g-blue); }}
code {{ font-size:0.9em; background:rgba(0,0,0,0.04); padding:1px 5px; border-radius:5px; }}
.wrap {{ max-width:1040px; margin:0 auto; padding:0 16px; }}

.topbar {{
  position:sticky; top:0; z-index:50; background:rgba(255,255,255,0.9);
  backdrop-filter:blur(10px); border-bottom:1px solid rgba(232,234,237,0.6);
  box-shadow:0 2px 20px rgba(0,0,0,0.05);
}}
.topbar .wrap {{ display:flex; align-items:center; justify-content:space-between; height:64px; gap:10px; }}
.brand {{ font-weight:800; font-size:1.4rem; letter-spacing:-0.5px; color:var(--g-dark); text-decoration:none; white-space:nowrap; }}
.brand span {{ color:var(--g-blue); }}
.topbar .back {{ font-size:0.85rem; font-weight:600; text-decoration:none; text-align:right; }}

.switch {{ display:flex; gap:8px; margin:20px 0 0; flex-wrap:wrap; }}
.switch a {{
  font-size:0.82rem; font-weight:600; text-decoration:none; padding:7px 16px;
  border-radius:999px; border:1px solid var(--border); background:var(--white); color:#5F6368;
}}
.switch a.on {{ background:var(--gradient-primary); color:#fff; border-color:transparent; }}

.hero {{ padding:28px 0 24px; }}
.hero .eyebrow {{ text-transform:uppercase; letter-spacing:2px; font-size:0.78rem; font-weight:600; color:var(--g-blue); margin:0 0 12px; }}
.hero h1 {{ font-size:2rem; font-weight:800; letter-spacing:-1px; margin:0 0 14px; line-height:1.15; }}
.hero p {{ font-size:1.05rem; color:#5F6368; margin:0 0 8px; max-width:65ch; }}

.disclaimer {{
  background:#FFF8E1; border-left:6px solid var(--g-yellow); padding:18px 22px;
  border-radius:0 14px 14px 0; margin:24px 0; color:#614C00; font-size:0.98rem;
}}
.disclaimer strong {{ color:#B28900; }}

.stats {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin:24px 0 8px; }}
.stat {{ background:var(--white); border:1px solid var(--border); border-radius:16px; padding:18px; box-shadow:0 6px 18px rgba(0,0,0,0.04); }}
.stat b {{ display:block; font-size:1.7rem; font-weight:800; line-height:1; margin-bottom:6px; }}
.stat small {{ color:#5F6368; font-size:0.82rem; }}

h2.sec {{ font-size:1.4rem; font-weight:800; margin:44px 0 6px; }}
.sec-note {{ color:#5F6368; font-size:0.92rem; margin:0 0 18px; }}

.table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:14px; }}
table.rank {{ width:100%; border-collapse:collapse; background:var(--white); border:1px solid var(--border); border-radius:14px; overflow:hidden; font-size:0.86rem; min-width:640px; }}
table.rank th, table.rank td {{ padding:10px; text-align:center; border-bottom:1px solid var(--border); }}
table.rank th {{ background:var(--g-gray); font-weight:600; color:#5F6368; font-size:0.78rem; }}
table.rank td.tl {{ text-align:left; white-space:nowrap; }}
table.rank td.tot {{ font-size:1rem; }}
table.rank tr:last-child td {{ border-bottom:none; }}
.code {{ display:inline-block; font-size:0.68rem; font-weight:600; color:#5F6368; background:var(--g-gray); border:1px solid var(--border); padding:1px 6px; border-radius:6px; vertical-align:middle; }}

.tier {{ display:inline-block; font-size:0.72rem; font-weight:600; padding:3px 9px; border-radius:999px; white-space:nowrap; }}
.tier-consolidado {{ background:#E6F4EA; color:#137333; }}
.tier-emergente {{ background:#E8F0FE; color:#1A73E8; }}
.tier-parcial {{ background:#FEF7E0; color:#B06000; }}
.tier-invisible {{ background:#FCE8E6; color:#C5221F; }}

.acc {{ background:var(--white); border:1px solid var(--border); border-radius:16px; margin-bottom:12px; box-shadow:0 4px 14px rgba(0,0,0,0.04); overflow:hidden; }}
.acc[open] {{ box-shadow:0 8px 26px rgba(0,0,0,0.09); }}
.acc summary {{ list-style:none; cursor:pointer; padding:16px 18px; display:block; }}
.acc summary::-webkit-details-marker {{ display:none; }}
.acc-top {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.rank {{ font-weight:800; color:var(--g-blue); font-size:0.95rem; min-width:2.2em; }}
.rank-out {{ color:#9AA0A6; }}
.acc-name {{ flex:1 1 auto; min-width:140px; font-size:1rem; }}
.acc-score {{ font-weight:800; font-size:1.15rem; }}
.acc-score small {{ font-size:0.7rem; color:#9AA0A6; font-weight:600; }}
.chev {{ font-size:1.4rem; color:#9AA0A6; transition:transform 0.25s; line-height:1; }}
.acc[open] .chev {{ transform:rotate(90deg); }}
.bar {{ display:block; height:6px; background:var(--g-gray); border-radius:999px; margin-top:12px; overflow:hidden; }}
.bar-fill {{ display:block; height:100%; border-radius:999px; }}

.acc-body {{ padding:4px 18px 22px; border-top:1px solid var(--border); }}
.acc-meta {{ font-size:0.9rem; color:#5F6368; margin:14px 0; }}
.note {{ font-size:0.9rem; color:#5F6368; background:var(--g-gray); border-radius:10px; padding:10px 14px; margin:12px 0; }}
.prov {{ color:#B06000; font-weight:600; }}
.muted {{ color:#9AA0A6; }}
.ts {{ font-size:0.78rem; color:#9AA0A6; margin:16px 0 0; }}
.st-box {{ border-radius:10px; padding:12px 14px; font-size:0.9rem; margin:12px 0; }}
.st-box.st-bad {{ background:#FCE8E6; color:#C5221F; }}
.st-box.st-warn {{ background:#FEF7E0; color:#B06000; }}
.st-box.st-na {{ background:var(--g-gray); color:#5F6368; }}

.dim {{ margin:18px 0; }}
.dim-head {{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:8px; }}
.dim-head h4 {{ margin:0; font-size:0.98rem; font-weight:600; }}
.dim-score {{ font-weight:800; font-size:0.95rem; white-space:nowrap; }}
table.subs {{ width:100%; border-collapse:collapse; font-size:0.82rem; min-width:560px; background:var(--white); border:1px solid var(--border); border-radius:10px; overflow:hidden; }}
table.subs th {{ background:var(--g-gray); color:#5F6368; font-weight:600; font-size:0.75rem; padding:7px 9px; text-align:left; }}
table.subs td {{ padding:8px 9px; border-top:1px solid var(--border); vertical-align:top; }}
.sub-id {{ font-weight:600; color:#5F6368; white-space:nowrap; }}
.sub-pts {{ white-space:nowrap; font-weight:600; }}
.sub-ev {{ color:#5F6368; }}
.st {{ display:block; font-size:0.7rem; font-weight:600; margin-top:3px; }}
.st.st-ok {{ color:#137333; }}
.st.st-warn {{ color:#B06000; }}
.st.st-bad {{ color:#C5221F; }}
.st.st-na {{ color:#9AA0A6; }}

footer {{ padding:40px 0 60px; color:#5F6368; font-size:0.88rem; }}
footer a {{ font-weight:600; }}

@media (min-width:760px) {{
  .hero h1 {{ font-size:2.7rem; }}
  .stats {{ grid-template-columns:repeat(4,1fr); }}
  .wrap {{ padding:0 24px; }}
  .topbar .back {{ font-size:0.9rem; }}
}}
</style>
</head>
<body>
<div class="topbar"><div class="wrap">
  <a class="brand" href="https://maria.ar">mar<span>IA</span>.ar</a>
  <a class="back" href="https://maria.ar">&larr; volver a maria.ar</a>
</div></div>

<div class="wrap">
  <nav class="switch">
    <a href="/indice-GEO-tecnico/" class="{'on' if cfg['slug']=='ar' else ''}">🇦🇷 Panel Argentina</a>
    <a href="/indice-GEO-tecnico-es/" class="{'on' if cfg['slug']=='es' else ''}">🇪🇸 Panel España</a>
  </nav>

  <section class="hero">
    <p class="eyebrow">Motor Jet MarIA · corrida de prueba</p>
    <h1>{cfg['h1']}</h1>
    <p>Auditoría automática del <strong>Índice de Visibilidad IA</strong>: qué tan legible, accesible y confiable es cada sitio para los motores generativos (ChatGPT, Claude, Perplexity, Google AI). {n_total} cuentas evaluadas; {len(ranked)} entraron al ranking.</p>
    <p class="muted" style="font-size:0.9rem">Corrida del servidor <code>maria</code> · {cfg['fecha']} · rúbrica SDD rev. 4 (6 dimensiones sobre 100).</p>
  </section>

  <div class="disclaimer">
    <strong>Lectura provisional.</strong> Esta corrida fue <strong>solo estática</strong>: el motor leyó el HTML crudo servido y <code>robots.txt</code>, pero <strong>no</strong> hubo captura del DOM renderizado (fase <code>maria-render</code>). Por eso {total_unv} sub-criterios quedaron <strong>sin verificar</strong> y se puntúan a mitad de su máximo (regla RF-02). Los totales pueden subir o bajar cuando se corra el render.{cfg['disclaimer_extra']}
  </div>

  <div class="stats">
    <div class="stat"><b>{n_total}</b><small>cuentas en el panel</small></div>
    <div class="stat"><b style="color:var(--g-blue)">{prom:.0f}<small style="font-size:0.6rem">/100</small></b><small>promedio del ranking</small></div>
    <div class="stat"><b style="color:var(--g-green)">{max(scores):g}</b><small>máximo ({esc(best)})</small></div>
    <div class="stat"><b style="color:var(--g-red)">{total_unv}</b><small>sub-criterios sin verificar</small></div>
  </div>

  <h2 class="sec">Ranking</h2>
  <p class="sec-note">Puntaje total sobre 100 = suma de las 6 dimensiones (core 95 + D6 5). D1 Estructura semántica (25) · D2 Accesibilidad crawlers IA (20) · D3 Legibilidad sin JS (20) · D4 Divulgación y confianza (15) · D5 Captura de leads (15) · D6 Frontera MCP (5).</p>
  <div class="table-wrap"><table class="rank">
    <thead><tr><th>#</th><th class="tl">Cuenta</th><th>Gr.</th><th>D1</th><th>D2</th><th>D3</th><th>D4</th><th>D5</th><th>D6</th><th>/100</th><th>Tier</th></tr></thead>
    <tbody>{rank_rows}</tbody>
  </table></div>

  <h2 class="sec">Detalle por cuenta</h2>
  <p class="sec-note">Tocá cada cuenta para ver el desglose dimensión por dimensión, con la evidencia recogida y el estado de cada sub-criterio.</p>
  {acc_ranked}
{out_section}

  <footer>
    <p><strong>Metodología.</strong> Motor <code>Jet MarIA</code> — herramienta <code>maria</code> (fetch estático + robots.txt + 6 probes + scoring determinista + tiers). Rúbrica congelada en <code>docs/decisiones/2026-09-01-rubrica.md</code>. Los sub-criterios que dependen del DOM renderizado (JSON-LD post-JS, ratio de texto útil, formularios, <code>navigator.modelContext</code>) requieren la fase <code>maria-render</code> con navegador, no incluida en esta corrida.</p>
    <p>Generado el {datetime.date.today().isoformat()} · <a href="https://maria.ar">maria.ar</a></p>
  </footer>
</div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(cfg["out"]), exist_ok=True)
    open(cfg["out"], "w").write(HTML)
    print("wrote", cfg["out"], len(HTML), "bytes |", len(ranked), "ranked,", len(out_rank), "out")


PANELS = {
    "ar": dict(
        slug="ar",
        report_dir=os.path.expanduser("~/jet-maria-motor/out/report"),
        out=os.path.expanduser("~/public_html/indice-GEO-tecnico/index.html"),
        title="Índice GEO Técnico — Panel AR",
        h1="Índice GEO Técnico<br>Panel AR de aviación privada",
        meta_desc="Resultados de la prueba del motor Jet MarIA (auditoría GEO / visibilidad IA) sobre el panel de aviación privada argentina.",
        fecha="2026-09-06",
        grupo_label=GRUPO_LABEL_AR,
        disclaimer_extra=" Modena, Tenil y Aviones Privados no pudieron medirse por bloqueo o error de servidor.",
        out_note="No pudieron puntuarse: bloqueo del servidor, error técnico o sin sitio propio.",
    ),
    "es": dict(
        slug="es",
        report_dir=os.path.expanduser("~/jet-maria-motor/out/report-es"),
        out=os.path.expanduser("~/public_html/indice-GEO-tecnico-es/index.html"),
        title="Índice GEO Técnico — Panel ES",
        h1="Índice GEO Técnico<br>Panel ES de aviación ejecutiva",
        meta_desc="Resultados de la prueba del motor Jet MarIA (auditoría GEO / visibilidad IA) sobre el panel de aviación ejecutiva española y europea.",
        fecha="2026-09-06",
        grupo_label=GRUPO_LABEL_ES,
        disclaimer_extra=" Dos correcciones del analista sobre este panel: <strong>Gestair</strong> se mide en <code>www.gestair.com</code> porque el apex <code>gestair.com</code> no presenta certificado TLS válido, y <strong>Aerobroker</strong> se puntúa con la captura de las 20:06:58 UTC porque después el servidor pasó a rechazar la conexión desde la IP del auditor.",
        out_note="No pudo puntuarse: el servidor bloquea a los clientes que no son navegador.",
    ),
}

for key in (sys.argv[1:] or ["ar", "es"]):
    build(PANELS[key])
