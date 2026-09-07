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


def puntuar_marca(
    marca: Marca,
    capturas: list[Captura],
    *,
    superficie: str = "gemini",
    modelo: str = "gemini-2.5-flash",
    timestamp_utc: str | None = None,
) -> MarcaRun:
    """Puntúa una marca contra todas las capturas de una corrida."""
    r1 = SenalResult(id="R1", nombre=SENALES[0][1])
    r2 = SenalResult(id="R2", nombre=SENALES[1][1])
    r3 = SenalResult(id="R3", nombre=SENALES[2][1])

    con_busqueda = 0
    for cap in capturas:
        cuenta = cap.cuenta_para_el_denominador
        if cuenta:
            con_busqueda += 1

        # Una frase que no cuenta entra igual al informe, con puntos_max 0: se ve
        # que fue evaluada y por qué no puntuó.
        if not cuenta:
            motivo = [Evidencia(metodo="regla", detalle=cap.motivo or cap.estado)]
            for señal in (r1, r2, r3):
                señal.por_frase.append(
                    SubSenal(frase_id=cap.frase_id, puntos=0.0, puntos_max=0.0,
                             estado=cap.estado, evidencia=motivo)
                )
            continue

        variante, offset = buscar_mencion(cap.texto, marca)
        citas = buscar_citas(cap.fuentes, marca)

        # --- R1 · mención ---
        ev1 = [Evidencia(
            metodo="respuesta",
            detalle=(f"nombrada como {variante!r}" if variante else "no nombrada"),
        )]
        r1.por_frase.append(SubSenal(
            frase_id=cap.frase_id, puntos=PTS_MENCION if variante else 0.0,
            puntos_max=PTS_MENCION, estado=cap.estado, evidencia=ev1,
        ))

        # --- R2 · cita ---
        ev2 = [Evidencia(
            metodo="fuente",
            detalle=("citada: " + ", ".join(citas) if citas else "sin cita de dominio propio"),
        )]
        r2.por_frase.append(SubSenal(
            frase_id=cap.frase_id, puntos=PTS_CITA if citas else 0.0,
            puntos_max=PTS_CITA, estado=cap.estado, evidencia=ev2,
        ))

        # --- R3 · posición ---
        if variante and offset is not None:
            pos = posicion_relativa(cap.texto, offset)
            pts = puntos_posicion(pos)
            det = f"primera mención al {pos:.1%} del texto"
        else:
            pts, det = 0.0, "sin mención que ubicar"
        r3.por_frase.append(SubSenal(
            frase_id=cap.frase_id, puntos=pts, puntos_max=PTS_POSICION,
            estado=cap.estado, evidencia=[Evidencia(metodo="respuesta", detalle=det)],
        ))

    run = MarcaRun(
        cuenta=marca,
        superficie=superficie,
        modelo=modelo,
        estado="medida" if con_busqueda else "sin_cobertura",
        dimensiones=[r1, r2, r3],
        frases_con_busqueda=con_busqueda,
        frases_totales=len(capturas),
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
