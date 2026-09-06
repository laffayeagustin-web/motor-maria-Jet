"""
PRUEBA DE HUMO sobre el panel completo — no es el motor real (T1-T20, ver PLAN-JET-MARIA-SDD.md).
Corre prueba_indice.run() contra las 14 cuentas de "Objetivos" (Paso Cero). Sin URL
conocida o sin sitio activo -> queda registrado como error, no se inventa nada.

Preflight: si el túnel de Chromium remoto (tools/remote-chromium-server/) está activo,
se resuelven también D1/D3/D5/D6 con render; si no, esos sub-criterios quedan
'unverified' (RF-02). Endpoint: env CHROMIUM_WS_ENDPOINT (default ws://127.0.0.1:9223/jet-maria).

Uso:
    # 1. en la notebook:  jet-maria/tools/remote-chromium-server/start.sh
    # 2. en el servidor:
    .venv/bin/python scratch/prueba_panel.py > scratch/prueba_panel.json
"""
import json
import sys
from datetime import datetime, timezone

import httpx

from prueba_indice import run, ws_endpoint


def check_tunnel():
    """Preflight: intenta conectar al Chromium remoto antes de arrancar el panel."""
    endpoint = ws_endpoint()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect(endpoint, timeout=5_000)
            browser.close()
        return True, endpoint, None
    except Exception as e:
        return False, endpoint, f"{type(e).__name__}: {str(e).splitlines()[0].strip()}"

PANEL = [
    ("Sundown Jet", "A", "https://sundownjet.com"),
    ("Royal Class", "A", "https://royalclass.com.ar"),
    ("Modena Air Service", "A", "https://modenaair.com"),
    ("Argentina Fly", "A", "https://argentina-fly.com"),
    ("Tenil Aviación", "A", "https://tenilaviacion.com.ar"),
    ("Baires Fly", "A", None),  # SIN SITIO PROPIO ACTIVO (DNS no resuelve) — dato del panel Objetivos
    ("Baires Global Jets", "A", "https://bairesglobaljets.com"),
    ("Aviones Privados S.A.", "A", "https://avionesprivadossa.com.ar"),
    ("South American Jets", "B", "https://southjets.com"),
    ("Flapper", "B", "https://flyflapper.com/es-ES"),
    ("Air Charter Service", "B", "https://aircharterservice.com.ar"),
    ("LunaJets", "B", "https://lunajets.com/es/"),
    ("American Jet", "C", "https://americanjet.com.ar"),
    ("Argentina Jets", "A", None),  # sin web registrada en Objetivos
]


def main():
    tunel_ok, endpoint, tunel_err = check_tunnel()
    if tunel_ok:
        print(f"TÚNEL OK  {endpoint} — se resuelven D1/D3/D5/D6 con render", file=sys.stderr)
    else:
        print(f"TÚNEL CAÍDO  {endpoint} — {tunel_err}", file=sys.stderr)
        print("             ~11 sub-criterios por cuenta quedarán 'unverified' (RF-02).", file=sys.stderr)
        print("             Levantalo con: jet-maria/tools/remote-chromium-server/start.sh", file=sys.stderr)
    print("", file=sys.stderr)

    resultados = []
    for nombre, grupo, url in PANEL:
        if url is None:
            resultados.append({
                "cuenta": nombre, "grupo": grupo, "url": None,
                "error": "sin URL conocida (no figura en la hoja Objetivos)",
            })
            print(f"SKIP  {nombre}: sin URL", file=sys.stderr)
            continue
        try:
            r = run(nombre, url, skip_render=not tunel_ok)
            r["grupo"] = grupo
            resultados.append(r)
            res = r["resumen"]
            render_tag = "render" if r["render"]["ok"] else "sin-render"
            print(
                f"OK    {nombre}: {res['puntos_obtenidos']}/{res['puntos_max_totales_de_la_rubrica']}"
                f" ({render_tag}, {res['sub_criterios_unverified']} unverified)",
                file=sys.stderr,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
            resultados.append({
                "cuenta": nombre, "grupo": grupo, "url": url,
                "error": f"{type(e).__name__}: {e}",
            })
            print(f"FAIL  {nombre}: {type(e).__name__}", file=sys.stderr)

    out = {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "tunel": {"ok": tunel_ok, "endpoint": endpoint, "motivo": tunel_err},
        "nota": "PRUEBA DE HUMO sobre el panel AR (14 cuentas de Objetivos/Paso Cero). No es el motor final.",
        "resultados": resultados,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
