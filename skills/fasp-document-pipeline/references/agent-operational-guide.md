# Guía operativa para invocar el pipeline desde el agente

Esta guía documenta cómo el agente (Alfredo Domínguez Díaz, Analista Senior Redes+ARS) opera el pipeline FASP cuando un usuario le pide ejecutar el proceso. Cubre cuatro temas que el usuario pidió explícitamente:

1. **Cómo se debe llamar el prompt** (convención de nombres para invocar cada módulo).
2. **Cuándo cerrar una etapa y cuándo continuar** (reglas de cierre + bloqueos).
3. **Entradas, salidas e insumos** por módulo (contrato de cada componente).
4. **Registros de evidencia** que se generan (dónde queda la trazabilidad en la BD).

La fuente única de esta información también está embebida en el tab "Ayuda del proceso" del dashboard (`scripts/fasp_dashboard.py → render_ayuda()`). Este archivo es la versión textual de referencia.

## 1. Convención de nombres para prompts al agente

Cuando invoques un módulo LLM via el agente, usa el **nombre exacto del sub-skill** (el ID que aparece en `sub-skills/llm-N-*.md` o el módulo Python correspondiente). El agente debe poder parsear el comando sin ambigüedad.

| Comando del prompt al agente | Módulo que dispara | Cuándo invocarlo |
|---|---|---|
| `"ejecuta LLM-1 sobre el MD"` | `llm-1-parser-juridico.py` | Tras convertir PDF a MD (Etapa 1) |
| `"ejecuta LLM-2 sobre la salida de LLM-1"` | `llm-2-matriz-congruencia` (prompt) | Tras LLM-1, para clasificar unidades |
| `"ejecuta LLM-3 para el directorio de actores"` | `llm-3-directorio-actores` (prompt) | Tras LLM-1, paralelo a LLM-2 |
| `"ejecuta PY-1"` | `py-1-estructuracion.py` | Cierre Etapa 1 (genera Anexo 1) |
| `"ejecuta LLM-4 sobre las transcripciones"` | `llm-4-relaciones-campo` (prompt) | Etapa 2, inicio |
| `"ejecuta LLM-5 para normalizar nodos"` | `llm-5-normalizador-nodos` (prompt) | Tras LLM-4 |
| `"ejecuta PY-2"` | `py-2-matrices-red.py` | Tras LLM-5 (genera Anexo 4, matrices incidencia) |
| `"ejecuta PY-3"` | `py-3-metricas-ars.py` | Tras PY-2 (genera Anexos 5, 6 + memoria algorítmica) |
| `"genera el sociograma"` | `py-3-sociograma.py` | Tras PY-3 |
| `"ejecuta LLM-6 para redactar hallazgos ARS"` | `llm-6-redactor-ars` (prompt) | Tras PY-3 (Producto 2 narrativo) |
| `"ejecuta LLM-7 para triangular"` | `llm-7-triangulador` (prompt) | Inicio Etapa 3 |
| `"ejecuta LLM-8 para fichas de hallazgos"` | `llm-8-fichas-hallazgos` (prompt) | Tras LLM-7 |
| `"ejecuta LLM-9 para el Informe Final"` | `llm-9-informe-final` (prompt) | Cierre Etapa 3 |
| `"ejecuta PY-4 para exportar"` | `py-4-exportacion.py` | Tras LLM-9 (genera Anexo 8) |

**Anti-patrones:** no uses descripciones vagas como "procesa el archivo" o "haz el análisis". El agente necesita un disparador explícito por módulo. Si el usuario pide algo ambiguo, **pregunta antes** de invocar módulos en lote.

## 2. Cuándo cerrar una etapa y cuándo continuar

### Regla de cierre por etapa

| Etapa | Se puede cerrar cuando... | Acción a tomar |
|---|---|---|
| **Etapa 1 (Documental)** | (a) Todas las normas planeadas están en la BD con sus unidades normativas. (b) El Anexo 1 (Ficha técnica FASP) está generado por PY-1. (c) `audit_log` tiene al menos 1 evento de LLM-1 y 1 de PY-1. | `checkpoint.py --etapa etapa_1_documental --perfil coordinadora --anexo "Anexo 1" --decision aprobado` |
| **Etapa 2 (Campo + ARS)** | (a) Las transcripciones de entrevistas están ingestadas. (b) LLM-4 extrajo aristas y LLM-5 normalizó los nodos. (c) PY-2 generó la matriz de adyacencia. (d) PY-3 calculó las 8 métricas ARS y la memoria algorítmica. (e) LLM-6 redactó los borradores de hallazgos ARS. | `checkpoint.py --etapa etapa_2_campo_ars --perfil analista_senior_redes --anexo "Anexo 4" --decision aprobado` |
| **Etapa 3 (Triangulación)** | (a) LLM-7 cruzó norma-red-campo. (b) LLM-8 generó las fichas de hallazgos. (c) LLM-9 redactó el Informe Final. (d) PY-4 exportó el paquete replicable (Anexo 8). | `checkpoint.py --etapa etapa_3_triangulacion --perfil coordinacion_evaluacion --anexo "Anexo 10" --decision aprobado` |

