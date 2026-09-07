"""Índice de Visibilidad en Respuestas de IA — mide si una marca aparece cuando
un motor generativo responde, no si su sitio está preparado para ser leído.

Hermano del Índice GEO Técnico (`maria`), con rúbrica, panel y tiers propios.
Rúbrica congelada en `docs/decisiones/2026-09-06-rubrica-respuestas.md`.

Frontera del paquete, igual que en `maria`: este módulo y sus submódulos de
scoring (`match`, `score`, `parse`) **no tocan la red**. La adquisición vive en
`surfaces/` y `acquire`, y produce un artefacto (`Captura`) que el scoring lee.
"""
