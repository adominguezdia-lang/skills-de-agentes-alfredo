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

## Cómo invocar el skill (4 métodos, ordenados por velocidad)

| # | Método | Comando | Cuándo usarlo |
|---|---|---|---|
| **1** | **CLI directo (rápido)** | `python3 ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/db_init.py --db ./fasp.db` y luego encadenar `pdf_to_md.py` + `llm-1-parser-juridico.py` + `py-1-estructuracion.py` | Producción, batch, CI/CD. **< 30 segundos** para un PDF típico de 50 KB / 3 páginas. |
| **2** | **Pipeline FASP completo** | Encadenar los 6 scripts del método 1 + `nomenclatura.py` + `checkpoint.py` | Cuando el output debe respetar la nomenclatura `FASP_2026_<PRODUCTO>_<EDO>_<TIPO>_V<X>.<EXT>` y los 15 gates humanos. |
| **3** | **Agente Hermes local** | Decirle al agente en conversación: "Convierte /ruta/al.pdf a Markdown usando el skill pdf-to-knowledge-graph y luego genera los Anexos 1-3" | Exploración, debugging, iteración conversacional. Latencia: ~3-10s por paso. |
| **4** | **Perfil `fasp-bedrock`** (Claude Sonnet 4.5) | `fasp-bedrock chat -q "..." --tools 'terminal,file'` | Supervisión, revisión cualitativa, redacción de hallazgos ARS (Producto 2) e Informe Final (Producto 3). ⚠️ **No usar para ejecutar el pipeline completo**: cada tool call incurre en round-trip HTTP a Bedrock (~5-15s de latencia cada uno), por lo que los 6 pasos tardan **> 3 minutos** cuando por CLI son 30 segundos. Mezclar los dos (por ejemplo, pedirle al agente que ejecute el pipeline) funciona pero desperdicia tiempo de Bedrock. |

Después de cualquier ejecución, regenera el dashboard: `python3 scripts/fasp_dashboard.py --db ./fasp.db --output ./dashboard.html && open dashboard.html`.

## Arquitectura de 3 etapas con 13 módulos

### Etapa 1 — Análisis documental (Producto 1)

| Módulo | Tipo | Insumos | Producto |
|---|---|---|---|
| **LLM-1** | Parser jurídico-documental | Normas fed/est/mun, convenios FASP, manuales, lineamientos | Tabla con `id_norma, nivel, jerarquía, artículo, tema, referencia a coordinación` |
| **LLM-2** | Constructor de matriz de congruencia | Salida LLM-1 | Matriz con taxonomía cerrada (competencia × obligatoriedad × dimensión ciclo) |
| **LLM-3** | Generador del directorio preliminar de actores | Normas clasificadas + convenios | Directorio: nombre oficial, nivel, naturaleza (formal/informal), funciones |
| **PY-1** | Estructuración de bases | Salidas LLM-1/2/3 | Asigna IDs únicos + Ficha técnica FASP (Anexo 1) |

**Anexos producidos:** 1 (Ficha técnica FASP), 2 (Matriz de congruencia), 3 (Directorio preliminar)
**Gate de control:** Coordinadora + Analista Senior jurídico (registro de avance)

### Etapa 2 — Trabajo de campo + ARS (Producto 2)

| Módulo | Tipo | Insumos | Producto |
|---|---|---|---|
| **LLM-4** | Extractor de relaciones y atributos | Transcripciones de entrevistas + grupos de enfoque | Edge list con origen/destino/tipo/peso/direccionalidad |
| **LLM-5** | Normalizador de nodos | Edge list preliminar + directorio | Nodos unificados (dedup semántica de siglas vs nombres completos) |
| **PY-2** | Constructor de matrices de red | Edge list validada + diccionario de nodos | Matriz de adyacencia (Actor-Actor) + Matriz de incidencia (Actor-Proceso) |
| **PY-3** | Cálculo de métricas | Matrices de PY-2 | Métricas ARS: centralidad de grado (in/out), intermediación, cercanía, densidad, modularidad, diámetro + Memoria algorítmica |
| **LLM-6** | Redactor de hallazgos ARS | Métricas + sociogramas | Borradores narrativos del Producto 2 |

