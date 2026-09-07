"""Scoring del Índice de Respuestas: capturas + panel → un `MarcaRun` por marca.

Determinista y sin red (RR-13): dos corridas sobre las mismas capturas producen
el mismo JSON byte por byte. Todo el no determinismo vive en la adquisición, que
ya dejó su artefacto.

Rúbrica congelada (`docs/decisiones/2026-09-06-rubrica-respuestas.md`):

| señal | qué mide | por frase |
|---|---|---|
| R1 | la marca es nombrada en la respuesta | 4,0 |
| R2 | un dominio propio es citado como fuente | 4,0 |
| R3 | qué tan temprano aparece la primera mención | 0–2,0 |

El puntaje se normaliza a 100 sobre las frases que dispararon búsqueda: una
frase `sin_busqueda` no puntúa cero, **sale del denominador**.
"""
from __future__ import annotations

from .contract import (
    Captura,
    Evidencia,
    Marca,
    MarcaRun,
    PanelRespuestas,
    SenalResult,
    SubSenal,
)
from .match import buscar_citas, buscar_mencion, posicion_relativa

PTS_MENCION = 4.0
PTS_CITA = 4.0
PTS_POSICION = 2.0

SENALES = [
    ("R1", "Mención de la marca en la respuesta"),
    ("R2", "Cita con enlace a un dominio propio"),
    ("R3", "Posición de la primera mención"),
]


def puntos_posicion(pos_rel: float) -> float:
    """Escala lineal: al principio del texto vale 2,0; al final, 0.

    Pendiente de confirmación empírica tras la primera semana de serie — así
    quedó anotado en la rúbrica.
    """
    return round(PTS_POSICION * (1.0 - pos_rel), 2)


def agrupar_por_frase(capturas: list[Captura]) -> "dict[str, list[Captura]]":
    """Agrupa repeticiones de la misma frase preservando el orden de aparición."""
    grupos: dict[str, list[Captura]] = {}
    for cap in capturas:
        grupos.setdefault(cap.frase_id, []).append(cap)
    return grupos


def puntuar_marca(
    marca: Marca,
    capturas: list[Captura],
    *,
    superficie: str = "gemini",
    modelo: str = "gemini-2.5-flash",
    timestamp_utc: str | None = None,
) -> MarcaRun:
    """Puntúa una marca contra las capturas de una corrida.

    Varias capturas con el mismo `frase_id` son **repeticiones** de esa frase y se
    agregan por frecuencia: una marca nombrada en 2 de 3 repeticiones puntúa dos
    tercios de R1. Con una sola repetición el resultado es el binario de siempre.

    La agregación existe porque medir una vez no alcanza: entre dos corridas de
    las mismas 10 frases solo reaparece el 60 % de las fuentes citadas
    (enmienda §7 de la rúbrica).
    """
    r1 = SenalResult(id="R1", nombre=SENALES[0][1])
    r2 = SenalResult(id="R2", nombre=SENALES[1][1])
    r3 = SenalResult(id="R3", nombre=SENALES[2][1])

    grupos = agrupar_por_frase(capturas)
    con_busqueda = 0

    for frase_id, reps in grupos.items():
        utiles = [c for c in reps if c.cuenta_para_el_denominador]

        # Una frase que no cuenta entra igual al informe, con puntos_max 0: se ve
        # que fue evaluada y por qué no puntuó.
        if not utiles:
            primera = reps[0]
            motivo = [Evidencia(metodo="regla", detalle=primera.motivo or primera.estado)]
            for señal in (r1, r2, r3):
                señal.por_frase.append(
                    SubSenal(frase_id=frase_id, puntos=0.0, puntos_max=0.0,
                             estado=primera.estado, evidencia=motivo)
                )
            continue

        con_busqueda += 1
        n = len(utiles)
        menciones = 0
        citadas = 0
        dominios: set[str] = set()
        pos_pts: list[float] = []
        variantes: set[str] = set()

        for cap in utiles:
            variante, offset = buscar_mencion(cap.texto, marca)
            citas = buscar_citas(cap.fuentes, marca)
            if variante:
                menciones += 1
                variantes.add(variante)
                pos_pts.append(puntos_posicion(posicion_relativa(cap.texto, offset or 0)))
            else:
                pos_pts.append(0.0)
            if citas:
                citadas += 1
                dominios.update(citas)

        frac_m = menciones / n
        frac_c = citadas / n
        sufijo = f" ({menciones}/{n} repeticiones)" if n > 1 else ""

        r1.por_frase.append(SubSenal(
            frase_id=frase_id, puntos=round(PTS_MENCION * frac_m, 2),
            puntos_max=PTS_MENCION, estado="con_busqueda",
            evidencia=[Evidencia(
                metodo="respuesta",
                detalle=(f"nombrada como {', '.join(sorted(variantes))}{sufijo}"
                         if menciones else f"no nombrada{sufijo}"),
            )],
        ))

        r2.por_frase.append(SubSenal(
            frase_id=frase_id, puntos=round(PTS_CITA * frac_c, 2),
            puntos_max=PTS_CITA, estado="con_busqueda",
            evidencia=[Evidencia(
                metodo="fuente",
                detalle=(f"citada: {', '.join(sorted(dominios))}"
                         f"{f' ({citadas}/{n} repeticiones)' if n > 1 else ''}"
                         if citadas else
                         f"sin cita de dominio propio"
                         f"{f' (0/{n} repeticiones)' if n > 1 else ''}"),
            )],
        ))

        media_pos = sum(pos_pts) / n
        r3.por_frase.append(SubSenal(
            frase_id=frase_id, puntos=round(media_pos, 2),
            puntos_max=PTS_POSICION, estado="con_busqueda",
            evidencia=[Evidencia(
                metodo="respuesta",
                detalle=(f"posición media de la primera mención sobre {n} "
                         f"repeticion{'es' if n > 1 else ''}"
                         if menciones else "sin mención que ubicar"),
            )],
        ))

    run = MarcaRun(
        cuenta=marca,
        superficie=superficie,
        modelo=modelo,
        estado="medida" if con_busqueda else "sin_cobertura",
        dimensiones=[r1, r2, r3],
        frases_con_busqueda=con_busqueda,
        frases_totales=len(grupos),
    )
    if timestamp_utc:
        run.timestamp_utc = timestamp_utc
    return run


def puntuar_panel(
    panel: PanelRespuestas,
    capturas: list[Captura],
    *,
    timestamp_utc: str | None = None,
) -> list[MarcaRun]:
    """Una corrida completa: todas las marcas contra las mismas capturas.

    El orden de salida es el ranking: puntaje descendente, y a igual puntaje por
    código, para que dos corridas idénticas produzcan la misma lista.
    """
    runs = [
        puntuar_marca(m, capturas, superficie=panel.superficie,
                      modelo=panel.modelo, timestamp_utc=timestamp_utc)
        for m in panel.marcas
    ]
    return sorted(runs, key=lambda r: (-(r.puntaje_total or -1.0), r.cuenta.codigo))
