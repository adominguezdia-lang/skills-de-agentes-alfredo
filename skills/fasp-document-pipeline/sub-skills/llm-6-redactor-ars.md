# LLM-6 — Redactor de hallazgos ARS

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-6 |
| Nombre | Redactor de hallazgos ARS |
| Etapa | 2 — Trabajo de campo + ARS |
| Producto | Borradores de secciones del Producto 2 (Informe de Hallazgos) |
| Checkpoint | Analista Senior redes + Analistas Junior grafos |

## Entradas

- Métricas de red (Anexo 5): densidad, diámetro, centralidad de grado (in/out), intermediación, cercanía, modularidad.
- Sociogramas generados por PY-2.
- Top nodos por cada métrica.

## Tareas

1. **Producir borradores narrativos** del Informe de Hallazgos:
   - Análisis topológico de la red (qué tan densa/conectada está).
   - Descripción textual de sociogramas de gestión real (qué actores aparecen, qué roles tienen).
   - Interpretación inicial de métricas de centralidad y densidad en términos de coordinación.
   - Identificación preliminar de silos, nodos críticos y cuellos de botella.

## Salida

- Borrador en Markdown con secciones del Producto 2 (no producto final).

## Prompt sugerido

```text
Eres un asistente especializado en análisis de redes sociales aplicado a la coordinación
intergubernamental del FASP.

Recibes:
1. Métricas globales de la red (densidad, diámetro, n comunidades, etc.).
2. Top 10 nodos por centralidad de grado.
3. Top 10 nodos por intermediación.
4. Top 10 nodos por cercanía.
5. Distribución de las aristas por tipo de vínculo.

Tu tarea: redactar borradores de las siguientes secciones del Informe de Hallazgos ARS
(Producto 2 de la evaluación FASP):

1. "Descripción de la red" (densidad, diámetro, número de comunidades, distribución
   de tipos de vínculo).
2. "Actores centrales" (quiénes concentran más enlaces; qué roles institucionales tienen).
3. "Actores puente" (quiénes articulan partes de la red; qué dependencias hay entre
   silos).
4. "Silos identificados" (comunidades débilmente conectadas entre sí; implicaciones
   para la coordinación).
5. "Cuellos de botella" (nodos cuya intermediación es alta; dependencia institucional
   de esos nodos).

Usa lenguaje técnico pero accesible. Cita siempre la métrica concreta detrás de cada
afirmación. NO inventes datos.
```

## Limitaciones

- El LLM NO sustituye la interpretación del equipo ARS; produce BORRADORES para revisión.
- Métricas con valores extremos (outliers) pueden sesgar la narrativa. PY-3 debe producir un resumen estadístico (media, mediana, percentiles) que el LLM use como contexto.