**Anexos producidos:** 4 (Matriz de adyacencia), 5 (Memoria algorítmica), 6 (Diccionario de atributos)
**Gate de control:** Analista Senior experto en redes + Analistas Junior de grafos

### Etapa 3 — Triangulación + Recomendaciones (Producto 3)

| Módulo | Tipo | Insumos | Producto |
|---|---|---|---|
| **LLM-7** | Triangulador norma-red-campo | Matriz Producto 1 + ARS Producto 2 + resúmenes entrevistas | Coincidencias/divergencias + diagnóstico de riesgos de coordinación |
| **LLM-8** | Generador de fichas de hallazgos | Listado priorizado de problemas | Fichas: `verbo + producto/proceso + oportunidad + justificación + efecto esperado` |
| **LLM-9** | Redactor del Informe Final | Diagnósticos + ARS + fichas validadas | Secciones narrativas del Producto 3 + Glosario + Metodología de replicabilidad |
| **PY-4** | Exportación y replicabilidad | Todo lo previo | Tablas + matrices + sociogramas en formatos abiertos |

**Anexos producidos:** 7 (Glosario), 8 (Metodología de replicabilidad), 9 (Propuesta modificación normativa), 10 (Hallazgos/recs/ASM), 11 (Ficha técnica administrativa), 12 (Fuentes)
**Gate de control:** Coordinadora + equipo de análisis

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

2. **Asumir que los "checkpoints" del skill son firmas de identidad**. **No lo son.** Los 15 gates del sistema (5 perfiles × 3 etapas) son **metadata de trazabilidad**: el campo `aprobador` es texto libre, NO hay verificación de quién firma, NO hay autenticación, NO hay permisos. **Alfredo Domínguez Díaz coordina el stack completo del pipeline FASP** en su rol de Analista Senior Redes+ARS. Cada gate registra **avance por etapa y perfil** en la BD; nadie "firma como Coordinadora" porque eso requeriría un sistema de identidad que este skill no tiene ni necesita. **Consecuencia operativa**: cuando el usuario dice "los gates no son firmas, no hacen falta validaciones", **tienes razón** — el script `checkpoint.py` solo escribe en la BD un registro con texto libre. Si alguna vez necesitas agregar verificación de identidad real (por ejemplo, porque el equipo creció y varios analistas firman checkpoints), es un cambio arquitectónico mayor: tabla `usuarios_autorizados`, validación contra email, autenticación — no algo que se añade en 10 minutos. **Cómo reconocer el error**: si estás a punto de escribir código que valida "este usuario tiene rol X", detente. Pregunta primero si el sistema realmente requiere verificación de identidad.

3. **No respetar las taxonomías cerradas**. Los 5 vocabularios fijos no son opcionales. Si un LLM devuelve "tipo de competencia: mixta", la validación falla.

4. **Asumir que los LLMs se invocan solos**. Por defecto el skill viene con prompts documentados. Configurar API key o local LLM si quieres invocación programática.

5. **Confundir los niveles de registro de avance en los gates**. Aunque los gates no son firmas, sí representan perfiles diferentes (Coordinadora, Analista Senior jurídico, Analista Senior redes, Junior grafos, Coordinación de evaluación). Cada perfil tiene una responsabilidad distinta sobre los entregables. Si Alfredo registra avance "como Junior grafos" sobre un anexo que en realidad tocó el equipo Cuali, está mintiendo en la trazabilidad aunque no haya seguridad comprometida. Convención: usar `aprobador="Alfredo Dominguez"` en todos los gates, dejando que el campo `perfil` indique la responsabilidad ejercida. NO escribir `aprobador="Janett Salvador"` porque Janett no opera este skill — Alfredo es quien coordina.

6. **Olvidar la BD como fuente de verdad**. Los anexos se derivan de queries a la BD. Generar anexos "a mano" introduce inconsistencias entre la matriz de congruencia y las aristas del sociograma.

