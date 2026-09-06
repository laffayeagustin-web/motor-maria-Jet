#!/usr/bin/env python3
"""
geo_probe.py — Medicion tecnica de GEO (Generative Engine Optimization).

Mide, por URL, que porcion del contenido es accesible para crawlers de motores
generativos, que a diferencia de Googlebot NO ejecutan JavaScript.

--------------------------------------------------------------------------
METRICA CENTRAL — ratio de texto util (D3 de la rubrica Jet MarIA)

    ratio = palabras(HTML crudo) / palabras(DOM renderizado)

Ambos lados se miden CON EL MISMO CRITERIO, y esto no es un detalle:

  * los dos usan textContent, no innerText;
  * los dos incluyen el texto oculto por CSS;
  * a los dos se les quita script / style / noscript / template.

Por que importa: `innerText` devuelve solo texto VISIBLE, mientras que del
HTML crudo no se puede saber que esta oculto sin aplicar CSS. Comparar
crudo-con-oculto contra renderizado-sin-oculto infla el ratio y lo puede
llevar por encima de 1,0 — imposible si el ratio significara lo que dice.
Medido sobre americanjet.com.ar el 29-08-2026: la formula asimetrica daba
1,093 (PASA holgado) y la simetrica 0,482 (casi el piso). Misma pagina,
conclusiones opuestas, 8 puntos de diferencia.

El criterio correcto es incluir el texto oculto de los dos lados: los
crawlers de IA parsean el HTML servido sin aplicar CSS, asi que ese texto
si les llega.

Un ratio > 1,0 NO es un puntaje alto: es una anomalia. Se reporta como tal.
--------------------------------------------------------------------------

Uso:
    python geo_probe.py https://ejemplo.com https://ejemplo.com/otra
    python geo_probe.py --urls-file urls.txt --out resultados.json
    python geo_probe.py https://ejemplo.com --cdp ws://127.0.0.1:9223/jet-maria
"""
import argparse, asyncio, json, os, re, time
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin

import httpx
from selectolax.lexbor import LexborHTMLParser
from playwright.async_api import async_playwright

# Crawlers de motores generativos. Ninguno ejecuta JS (a mayo 2026).
AI_CRAWLERS = {
    "GPTBot":            "OpenAI - entrenamiento",
    "OAI-SearchBot":     "OpenAI - indice de ChatGPT Search",
    "ChatGPT-User":      "OpenAI - fetch en vivo por pedido del usuario",
    "ClaudeBot":         "Anthropic - entrenamiento",
    "Claude-User":       "Anthropic - fetch en vivo",
    "PerplexityBot":     "Perplexity - indice",
    "Perplexity-User":   "Perplexity - fetch en vivo",
    "Google-Extended":   "Google - permiso de Gemini/AI Overviews",
    "CCBot":             "Common Crawl - alimenta a casi todos",
    "Bytespider":        "ByteDance/Doubao",
    "Applebot-Extended": "Apple Intelligence",
}
# Principio 6 de la constitucion: user-agent identificable, sin evasion de
# anti-bot. NO se suplanta a GPTBot ni a ningun otro crawler: la politica
# declarada para cada crawler se lee de robots.txt (dato publico), y la
# respuesta real del servidor se mide con este UA propio y honesto.
UA_STRING = "MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)"

STRIP_TAGS = ["script", "style", "noscript", "template"]
WORD_RE = re.compile(r"[^\W_][\w'’-]*", re.UNICODE)

# Umbrales de D3 segun la rubrica: 8 pts, escalado lineal de 0,40 a 0,80.
D3_MIN, D3_MAX, D3_PTS = 0.40, 0.80, 8

# Un ratio levemente > 1 es normal: el cliente sin cookies recibe marcado que el
# navegador no muestra (banners de consentimiento, sobre todo). Medido sobre el
# panel AR el 29-08-2026: 5 de 10 cuentas entre 1,003 y 1,076. Solo se informa
# por encima de este umbral. PENDIENTE DE CONFIRMAR en la sesion SDD.
ANOMALIA_RATIO = 1.10

# Content Signals (Cloudflare). Decision de rubrica: una senal explicita en "no"
# para ai-train o ai-input CUENTA COMO BLOQUEO — la politica declarada del sitio
# es parte de lo que se audita. La AUSENCIA de senal es neutra, tal como establece
# la clausula (c) del propio texto: no concede ni restringe.
CONTENT_SIGNAL_RE = re.compile(r"content-signal\s*:\s*(.+)", re.I)
SIGNAL_PAIR_RE = re.compile(r"([a-z-]+)\s*=\s*(yes|no)", re.I)
SENALES_QUE_BLOQUEAN = ("ai-train", "ai-input")

