---
name: fasp-document-pipeline
description: "Pipeline LLM–Python–ARS para la Evaluación Estratégica de Coordinación al FASP (Fondo de Aportaciones para la Seguridad Pública). Procesa 3 etapas secuenciales (análisis documental, trabajo de campo + ARS, triangulación + recomendaciones) con 9 módulos LLM (LLM-1 a LLM-9), 4 scripts Python (PY-1 a PY-4), y produce los 12 anexos TdR. Incluye BD SQLite para trazabilidad y sistema de checkpoints por perfil humano. Reutiliza pdf-to-knowledge-graph para la Etapa 1. Triggers: 'fasp', 'seguridad pública', 'matriz de congruencia', 'análisis de redes fasp', 'evaluación fasp', 'convenio fasp', 'triangulación norma-red-campo'. Distinct from pdf-to-knowledge-graph (que es solo extracción genérica sin taxonomía cerrada) and from biblio-metadata-extractor (que extrae solo metadata bibliográfica)."
version: 1.0.0
author: Alfredo Domínguez
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fasp, seguridad-publica, ars, redes, gobernanza, normativa, evaluacion]
    related_skills: [pdf-to-knowledge-graph, biblio-metadata-extractor, document-processing]
---

# FASP Document Pipeline

Orquestador LLM–Python–ARS para la Evaluación Estratégica de Coordinación al **FASP**. Procesa documentos normativos y trabajo de campo para producir los 3 productos TdR (Informe 1, Informe 2, Informe Final) con sus 12 anexos numerados.

## Cuándo usar

- Tienes un corpus de normas (federales/estatales/municipales), convenios FASP, manuales y lineamientos para una evaluación de coordinación del FASP.
- Necesitas construir una matriz de congruencia normativa con taxonomía cerrada (3 tipos de competencia × 3 niveles de obligatoriedad × 5 dimensiones del ciclo).
- Tienes transcripciones de entrevistas semiestructuradas y grupos de enfoque aplicadas a actores formales e informales en los 3 niveles de gobierno.
- Necesitas producir los 12 anexos TdR bajo supervisión de perfiles humanos específicos (Coordinadora, Analista Senior jurídico, Analista Senior redes, Analistas Junior grafos, Coordinación de evaluación).

No usar para:
- Solo extracción PDF→MD genérica → `pdf-to-knowledge-graph`.
- Solo metadata bibliográfica → `biblio-metadata-extractor`.
- Análisis de redes genérico sin contexto FASP → `pdf-to-knowledge-graph` (Etapa 3).

## Arquitectura de 3 etapas con 13 módulos

### Etapa 1 — Análisis documental (Producto 1)

| Módulo | Tipo | Insumos | Producto |
|---|---|---|---|
| **LLM-1** | Parser jurídico-documental | Normas fed/est/mun, convenios FASP, manuales, lineamientos | Tabla con `id_norma, nivel, jerarquía, artículo, tema, referencia a coordinación` |
| **LLM-2** | Constructor de matriz de congruencia | Salida LLM-1 | Matriz con taxonomía cerrada (competencia × obligatoriedad × dimensión ciclo) |
| **LLM-3** | Generador del directorio preliminar de actores | Normas clasificadas + convenios | Directorio: nombre oficial, nivel, naturaleza (formal/informal), funciones |
| **PY-1** | Estructuración de bases | Salidas LLM-1/2/3 | Asigna IDs únicos + Ficha técnica FASP (Anexo 1) |

**Anexos producidos:** 1 (Ficha técnica FASP), 2 (Matriz de congruencia), 3 (Directorio preliminar)
**Checkpoint humano:** Coordinadora + Analista Senior jurídico

### Etapa 2 — Trabajo de campo + ARS (Producto 2)

| Módulo | Tipo | Insumos | Producto |
|---|---|---|---|
| **LLM-4** | Extractor de relaciones y atributos | Transcripciones de entrevistas + grupos de enfoque | Edge list con origen/destino/tipo/peso/direccionalidad |
| **LLM-5** | Normalizador de nodos | Edge list preliminar + directorio | Nodos unificados (dedup semántica de siglas vs nombres completos) |
| **PY-2** | Constructor de matrices de red | Edge list validada + diccionario de nodos | Matriz de adyacencia (Actor-Actor) + Matriz de incidencia (Actor-Proceso) |
| **PY-3** | Cálculo de métricas | Matrices de PY-2 | Métricas ARS: centralidad de grado (in/out), intermediación, cercanía, densidad, modularidad, diámetro + Memoria algorítmica |
| **LLM-6** | Redactor de hallazgos ARS | Métricas + sociogramas | Borradores narrativos del Producto 2 |

**Anexos producidos:** 4 (Matriz de adyacencia), 5 (Memoria algorítmica), 6 (Diccionario de atributos)
**Checkpoint humano:** Analista Senior experto en redes + Analistas Junior de grafos

