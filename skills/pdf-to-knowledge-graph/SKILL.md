---
name: pdf-to-knowledge-graph
description: "Pipeline de 3 etapas para convertir PDFs de gobernanza en grafos analizables: (1) PDF→Markdown con preservación de estructura, (2) Markdown→entidades nombradas con clasificación por capa (normativo/operativo/informal) y co-ocurrencia, (3) entidades→grafo NetworkX con métricas (densidad, centralidad, comunidades, silos). Salidas: tabla de aristas, grafo GraphML, JSON de métricas, visualización HTML interactiva. Triggers: 'pdf a markdown', 'convertir pdf a md', 'grafo de gobernanza', 'análisis de redes documentales', 'pipeline pdf knowledge graph', 'entidades nombradas pdf', 'normativo operativo informal', 'columna de gobernanza'. Distinct from biblio-metadata-extractor (que solo extrae metadata bibliográfica) and document-processing (que solo extrae texto)."
version: 1.0.0
author: Alfredo Domínguez
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [pdf, markdown, knowledge-graph, networkx, governance, nlp, ner]
    related_skills: [biblio-metadata-extractor, document-processing, plan]
---

# PDF → Knowledge Graph (Columna de Gobernanza)

Pipeline de tres etapas para convertir documentos PDF de gobernanza (leyes, reglamentos, oficios, circulares, memorandos, entrevistas de campo) en un grafo analizable que contrasta tres capas:

| Capa | Tipo de fuente | Ejemplos |
|---|---|---|
| **Normativa** | Leyes primarias, secundarias, reglamentos | Constitución, leyes federales/estatales, reglamentos, NOMs |
| **Operativa** | Documentos administrativos que ejecutan la ley | Oficios, circulares, memorandos, manuales de procedimiento |
| **Informal** | Material de campo, entrevistas, minutas | Transcripciones de entrevistas, bitácoras, hallazgos |

## Cuándo usar

- El usuario tiene un corpus de PDFs de gobernanza y quiere **medir cómo se conectan** ley → reglamento → oficio → práctica real.
- Necesita detectar **silos institucionales**, **actores puente** (entre capas), o **discrepancias entre lo normativo y lo operativo**.
- El corpus tiene **al menos 5 documentos**; debajo de eso, el grafo es trivial (ver §Cuántos documentos).
- Ya tiene MD limpio y solo quiere pasar a entidades/grafo → saltar a Etapa 2.

No usar para:
- Extraer solo metadata bibliográfica → `biblio-metadata-extractor`.
- Solo extraer texto sin análisis → `document-processing`.
- Análisis de texto sin grafo (resúmenes, Q&A) → usar el LLM directamente.

## Arquitectura: 3 etapas secuenciales

```
ETAPA 1 — PDF → Markdown
    pdf_to_md.py  →  <doc>.md  +  <doc>.meta.json  +  <doc>.layout.json

ETAPA 2 — Markdown → Entidades
    extract_entities.py  →  entities.jsonl (una línea por entidad con tipo y capa)

ETAPA 3 — Entidades → Grafo + Métricas
    build_graph.py  →  graph.graphml  +  edges.csv  +  metrics.json  +  graph.html
```

Cada etapa produce artefactos versionados y trazables. Si necesitas re-procesar, basta con borrar el artefacto de esa etapa — las anteriores siguen siendo válidas.

## Cuándo analizar (cuál es el momento correcto)

Esto NO es trivial. El orden importa porque análisis prematuros producen ruido.

| Etapa | Análisis válido | Por qué |
|---|---|---|
| T0 → T1 | Ninguno. Solo limpieza textual. | Sin texto limpio no hay entidades fiables; sin entidades no hay nodos. |
| T1 → T2 | Tampoco. Aquí solo extraes entidades. | Nodos sin grafo = tabla sin relaciones. |
| T2 → T3 | **Sí. Aquí construyes el grafo y mides.** | Las relaciones entre documentos solo emergen con ≥ 5 docs procesados. |
| Post-T3 | Iterar: si hay silos, volver a T1 y re-extraer con otra estrategia. | Las métricas son diagnóstico, no fin. Sirven para decidir dónde re-trabajar. |

**Regla práctica**: no construyas el grafo con menos de 5 documentos. Con 1-3 docs el grafo es trivial. Con 5-15 es exploratorio. Con 20-50 es el punto óptimo para gobernanza.

## Workflow (10 pasos)

