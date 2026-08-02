# Auditoría de calidad de conversiones PDF → MD

Receta operativa para auditar cada conversión producida por `pdf_to_md.py` (skill `pdf-to-knowledge-graph`, Etapa 1 del FASP). El script `scripts/audit_conversions.py` automatiza este flujo.

## Cuándo auditar

- Después de cualquier cambio al `pdf_to_md.py` o a `llm-1-parser-juridico.py`.
- Antes de un entregable formal (Anexo 1, 2, 3 firmado).
- Cuando un job produce cobertura < 0.85 o similitud < 0.85.
- Periódicamente en un corpus nuevo para calibrar los umbrales.

## Métricas y umbrales (calibrados con CSN.pdf, 2 páginas, 49.6 KB)

| Métrica | Cálculo | Umbral OK | Umbral revisar | Fuente |
|---|---|---|---|---|
| **Cobertura** | `palabras_md / palabras_pdf` | ≥ 0.85 | < 0.85 | `validation.json` |
| **Similitud de texto** | `SequenceMatcher` sobre primeros 5000 chars | ≥ 0.85 | < 0.85 | Calculada en `audit_conversions.py` |
| **Preservación de keywords** | % de palabras en MAYÚSCULAS del PDF (≥ 5 letras) que sobreviven en el MD | ≥ 0.80 | < 0.80 | Calculada en `audit_conversions.py` |
| **Issues detectados** | Cantidad de entradas en `validation.issues` | 0 | ≥ 1 | `validation.json` |
| **Score compuesto** | `0.4·cobertura + 0.3·keywords + 0.2·similitud + max(0, 10 - 2·issues)` | ≥ 85 EXCELENTE / 70 BUENO / 50 ACEPTABLE / < 50 BAJA | Calculado en `audit_conversions.py` |

**Benchmark CSN.pdf (job csn-39021)** — referencia para comparar:

| Métrica | Valor |
|---|---|
| Cobertura | 1.007 (100.7%) |
| Palabras PDF / MD | 603 / 607 |
| Similitud de texto | 0.975 |
| Preservación de keywords | 1.000 (100%) |
| Issues | 0 |
| Headings en MD | 4 (todos nivel 1) |
| **Score compuesto** | **99.78 / 100 → EXCELENTE** |

## Uso

```bash
# Auditar todos los jobs de una carpeta
python3 ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/audit_conversions.py \
    --jobs-dir /tmp/jobs/

# Auditar un job específico
python3 .../audit_conversions.py --jobs-dir /tmp/jobs/ --job-id csn-39021

# Generar JSON para integración con otros pipelines
python3 .../audit_conversions.py --jobs-dir /tmp/jobs/ --output-json /tmp/audit.json
```

El script busca el PDF original en `~/Downloads`, `~/Documents`, `~/Desktop`, y en la ruta del script. Si el job se movió de carpeta, la búsqueda agresiva lo encuentra. Si no lo encuentra, el reporte muestra la métrica de cobertura del `validation.json` pero omite similitud y keywords (porque no tiene con qué comparar).

## Parámetros de conversión por job

El reporte muestra los **parámetros de conversión** que se usaron para producir el MD. Esto es crítico para debugging porque dos jobs con la misma cobertura pueden tener causas distintas si usaron `method` o `prompt_version` diferentes.

| Parámetro | Valores posibles | Fuente |
|---|---|---|
| `method` | `text` (texto embebido) o `ocr` (tesseract) | `<job_id>.meta.json` |
| `prompt_version` | `v1` (base), `v2` (con tablas), `v3` (para OCR) | `<job_id>.meta.json` |
| `layer` | `normativo`, `operativo`, `informal` (del Plan FASP) | `<job_id>.meta.json` |
| `user_id` | quien ejecutó la conversión | `<job_id>.meta.json` |
| `filename` | nombre del PDF original | `<job_id>.meta.json` |
| `n_pages` | número de páginas del PDF | `<job_id>.meta.json` |
| `n_blocks` | bloques de texto extraídos por pymupdf | `<job_id>.meta.json` |

## Pitfalls conocidos del auditor

1. **El auditor dice `text_similarity: 0` cuando el PDF no se encuentra.** Esto NO es que la conversión sea mala — es que el script no pudo comparar con el original. Verificar primero que el PDF exista en alguna ruta accesible.

2. **`Preservación de keywords: 0` cuando hay acentos inconsistentes.** La heurística compara `palabra_mayuscula` con la versión raw del MD. Si el PDF dice `NACIONAL` y el MD dice `Nacional` (con capitalización normal de Markdown), cuenta como preservado. Pero si el PDF dice `NACIÓN` y el MD dice `NACION` (sin tilde por pérdida de encoding), cuenta como **no preservado** aunque sea la misma palabra.

3. **`Score compuesto ACEPTABLE` (50-69) no es necesariamente una conversión mala.** La métrica de similitud (SequenceMatcher) es sensible al whitespace y puntuación. Un PDF con headers de página repetidos o con layout de 2 columnas puede tener similitud ~0.6 aunque la conversión sea correcta. **Si cobertura ≥ 0.85 y keywords ≥ 0.80, la conversión probablemente es buena aunque el score baje.**

4. **El score NO detecta errores semánticos.** Un MD que tiene 100% de similitud pero reemplaza una palabra clave con un sinónimo se calificaría como EXCELENTE. La auditoría es estructural, no semántica. Para validación semántica, leer el MD y comparar con el PDF manualmente.

## Reproducir el benchmark CSN

```bash
PY=/tmp/pdfkg-venv/bin/python
PDF=/Users/adominguezdia/ComfyUI-Manager/.hermes/desktop-attachments/CSN.pdf
DB=/tmp/fasp-audit-bench.db
JOB=csn-bench
rm -f $DB
rm -rf /tmp/csn-bench
mkdir -p /tmp/csn-bench
cp "$PDF" /tmp/csn-bench/norma.pdf

$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/db_init.py --db $DB
$PY ~/.hermes/skills/productivity/pdf-to-knowledge-graph/scripts/pdf_to_md.py \
    --input /tmp/csn-bench/norma.pdf --output /tmp/csn-bench/jobs/$JOB/ --job-id $JOB --layer normativo --prompt v1
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/llm-1-parser-juridico.py \
    --md /tmp/csn-bench/jobs/$JOB/$JOB.md --db $DB
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/audit_conversions.py \
    --jobs-dir /tmp/csn-bench/jobs/ --job-id $JOB
# Esperado: score 99.78 / 100, similitud 0.975, keywords 1.0
```

Si el score baja significativamente en una corrida futura, el cambio que bajó la calidad está en `pdf_to_md.py` o `llm-1-parser-juridico.py`. Buscar diferencias en las funciones de extracción, heurísticas de heading, o regex de artículos/fracciones.