# Estados posibles de una cuenta en una corrida.
#   medido      - se obtuvo crudo y render, el puntaje es real
#   bloqueado   - el servidor rechazo al cliente identificado (403/503) -> D2 = 0, critico
#   inaccesible - no se pudo obtener el recurso (TLS roto, bucle de redirects, DNS)
#   unverified  - se obtuvo el crudo pero no el render; los sub-criterios que
#                 dependen del DOM van a mitad de puntaje (principio 4)
#   no_aplica   - la cuenta no tiene sitio web. NO lo determina el probe: es una
#                 anotacion del panel (caso Baires Fly). Se documenta aca para que
#                 el enum del contrato JSON este completo.
ESTADOS = ("medido", "bloqueado", "inaccesible", "unverified", "no_aplica")

# T7 — captura de fixtures. Cuando esta activa, cada cuenta deja en disco los tres
# artefactos que pide el plan (HTML crudo + DOM renderizado + robots.txt) con su
# fecha, para que la suite base pueda correr sin tocar la red (principio 5).
DUMP_DIR = None

# Extrae el textContent del <body> con el mismo criterio que selectolax:
# clona para no mutar la pagina, quita los mismos tags, conserva texto oculto.
JS_TEXT_CONTENT = """() => {
  const b = document.body ? document.body.cloneNode(true) : null;
  if (!b) return '';
  b.querySelectorAll('script,style,noscript,template').forEach(n => n.remove());
  return b.textContent || '';
}"""

JS_JSONLD = """() => Array.from(
  document.querySelectorAll('script[type="application/ld+json"]')
).map(s => s.textContent)"""