### 1. Inventariar el corpus

Reunir todos los PDFs en una carpeta. Listar con:

```bash
python3 scripts/pdf_to_md.py --scan ./corpus/ --output ./jobs/
```

Esto crea un `jobs/manifest.json` con todos los PDFs detectados y un `job_id` por cada uno (UUID corto).

### 2. Clasificar por capa

Antes de procesar, clasificar manualmente cada PDF como:

- `layer: normativo` — leyes, reglamentos, NOMs.
- `layer: operativo` — oficios, circulares, memorandos, manuales.
- `layer: informal` — entrevistas, minutas, bitácoras.

Esta clasificación se guarda en `manifest.json` por documento y **se usa como atributo de aristas** en el grafo final. Sin esta clasificación, el grafo no puede contrastar capas.

### 3. Etapa 1 — Convertir PDF a Markdown

```bash
python3 scripts/pdf_to_md.py --job <job_id> --input ./corpus/<file>.pdf --output ./jobs/<job_id>/
```

Para cada job produce:

- `<job_id>.md` — Markdown limpio con headings `#`, `##`, ..., listas, tablas GFM, blockquotes.
- `<job_id>.meta.json` — metadata extra (autor si está, año, número de páginas, método: `text` u `ocr`).
- `<job_id>.layout.json` — información de layout por bloque (heading level, table, list, paragraph).

Si el PDF no tiene texto embebido (escaneado), el script cae a OCR vía `tesseract` (binario ya disponible en macOS).

**Selección de prompt versionado**: usa `prompts/prompt_conversion_v1.md` por defecto. Para PDFs con tablas complejas, usar `--prompt v2`. Para escaneos OCR, `v3`.

### 4. Validar la Etapa 1

```bash
python3 scripts/pdf_to_md.py --job <job_id> --validate
```

Chequeos: ¿el MD empieza con `#`? ¿tiene al menos un heading? ¿se preservaron palabras clave del PDF original? ¿la cobertura (palabras_md / palabras_pdf) ≥ 0.85?

Si falla, re-procesar con otro prompt o activar OCR forzado.

### 5. Etapa 2 — Extraer entidades

```bash
python3 scripts/extract_entities.py --job <job_id> --input ./jobs/<job_id>/<job_id>.md --output ./jobs/<job_id>/
```

Produce `entities.jsonl`, una línea por entidad detectada:

```json
{"entity":"Secretaría de Seguridad y Protección Ciudadana","type":"INSTITUCION","layer":"operativo","context":"...texto donde aparece...","section":"DE LA SECRETARÍA DE SEGURIDAD Y PROTECCIÓN CIUDADANA"}
{"entity":"Coordinación Nacional de Protección Civil","type":"INSTITUCION","layer":"operativo","context":"...","section":"DE LA SECRETARÍA DE SEGURIDAD Y PROTECCIÓN CIUDADANA"}
{"entity":"Ley de Seguridad Nacional","type":"NORMA","layer":"normativo","context":"...artículo 6, fracción II...","section":"INTRODUCCIÓN"}
```

Tipos de entidad que detecta:

- `INSTITUCION` — dependencias, órganos, entidades (Secretaría X, Instituto Y, etc.).
- `CARGO` — puestos mencionados (Secretario, Director, Coordinador, etc.).
- `NORMA` — leyes, reglamentos, NOMs citados.
- `DOCUMENTO` — oficios, circulares, memorandos referenciados.
- `PERSONA` — nombres propios mencionados.
- `LUGAR` — lugares geográficos (entidades federativas, ciudades).

El extractor combina tres estrategias:

1. **Diccionario base** en `references/diccionario_gobernanza_mx.txt` (instituciones federales comunes).
2. **Patrones regex** para cargos, leyes y oficios.
3. **LLM opcional** (`--use-llm`) para mejorar召回 en textos ambiguos. Más caro pero mejor.

### 6. Validar la Etapa 2

```bash
python3 scripts/extract_entities.py --job <job_id> --validate
```

Chequeos: ¿hay al menos 3 entidades? ¿los tipos son los del enum? ¿la capa es válida? ¿las secciones donde aparecen existen en el MD?

### 7. Etapa 3 — Construir el grafo

```bash
python3 scripts/build_graph.py --corpus ./jobs/ --output ./grafo/
```

Esto cruza los `entities.jsonl` de todos los jobs y construye un grafo donde:

- **Nodos** = entidades únicas normalizadas (lowercase + acentos preservados).
- **Aristas** = co-ocurrencia dentro del mismo documento + misma sección, ponderada por frecuencia.
- **Atributos de nodo**: tipo, capa (de la primera aparición), frecuencia global.
- **Atributos de arista**: capa, documentos compartidos, peso.

Produce:

- `graph.graphml` — formato estándar importable a Gephi, Cytoscape, Neo4j.
- `edges.csv` — tabla de aristas para análisis tabular.
- `nodes.csv` — tabla de nodos con sus atributos.
- `metrics.json` — métricas globales calculadas (ver §Métricas).
- `graph.html` — visualización interactiva con PyVis (si está disponible; fallback: texto).

### 8. Calcular métricas

Las métricas se calculan dentro de `build_graph.py` y se guardan en `metrics.json`:

```json
{
  "nodos_totales": 87,
  "aristas_totales": 234,
  "densidad": 0.062,
  "componentes_conexas": 4,
  "comunidades_louvain": 6,
  "top_centralidad_grado": [{"nodo": "...", "valor": 0.45}, ...],
  "top_betweenness": [{"nodo": "...", "valor": 0.31}, ...],
  "densidad_por_capa": {"normativo": 0.08, "operativo": 0.12, "informal": 0.04},
  "actores_transversales": [{"nodo": "...", "capas": ["normativo","operativo","informal"]}, ...]
}
```

### 9. Interpretar las métricas

Esto NO lo hace el script — lo haces tú con apoyo del LLM, cargando `metrics.json` en conversación:

| Si ves... | Significa... | Acción |
|---|---|---|
| Densidad < 0.05 y muchas componentes | Silos institucionales severos | Volver a Etapa 1, revisar clasificación de capa |
| Densidad normativa baja pero operativa alta | La ley no se conecta con la práctica | Documentar; pedir al admin que revise |
| Betweenness alto en un nodo | Un actor sostiene el flujo | Entrevistar a ese actor; es crítico |
| Actor en las 3 capas | Bridge institucional | Mapeo de poder informal vs formal |
| Comunidad = un solo proceso | El corpus está bien delimitado | Buen corpus. Continuar análisis fino. |
| Comunidad = una sola secretaría | Sesgo de muestreo | Añadir docs de otras secretarías |

### 10. Iterar

Las métricas guían la siguiente iteración. Si la cobertura es baja (< 0.85), re-procesar con `v2` o `v3`. Si las comunidades no coinciden con lo esperado, revisar la clasificación de capa del paso 2.

## Prompts versionados

La carpeta `prompts/` contiene **plantillas de prompt** documentadas (v1 base, v2 con tablas, v3 para OCR) que describen cómo un LLM debería convertir texto crudo a Markdown. Los archivos están ahí como **referencia conceptual** y para que el usuario los copie a su cliente LLM preferido.

El script `pdf_to_md.py` **no invoca un LLM directamente** — extrae texto y estructura con pymupdf. La conversión final a Markdown limpio se hace con heurísticas de heading/lista basadas en tamaño de fuente y patrones. Si el usuario quiere aplicar los prompts a un LLM externo, debe:

1. Extraer el texto crudo con `pdf_to_md.py --input doc.pdf --output ./jobs/<id>/` (queda en `<id>.layout.json` y en el cuerpo del `<id>.md`).
2. Pasar ese texto al LLM junto con la plantilla de prompt elegida.
3. Sobrescribir el `<id>.md` con el resultado del LLM.
4. Registrar la versión de prompt usada en `<id>.meta.json` → `prompt_version`.

Cada job guarda qué versión usó en `<job_id>.meta.json` → `prompt_version`.

## Métricas explicadas (no son solo números)

| Métrica | Fórmula simple | Lectura |
|---|---|---|
| **Densidad** | `2 * aristas / (n * (n-1))` | 0 = sin conexiones; 1 = todos conectados. < 0.05 = silos. |
| **Componentes conexas** | Subgrafos sin conexión entre sí | > 1 = fragmentación. |
| **Comunidades (Louvain)** | Modularidad máxima | Cada comunidad = un "clúster" de trabajo. |
| **Centralidad de grado** | N° de vecinos / (n-1) | Actores más referenciados. |
| **Betweenness** | Frecuencia como puente en caminos mínimos | Actores que conectan silos. |
| **Densidad por capa** | Solo aristas intra-capa | Mide cohesión interna de cada ámbito. |
| **Actores transversales** | Nodos presentes en ≥ 2 capas | Bridge nodes — los más críticos para gobernanza. |

