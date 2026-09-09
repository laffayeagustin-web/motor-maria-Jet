# AGENTS.md — contexto permanente para agentes en jet-maria-motor

> Contexto que **no cambia entre tareas**. Para el flujo operativo del repo y las
> trampas del entorno, ver [`CLAUDE.md`](CLAUDE.md). Para los principios verificables,
> [`constitution.md`](constitution.md). Para el QUÉ y el POR QUÉ del motor,
> [`spec.md`](spec.md) y [`docs/plan.md`](docs/plan.md).

## Qué es MarIA

Consultoría de Growth Marketing / **GEO** (Generative Engine Optimization) de Agustín
Laffaye: posicionar marcas en las respuestas de los motores de IA (ChatGPT, Gemini,
AI Overviews, Perplexity, Copilot). El contexto de negocio del ecosistema completo
está en `~/docs/producto.md`; acá solo lo que necesita quien toca el motor.

Este repo es el **motor canónico**: dado un sitio o una industria, emite JSON con
puntaje, tier y evidencia citada. Dos índices distintos, que **no comparten rúbrica,
tiers ni panel**:

- **Índice de Visibilidad GEO Técnico** (`maria`, `maria-render`) — audita el *sitio*.
  Rúbrica D1–D6 sobre 95 + 5 bonus. Vertical piloto: aviación ejecutiva Argentina.
- **Índice de Visibilidad en Respuestas** (`maria-respuestas`) — mide la *respuesta*
  de Gemini con grounding: cuánto nombra y cita a las marcas del panel. Señales
  R1/R2/R3, serie diaria.

## Cliente ideal

C-levels, asistentes ejecutivos, family offices y directores de operaciones que
contratan chárter/aviación privada. El comprador del informe es técnico o tiene
quien lo asesore: **el informe se lee frente al CTO del prospecto**, y una sola
métrica mal medida destruye más valor que diez métricas ausentes (ver "Las tres
lecciones ya pagadas").

## Clasificación obligatoria por flujo operativo

Toda cuenta del panel se clasifica por su flujo de negocio, y la tabla comparativa
**nunca** mezcla flujos sin decirlo (RF-17):

| Flujo | Qué es |
|---|---|
| corporativo-industrial | vuelos de empresa, rutas fijas, contrato marco |
| turismo VIP | ocio, chárter puntual, clientela premium no recurrente |
| sanitario | ambulancia aérea, traslado de órganos, urgencia |

Comparar una empresa de ambulancia aérea con un bróker de turismo VIP por el mismo
puntaje es un error de lectura, no un ranking.

## Regla de argumentos y contraargumentos

Toda decisión de diseño se registra con **su alternativa descartada y por qué**
(`docs/plan.md` §4) y todo análisis lleva su sección **"En contra"** con los riesgos
reales, no un descargo formal (`docs/plan.md` §8). Si vas a proponer un cambio de
rúbrica, scoring o alcance: escribí primero el contraargumento más fuerte contra tu
propia propuesta. Si no lo tenés, no la propongas todavía.

## Las tres lecciones ya pagadas

Nacieron de errores reales del proyecto y están institucionalizadas en la rúbrica y
los tests. No las re-litigues:

1. **No confiar en fetch de solo-HTML para el `<head>`.** En la Fase 2 se publicó
   "0 de 7 con schema.org" cuando eran 4 de 7: el schema lo inyecta JavaScript. Por
   eso el doble fetch (crudo + DOM renderizado) y el reporte de la discrepancia
   cuando difieren (constitución, principio 2).
2. **Bloqueo de crawler ≠ ausencia de estructura.** Un 403/503 al cliente
   identificado es el estado `bloqueado` con hallazgo crítico, no un 0 de schema
   mezclado con las cuentas medidas (constitución, principio 4; RF-03).
3. **Un "cotizador" que no cotiza es un hallazgo de fricción, no de nomenclatura.**
   Si la página llama "cotizador" a un formulario sin precio en pantalla, eso baja
   D5 y se nombra en el informe como fricción de conversión.

## Cómo se referencian las decisiones

Por ruta relativa y número de sección: `§2 de docs/plan.md`, `enmienda §4 de
docs/decisiones/2026-09-01-rubrica.md`, `RR-19`, `principio 6`. No hay IDs tipo
`ADR-003`. Toda decisión de rúbrica/scoring está en `docs/decisiones/` con fecha y
un bloque *"Por qué está en la rúbrica y no en el código"*.