7. **Modificar la taxonomía sin actualizar schemas**. Si añades un valor a "tipos de competencia", debes actualizar `schemas/taxonomias.json` y los validadores.

8. **Acentos en constraints CHECK de SQLite**. La BD define `CHECK (nivel IN ('Federal','Estatal','Municipal'))`, `CHECK (etapa_ciclo IN ('Integración',...))`, `CHECK (tipo_vinculo IN ('Formal','Informal','Jerárquico','Operativo','Consultivo'))`. Todos con tildes. Si un script de prueba o un usuario inserta `"Jerarquico"` sin tilde o `"Distribucion"` sin tilde, el INSERT falla con `IntegrityError`. Lección: cuando uses estos valores literales en Python, cópialos de `references/patrones_juridicos.txt` o de los schemas JSON — nunca los escribas de memoria. Patrón observado en pruebas: el validador detecta `"Mixta"` y `"Etapa inventada"` correctamente, pero las inserciones crudas en `INSERT INTO aristas VALUES (..., 'Jerarquico')` pasan la validación regex pero fallan en el constraint. **Fix**: usar una constante `ETAPAS_FASP = ["Integración", "Distribución", ...]` o leer de `schemas/taxonomias.json` en cada script que inserte.

9. **Empaquetar el zip del skill antes de propagar los nuevos archivos**. Si modificas `scripts/fasp_dashboard.py` pero ejecutas `zip` desde un directorio viejo (`/tmp/pdf-to-knowledge-graph/` en vez de `/tmp/fasp-document-pipeline/`), el zip queda incompleto. Lección del flujo de Alfredo: el orden correcto es **siempre** (1) editar en `~/.hermes/skills/<skill>/`, (2) copiar a `/tmp/<skill>/`, (3) `cd /tmp && zip`, (4) copiar a `~/Downloads/`, (5) commit+push a GitHub. Si inviertes cualquier paso, el zip queda desincronizado. Verificación rápida: `unzip -l skill.zip | grep <archivo_nuevo>` debe devolver el archivo.

8. **Leer un `.docx` como si fuera un archivo de texto plano**. La arquitectura del FASP suele llegar como un `.docx` (Word) que describe la arquitectura o el Plan de Trabajo. NO se lee con `read_file`, `cat` o `head`. `.docx` es un ZIP con XML dentro. La forma rápida de inspección desde shell: `unzip -l archivo.docx` lista los archivos internos; `unzip -p archivo.docx word/document.xml` da el cuerpo. Patrón observado: decir "lee el archivo X" sin mencionar la extensión lleva a tratar un `.docx` como si fuera `.md` y concluir erróneamente "el archivo está vacío" cuando el XML tiene contenido. La receta Python completa para extraer el texto:

   ```python
   import zipfile
   from xml.etree import ElementTree as ET
   with zipfile.ZipFile("archivo.docx") as z:
       with z.open("word/document.xml") as f:
           root = ET.fromstring(f.read())
       ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
       for p in root.iter(f"{ns}p"):
           txt = "".join(t.text or "" for t in p.iter(f"{ns}t")).strip()
           if txt:
               print(txt)
   ```

9. **Iterar con `git add .` sobre el paquete entero cuando solo cambiaste una parte**. Si trabajas dentro de un paquete distribuible (este skill, o `pdf-to-knowledge-graph`, o cualquier subcarpeta de un repo de skills), tu `git add .` desde la raíz sube TODO el repo incluyendo las dependencias sin versionar. Convención: `cd skills/fasp-document-pipeline && git status` antes de cada commit para ver el blast radius. Si el repo padre es `skills-de-agentes-alfredo`, operá siempre desde la subcarpeta del skill o usá `git add skills/fasp-document-pipeline/` explícitamente.