## Common pitfalls

1. **Procesar 1-3 PDFs y pretender ver "redes"**. Por debajo de 5 documentos el grafo es trivial. Con 1 doc, no hay red.
2. **Saltarse la clasificación de capa en el paso 2**. Sin clasificación por capa, todas las aristas quedan sin atributo `layer` y no se puede medir "normativo vs operativo". El grafo se ve completo pero inútil.
3. **Usar `marker-pdf` cuando no hace falta**. marker-pdf es pesado (3GB+ de modelos). Para texto embebido, `pymupdf` basta. Para OCR escaneos, `tesseract` directo. marker solo si hay layouts muy complejos.
4. **Confundir Firecrawl con extractor de PDF**. Firecrawl es para web (HTML), no PDFs. El diseño original tenía este error; aquí está corregido.
5. **Dejar acentos en los nombres de nodo**. "Secretaría" y "Secretaria" se convierten en dos nodos distintos. El normalizador en `build_graph.py` los unifica (lowercase + strip accents para el ID, preserva forma original para display).
6. **Construir el grafo antes de validar las entidades**. Si el JSONL tiene entidades duplicadas o con typos, el grafo tiene nodos espurios. Validar antes.
7. **Olvidar el `user_id` en jobs multiusuario**. Si dos usuarios procesan el mismo PDF, los jobs deben distinguirse por `user_id` además de `job_id`.
8. **Usar modelo premium sin justificación**. El LLM activo de Hermes hace la conversión razonablemente bien. Solo forzar Claude/GPT-4o si la calidad con el modelo default falla los chequeos del paso 4.
9. **Comparar densidades de corpus de distinto tamaño**. La densidad no es comparable entre corpus de diferente n. Usar `edges / nodes` (densidad normalizada) o agrupar por tamaño.
10. **Releer transcripciones de entrevistas como si fueran documentos formales**. Las entrevistas tienen oralidad, Muletas, repeticiones. El extractor las trata como `layer: informal` y baja la exigencia de estructura.

## Verification checklist (por etapa)

### Etapa 1
```
[ ] <job_id>.md empieza con #
[ ] Cobertura (palabras_md / palabras_pdf) ≥ 0.85
[ ] Todas las secciones detectadas como headings tienen #
[ ] Tablas convertidas a GFM si el original las tenía
[ ] meta.json tiene prompt_version + método (text|ocr)
```

### Etapa 2
```
[ ] entities.jsonl tiene ≥ 3 entidades por documento
[ ] Cada entidad tiene type ∈ {INSTITUCION, CARGO, NORMA, DOCUMENTO, PERSONA, LUGAR}
[ ] Cada entidad tiene layer ∈ {normativo, operativo, informal}
[ ] Sección donde aparece existe en el MD
[ ] Diccionario base cargó correctamente
```

### Etapa 3
```
[ ] graph.graphml es XML válido
[ ] edges.csv y nodes.csv importan a Gephi sin errores
[ ] metrics.json tiene las 6 claves top-level
[ ] densidad entre 0 y 1
[ ] comunidades_louvain ≥ 1
[ ] Si corpus < 5 docs, advertencia explícita en métricas
```

## Support files

- `scripts/pdf_to_md.py` — extracción PDF→MD con pymupdf y fallback OCR tesseract.
- `scripts/extract_entities.py` — extracción de entidades con regex + diccionario + LLM opcional.
- `scripts/build_graph.py` — grafo NetworkX + métricas + exportación GraphML/CSV/HTML.
- `scripts/validate_pipeline.py` — corre las validaciones de las 3 etapas.
- `prompts/prompt_conversion_v1.md` — prompt base.
- `prompts/prompt_conversion_v2.md` — con manejo de tablas.
- `prompts/prompt_conversion_v3.md` — para OCR.
- `references/diccionario_gobernanza_mx.txt` — instituciones federales comunes (iniciadores, no exhaustivo).
- `schemas/job.schema.json`, `schemas/entity.schema.json`, `schemas/metrics.schema.json` — JSON Schemas.
- `examples/instanciaas_seguridad/` — ejemplo end-to-end con el PDF de prueba.
- `examples/ojs-article/` — ejemplo con un paper académico (capa normativa para contrastar).

## Licencia

MIT.