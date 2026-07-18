# pdf-to-knowledge-graph

Pipeline de 3 etapas para convertir PDFs de gobernanza en grafos analizables, contrastando 3 capas (normativo / operativo / informal). Diseñado para columnas de análisis de gobernanza donde interesa medir la conexión entre ley → reglamento → oficio → práctica real.

## Quick start

```bash
# 1. Escanear carpeta con PDFs y crear manifest
python3 scripts/pdf_to_md.py --scan ./mi_corpus/ --output ./jobs/

# 2. Editar ./jobs/manifest.json — llenar 'layer' (normativo/operativo/informal) por documento

# 3. Procesar todos (un job por PDF)
for pdf in ./mi_corpus/*.pdf; do
    python3 scripts/pdf_to_md.py --input "$pdf" --output ./jobs/<job_id>/ --layer operativo
done

# 4. Extraer entidades de cada MD
python3 scripts/extract_entities.py --md ./jobs/<id>/<id>.md --meta ./jobs/<id>/<id>.meta.json --output ./jobs/<id>/

# 5. Construir el grafo
python3 scripts/build_graph.py --corpus ./jobs/ --output ./grafo/

# 6. Visualizar
open ./grafo/graph.html
```

## Estructura

```
pdf-to-knowledge-graph/
├── SKILL.md                       # documentación completa + reglas + pitfalls
├── README.md                      # este archivo
├── prompts/
│   ├── prompt_conversion_v1.md    # base
│   ├── prompt_conversion_v2.md    # con tablas
│   └── prompt_conversion_v3.md    # para OCR
├── references/
│   └── diccionario_gobernanza_mx.txt   # instituciones + leyes federales comunes
├── schemas/
│   ├── job.schema.json
│   ├── entity.schema.json
│   └── metrics.schema.json
├── scripts/
│   ├── pdf_to_md.py               # Etapa 1
│   ├── extract_entities.py        # Etapa 2
│   ├── build_graph.py             # Etapa 3
│   └── validate_pipeline.py       # corre todas las validaciones
└── examples/
    └── instanciaas_seguridad/     # ejemplo end-to-end
```

## Cuándo analizar (regla clave)

| Etapa | Análisis válido | Por qué |
|---|---|---|
| T0 → T1 | Ninguno. Solo limpieza textual. | Sin texto limpio no hay entidades fiables. |
| T1 → T2 | Tampoco. Aquí extraes entidades. | Sin entidades no hay nodos. |
| T2 → T3 | **Sí. Aquí construyes el grafo.** | Las relaciones emergen con ≥ 5 documentos. |
| Post-T3 | Iterar si hay silos. | Métricas son diagnóstico, no fin. |

**Recomendación**: no construir el grafo con menos de 5 documentos. Con 1-3 docs el grafo es trivial.

## Dependencias

```bash
pip install pymupdf networkx
# tesseract binario (macOS) — opcional, solo para PDFs escaneados:
brew install tesseract tesseract-lang
# pyvis opcional para visualización interactiva:
pip install pyvis
```

Ver `requirements.txt` para versiones mínimas probadas.

## Salidas

Por job (`<job_id>/`):
- `<job_id>.md` — Markdown limpio
- `<job_id>.meta.json` — metadata + prompt_version
- `<job_id>.layout.json` — bloques con tamaños de fuente
- `<job_id>.validation.json` — chequeos de cobertura
- `entities.jsonl` — entidades extraídas (Etapa 2)
- `entities.validation.json` — chequeos de entidades

Globales (`grafo/`):
- `graph.graphml` — grafo importable a Gephi/Cytoscape
- `nodes.csv` / `edges.csv` — tablas para análisis tabular
- `metrics.json` — densidad, centralidad, comunidades, actores transversales
- `graph.html` — visualización (PyVis interactivo o tabla fallback)

## Licencia

MIT.