10. **Asumir que LLM-1 con keywords clasifica una unidad normativa en una sola etapa del FASP**. La clasificación inicial del parser jurídico es **tentativa y monoetiqueta**: para cada unidad elige la etapa con mayor score de palabras clave. Esto es **incorrecto para documentos institucionales transversales** (CSN, SESNSP, Secretariado Ejecutivo, Comités de Coordinación) que participan en todas las etapas del ciclo del FASP simultáneamente. Patrón observado al probar con `CSN.pdf` (Consejo de Seguridad Nacional): LLM-1 asignó `etapa_ciclo_fasp = "Integración"` porque la palabra "integración" domina el score, pero el CSN coordina Integración, Distribución, Administración, Supervisión y Seguimiento a la vez. **Solución**: cuando LLM-2 (constructor de matriz de congruencia) esté implementado, debe detectar estas unidades transversales y marcarlas con `etapas_ciclo_fasp = ["Integración","Distribución","Administración","Supervisión","Seguimiento"]` (las 5). Mientras LLM-2 sea placeholder, el usuario debe revisar manualmente las unidades cuyo texto menciona explícitamente "Consejo", "Comité", "Coordinación" o "Seguimiento" en el mismo párrafo — son candidatas a ser transversales.

11. **Invocar el pipeline completo via agente Bedrock esperando respuesta rápida**. El pipeline completo (PDF→MD→entidades→BD→Anexos) ejecutado directamente desde CLI toma < 30 segundos para un PDF típico de 50 KB / 3 páginas. La **misma cadena de 6 pasos ejecutada por un agente conversacional (Claude Sonnet 4.5 vía AWS Bedrock) tarda > 3 minutos** porque cada tool call incurre en round-trip HTTP a Bedrock (~5-15s de latencia cada uno). Decisión: **usa CLI directo para batch y producción; usa el agente Bedrock solo para revisión, supervisión o cuando necesitas interpretación cualitativa del LLM**. Mezclar los dos (por ejemplo, pedirle al agente que ejecute el pipeline completo) funciona pero desperdicia tiempo de Bedrock. Cuando el usuario diga "procesa este PDF con el skill", ejecuta los scripts directamente salvo que pida explícitamente "usando el agente de Bedrock".

## Workflow de versioning: reducir primero, endurecer después

El usuario (Alfredo) usa un patrón específico al revisar el skill entre versiones. Memorízalo así la próxima vez que recibas feedback tipo "está muy grande" o "tiene cosas que no funcionan":

### Fase 1 — REDUCIR (cuando el usuario reporta features fantasma, código muerto, o sobrante)

1. Inventariar `git log --oneline -20` y `tests/test_smoke.py` para entender qué está probado.
2. Buscar `--flags` declarados en SKILL.md que NO existan en el código. Cada uno es candidato a eliminar.
3. Buscar imports y dependencias declaradas que no se usan (ej. `pdfplumber` importado pero no usado).
4. Eliminar ramas de código inalcanzables (ej. `if args.use_llm: ...` cuando el flag no existe).
5. Actualizar SKILL.md para reflejar la realidad: lo que el código hace, no lo que el código "debería hacer".
6. Re-ejecutar tests después de cada eliminación.

### Fase 2 — ENDURECER (solo cuando la reducción está limpia)

1. Añadir `tests/test_smoke.py` para los componentes nuevos que sobreviven a la fase 1.
2. Añadir `requirements.txt` con versiones mínimas probadas.
3. Documentar el límite v1.1 vs v2.0 en SKILL.md (qué se queda como placeholder, qué se implementa).
4. NO añadir features nuevas en esta fase — la reducción tiene que asentarse primero.

### Fase 3 — EXPANDIR (solo bajo pedido explícito del usuario, no proactivamente)

1. Implementar los placeholders uno a uno, no en bloque.
2. Cada feature nueva trae su test + doc + ejemplo.
3. Bump de minor version (v1.1 → v1.2) por cada feature nueva.

**Por qué importa**: saltarse la fase 1 produce skills inflados con features fantasma que el siguiente agente intentará usar y fallará. Saltarse la fase 2 produce skills sin tests donde los cambios rompen en silencio. El orden correcto es REDUCIR → ENDURECER → EXPANDIR, no al revés.

## Verification checklist

