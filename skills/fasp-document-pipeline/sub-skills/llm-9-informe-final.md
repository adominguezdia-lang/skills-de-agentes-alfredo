# LLM-9 — Redactor asistido del Informe Final

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-9 |
| Nombre | Redactor asistido del Informe Final |
| Etapa | 3 — Triangulación + Recomendaciones |
| Producto | Informe Final (Producto 3) + Glosario (Anexo 7) + Metodología (Anexo 8) |
| Checkpoint | Coordinadora + equipo de análisis |

## Entradas

- Diagnósticos normativos (Producto 1).
- Resultados ARS (Producto 2).
- Fichas validadas (LLM-8).
- Memorias algorítmicas y diccionarios (Anexos 5 y 6).

## Tareas

1. **Redactar el Informe Final** (Producto 3) con secciones:
   - Justificación metodológica global.
   - Síntesis analítica de la triangulación.
   - Diagnóstico de riesgos de coordinación.
   - Propuesta de reformas normativas.
   - Propuesta de rediseño de lógicas operativas.
   - Recomendaciones finales.
2. **Generar el Glosario especializado** (Anexo 7): términos del FASP, ARS, marco normativo.
3. **Elementos textuales de la Metodología para la replicabilidad** (Anexo 8): coherente con la Memoria algorítmica y el Diccionario de nodos.

## Salida

- `producto3_final.md` — Informe Final completo.
- `anexo7_glosario.md` — Glosario.
- `anexo8_metodologia.md` — texto narrativo de la metodología (complementa el Anexo 8 generado por PY-4).

## Prompt sugerido

```text
Eres un asistente especializado en redacción de informes finales de evaluación estratégica
del FASP.

Recibes:
1. La matriz de congruencia normativa (Anexo 2).
2. El Informe de Hallazgos ARS (Producto 2, borrador de LLM-6).
3. Las fichas de hallazgos y recomendaciones validadas (Anexo 10, salida de LLM-8).
4. La memoria algorítmica y diccionario de nodos (Anexos 5-6).
5. El listado priorizado de riesgos de coordinación (LLM-7).

Tu tarea: redactar el INFORME FINAL (Producto 3) con las siguientes secciones:

1. Resumen ejecutivo (≤ 1 página).
2. Justificación metodológica.
3. Síntesis analítica de la triangulación norma-red-campo.
4. Diagnóstico de riesgos de coordinación.
5. Propuesta de reformas normativas.
6. Propuesta de rediseño de lógicas operativas.
7. Recomendaciones finales (síntesis de las fichas del Anexo 10).
8. Anexos (referencias a Anexos 1-12).

Además, redacta:
- Anexo 7: Glosario especializado (términos del FASP, ARS, marco normativo).
- Anexo 8: Texto narrativo de la Metodología para la replicabilidad (complementa la
  memoria algorítmica del Anexo 5 con prosa explicativa).

Usa lenguaje técnico pero accesible. NO inventes datos; cada afirmación debe
referenciar explícitamente el anexo que la sustenta.
```

## Validación

- El Informe Final debe contener referencias a todos los anexos producidos (1-12).
- El Glosario debe incluir los términos introducidos por la evaluación.
- La Metodología debe ser coherente con el Anexo 5 (Memoria algorítmica).

## Limitaciones

- La longitud del Informe Final depende de los TdR; suele ser 80-150 páginas.
- El LLM puede producir borradores por sección; la integración final debe ser revisada por el equipo.