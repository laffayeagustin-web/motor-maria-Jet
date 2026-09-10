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

# Los tiers no se publican en las páginas del panel: solo puntaje /100 + desglose
# por dimensión (decisión 09-09-2026, docs/decisiones/2026-09-09-tiers-no-publicados.md).

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
        estado, total = d.get("estado"), d.get("puntaje_total")
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
          {score_html}<span class="chev" aria-hidden="true">›</span></span>{bar}
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
                f'<td class="tot" style="color:{score_color(total/100)}"><strong>{total:g}</strong></td></tr>')

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
    <a href="/indice-GEO-tecnico/" class="{'on' if cfg['slug']=='ar' else ''}">🇦🇷 GEO Técnico · AR</a>
    <a href="/indice-GEO-tecnico-es/" class="{'on' if cfg['slug']=='es' else ''}">🇪🇸 GEO Técnico · ES</a>
    <a href="/indice-respuestas-ia/">💬 Respuestas · ES</a>
    <a href="/indice-respuestas-ia-ar/">💬 Respuestas · AR</a>
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
    <thead><tr><th>#</th><th class="tl">Cuenta</th><th>Gr.</th><th>D1</th><th>D2</th><th>D3</th><th>D4</th><th>D5</th><th>D6</th><th>/100</th></tr></thead>
    <tbody>{rank_rows}</tbody>
  </table></div>

  <h2 class="sec">Detalle por cuenta</h2>
  <p class="sec-note">Tocá cada cuenta para ver el desglose dimensión por dimensión, con la evidencia recogida y el estado de cada sub-criterio.</p>
  {acc_ranked}
{out_section}

  <footer>
    <p><strong>Metodología.</strong> Motor <code>Jet MarIA</code> — herramienta <code>maria</code> (fetch estático + robots.txt + 6 probes + scoring determinista). Rúbrica congelada en <code>docs/decisiones/2026-09-01-rubrica.md</code>. Cada cuenta se puntúa contra esa rúbrica publicada, en la fecha indicada; el índice mide la legibilidad automática del sitio, no la calidad, la seguridad ni la operación de la empresa. Los sub-criterios que dependen del DOM renderizado (JSON-LD post-JS, ratio de texto útil, formularios, <code>navigator.modelContext</code>) requieren la fase <code>maria-render</code> con navegador, no incluida en esta corrida.</p>
    <p>Generado el {datetime.date.today().isoformat()} · <a href="https://maria.ar">maria.ar</a></p>
  </footer>
</div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(cfg["out"]), exist_ok=True)
    open(cfg["out"], "w").write(HTML)
    print("wrote", cfg["out"], len(HTML), "bytes |", len(ranked), "ranked,", len(out_rank), "out")


# ============================================================================ #
#  Índice de Visibilidad en Respuestas de IA  (tercer panel)
# ============================================================================ #

# Sin etiqueta de tier en la página pública (decisión 09-09-2026): puntaje /100 +
# desglose por señal. docs/decisiones/2026-09-09-tiers-no-publicados.md.


def _sparkline(serie, w=132, h=30):
    """SVG mínimo de la serie de puntajes. Los puntos sin cobertura se saltan."""
    pts = [(i, p["puntaje"]) for i, p in enumerate(serie) if p.get("puntaje") is not None]
    if len(pts) < 2:
        return '<span class="spark-na">serie corta</span>'
    xs = [i for i, _ in pts]
    ys = [v for _, v in pts]
    x0, x1 = min(xs), max(xs)
    lo, hi = 0.0, max(100.0, max(ys))
    def px(i): return (i - x0) / (x1 - x0) * (w - 4) + 2 if x1 > x0 else w / 2
    def py(v): return h - 2 - (v - lo) / (hi - lo) * (h - 4)
    d = " ".join(f"{'M' if k == 0 else 'L'}{px(i):.1f},{py(v):.1f}"
                 for k, (i, v) in enumerate(pts))
    last = pts[-1]
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'aria-hidden="true"><path d="{d}" fill="none" stroke="currentColor" '
            f'stroke-width="1.5"/><circle cx="{px(last[0]):.1f}" cy="{py(last[1]):.1f}" '
            f'r="2.4" fill="currentColor"/></svg>')


