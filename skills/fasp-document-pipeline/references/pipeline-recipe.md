# Receta del pipeline FASP en 6 pasos (CLI directo)

Ejecuta el pipeline completo sobre un PDF usando solo CLI. < 30 segundos para un PDF típico de 50 KB / 3 páginas. Asume `PY` apuntando a un Python con `pymupdf`, `networkx`, y los scripts del skill en `~/.hermes/skills/productivity/fasp-document-pipeline/scripts/`.

## Variables de entorno

```bash
PY=/path/to/python   # con pymupdf, pdfplumber, networkx
SKILL=~/.hermes/skills/productivity/fasp-document-pipeline
PKG=$HOME/.hermes/skills/productivity/pdf-to-knowledge-graph
PDF=/ruta/al/documento.pdf
DB=./fasp.db
JOB=$(uuidgen | cut -c1-12)
EDO=NAL              # MEX, CHI, MIC, TAM, HID, QRO, TAB, ZAC, o NAL
PRODUCTO=P1         # P1, P2, P3, IF
```

## Los 6 pasos

```bash
# 1. Crear la BD (idempotente; usa --reset para borrar y recrear)
$PY $SKILL/scripts/db_init.py --db $DB

# 2. Convertir PDF a Markdown (reutiliza pdf-to-knowledge-graph)
mkdir -p ./jobs/$JOB
$PY $PKG/scripts/pdf_to_md.py --input $PDF --output ./jobs/$JOB/ \
    --job-id $JOB --layer normativo --prompt v1
# Salidas: ./jobs/$JOB/$JOB.md (MD limpio), .meta.json, .layout.json

# 3. Parser jurídico (LLM-1) — segmenta el MD en unidades normativas
$PY $SKILL/scripts/llm-1-parser-juridico.py \
    --md ./jobs/$JOB/$JOB.md --db $DB
# Inserta filas en normas y norma_unidades

# 4. Generar Ficha técnica FASP (Anexo 1) + asignar IDs únicos
$PY $SKILL/scripts/py-1-estructuracion.py \
    --db $DB --anexo1 ./anexo1_ficha_tecnica.md
# Asigna IDs hash a actores, genera Anexo 1 con estadísticas

# 5. Validar nomenclatura del archivo generado
$PY $SKILL/scripts/nomenclatura.py construir \
    --producto $PRODUCTO --edo $EDO --tipo INFORME \
    --version V1.0 --ext .md
# Renombra tu archivo a ese nombre (mv ./anexo1_ficha_tecnica.md <salida>)

# 6. Registrar firma humana (checkpoints)
$PY $SKILL/scripts/checkpoint.py --db $DB \
    --etapa etapa_1_documental --perfil coordinadora \
    --anexo "Anexo 1" --decision aprobado --aprobador "Janett Salvador Martinez"
$PY $SKILL/scripts/checkpoint.py --db $BD \
    --etapa etapa_1_documental --perfil analista_senior_juridico \
    --anexo "Anexo 2" --decision aprobado --aprobador "Diana Valadez Rovelo"
# Antes de avanzar a Etapa 2: AMBOS checkpoints deben estar aprobados
```

## Verificación final

```bash
# Ver métricas y estado
$PY $SKILL/scripts/fasp_dashboard.py --db $DB --output ./dashboard.html
open ./dashboard.html

# Ver conteos rápidos en BD
sqlite3 $DB "SELECT 'normas', COUNT(*) FROM normas UNION ALL
              SELECT 'unidades', COUNT(*) FROM norma_unidades UNION ALL
              SELECT 'checkpoints_aprobados', COUNT(*) FROM checkpoints WHERE decision='aprobado';"
```

## Para procesar N PDFs en batch

```bash
# Escanear carpeta y crear manifest (paso 1 de batch)
$PY $PKG/scripts/pdf_to_md.py --scan /ruta/corpus/ --output ./jobs/

# Editar ./jobs/manifest.json y llenar 'layer' por documento

# Procesar cada PDF
for pdf in /ruta/corpus/*.pdf; do
    # ...
done

# Validar todos los jobs al final
$PY $SKILL/tests/test_smoke.py
```

## Tiempos esperados

| Paso | PDF típico (50 KB, 3 pgs) | PDF grande (5 MB, 100 pgs) |
|---|---|---|
| db_init | < 1 s | < 1 s |
| pdf_to_md | 1-2 s | 30-60 s |
| llm-1-parser | < 1 s | 5-10 s |
| py-1-estructuracion | < 1 s | < 1 s |
| nomenclatura | < 1 s | < 1 s |
| checkpoint (×2) | < 1 s | < 1 s |
| **TOTAL** | **< 5 s** | **~1 min** |

## Errores comunes (ver `references/common-errors.md` para más)

- `IntegrityError: CHECK constraint failed: etapa_ciclo IN ...` → usaste `"Distribucion"` en vez de `"Distribución"`. El constraint exige tildes.
- `Schema validation failed` → tu JSON de salida no respeta el schema del anexo. Revisa `schemas/anexos/anexoN-*.json`.
- `No se encontro el PDF` → verifica que `--input` apunte a un archivo existente y legible.

## Cuándo NO usar este receta

- Si necesitas redactar narrativa (Producto 2 hallazgos, Producto 3 Informe Final) → usa el perfil `fasp-bedrock` con Claude Sonnet 4.5 vía AWS Bedrock. El LLM agrega valor cualitativo que los scripts CLI no pueden.
- Si el PDF es un escaneo sin texto embebido → usa `--force-ocr` en el paso 2 (requiere `tesseract` instalado vía `brew install tesseract tesseract-lang`).

## Para usar desde Claude (Bedrock)

```bash
fasp-bedrock chat -q "Procesa /tmp/norma.pdf con el skill fasp-document-pipeline. Usa el venv /tmp/pdfkg-venv/bin/python para los scripts. Para los pasos de redaccion (LLM-6, LLM-9) usa tu propio criterio." --tools 'terminal,file'
```

⚠️ Bedrock añade 5-15s de latencia por tool call. Para los 6 pasos mecánicos del CLI, usa esta receta directamente. Para revisión/supervisión con interpretación, usa Bedrock.