def words(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def raw_text_content(html: str) -> str:
    """textContent del body del HTML servido. Incluye texto oculto por CSS."""
    tree = LexborHTMLParser(html)
    tree.strip_tags(STRIP_TAGS)
    return tree.body.text(deep=True, separator=" ", strip=True) if tree.body else ""


def jsonld_types_from_blobs(blobs) -> list:
    """Tipos schema.org, recorriendo @graph y listas. '__parse_error__' si no parsea."""
    out = []
    for blob in blobs:
        if not blob or not blob.strip():
            continue
        try:
            data = json.loads(blob)
        except Exception:
            out.append("__parse_error__")
            continue

        def walk(node):
            if isinstance(node, list):
                for n in node:
                    walk(n)
            elif isinstance(node, dict):
                t = node.get("@type")
                if t:
                    out.extend(t if isinstance(t, list) else [t])
                if "@graph" in node:
                    walk(node["@graph"])
        walk(data)
    return sorted(set(out))


def jsonld_from_html(html: str) -> list:
    tree = LexborHTMLParser(html)
    blobs = [n.text(deep=True) for n in tree.css('script[type="application/ld+json"]')]
    return jsonld_types_from_blobs(blobs)


def guardar_fixture(url, raw_html, rendered_html, robots_txt, meta):
    """Vuelca los artefactos de una cuenta bajo DUMP_DIR/<dominio>/."""
    if not DUMP_DIR:
        return None
    u = urlparse(url)
    # dominio + slug del path: dos paginas del mismo host no se pisan (hara falta en D4)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (u.path or "/").strip("/")) or "home"
    dom = u.netloc.replace(":", "_")
    carpeta = os.path.join(DUMP_DIR, f"{dom}__{slug}")
    os.makedirs(carpeta, exist_ok=True)
    escritos = []
    for nombre, contenido in (("raw.html", raw_html),
                              ("rendered.html", rendered_html),
                              ("robots.txt", robots_txt)):
        if contenido is None:
            continue
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
            f.write(contenido)
        escritos.append(nombre)
    with open(os.path.join(carpeta, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return {"dominio": dom, "carpeta": carpeta, "archivos": escritos}


def score_d3_ratio(ratio):
    """8 pts si ratio >= 0,80; 0 si <= 0,40; lineal en el medio. None si no aplica."""
    if ratio is None:
        return None
    r = min(ratio, 1.0)          # un ratio > 1 no da puntaje extra
    if r >= D3_MAX:
        return D3_PTS
    if r <= D3_MIN:
        return 0.0
    return round(D3_PTS * (r - D3_MIN) / (D3_MAX - D3_MIN), 2)


def parse_content_signals(txt: str):
    """Lee las lineas 'content-signal:' de robots.txt, esten o no comentadas.

    Devuelve (senales, bloquea). `senales` es {uso: 'yes'|'no'}; `bloquea` es True
    solo si hay una senal EXPLICITA en 'no' para ai-train o ai-input. Un archivo
    con solo el preambulo de Cloudflare y ninguna senal devuelve ({}, False):
    no declara politica (clausula (c) del propio texto).
    """
    senales = {}
    for raw in txt.splitlines():
        line = raw.lstrip("# \t")
        m = CONTENT_SIGNAL_RE.search(line)
        if not m:
            continue
        for uso, val in SIGNAL_PAIR_RE.findall(m.group(1)):
            senales[uso.lower()] = val.lower()
    bloquea = any(senales.get(u) == "no" for u in SENALES_QUE_BLOQUEAN)
    return senales, bloquea


def parse_robots(txt: str):
    groups, current = {}, []
    for raw in txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            ua = value.lower()
            groups.setdefault(ua, {"allow": [], "disallow": []})
            current = [ua]
        elif field in ("allow", "disallow") and current:
            for ua in current:
                groups.setdefault(ua, {"allow": [], "disallow": []})[field].append(value)
    return groups


def crawler_verdict(groups, ua: str, path: str):
    g = groups.get(ua.lower()) or groups.get("*")
    source = ua if ua.lower() in groups else ("*" if "*" in groups else None)
    if not g:
        return {"allowed": True, "rule": None, "group": None}
    best = {"allowed": True, "rule": None}
    for kind in ("disallow", "allow"):
        for rule in g[kind]:
            if kind == "disallow" and rule == "":
                continue  # 'Disallow:' vacio = permitir todo
            if path.startswith(rule.rstrip("*")) and (best["rule"] is None or len(rule) > len(best["rule"])):
                best = {"allowed": kind == "allow", "rule": rule}
    return {**best, "group": source}


async def probe(url: str, browser, robots_cache: dict) -> dict:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    r = {"url": url, "errors": [], "anomalias": []}

    # --- 1. robots.txt y llms.txt (una vez por origen) ---
    if origin not in robots_cache:
        entry = {"robots": None, "llms_txt": False, "groups": {},
                 "signals": {}, "signals_block": False}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            try:
                resp = await c.get(urljoin(origin, "/robots.txt"), headers={"User-Agent": UA_STRING})
                if resp.status_code == 200 and "html" not in resp.headers.get("content-type", ""):
                    entry["robots"], entry["groups"] = resp.text, parse_robots(resp.text)
                    entry["signals"], entry["signals_block"] = parse_content_signals(resp.text)
            except Exception as e:
                entry["robots_error"] = str(e)
            try:
                # soft-404: muchos hosts devuelven 200 con HTML. Se exige no-HTML.
                resp = await c.get(urljoin(origin, "/llms.txt"), headers={"User-Agent": UA_STRING})
                body_head = resp.text[:400].lower()
                entry["llms_txt"] = (resp.status_code == 200
                                     and "html" not in resp.headers.get("content-type", "")
                                     and "<html" not in body_head)
            except Exception:
                pass
        robots_cache[origin] = entry
    rc = robots_cache[origin]
    r["llms_txt"] = rc["llms_txt"]
    r["robots_txt_present"] = rc["robots"] is not None
    r["content_signals"] = rc["signals"]
    r["content_signals_bloquean"] = rc["signals_block"]
    if rc["signals_block"]:
        r["hallazgos"] = r.get("hallazgos", []) + [{
            "severidad": "alta", "dimension": "D2",
            "detalle": "Content Signals declara 'no' para " + ", ".join(
                u for u in SENALES_QUE_BLOQUEAN if rc["signals"].get(u) == "no")
            + ". Es una reserva expresa de derechos: cuenta como bloqueo."}]
    elif rc["robots"] and not rc["groups"] and not rc["signals"]:
        r["hallazgos"] = r.get("hallazgos", []) + [{
            "severidad": "informativa", "dimension": "D2",
            "detalle": "robots.txt presente pero sin ninguna directiva ni senal: "
                       "no declara politica (clausula (c) de Content Signals)."}]
    r["crawlers"] = {ua: {**crawler_verdict(rc["groups"], ua, path), "quien": desc}
                     for ua, desc in AI_CRAWLERS.items()}
    r["crawlers_bloqueados"] = sorted(ua for ua, v in r["crawlers"].items() if not v["allowed"])

    # --- 2. HTML crudo, como lo ve un crawler de IA (sin JS) ---
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        try:
            resp = await c.get(url, headers={"User-Agent": UA_STRING})
            raw_html = resp.text
            r["status"] = resp.status_code
            r["final_url"] = str(resp.url)
            r["ttfb_ms"] = round((time.perf_counter() - t0) * 1000)
            if resp.headers.get("x-robots-tag"):
                r["x_robots_tag"] = resp.headers["x-robots-tag"]
            if resp.status_code in (403, 503):
                r["estado"] = "bloqueado"
                r["hallazgos"] = r.get("hallazgos", []) + [{
                    "severidad": "critica", "dimension": "D2",
                    "detalle": f"El servidor respondio {resp.status_code} a un cliente "
                               "identificado y no-navegador. Acceso bloqueado, no falta de estructura."}]
        except Exception as e:
            msg = str(e)
            r["errors"].append(f"fetch crudo: {msg}")
            r["estado"] = "inaccesible"
            if "CERTIFICATE_VERIFY_FAILED" in msg or "SSL" in msg:
                motivo = "certificado TLS invalido para este dominio"
            elif "redirect" in msg.lower():
                motivo = "bucle de redirecciones para un cliente que no es navegador"
            else:
                motivo = "no se pudo obtener el recurso"
            r["motivo_inaccesible"] = motivo
            r["hallazgos"] = r.get("hallazgos", []) + [{
                "severidad": "critica", "dimension": "D2",
                "detalle": f"Recurso inalcanzable: {motivo}. Ningun crawler de IA "
                           "puede obtener la pagina. No es ausencia de estructura."}]
            return r

    r["raw_words"] = words(raw_text_content(raw_html))
    r["raw_jsonld"] = jsonld_from_html(raw_html)
    r["raw_title"] = bool(re.search(r"<title[^>]*>\s*\S", raw_html, re.I))
    r["raw_h1"] = bool(re.search(r"<h1[^>]*>\s*\S", raw_html, re.I))
    r["raw_meta_desc"] = bool(re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']\s*\S', raw_html, re.I))
    r["raw_canonical"] = bool(re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']\s*\S', raw_html, re.I))
    mr = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)', raw_html, re.I)
    r["meta_robots"] = mr.group(1) if mr else None

    # --- 3. DOM renderizado, mismo criterio de extraccion ---
    page = await browser.new_page()
    rendered_html = None
    try:
        # Decision de rubrica (01-09-2026): el DOM se lee con wait_until="networkidle".
        # El momento de captura es un PARAMETRO de la medicion, no un detalle: sobre
        # southjets.com leer el DOM antes de networkidle dio ratio 0,999 y leerlo
        # despues dio 0,460. Cambiar esto cambia el puntaje.
        await page.goto(url, wait_until="networkidle", timeout=45000)
        r["captura_dom"] = "networkidle"
        r["rendered_words"] = words(await page.evaluate(JS_TEXT_CONTENT))
        r["rendered_jsonld"] = jsonld_types_from_blobs(await page.evaluate(JS_JSONLD))
        if DUMP_DIR:
            rendered_html = await page.content()
    except Exception as e:
        r["errors"].append(f"render: {e}")
        r["rendered_words"] = None
    finally:
        await page.close()

    if DUMP_DIR:
        r["fixture"] = guardar_fixture(url, raw_html, rendered_html, rc["robots"], {
            "url": url, "final_url": r.get("final_url"), "status": r.get("status"),
            "capturado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_agent": UA_STRING, "captura_dom": r.get("captura_dom"),
            "playwright": "chromium"})

    # --- 4. Ratio simetrico ---
    if r.get("rendered_words"):
        ratio = r["raw_words"] / r["rendered_words"]
        r["ratio_texto_util"] = round(ratio, 3)
        r["d3_puntos_ratio"] = score_d3_ratio(ratio)
        r["palabras_solo_con_js"] = max(0, r["rendered_words"] - r["raw_words"])
        r["jsonld_solo_con_js"] = sorted(set(r["rendered_jsonld"]) - set(r["raw_jsonld"]))

        r.setdefault("estado", "medido")
        if ratio > ANOMALIA_RATIO:
            r["anomalias"].append(
                f"ratio {ratio:.3f} > {ANOMALIA_RATIO} — el HTML servido tiene bastante "
                "mas texto que el DOM renderizado. Revisar extraccion o contenido que "
                "el JS elimina.")
        if ratio >= D3_MAX:
            r["veredicto"] = "OK — el contenido esta en el HTML servido"
        elif ratio >= D3_MIN:
            r["veredicto"] = "ATENCION — porcion relevante del contenido depende de JS"
        else:
            r["veredicto"] = "CRITICO — la mayor parte del contenido es invisible para motores de IA"
    else:
        r["ratio_texto_util"] = None
        r["d3_puntos_ratio"] = None
        r["estado"] = r.get("estado", "unverified")
        r["veredicto"] = "unverified — sin render disponible"
    return r