### Etapa 3 — Triangulación + Recomendaciones (Producto 3)

| Módulo | Tipo | Insumos | Producto |
|---|---|---|---|
| **LLM-7** | Triangulador norma-red-campo | Matriz Producto 1 + ARS Producto 2 + resúmenes entrevistas | Coincidencias/divergencias + diagnóstico de riesgos de coordinación |
| **LLM-8** | Generador de fichas de hallazgos | Listado priorizado de problemas | Fichas: `verbo + producto/proceso + oportunidad + justificación + efecto esperado` |
| **LLM-9** | Redactor del Informe Final | Diagnósticos + ARS + fichas validadas | Secciones narrativas del Producto 3 + Glosario + Metodología de replicabilidad |
| **PY-4** | Exportación y replicabilidad | Todo lo previo | Tablas + matrices + sociogramas en formatos abiertos |

**Anexos producidos:** 7 (Glosario), 8 (Metodología de replicabilidad), 9 (Propuesta modificación normativa), 10 (Hallazgos/recs/ASM), 11 (Ficha técnica administrativa), 12 (Fuentes)
**Checkpoint humano:** Coordinadora + equipo de análisis

## Taxonomías cerradas del dominio FASP

Estos vocabularios son **fijos** — la matriz de congruencia (Anexo 2) y la red ARS (Anexos 4-6) los usan como clases restringidas.

| Taxonomía | Valores |
|---|---|
| **5 etapas del ciclo FASP** | Integración, Distribución, Administración, Supervisión, Seguimiento |
| **5 dimensiones del ciclo** | Planeación, Asignación, Ejecución, Seguimiento, Rendición de cuentas |
| **3 tipos de competencia** | Exclusiva, Concurrente, Complementaria |
| **3 niveles de obligatoriedad** | Mandatoria, Facultativa, Recomendatoria |
| **5 tipos de vínculo ARS** | Formal, Informal, Jerárquico, Operativo, Consultivo |

## Relación con `pdf-to-knowledge-graph`

Este skill **reutiliza** `pdf-to-knowledge-graph` como sub-componente de la Etapa 1:

| Componente reusado | Uso en FASP |
|---|---|
| `pdf_to_md.py` | Conversión PDF→MD de normas y lineamientos (entrada a LLM-1) |
| `diccionario_gobernanza_mx.txt` | Base para LLM-3 (directorio de actores) |
| Esquemas JSON | Compatibilidad de artefactos intermedios |

Pero el FASP **extiende** significativamente:

| Componente FASP | NO existe en pdf-to-knowledge-graph |
|---|---|
| Parser jurídico (LLM-1) | Reconoce "Artículo N°", "Fracción X", "Transitorio Y" — no headings genéricos |
| Taxonomía cerrada | 5 vocabularios fijos de 3-5 valores cada uno |
| BD SQLite | Persistencia estructurada con esquema para los 12 anexos |
| Checkpoints por perfil | 5 perfiles × 3 etapas = 15 gates humanos |
| 8 métricas ARS específicas | Centralidad de grado (in/out), intermediación, cercanía, densidad, modularidad, diámetro |
| Generador narrativo (LLM-6, LLM-9) | Convierte métricas en texto, no solo extracción |

## Common pitfalls

1. **Confundir este skill con `pdf-to-knowledge-graph`**. El FASP es un sistema especializado en evaluación de coordinación al FASP con taxonomía cerrada. El pdf-to-knowledge-graph es extracción genérica. Usar el equivocado produce matrices mal clasificadas.

2. **Saltarse los checkpoints humanos**. Cada anexo tiene un gate de aprobación por perfil. Saltarse un checkpoint produce entregables no auditables.

3. **No respetar las taxonomías cerradas**. Los 5 vocabularios fijos no son opcionales. Si un LLM devuelve "tipo de competencia: mixta", la validación falla.

4. **Asumir que los LLMs se invocan solos**. Por defecto el skill viene con prompts documentados. Configurar API key o local LLM si quieres invocación programática.

5. **Confundir los niveles de supervisión**. Etapa 1 → jurídica. Etapa 2 → redes. Etapa 3 → coordinación. Asignar el perfil equivocado genera firmas que no tienen autoridad sobre el producto.

6. **Olvidar la BD como fuente de verdad**. Los anexos se derivan de queries a la BD. Generar anexos "a mano" introduce inconsistencias entre la matriz de congruencia y las aristas del sociograma.

7. **Modificar la taxonomía sin actualizar schemas**. Si añades un valor a "tipos de competencia", debes actualizar `schemas/taxonomias.json` y los validadores.

## Verification checklist

### Por etapa (antes de pasar a la siguiente)