def _delta_badge(delta):
    """▲/▼ del puntaje total contra ayer. Gris si el movimiento está dentro del ruido."""
    if not delta or delta.get("total") is None:
        return '<span class="delta delta-none">—</span>'
    t = delta["total"]
    if abs(t) < 5:                       # rúbrica §7 bis: < ~5 pts no se comenta
        return f'<span class="delta delta-flat">±{abs(t):g}</span>'
    if t > 0:
        return f'<span class="delta delta-up">▲ {t:g}</span>'
    return f'<span class="delta delta-down">▼ {abs(t):g}</span>'


def build_respuestas(cfg):
    reports, frases_meta = {}, None
    for f in glob.glob(os.path.join(cfg["report_dir"], "*.json")):
        name = os.path.basename(f)
        if name == "frases.json":
            frases_meta = json.load(open(f))
            continue
        d = json.load(open(f))
        reports[d["cuenta"]["codigo"]] = d

    if not reports:
        print("build_respuestas: no hay informes en", cfg["report_dir"], "— nada que generar")
        return

    medidas = sorted(
        [c for c, d in reports.items() if d.get("puntaje_total") is not None],
        key=lambda c: -reports[c]["puntaje_total"],
    )
    sin_cob = sorted(c for c in reports if c not in medidas)

    modelo = next((reports[c].get("modelo") for c in reports), "gemini")
    medicion = (frases_meta or {}).get("medicion_utc") or next(
        (reports[c].get("timestamp_utc") for c in reports), "")
    cob_c = (frases_meta or {}).get("con_busqueda")
    cob_t = (frases_meta or {}).get("total")
    reps = (frases_meta or {}).get("repeticiones")

    def señal_tabla(dim):
        rows = []
        for s in dim.get("por_frase", []):
            ev = " · ".join(e["detalle"] for e in s.get("evidencia", []))
            rows.append(
                f'<tr><td class="sub-id">{esc(s["frase_id"])}</td>'
                f'<td class="sub-pts">{s["puntos"]:g}<span class="muted">/{s["puntos_max"]:g}</span></td>'
                f'<td class="sub-st">{esc(s["estado"])}</td>'
                f'<td class="sub-ev">{esc(ev)}</td></tr>'
            )
        return (f'<div class="dim"><div class="dim-head"><h4>{esc(dim["id"])} · '
                f'{esc(dim["nombre"])}</h4><span class="dim-score">{dim["puntos"]:g}'
                f'<span class="muted"> / {dim["puntos_max"]:g}</span></span></div>'
                f'<div class="table-wrap"><table class="subs"><thead><tr><th>frase</th>'
                f'<th>pts</th><th>estado</th><th>evidencia</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div></div>')

    def accordion(code, rank=None):
        d = reports[code]
        c = d["cuenta"]
        total = d.get("puntaje_total")
        mm = d.get("media_movil_7d")
        serie = d.get("serie") or []
        rank_badge = (f'<span class="rank">#{rank}</span>' if rank
                      else '<span class="rank rank-out">—</span>')
        if total is not None:
            pct = total / 100.0
            score_html = (f'<span class="acc-score" style="color:{score_color(pct)}">'
                          f'{total:g}<small>/100</small></span>')
            bar = (f'<span class="bar"><span class="bar-fill" style="width:'
                   f'{max(pct*100,2):.0f}%;background:{score_color(pct)}"></span></span>')
        else:
            score_html = '<span class="acc-score muted">s/cob.</span>'
            bar = '<span class="bar"></span>'

        body = []
        doms = ", ".join(c.get("dominios") or [])
        alias = ", ".join(c.get("alias") or [])
        meta = [f'dominios: {esc(doms)}' if doms else 'sin dominio declarado']
        if alias:
            meta.append(f'alias: {esc(alias)}')
        meta.append(f'cobertura {esc(d.get("cobertura","—"))}')
        body.append(f'<p class="acc-meta">{" · ".join(meta)}</p>')

        if total is None:
            body.append('<div class="st-box st-na"><strong>Sin cobertura.</strong> '
                        'Ninguna de las frases con búsqueda de esta corrida nombró ni '
                        'citó a la marca. No es un cero: no hay denominador para '
                        'normalizar.</div>')
        else:
            delta = d.get("delta") or {}
            linea = [f'Media móvil 7 días: <strong>{mm:g}</strong>' if mm is not None
                     else 'Media móvil 7 días: <span class="muted">aún sin serie</span>']
            if delta.get("total") is not None:
                linea.append(f'Δ vs. corrida anterior: {_delta_badge(delta)}')
            body.append(f'<p class="acc-serie">{_sparkline(serie)} '
                        f'<span>{" · ".join(linea)}</span></p>')
            if delta.get("total") is not None and abs(delta["total"]) < 5:
                body.append('<p class="note">El movimiento del día está dentro del '
                            'ruido medido del modelo (§7 bis de la rúbrica): no se '
                            'interpreta como causa.</p>')
            for dim in d.get("dimensiones", []):
                body.append(señal_tabla(dim))

        body.append(f'<p class="ts">Medición: {esc(d.get("timestamp_utc",""))} · '
                    f'superficie {esc(d.get("superficie","gemini"))} · modelo '
                    f'<code>{esc(d.get("modelo",""))}</code></p>')

        return f"""<details class="acc">
      <summary><span class="acc-top">{rank_badge}
          <span class="acc-name"><strong>{esc(c['nombre'])}</strong> <span class="code">{esc(code)}</span></span>
          {score_html}<span class="chev" aria-hidden="true">›</span></span>{bar}
      </summary>
      <div class="acc-body">{''.join(body)}</div>
    </details>"""

    def trow(code, i):
        d = reports[code]
        c = d["cuenta"]
        dims = {x["id"]: x["puntos"] for x in d.get("dimensiones", [])}
        g = lambda k: (f'{dims[k]:g}' if k in dims else "—")
        total = d["puntaje_total"]
        mm = d.get("media_movil_7d")
        return (f'<tr><td>{i}</td><td class="tl"><strong>{esc(c["nombre"])}</strong> '
                f'<span class="code">{esc(code)}</span></td>'
                f'<td>{g("R1")}</td><td>{g("R2")}</td><td>{g("R3")}</td>'
                f'<td class="tot" style="color:{score_color(total/100)}"><strong>{total:g}</strong></td>'
                f'<td>{f"{mm:g}" if mm is not None else "—"}</td>'
                f'<td>{_delta_badge(d.get("delta"))}</td>'
                f'<td>{esc(d.get("cobertura","—"))}</td></tr>')

    scores = [reports[c]["puntaje_total"] for c in medidas]
    prom = sum(scores) / len(scores) if scores else 0
    maximo = max(scores) if scores else 0
    best = reports[medidas[0]]["cuenta"]["nombre"] if medidas else "—"
    rank_rows = "\n".join(trow(c, i + 1) for i, c in enumerate(medidas))
    acc_medidas = "\n".join(accordion(c, i + 1) for i, c in enumerate(medidas))
    acc_sin = "\n".join(accordion(c) for c in sin_cob)

    frases_rows = ""
    for fr in (frases_meta or {}).get("frases", []):
        st_cls = {"con_busqueda": "st-ok", "sin_busqueda": "st-warn",
                  "error": "st-bad"}.get(fr["estado"], "")
        frases_rows += (
            f'<tr><td class="sub-id">{esc(fr["id"])}</td>'
            f'<td class="tl">{esc(fr["texto"])}</td>'
            f'<td>{esc(fr["tipo"])}</td>'
            f'<td><span class="st {st_cls}">{esc(fr["estado"])}</span></td>'
            f'<td>{fr.get("con_busqueda",0)}/{fr.get("repeticiones",0)}</td>'
            f'<td class="muted">{esc(fr.get("motivo") or "")}</td></tr>'
        )
    frases_section = ""
    if frases_rows:
        frases_section = f"""
  <h2 class="sec">Cobertura de la corrida — frase por frase</h2>
  <p class="sec-note">Una frase entra al puntaje solo si al menos una de sus {esc(str(reps or ''))} repeticiones disparó búsqueda web. Las que el modelo respondió de memoria (<code>sin_busqueda</code>) se informan y <strong>salen del denominador</strong>, no puntúan cero.</p>
  <div class="table-wrap"><table class="rank">
    <thead><tr><th>#</th><th class="tl">Frase</th><th>Tipo</th><th>Estado</th><th>Reps c/búsqueda</th><th>Motivo</th></tr></thead>
    <tbody>{frases_rows}</tbody>
  </table></div>"""

    sin_section = ""
    if sin_cob:
        sin_section = f"""
  <h2 class="sec">Sin cobertura en esta corrida</h2>
  <p class="sec-note">Ninguna frase con búsqueda las nombró ni las citó. Su ausencia es el dato — pero solo en las respuestas de Gemini con búsqueda, y solo para estas frases.</p>
  {acc_sin}"""

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
.topbar {{ position:sticky; top:0; z-index:50; background:rgba(255,255,255,0.9); backdrop-filter:blur(10px); border-bottom:1px solid rgba(232,234,237,0.6); box-shadow:0 2px 20px rgba(0,0,0,0.05); }}
.topbar .wrap {{ display:flex; align-items:center; justify-content:space-between; height:64px; gap:10px; }}
.brand {{ font-weight:800; font-size:1.4rem; letter-spacing:-0.5px; color:var(--g-dark); text-decoration:none; white-space:nowrap; }}
.brand span {{ color:var(--g-blue); }}
.topbar .back {{ font-size:0.85rem; font-weight:600; text-decoration:none; text-align:right; }}
.switch {{ display:flex; gap:8px; margin:20px 0 0; flex-wrap:wrap; }}
.switch a {{ font-size:0.82rem; font-weight:600; text-decoration:none; padding:7px 16px; border-radius:999px; border:1px solid var(--border); background:var(--white); color:#5F6368; }}
.switch a.on {{ background:var(--gradient-primary); color:#fff; border-color:transparent; }}
.hero {{ padding:28px 0 24px; }}
.hero .eyebrow {{ text-transform:uppercase; letter-spacing:2px; font-size:0.78rem; font-weight:600; color:var(--g-blue); margin:0 0 12px; }}
.hero h1 {{ font-size:2rem; font-weight:800; letter-spacing:-1px; margin:0 0 14px; line-height:1.15; }}
.hero p {{ font-size:1.05rem; color:#5F6368; margin:0 0 8px; max-width:65ch; }}
.disclaimer {{ background:#FFF8E1; border-left:6px solid var(--g-yellow); padding:18px 22px; border-radius:0 14px 14px 0; margin:24px 0; color:#614C00; font-size:0.96rem; }}
.disclaimer strong {{ color:#B28900; }}
.stats {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin:24px 0 8px; }}
.stat {{ background:var(--white); border:1px solid var(--border); border-radius:16px; padding:18px; box-shadow:0 6px 18px rgba(0,0,0,0.04); }}
.stat b {{ display:block; font-size:1.7rem; font-weight:800; line-height:1; margin-bottom:6px; }}
.stat small {{ color:#5F6368; font-size:0.82rem; }}
h2.sec {{ font-size:1.4rem; font-weight:800; margin:44px 0 6px; }}
.sec-note {{ color:#5F6368; font-size:0.92rem; margin:0 0 18px; }}
.table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:14px; }}
table.rank {{ width:100%; border-collapse:collapse; background:var(--white); border:1px solid var(--border); border-radius:14px; overflow:hidden; font-size:0.86rem; min-width:720px; }}
table.rank th, table.rank td {{ padding:10px; text-align:center; border-bottom:1px solid var(--border); }}
table.rank th {{ background:var(--g-gray); font-weight:600; color:#5F6368; font-size:0.78rem; }}
table.rank td.tl {{ text-align:left; }}
table.rank td.tot {{ font-size:1rem; }}
table.rank tr:last-child td {{ border-bottom:none; }}
.code {{ display:inline-block; font-size:0.68rem; font-weight:600; color:#5F6368; background:var(--g-gray); border:1px solid var(--border); padding:1px 6px; border-radius:6px; vertical-align:middle; }}
.delta {{ font-size:0.78rem; font-weight:700; white-space:nowrap; }}
.delta-up {{ color:#137333; }}
.delta-down {{ color:#C5221F; }}
.delta-flat, .delta-none {{ color:#9AA0A6; }}
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
.acc-meta {{ font-size:0.88rem; color:#5F6368; margin:14px 0; }}
.acc-serie {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; font-size:0.86rem; color:#5F6368; margin:14px 0; }}
.spark {{ width:132px; height:30px; color:var(--g-blue); flex:0 0 auto; }}
.spark-na {{ font-size:0.78rem; color:#9AA0A6; }}
.note {{ font-size:0.88rem; color:#5F6368; background:var(--g-gray); border-radius:10px; padding:10px 14px; margin:12px 0; }}
.muted {{ color:#9AA0A6; }}
.ts {{ font-size:0.78rem; color:#9AA0A6; margin:16px 0 0; }}
.st-box {{ border-radius:10px; padding:12px 14px; font-size:0.9rem; margin:12px 0; }}
.st-box.st-na {{ background:var(--g-gray); color:#5F6368; }}
.dim {{ margin:18px 0; }}
.dim-head {{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:8px; }}
.dim-head h4 {{ margin:0; font-size:0.98rem; font-weight:600; }}
.dim-score {{ font-weight:800; font-size:0.95rem; white-space:nowrap; }}
table.subs {{ width:100%; border-collapse:collapse; font-size:0.82rem; min-width:520px; background:var(--white); border:1px solid var(--border); border-radius:10px; overflow:hidden; }}
table.subs th {{ background:var(--g-gray); color:#5F6368; font-weight:600; font-size:0.75rem; padding:7px 9px; text-align:left; }}
table.subs td {{ padding:8px 9px; border-top:1px solid var(--border); vertical-align:top; }}
table.subs td.tl {{ }}
.sub-id {{ font-weight:600; color:#5F6368; white-space:nowrap; }}
.sub-pts {{ white-space:nowrap; font-weight:600; }}
.sub-ev {{ color:#5F6368; }}
.st {{ display:inline-block; font-size:0.7rem; font-weight:600; }}
.st.st-ok {{ color:#137333; }}
.st.st-warn {{ color:#B06000; }}
.st.st-bad {{ color:#C5221F; }}
footer {{ padding:40px 0 60px; color:#5F6368; font-size:0.88rem; }}
footer a {{ font-weight:600; }}
.cta {{ background:var(--gradient-primary); color:#fff; border-radius:18px; padding:24px 26px; margin:32px 0; }}
.cta h2 {{ margin:0 0 8px; font-size:1.3rem; }}
.cta p {{ margin:0 0 14px; opacity:0.95; font-size:0.95rem; max-width:60ch; }}
.cta a {{ display:inline-block; background:#fff; color:#1A73E8; font-weight:700; text-decoration:none; padding:10px 20px; border-radius:999px; font-size:0.9rem; }}
@media (min-width:760px) {{
  .hero h1 {{ font-size:2.7rem; }}
  .stats {{ grid-template-columns:repeat(4,1fr); }}
  .wrap {{ padding:0 24px; }}
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
    <a href="/indice-GEO-tecnico/">🇦🇷 GEO Técnico · AR</a>
    <a href="/indice-GEO-tecnico-es/">🇪🇸 GEO Técnico · ES</a>
    <a href="/indice-respuestas-ia/" class="{'on' if cfg['slug']=='respuestas' else ''}">💬 Respuestas · ES</a>
    <a href="/indice-respuestas-ia-ar/" class="{'on' if cfg['slug']=='respuestas-ar' else ''}">💬 Respuestas · AR</a>
  </nav>

  <section class="hero">
    <p class="eyebrow">Motor Jet MarIA · serie diaria</p>
    <h1>{cfg['h1']}</h1>
    <p>Para {esc(str(cob_t or '10'))} frases congeladas de <strong>{esc(cfg['industria'])}</strong>, este índice le pregunta a <strong>Gemini con búsqueda de Google</strong>, guarda la respuesta y sus citas, y puntúa la presencia de cada marca con tres señales: la nombra (R1), la cita como fuente (R2) y qué tan temprano la nombra (R3).</p>
    <p class="muted" style="font-size:0.9rem">Última corrida: {esc(medicion)} · modelo <code>{esc(modelo)}</code> · {esc(str(reps or '3'))} repeticiones por frase · rúbrica congelada en <code>docs/decisiones/2026-09-06-rubrica-respuestas.md</code>.</p>
  </section>

  <div class="disclaimer">
    <strong>Qué mide y qué no.</strong> Una marca ausente de estas respuestas <strong>no</strong> es una marca ausente de ChatGPT, Perplexity, Copilot ni de los AI Overviews de Google. Lo único que este índice puede afirmar es <em>"no aparece en las respuestas de Gemini con búsqueda para estas {esc(str(cob_t or '10'))} frases"</em>. El puntaje se normaliza sobre las frases que efectivamente dispararon búsqueda; se publica siempre junto a la <strong>cobertura</strong>. Con {esc(str(reps or '3'))} repeticiones por frase, un movimiento diario menor a ~5 puntos está dentro del ruido del modelo y no se interpreta.
  </div>

  <div class="stats">
    <div class="stat"><b>{len(reports)}</b><small>marcas en el panel</small></div>
    <div class="stat"><b style="color:var(--g-blue)">{f'{cob_c}/{cob_t}' if cob_c is not None else '—'}</b><small>cobertura del panel (frases con búsqueda)</small></div>
    <div class="stat"><b style="color:var(--g-green)">{maximo:g}</b><small>máximo ({esc(best)})</small></div>
    <div class="stat"><b>{prom:.0f}<small style="font-size:0.6rem">/100</small></b><small>promedio de las medidas</small></div>
  </div>

  <h2 class="sec">Ranking del día</h2>
  <p class="sec-note">R1 mención (0–40) · R2 cita con enlace al dominio propio (0–40) · R3 posición de la primera mención (0–20). Total sobre 100, normalizado a las frases con búsqueda. <strong>MM7</strong> = media móvil de 7 corridas. <strong>Δ</strong> = cambio contra la corrida anterior (gris si está dentro del ruido).</p>
  <div class="table-wrap"><table class="rank">
    <thead><tr><th>#</th><th class="tl">Marca</th><th>R1</th><th>R2</th><th>R3</th><th>/100</th><th>MM7</th><th>Δ</th><th>cobertura</th></tr></thead>
    <tbody>{rank_rows}</tbody>
  </table></div>

  <h2 class="sec">Detalle por marca</h2>
  <p class="sec-note">Tocá cada marca para ver la serie, la media móvil, el delta y el desglose señal por señal, frase por frase, con la evidencia recogida.</p>
  {acc_medidas}
{sin_section}
{frases_section}

  <div class="cta">
    <h2>¿Querés el informe de tu empresa?</h2>
    <p>Elegí tu industria y tu empresa. La herramienta propone tus competidores a partir de los dominios que Google cita de hecho, arma 10 frases y devuelve una corrida de medición. El seguimiento diario arranca solo si aprobás el panel.</p>
    <a href="/indice-respuestas-ia/solicitar/">Pedir un informe →</a>
  </div>

  <footer>
    <p><strong>Metodología.</strong> Motor <code>Jet MarIA</code> — herramienta <code>maria-respuestas</code>. Adquisición no determinista (Gemini <code>generateContent</code> + <code>google_search</code>, <code>temperature:0</code>) que guarda cada respuesta verbatim como evidencia; scoring determinista y sin red sobre esas capturas (dos corridas sobre la misma captura dan el mismo JSON). Competidores y frases congelados en <code>panels/respuestas-*.yaml</code>. La serie diaria se archiva en <code>out/runs-respuestas/&lt;marca&gt;/&lt;ts&gt;.json</code>. El índice mide la presencia de cada marca en las respuestas de Gemini para estas frases y en esta fecha, no la calidad, la seguridad ni la operación de ninguna empresa.</p>
    <p>Generado el {datetime.date.today().isoformat()} · <a href="https://maria.ar">maria.ar</a></p>
  </footer>
</div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(cfg["out"]), exist_ok=True)
    open(cfg["out"], "w").write(HTML)
    print("wrote", cfg["out"], len(HTML), "bytes |", len(medidas), "medidas,", len(sin_cob), "sin cobertura")


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

RESP_PANELS = {
    "respuestas": dict(
        slug="respuestas",
        report_dir=os.path.expanduser("~/jet-maria-motor/out/report-respuestas"),
        out=os.path.expanduser("~/public_html/indice-respuestas-ia/index.html"),
        title="Índice de Visibilidad en Respuestas de IA",
        h1="Índice de Visibilidad<br>en Respuestas de IA",
        meta_desc="Serie diaria: menciones y citas de cada marca de aviación ejecutiva ES en las respuestas de Gemini con búsqueda de Google.",
        industria="aviación ejecutiva (mercado España)",
    ),
    "respuestas-ar": dict(
        slug="respuestas-ar",
        report_dir=os.path.expanduser("~/jet-maria-motor/out/report-respuestas-ar"),
        out=os.path.expanduser("~/public_html/indice-respuestas-ia-ar/index.html"),
        title="Índice de Visibilidad en Respuestas de IA — Panel AR",
        h1="Índice de Visibilidad<br>en Respuestas de IA · AR",
        meta_desc="Serie: menciones y citas de cada marca de aviación privada argentina en las respuestas de Gemini con búsqueda de Google.",
        industria="aviación privada (mercado Argentina)",
    ),
}

def main(argv):
    for key in (argv or ["ar", "es", "respuestas", "respuestas-ar"]):
        if key in RESP_PANELS:
            build_respuestas(RESP_PANELS[key])
        else:
            build(PANELS[key])


if __name__ == "__main__":
    main(sys.argv[1:])
