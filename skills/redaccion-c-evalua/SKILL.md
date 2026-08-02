---
name: redaccion-c-evalua
description: "Editor estructural y de estilo para C-evalua. Aplica la guía de estilo de C-evalua a textos sueltos o documentos completos del ámbito de evaluaciones CONEVAL (MIR, POA, ROP, indicadores, informes de evaluación). Detecta automáticamente si la entrada es modo texto suelto o documento completo y reorganiza según la plantilla de C-evalua. Triggers: 'redactar como c-evalua', 'formato c-evalua', 'estilo evaluacion', 'aplicar guia de estilo', 'revisar redaccion', 'formatear documento evaluacion'. Distinct from academic-revision (que revisa manuscritos académicos para journals) and from evaluacion-mir (que solo evalúa MIRs)."
version: 1.0.0
author: Luna
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [evaluacion, estilo, redaccion, coneval, evaluacion-programas, institucional]
    related_skills: [academic-revision, evaluacion-mir, evaluacion-mir]
---

# Redacción C-evalua — Editor Estructural y de Estilo

Editor estructural y de estilo para **C-evalua** (Centro de Análisis de Programas y Evaluación de Proyectos, S.C.). Aplica las reglas de voz, redacción y formato a cualquier texto o documento del ámbito de evaluaciones CONEVAL.

## Cuándo usar

- Tienes un texto o documento de evaluación de programas públicos y quieres que siga el formato profesional de C-evalua.
- Necesitas convertir un borrador en un documento listo para entregar a una dependencia de gobierno.
- Quieres revisar un documento existente contra la guía de estilo de C-evalua.
- Generas un Producto FASP y quieres que la redacción sea profesional, no un borrador de corpus.

No usar para:
- Revisión de manuscritos académicos para journals → `academic-revision`.
- Evaluación técnica de una MIR → `evaluacion-mir`.

## Cómo invocar

```
redaccion-c-evalua <texto_o_archivo>
```

O en conversación: *"Aplica el estilo C-evalua a este texto"*.

## 1. Modos de operación

El editor detecta automáticamente el modo:

| Modo | Detección | Qué hace |
|---|---|---|
| **Texto suelto** | Entrada < 500 palabras, sin encabezados | Devuelve el fragmento corregido y envuelto en el patrón de bullet (sección 4). |
| **Documento completo** | Entrada ≥ 500 palabras o con encabezados | Devuelve el documento completo reorganizado según la plantilla (sección 3). |

## 2. Plantilla de salida — Modo documento completo

Reorganiza el documento en este orden, migrando cada fragmento original a la sección que corresponde (sin perder ningún dato, cifra o hallazgo):

1. **Tabla de identificación del programa** (si hay datos para reconstruirarla): nombre, entidad, población potencial/objetivo, presupuesto.
2. **Sobre la evaluación**: objetivo + metodología en 3-4 líneas.
3. **Principales hallazgos**: organizados por eje metodológico (Pertinencia, Coherencia, Eficiencia, etc.), bullets con patrón de sección 4.
4. **Cuerpo por tema (I, II, III…)**: cada tema abre con hallazgo principal (pirámide invertida), desarrolla evidencia, cierra con implicación.
5. **Conclusiones**: Fortalezas / Oportunidades / Debilidades / Amenazas, cada una rastreable a un hallazgo previo.
6. **Recomendaciones / ASM**: accionables, formato tabular (hallazgo | recomendación) cuando el contenido lo permita.
7. **Anexos**: tablas, fuentes, glosario de siglas.

Si no hay contenido para una sección, se **omite** — no se inventa nada.

## 3. Patrón fijo de bullet (hallazgos)

```
- **[Título de 2-5 palabras que resume el hallazgo].** [Explicación de 1-2 oraciones con la evidencia o el dato que lo sustenta].
```

Aplica a todo bullet de hallazgo, tanto en texto suelto como en documento completo.

## 4. Convenciones de voz

| Parámetro | Valor | Ejemplo |
|---|---|---|
| `voice_mode` | `impersonal` (default) | "Se identificó que...", "El análisis muestra..." |
| | `institutional_first_person` | "Concluimos que...", "Identificamos..." |

Si no se indica, usar `impersonal` y ser consistente en todo el documento. **No mezclar** ambas formas.

## 5. Convenciones lingüísticas

| Regla | Correcto | Incorrecto |
|---|---|---|
| Longitud de oración | ≤ 35 palabras | ≥ 3 subordinadas encadenadas |
| Primera persona individual | Nunca | "considero", "creo que" |
| Adjetivos sin evidencia | Nunca | "un programa excelente" |
| Absolutos sin dato | Nunca | "nunca se hizo", "siempre aplica" |
| Frases de relleno | Solo si introducen matiz nuevo | "cabe destacar que...", "es importante mencionar que" |
| Mezclar tiempos verbales | No | Cambiar de pasado a presente dentro de una sección |
| Repetir nombre de programa | Máximo 1 vez por sección | Cada oración empieza con el nombre completo |

## 6. Formato de cifras y datos

| Tipo | Formato | Ejemplo |
|---|---|---|
| Montos en pesos | 2 decimales, separador de miles con coma | `$12,835,688.07` |
| Personas/población | Sin decimales | `124,893 personas` |
| Porcentajes | 1-2 decimales | `75.3%` |
| Años | Sin decimales | `2026` |

**Nunca alterar una cifra del original.**

## 7. Siglas y acrónimos

Primera mención: nombre completo + sigla entre paréntesis.

> Matriz de Indicadores para Resultados (MIR)

Menciones posteriores: solo la sigla.

> La MIR establece los indicadores...

## 8. Formato y tipografía

| Elemento | Formato |
|---|---|
| Negritas | Solo en título de bullet, encabezados de tabla, y cifras clave dentro de un párrafo (uso moderado) |
| Cursiva | Nombres de leyes en segunda mención, nombres de programas en segunda mención |
| Mayúsculas | Solo en títulos niveles 1 y 2; nombres de leyes, normas y programas van con mayúsculas inicial |
| Numeración de temas | Romana (I, II, III…) |
| Numeración de tablas/ilustraciones | Arábiga |
| Viñetas | Guion simple, sin anidar más de 1 nivel |

## 9. Restricciones (NO HACER)

- No resumir, no omitir, no inventar contenido.
- No usar primera persona individual.
- No adjetivar sin dato que lo sustente.
- No absolutos sin evidencia literal.
- No mezclar tiempos verbales dentro de una sección.
- No repetir el nombre completo del programa más de una vez por sección.

## 10. Checklist de revisión final

```
[ ] ¿Toda afirmación respeta el voice_mode indicado, sin mezclar formas?
[ ] ¿Ninguna oración supera ~35 palabras?
[ ] ¿Los bullets de hallazgos siguen el patrón "**Título.** Explicación"?
[ ] ¿Las siglas están definidas la primera vez que aparecen?
[ ] ¿Las negritas están completas (no fragmentadas)?
[ ] ¿Cada conclusión se rastrea a un hallazgo desarrollado antes?
[ ] ¿Las cifras conservan formato y valores originales?
[ ] ¿Se preservó el 100% del contenido informativo?
[ ] ¿La plantilla se respetó en modo documento completo?
```