async def main():
    global UA_STRING, DUMP_DIR
    ap = argparse.ArgumentParser(description="Medicion tecnica de GEO con Playwright")
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--urls-file", help="archivo con una URL por linea")
    ap.add_argument("--out", default="geo_resultados.json")
    ap.add_argument("--cdp", help="endpoint remoto de Playwright (ws://host:9223/token) o CDP")
    ap.add_argument("--concurrency", type=int, default=3,
                    help="peticiones concurrentes GLOBALES. Ojo: no serializa por dominio "
                         "(principio 6). Con una URL por dominio es equivalente; si agregas "
                         "varias paginas del mismo host, usa --concurrency 1.")
    ap.add_argument("--dump-fixtures", metavar="DIR",
                    help="T7: vuelca por cuenta raw.html + rendered.html + robots.txt + "
                         "meta.json bajo DIR, y escribe DIR/MANIFEST.json")
    ap.add_argument("--ua", default="MarIA-GEO-Audit/0.1 (+https://maria.ar/bot)",
                    help="user-agent propio. No lo pongas a suplantar un crawler ajeno.")
    args = ap.parse_args()

    UA_STRING = args.ua
    DUMP_DIR = args.dump_fixtures
    if DUMP_DIR:
        os.makedirs(DUMP_DIR, exist_ok=True)
    urls = list(args.urls)
    if args.urls_file:
        urls += [l.strip() for l in open(args.urls_file) if l.strip() and not l.startswith("#")]
    if not urls:
        ap.error("pasa al menos una URL")

    async with async_playwright() as p:
        if args.cdp and "/devtools/" in args.cdp:
            browser = await p.chromium.connect_over_cdp(args.cdp)
        elif args.cdp:
            browser = await p.chromium.connect(args.cdp)      # servidor Playwright remoto
        else:
            browser = await p.chromium.launch(args=["--no-sandbox"])

        robots_cache, sem = {}, asyncio.Semaphore(args.concurrency)

        async def guarded(u):
            async with sem:
                try:
                    return await probe(u, browser, robots_cache)
                except Exception as e:
                    return {"url": u, "errors": [f"fatal: {e}"], "anomalias": []}

        results = await asyncio.gather(*(guarded(u) for u in urls))
        await browser.close()

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if DUMP_DIR:
        manifest = {
            "capturado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_agent": UA_STRING, "captura_dom": "networkidle",
            "cuentas": [{"url": r["url"], "estado": r.get("estado"),
                         "fixture": r.get("fixture")} for r in results]}
        with open(os.path.join(DUMP_DIR, "MANIFEST.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        ok = sum(1 for r in results if r.get("fixture"))
        print(f"Fixtures -> {DUMP_DIR}  ({ok}/{len(results)} cuentas con artefactos)")

    print(f"\n{'URL':<46} {'crudo':>7} {'render':>7} {'ratio':>7} {'D3':>5}  veredicto")
    print("-" * 118)
    for r in results:
        if r.get("rendered_words") is None and r.get("errors"):
            print(f"{r['url'][:46]:<46} {'—':>7} {'—':>7} {'—':>7} {'—':>5}  "
                  f"[{r.get('estado','error')}] {r.get('motivo_inaccesible', r['errors'][0][:38])}")
            continue
        ratio, pts, est = r.get("ratio_texto_util"), r.get("d3_puntos_ratio"), r.get("estado","—")
        print(f"{r['url'][:46]:<46} {r.get('raw_words',0):>7} {r.get('rendered_words',0):>7} "
              f"{(f'{ratio:.3f}' if ratio is not None else '—'):>7} "
              f"{(f'{pts:g}/8' if pts is not None else '—'):>5}  [{est}] {r.get('veredicto','')}")
        for a in r.get("anomalias", []):
            print(f"{'':<46} {'':>28}  ⚠ {a}")
        if r.get("crawlers_bloqueados"):
            print(f"{'':<46} {'':>28}  ⚠ bloqueados en robots.txt: {', '.join(r['crawlers_bloqueados'])}")
        if r.get("jsonld_solo_con_js"):
            print(f"{'':<46} {'':>28}  ⚠ schema solo tras JS: {', '.join(r['jsonld_solo_con_js'])}")
    print(f"\nJSON completo -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