### Cuándo NO continuar (bloqueos)

Si alguna de estas condiciones se cumple, **detente y reporta al usuario** — no avances ni intentes "arreglarlo" en silencio:

1. **LLM devuelve un valor fuera de la taxonomía cerrada** (ej. `tipo_competencia: "Mixta"`). El validador `validate_taxonomias.py` lo detecta. Pide al usuario que corrija el prompt o use otro modelo.
2. **La cobertura del MD es < 0.85** (visible en `audit_conversions.py`). El PDF probablemente es escaneado y requiere OCR forzado (`--force-ocr` en `pdf_to_md.py`).
3. **Un anexo no valida contra su schema JSON**. Revisa la salida del LLM y el schema en `schemas/anexos/`.
4. **El grafo ARS tiene < 5 nodos**. El corpus es muy pequeño para métricas confiables. Sugiere añadir más aristas antes de continuar.
5. **Hay un gate de control sin registrar para la etapa actual**. No cierres la etapa.

## 3. Entradas, salidas e insumos por módulo

### Etapa 1: Análisis Documental

| Módulo | Entradas | Salidas |
|---|---|---|
| **pdf-to-knowledge-graph** (reutilizado) | PDF del corpus normativo (ruta local) | `<job_id>.md`, `<job_id>.meta.json`, `<job_id>.layout.json`, `<job_id>.validation.json` en `jobs/<job_id>/` |
| **LLM-1 Parser jurídico** | MD del PDF | Filas en `normas` (1 por documento) + filas en `norma_unidades` (N por unidad detectada: artículo, fracción) |
| **LLM-2 Matriz de congruencia** | Salida de LLM-1 | Actualización de `norma_unidades` con `tipo_competencia`, `nivel_obligatoriedad`, `dimension_ciclo` |
| **LLM-3 Directorio de actores** | Normas clasificadas | Filas en `actores` + `actor_etapas` |
| **PY-1 Estructuración** | Salidas de LLM-1, LLM-2, LLM-3 | IDs únicos asignados (`id_actor`); **Anexo 1** Ficha técnica FASP (`FASP_2026_P1_<EDO>_INFORME_V1.0.md`) |

### Etapa 2: Campo + ARS

| Módulo | Entradas | Salidas |
|---|---|---|
| **LLM-4 Relaciones de campo** | Transcripciones de entrevistas semiestructuradas | Filas en `aristas` (origen, destino, peso, tipo_vinculo, direccionalidad, frecuencia, canal, etapa_ciclo) |
| **LLM-5 Normalizador** | Edge list preliminar + directorio de actores | Nodos unificados (alias colapsados, IDs consistentes) |
| **PY-2 Matrices de red** | Edge list + diccionario de nodos | `anexo4_matriz_adyacencia_aristas.csv`, `anexo4_matriz_adyacencia_cuadrada.csv`, `anexo4_matriz_incidencia_actor_etapa.csv` |
| **PY-3 Métricas ARS** | Matrices de PY-2 | `anexo5_memoria_algoritmica.md`, `anexo6_diccionario_atributos.csv`, persistencia en `metricas_ars` |
| **PY-3 Sociograma** | BD con aristas y métricas | `FASP_2026_<PRODUCTO>_<EDO>_INFORME_V1.0.html` (interactivo con vis.js); `FASP_2026_<PRODUCTO>_<EDO>_INFORME_V1.0.png` (estático, si matplotlib) |
| **LLM-6 Redactor ARS** | Métricas + sociogramas | Borrador narrativo del Producto 2 (Informe de Hallazgos) |

### Etapa 3: Triangulación

| Módulo | Entradas | Salidas |
|---|---|---|
| **LLM-7 Triangulador** | Matriz Producto 1 + ARS Producto 2 + resúmenes entrevistas | Coincidencias/divergencias norma-red-campo + diagnóstico de riesgos |
| **LLM-8 Fichas hallazgos** | Listado priorizado de problemas | Filas en tabla `fichas` (estructura: verbo + producto + oportunidad + justificación + efecto) |
| **LLM-9 Informe Final** | Diagnósticos + ARS + fichas validadas | Informe Final narrativo (Producto 3); **Anexo 7** Glosario; **Anexo 8** Metodología de replicabilidad (texto) |
| **PY-4 Exportación** | Toda la BD | `tabla_<nombre>.csv` por cada tabla; **Anexo 8** `anexo8_metodologia_replicabilidad.md`; paquete replicable completo |

## 4. Registros de evidencia

