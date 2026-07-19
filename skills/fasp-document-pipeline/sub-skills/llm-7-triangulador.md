# LLM-7 — Triangulador asistido norma-red-campo

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-7 |
| Nombre | Triangulador asistido norma-red-campo |
| Etapa | 3 — Triangulación + Recomendaciones |
| Producto | Coincidencias/divergencias + diagnóstico de riesgos de coordinación |
| Checkpoint | Coordinación de evaluación |

## Entradas

- Matriz de congruencia normativa (Anexo 2 — Producto 1).
- Resultados ARS (Anexo 4, 5, 6 — Producto 2).
- Resúmenes de entrevistas (campo).

## Tareas

1. **Comparar red formal (normativa) vs red real (operativa/ARS)**:
   - ¿La red normativa predice la red real? ¿Dónde coinciden? ¿Dónde divergen?
2. **Proponer hipótesis de riesgos de coordinación**:
   - Fallas estructurales.
   - Cuellos de botella.
   - Nodos críticos.
3. **Agrupar hallazgos en categorías temáticas**:
   - Normativos.
   - Organizacionales.
   - Capacidades.
   - Canales de comunicación.

## Salida

- Borrador del Anexo 9 (Propuesta de modificación normativa).
- Listado priorizado de riesgos para alimentar LLM-8.

## Prompt sugerido

```text
Eres un asistente especializado en triangulación metodológica (norma-red-campo)
para evaluaciones del FASP.

Recibes:
1. La matriz de congruencia normativa (Anexo 2): qué dice la norma sobre qué actor
   hace qué.
2. La red real medida por ARS (Anexos 4-6): qué actores realmente se coordinan.
3. Resúmenes de entrevistas: la voz de los actores.

Tu tarea: producir un análisis de triangulación que contenga:

1. **Coincidencias norma-real**: actores que la norma predice que se coordinan y
   que efectivamente se coordinan según ARS.
2. **Divergencias norma-real**: actores que la norma NO predice que se coordinen
   pero que en ARS sí aparecen vinculados (coordinación informal), o viceversa
   (actores que la norma obliga pero que en la práctica no coordinan).
3. **Hipótesis de riesgos de coordinación**: para cada divergencia significativa,
   formula una hipótesis sobre el riesgo institucional que representa.
4. **Agrupación temática**: clasifica cada hallazgo en una categoría:
   - "Normativo" (la norma es insuficiente o contradictoria).
   - "Organizacional" (la estructura institucional no facilita la coordinación).
   - "Capacidades" (falta formación, recursos o herramientas).
   - "Canales de comunicación" (los canales formales no se usan o son insuficientes).

Devuelve el resultado en formato Markdown con las 4 secciones.
```

## Validación

El listado priorizado se inserta en una tabla temporal `riesgos_coordinacion` (a crear en v1.1) que LLM-8 consume.