### Por etapa (antes de pasar a la siguiente)

```
Etapa 1:
[ ] Anexo 1 registrado (gate de control: Coordinadora + Analista Senior jurídico)
[ ] Anexo 2 sin valores fuera de la taxonomía cerrada
[ ] Anexo 3 con nivel de gobierno para cada actor
[ ] Todos los actores del Anexo 3 tienen ID único

Etapa 2:
[ ] Anexo 4 con tipos de vínculo ∈ {formal, informal, jerárquico, operativo, consultivo}
[ ] Anexo 5 documenta algoritmos, parámetros, tratamiento de nodos aislados
[ ] Anexo 6 con metadatos completos (nivel, naturaleza, rol en ciclo, frecuencia)
[ ] Anexo 4 registrado (gate de control: Analista Senior redes + Analistas Junior grafos)

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
[ ] Gates de control registrados en la BD (trazabilidad)
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

**Coordinación**: Alfredo Domínguez Díaz (Analista Senior Redes+ARS) opera el stack completo. Las decisiones sobre cuándo invocar cada LLM, con qué prompt y con qué parámetros son su responsabilidad.

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
- `scripts/llm-1-parser-juridico.py` — Parser jurídico (FUNCIONAL)
- `scripts/nomenclatura.py` — Validación y construcción de nombres FASP_2026_* (FUNCIONAL)
- `scripts/py-1-estructuracion.py` — ID únicos + Ficha técnica FASP (FUNCIONAL)
- `scripts/py-2-matrices-red.py` — Constructor matrices ARS (FUNCIONAL)
- `scripts/py-3-metricas-ars.py` — Métricas ARS + memoria algorítmica (FUNCIONAL)
- `scripts/py-3-sociograma.py` — Sociograma con 3 criterios topológicos (FUNCIONAL)
- `scripts/py-4-exportacion.py` — Exportación + replicabilidad (FUNCIONAL)
- `scripts/db_init.py` — Crea BD SQLite con esquema para los 12 anexos.
- `scripts/checkpoint.py` — Registra aprobaciones por perfil y etapa.
- `scripts/validate_taxonomias.py` — Verifica que valores pertenezcan a taxonomías cerradas.
- `schemas/anexos/*.json` — Esquemas JSON de 9 de los 12 anexos (1, 2, 3, 4, 5, 6, 10, 11, 12).
- `schemas/taxonomias.json` — Las 7 taxonomías cerradas (incluye entidades federativas y nomenclatura).
- `schemas/checkpoints.json` — Perfiles y gates humanos.
- `references/catalogo_unidades_administrativas.txt` — ~60 unidades federales/estatales con atribuciones FASP.
- `references/patrones_juridicos.txt` — Regex para artículos, fracciones, transitorios.
- `references/entidades_federativas.json` — Las 8 entidades evaluables + NAL (Plan de Trabajo FASP 2026).
- `references/equipo_cevalua.json` — Los 14 integrantes del equipo C-evalua.
- `references/cronograma.json` — Fechas de entrega escalonadas por quincena.
- `references/memoria_codificacion.json` — Escala de intensidad (0-10) y 3 criterios de visualización.
- `references/bedrock-setup.md` — Receta operativa para ejecutar el skill desde un perfil Hermes con AWS Bedrock (Claude Sonnet 4.5 / Haiku 4.5), incluyendo latencias esperadas por operación y los pitfalls del wrapper `fasp-bedrock`.
- `references/test-case-csn.md` — Caso de prueba reproducible (CSN.pdf, 2 páginas, 49.6 KB) con el resultado completo del pipeline y el hallazgo que llevó al pitfall de clasificación monoetiqueta de unidades transversales.
- `references/pipeline-recipe.md` — **Receta compacta del pipeline en 6 pasos CLI** con variables de entorno, comandos exactos, tiempos esperados, errores comunes y criterios para usar Bedrock vs CLI. Es el primer archivo a leer cuando un usuario nuevo pregunta "¿cómo proceso un PDF?".
- `references/common-errors.md` — **Catálogo de errores frecuentes** con causa raíz y solución concreta: `IntegrityError` por tildes faltantes en constraints, zip desincronizado, dashboard con gates fantasma, Nomenclatura inválida, clasificación monoetiqueta de unidades transversales, etc.
- `references/gates-and-traceability.md` — **Modelo de diseño de los gates de control** (metadata de trazabilidad, NO firmas de identidad). Documenta cuándo este modelo es correcto, cuándo NO lo es, y el anti-patrón de sobre-ingeniería de identidad que Alfredo Domínguez corrigió durante el diseño. Lectura obligatoria si una sesión futura vuelve a proponer validación de usuarios.
- `scripts/fasp_dashboard.py` — Genera dashboard HTML autocontenido (sin servidor web, sin dependencias externas) con 4 tabs (Resumen / Etapa 1 / Etapa 2 / Etapa 3), métricas globales, 15 gates humanos coloreados, tabla de las 8 entidades federativas y timeline del audit_log. Uso: `python3 scripts/fasp_dashboard.py --db ./fasp.db --output ./dashboard.html && open dashboard.html`.
- `tests/test_smoke.py` — 12 tests: BD, taxonomías, schemas, nomenclatura, sociograma end-to-end.

## Estado de implementación (v1.1 — acoplado al Plan de Trabajo FASP 2026)

| Componente | Estado |
|---|---|
| `pdf-to-knowledge-graph` (sub-componente Etapa 1) | ✅ Funcional (reusado) |
| BD SQLite con esquema para 12 anexos | ✅ Funcional |
| Taxonomías cerradas (5 vocabularios + entidades federativas) | ✅ Funcional (validables) |
| Nomenclatura obligatoria `FASP_2026_<PRODUCTO>_<EDO>_<TIPO>_V<X>.<EXT>` | ✅ Funcional (scripts/nomenclatura.py) |
| Referencias del Plan de Trabajo (entidades, equipo, cronograma, memoria) | ✅ 4 archivos JSON en references/ |
| LLM-1 Parser jurídico | ✅ Funcional (regex + keywords) |
| LLM-2 a LLM-9 | 📋 Prompts documentados (placeholders activables) |
| PY-1 Estructuración (Anexo 1) | ✅ Funcional |
| PY-2 Constructor matrices ARS | ✅ Funcional |
| PY-3 Métricas ARS (8 + geodesica_promedio) | ✅ Funcional |
| PY-3-sociograma con 3 criterios formales del Plan | ✅ Funcional |
| PY-4 Exportación | ✅ Funcional |
| Dashboard HTML de seguimiento | ✅ Funcional (`scripts/fasp_dashboard.py`) |
| Checkpoints humanos (5 perfiles × 3 etapas) | ✅ Funcional |
| Catálogo de unidades administrativas | 📋 Base inicial (~60), extensible |
| Detección patrones jurídicos | ✅ Funcional (regex) |
| Schemas para Anexos 1-12 | ✅ 9 schemas JSON (1, 2, 3, 4, 5, 6, 10, 11, 12) |

## Acoplamiento al Plan de Trabajo FASP 2026

### Entidades federativas a evaluar (8 + NAL)

| Clave | Estado | Senior responsable P1 |
|---|---|---|
| MEX | Estado de México | Jaqueline Meza Urías |
| HID | Hidalgo | Diana Valadez Rovelo |
| MIC | Michoacán de Ocampo | Jerónimo Hernández Hernández |
| QRO | Querétaro | Nancy García Vázquez |
| CHI | Chiapas | Diana Valadez Rovelo |
| TAB | Tabasco | Jerónimo Hernández Hernández |
| TAM | Tamaulipas | Jaqueline Meza Urías |
| ZAC | Zacatecas | Nancy García Vázquez |
| NAL | Agregación Nacional | — (consolidación) |

### Nomenclatura de archivos (Plan §V.H, Tabla 6)

Todo archivo generado debe seguir:

```
[PROGRAMA]_[PRODUCTO]_[EDO]_[TIPO_ARCHIVO]_V[X].[EXT]

FASP_2026_P3_MEX_INFORME_V1.0.docx       # Informe estatal
FASP_2026_P3_CHI_MAT_ADY_V1.0.csv        # Matriz adyacencia
FASP_2026_P3_MIC_MAT_INC_V1.0.xlsx       # Matriz incidencia
FASP_2026_P3_TAM_DIC_NODOS_V1.0.csv      # Diccionario de nodos
FASP_2026_P3_QRO_SCRIPT_V1.0.py         # Script Python
FASP_2026_IF_NAL_BBDD_V2.0.xlsx         # Base consolidada nacional
```

Ver `scripts/nomenclatura.py` para validación y construcción programática.

### Criterios formales de visualización del sociograma (Plan §V.G, Tabla 5)

| Atributo | Mapeo |
|---|---|
| Tamaño del nodo | ∝ Betweenness (centralidad de intermediación) |
| Color del nodo | Federal `#1a4480` / Estatal `#7a3e9d` / Municipal `#b5651d` |
| Grosor de aristas | ∝ Peso del vínculo (frecuencia + intensidad) |

El script `scripts/py-3-sociograma.py` aplica estos 3 criterios automáticamente.

### Equipo C-evalua (14 personas)

| Rol | Personas |
|---|---|
| Coordinadora | Janett Salvador Martínez (100%) |
| Analista Senior Redes | Alfredo Domínguez Díaz (100%) ← este script es tu entregable |
| Analistas Senior | Diana Valadez, Jaqueline Meza, Jerónimo Hernández, Nancy García (80% c/u) |
| Analistas Junior Redes | Paulina González, Nancy Morales, Erick Navarro, Sheila Morales (80% c/u) |
| Analistas Junior Cuali | Edgar Martínez, Arturo Torres, Anabelle García, Macarena Orozco (60% c/u) |

## Licencia

MIT.

## Patrón de diseño replicable (para futuras evaluaciones)

El FASP es un caso particular de un **patrón general** de arquitectura institucional multi-agente para evaluaciones de política pública. Si en el futuro recibes un encargo similar (otro fondo, otro programa con TdR + Plan de Trabajo + equipo + 8+ entidades federativas), este patrón aplica:

### Anatomía del patrón (8 componentes)

| # | Componente | Para qué sirve | En el FASP |
|---|---|---|---|
| 1 | **Documento de arquitectura** (`.docx` o `.md`) | Define qué módulos hay y cómo se conectan | `Anexo Técnico` migrado a `docs/fasp-architecture-documental.md` |
| 2 | **Plan de Trabajo** (`.docx`) | Define cronograma, equipo, entregables numerados, criterios de éxito | `260717 Plan de trabajo.docx` → `references/cronograma.json`, `equipo_cevalua.json` |
| 3 | **BD estructurada** (SQLite o equivalente) | Persistencia, trazabilidad, queries para anexos | 11 tablas, esquema en `scripts/db_init.py` |
| 4 | **Taxonomía cerrada** (JSON Schema + validador) | Vocabularios fijos que el LLM no puede inventar | `schemas/taxonomias.json` + `scripts/validate_taxonomias.py` |
| 5 | **Pipeline modular** (N scripts CLI) | Cada paso es ejecutable, testeable, versionado independientemente | 9 sub-skills LLM + 4 scripts Python |
| 6 | **Nomenclatura obligatoria** (regex + validador) | Identifica cada entregable de forma única y comparable | `scripts/nomenclatura.py` con regex `FASP_2026_PROD_EDO_TIPO_Vx.y.ext` |
| 7 | **Checkpoints humanos** (BD + CLI) | 5 perfiles × N etapas = N gates de aprobación con audit trail | `scripts/checkpoint.py` |
| 8 | **Dashboard de seguimiento** (HTML autocontenido) | Visibilidad del estado sin servidor web | `scripts/fasp_dashboard.py` |

### Cuándo aplicar este patrón

Aplica cuando se cumplen ≥ 3 de estas condiciones:
- Múltiples entregables numerados (anexos, informes, productos).
- Equipo multidisciplinario con roles diferenciados (no solo "el que hace todo").
- Taxonomía cerrada o vocabulario controlado que debe ser comparable entre iteraciones.
- Hay stakeholders externos que firman/revisan entregables.
- El plazo es de meses, no de horas (justifica la infraestructura).

### Pasos para instanciar el patrón en un nuevo proyecto

1. **Recibir el Anexo Técnico + Plan de Trabajo** del cliente. Generalmente son 2 `.docx`. Extraer su contenido con el snippet Python de este skill (pitfall #8).
2. **Construir la BD primero**, no al final. Esquema tentativo: `documentos` (entradas), `entidades_dominio` (la BD específica del proyecto), `artefactos` (salidas), `checkpoints` (firmas), `audit_log`. Crear `scripts/db_init.py` con el `SCHEMA_SQL` y `tests/test_db.py`.
3. **Definir la taxonomía cerrada** en `schemas/taxonomias.json` desde el día 1. Si el dominio no la tiene explícita, pregúntale al cliente — sin taxonomía cerrada, los LLMs inventan categorías y los anexos no son comparables.
4. **Crear el primer script funcional** que ya esté en producción (generalmente el extractor). Aplicar REDUCIR → ENDURECER → EXPANDIR desde el día 1 (no acumular placeholders que luego se olvidan).
5. **Diseñar la nomenclatura** ANTES del primer entregable. La pregunta a responder: "¿Cómo se llama un archivo para que un humano o un grep encuentre el entregable N del estado X en el producto Y?" Formato típico: `PROGRAMA_AAAA_PRODUCTO_ESTADO_TIPO_Vx.y.ext`.
6. **Implementar el sistema de checkpoints** con la cantidad de perfiles × etapas reales del proyecto. Cada gate = 1 INSERT en BD.
7. **Construir el dashboard solo cuando ya hay datos reales** (no antes). Patrón HTML autocontenido con CSS+JS embebidos es portable y no requiere infraestructura.
8. **Cada nuevo entregable** (anexo, informe) trae: schema JSON, script generador, test, ejemplo en `examples/`. Si no puedes producir los 4, el entregable no está listo para producción.

### Anti-patrones a evitar

- ❌ Construir el orquestador LLM antes de tener un solo script funcional que ya procese datos reales.
- ❌ Tener N archivos `.docx` fuente sin migrar a `.md` parseable (los humanos no pueden hacerles grep).
- ❌ "Lo vamos a afinar después" — los placeholders con flag `--use-llm` que no funcionan se quedan para siempre. Mejor eliminar el flag y documentar el placeholder como `📋`.
- ❌ Publicar el skill con un zip que no incluye los nuevos archivos. Si modificas 3 archivos y publicas un zip de hace 2 horas, el repo y el zip divergen y el siguiente agente usa el zip viejo.
- ❌ "Vamos a llenar la BD después" — la BD es la fuente de verdad. Los anexos se derivan de queries. Sin BD, los anexos se hacen "a mano" e introducen inconsistencias silenciosas.

### Lo que NO capturar en el skill (específico del FASP, no del patrón)

- El nombre "FASP" — el patrón es general, el caso es FASP.
- Los 8 nombres de entidades federativas (MEX/CHI/...) — son del FASP 2026, otro proyecto tendrá otros.
- Los 14 nombres del equipo C-evalua — son del FASP, otro proyecto tendrá otro equipo.
- La nomenclatura `FASP_2026_<PRODUCTO>_<EDO>_<TIPO>_V<X>.<EXT>` — la **idea** (programa+año+producto+estado+tipo+versión+extensión) es del patrón, los **valores específicos** son del FASP.

Lo que **sí** va en el skill porque es del FASP: las etapas, las taxonomías, los anexos, los checkpoints. Lo que va en el patrón pero NO en el skill específico: la **metodología** (este apartado) y las **plantillas** (`scripts/db_init.py` con `SCHEMA_SQL` como ejemplo de cómo estructurar tablas).