Cada módulo deja un rastro trazable. Estos son los lugares a consultar para auditoría:

| Tipo de evento | Dónde queda registrado |
|---|---|
| Inserción en cualquier tabla de la BD | Tabla `audit_log` con `modulo=<nombre>`, `accion=insert`, `detalle=<JSON>` |
| Actualización en cualquier tabla | Tabla `audit_log` con `modulo=<nombre>`, `accion=update` |
| Generación de un anexo (Anexo N) | Archivo `.md` o `.csv` con nomenclatura `FASP_2026_<PRODUCTO>_<EDO>_<TIPO>_V<X>.<ext>` |
| Avance por etapa y perfil | Tabla `checkpoints` con `etapa`, `perfil`, `decision`, `aprobador`, `fecha` |
| Conversión PDF→MD | `jobs/<job_id>/<job_id>.meta.json` con los parámetros de conversión y `audit_conversions.py` con métricas de calidad |
| Métricas ARS por nodo | Tabla `metricas_ars` con `in_degree`, `out_degree`, `degree_centrality`, `betweenness`, `closeness`, `comunidad_id` |

### Cómo ver la trazabilidad completa desde el shell

```bash
# Últimos 20 eventos del audit_log
sqlite3 fasp.db "SELECT timestamp, modulo, accion, tabla, detalle FROM audit_log ORDER BY id DESC LIMIT 20;"

# Conteo de filas por tabla
sqlite3 fasp.db "SELECT 'documentos', COUNT(*) FROM documentos UNION ALL SELECT 'normas', COUNT(*) FROM normas UNION ALL SELECT 'aristas', COUNT(*) FROM aristas UNION ALL SELECT 'checkpoints', COUNT(*) FROM checkpoints;"

# Gates por etapa y perfil
sqlite3 fasp.db "SELECT etapa, perfil, decision, aprobador, fecha FROM checkpoints ORDER BY id DESC;"

# Auditoría de calidad de conversiones
python3 scripts/audit_conversions.py --jobs-dir ./jobs/ --output-json ./audit.json

# Reporte de normas con parámetros de conversión
python3 scripts/norms_list.py --jobs-dir ./jobs/ --output-csv ./normas.csv

# Dashboard HTML
python3 scripts/fasp_dashboard.py --db ./fasp.db --output ./dashboard.html
```

## 5. Cómo se cierra una etapa (paso a paso)

1. **Verifica que todos los módulos de la etapa están ejecutados.** Revisa el tab "Resumen" del dashboard: las normas/conversiones deben tener score y rating. Si hay normas con "Sin MD", faltan conversiones.
2. **Registra los gates de control de la etapa** (son metadata de trazabilidad, NO son firmas de identidad):

   ```bash
   python3 scripts/checkpoint.py --db ./fasp.db \
       --etapa etapa_1_documental \
       --perfil coordinadora \
       --anexo "Anexo 1" \
       --decision aprobado \
       --aprobador "Alfredo Dominguez Diaz"
   ```

3. **Regenera el dashboard** para confirmar visualmente que la etapa aparece registrada:

   ```bash
   python3 scripts/fasp_dashboard.py --db ./fasp.db --output ./dashboard.html
   open ./dashboard.html
   ```

4. **Exporta el paquete replicable** con PY-4 al cierre de Etapa 3:

   ```bash
   python3 scripts/py-4-exportacion.py --db ./fasp.db --output ./export/
   ```

## Anti-patrones operativos

- ❌ **Ejecutar el pipeline completo via agente Bedrock esperando respuesta rápida.** El pipeline CLI toma < 30 segundos para un PDF de 50 KB. Por agente Bedrock tarda > 3 minutos por la latencia HTTP de cada tool call. **Usa CLI directo para batch; usa el agente Bedrock solo para revisión cualitativa.**
- ❌ **Mover el job a otra carpeta después de ejecutar el LLM-1.** El campo `normas.fuente` se calcula al momento del INSERT y refleja la ruta del MD. Si mueves el job, el `fasp_dashboard.py` no lo encontrará. Edita `fuente` en la BD con `UPDATE` o re-ejecuta `llm-1-parser-juridico.py` con la nueva ruta.
- ❌ **Asumir que "registrar el gate" cierra la etapa automáticamente.** El gate es solo metadata. El cierre de la etapa es una decisión humana (de Alfredo) que se documenta ejecutando `checkpoint.py`. No hay estado automático.
- ❌ **Pedir al agente "procesa todos los PDFs de esta carpeta y dame los anexos".** Cada PDF requiere un job_id único, un LLM-1, un PY-1 con su Anexo 1, y un checkpoint por estado. Hacerlo de uno en uno, validando cada paso, es más robusto que batch automático. Si necesitas batch, escribe un wrapper `fasp-procesar <pdf> --edo <EDO>` que itere y registre checkpoints.