```
Etapa 1:
[ ] Anexo 1 firmado por Coordinadora + Analista Senior jurídico
[ ] Anexo 2 sin valores fuera de la taxonomía cerrada
[ ] Anexo 3 con nivel de gobierno para cada actor
[ ] Todos los actores del Anexo 3 tienen ID único

Etapa 2:
[ ] Anexo 4 con tipos de vínculo ∈ {formal, informal, jerárquico, operativo, consultivo}
[ ] Anexo 5 documenta algoritmos, parámetros, tratamiento de nodos aislados
[ ] Anexo 6 con metadatos completos (nivel, naturaleza, rol en ciclo, frecuencia)
[ ] Anexo 4 firmado por Analista Senior redes + Analistas Junior grafos

Etapa 3:
[ ] Anexo 9 contrasta red formal (normativa) vs red real (operativa)
[ ] Anexo 10 con estructura: verbo + producto + oportunidad + justificación + efecto
[ ] Anexo 11 cubre todos los procesos administrativos del FASP evaluados
[ ] Anexo 12 lista completa de fuentes consultadas
```

### Por anexo

```
[ ] Esquema JSON del anexo validado
[ ] Valores de campos enumerados ∈ taxonomía cerrada (cuando aplique)
[ ] Firmas/checkpoints humanos registrados en la BD
[ ] Sin contradicción con anexos previos
```

## Cómo se invocan los LLMs

Los 9 módulos LLM son **sub-skills activables** con prompts documentados. El usuario tiene 3 opciones de invocación:

| Opción | Configuración | Caso de uso |
|---|---|---|
| **A. Cliente externo** | El usuario copia el prompt de `sub-skills/llm-N.md` a su cliente (Claude.ai, ChatGPT, etc.) y pega la salida | Trabajo interactivo, sin API key configurada |
| **B. API programática** | Configurar `OPENAI_API_KEY` o `ANTHROPIC_API_KEY` en el entorno; el script enruta a la API | Trabajo en batch, automatización |
| **C. Ejecución local** | Configurar Ollama o similar; enruta a `http://localhost:11434` | Privacidad, sin costos de API |

Por defecto, el skill viene con **Opción A** (placeholders con prompts documentados). El usuario activa la B o C según su entorno.

## Support files

- `sub-skills/llm-1-parser-juridico.md` — Entradas/Tareas/Salida/Prompt del LLM-1.
- `sub-skills/llm-2-matriz-congruencia.md`
- `sub-skills/llm-3-directorio-actores.md`
- `sub-skills/llm-4-relaciones-campo.md`
- `sub-skills/llm-5-normalizador-nodos.md`
- `sub-skills/llm-6-redactor-ars.md`
- `sub-skills/llm-7-triangulador.md`
- `sub-skills/llm-8-fichas-hallazgos.md`
- `sub-skills/llm-9-informe-final.md`
- `scripts/py-1-estructuracion.py` — ID únicos + Ficha técnica FASP (FUNCIONAL)
- `scripts/py-2-matrices-red.py` — Constructor matrices ARS (funcional)
- `scripts/py-3-metricas-ars.py` — Métricas ARS + memoria algorítmica (funcional)
- `scripts/py-4-exportacion.py` — Exportación + replicabilidad (funcional)
- `scripts/db_init.py` — Crea BD SQLite con esquema para los 12 anexos.
- `scripts/checkpoint.py` — Registra aprobaciones por perfil y etapa.
- `schemas/anexos/*.json` — Esquemas JSON de cada uno de los 12 anexos.
- `schemas/taxonomias.json` — Las 5 taxonomías cerradas del FASP.
- `schemas/checkpoints.json` — Perfiles y gates humanos.
- `references/catalogo_unidades_administrativas.txt` — ≥60 unidades federales/estatales con atribuciones FASP.
- `references/patrones_juridicos.txt` — Regex para artículos, fracciones, transitorios.
- `tests/test_smoke.py` — Verifica BD, taxonomías, schemas.

## Estado de implementación (v1.0)

| Componente | Estado |
|---|---|
| `pdf-to-knowledge-graph` (sub-componente Etapa 1) | ✅ Funcional (reusado) |
| BD SQLite con esquema para 12 anexos | ✅ Funcional |
| Taxonomías cerradas (5 vocabularios) | ✅ Funcional (validables) |
| LLM-1 Parser jurídico | ✅ Funcional (módulo CLI con regex) |
| LLM-2 a LLM-9 | 📋 Documentados con prompts (placeholders activables) |
| PY-1 Estructuración (Anexo 1) | ✅ Funcional |
| PY-2 Constructor matrices ARS | ✅ Funcional (esquema CSV) |
| PY-3 Métricas ARS | ✅ Funcional (cálculo + memoria) |
| PY-4 Exportación | ✅ Funcional (formatos abiertos) |
| Checkpoints humanos (5 perfiles × 3 etapas) | ✅ Funcional |
| Catálogo de unidades administrativas | 📋 Base inicial (~60 entradas), extensible |
| Detección patrones jurídicos | ✅ Funcional (regex) |

## Licencia

MIT.