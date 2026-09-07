#!/bin/bash
# Corrida diaria del Índice de Visibilidad en Respuestas de IA.
#
#   1. mide un panel contra Gemini con grounding (N repeticiones/frase),
#   2. archiva un run por marca en out/runs-respuestas-<slug>/<CODIGO>/<ts>.json,
#   3. regenera la página pública correspondiente.
#
# Uso:  cron-respuestas.sh [panel.yaml]
#   sin argumento  -> panels/respuestas-es-aviacion.yaml  (página /indice-respuestas-ia/)
#   respuestas-ar-aviacion.yaml -> out/*-respuestas-ar/     (página /indice-respuestas-ia-ar/)
#
# El slug sale del nombre del panel: respuestas-<slug>-*.yaml. "es" es el panel
# histórico y conserva los directorios sin sufijo + la clave de build `respuestas`.
#
# Crontab sugerido — LEJOS del "* * * * *" del growth-bot y de la hora en punto.
# Una línea por panel, con minutos distintos:
#
#   17 4 * * *  /home/seoagus/jet-maria-motor/tools/cron-respuestas.sh >> /home/seoagus/jet-maria-motor/out/cron/respuestas-es.log 2>&1
#   41 4 * * *  /home/seoagus/jet-maria-motor/tools/cron-respuestas.sh /home/seoagus/jet-maria-motor/panels/respuestas-ar-aviacion.yaml >> /home/seoagus/jet-maria-motor/out/cron/respuestas-ar.log 2>&1
#
# NO instalar hasta que el panel esté aprobado y congelado en panels/ y se haya
# medido el costo real de una corrida contra el saldo de la cuenta (Fase 0, riesgo 4).
set -euo pipefail

REPO="/home/seoagus/jet-maria-motor"
PANEL="${1:-$REPO/panels/respuestas-es-aviacion.yaml}"

# slug: respuestas-<slug>-aviacion.yaml -> <slug>
base="$(basename "$PANEL")"
slug="$(echo "$base" | sed -E 's/^respuestas-([a-z]+)-.*/\1/')"

if [ "$slug" = "es" ]; then
    sufijo=""            # el panel histórico no lleva sufijo en los directorios
    build_key="respuestas"
else
    sufijo="-$slug"
    build_key="respuestas-$slug"
fi

LOCK="$REPO/out/cron/.respuestas$sufijo.lock"

cd "$REPO"
mkdir -p out/cron

# Un solo proceso a la vez por panel: si la corrida de ayer todavía está viva, salir.
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) otra corrida en curso ($slug), salgo"
    exit 0
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "$(date -u +%FT%TZ) --- inicio corrida respuestas ($PANEL)"
maria-respuestas panel "$PANEL" \
    --out-dir "out/runs-respuestas$sufijo" \
    --report-dir "out/report-respuestas$sufijo" \
    --crudo-dir "out/crudo-respuestas$sufijo"
echo "$(date -u +%FT%TZ) --- medición lista, regenero la página ($build_key)"
python tools/build_pages.py "$build_key"
echo "$(date -u +%FT%TZ) --- fin"
