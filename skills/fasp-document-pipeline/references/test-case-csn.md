# Caso de prueba: CSN.pdf (Consejo de Seguridad Nacional)

PDF de prueba ejecutado contra el skill FASP el 2026-07-18. Sirve como referencia reproducible para validar que el pipeline funciona después de cambios al skill.

## Metadata del caso

| Campo | Valor |
|---|---|
| Archivo fuente | `.hermes/desktop-attachments/CSN.pdf` |
| Tamaño | 49.6 KB |
| Páginas | 2 |
| Capa FASP esperada | `normativo` |
| Jerarquía detectada | `Lineamiento` (realmente es un acuerdo del CSN, pero la heurística lo clasifica así) |
| Etapa FASP asignada por LLM-1 | `Integración` (incorrecto — el CSN es transversal) |

## Resultado del pipeline

```
PDF → MD:              39 bloques, cobertura 1.007
LLM-1:                 1 norma NOR-F8BCF94D0C6E, 1 unidad normativa
PY-1 (Anexo 1):        Ficha FASP-2026-EVAL-2026 generada
Nomenclatura:          FASP_2026_P1_NAL_INFORME_V1.0.md
Checkpoint:            aprobado por Coordinadora (Janett Salvador Martínez)
BD final:              1 norma, 1 unidad, 1 checkpoint, 2 audit_log entries
```

## Actores federales del CSN identificados en el MD

| Actor | Menciones | Rol en el CSN |
|---|---|---|
| SECRETARÍA DE SEGURIDAD Y PROTECCIÓN CIUDADANA | 2× | Secretario Ejecutivo |
| SECRETARÍA DE COMUNICACIONES Y TRANSPORTES | 1× | Integrante del Consejo |
| FISCALÍA GENERAL DE LA REPÚBLICA | 1× | Integrante del Consejo |
| CENTRO NACIONAL DE INTELIGENCIA | 1× | Integrante del Consejo |
| PRESIDENCIA DE LA REPÚBLICA | 0× match literal | (Presidente del Consejo, mencionado como "titular del Ejecutivo Federal") |

## Hallazgo que dio lugar al pitfall #10 del SKILL.md

LLM-1 clasificó `etapa_ciclo_fasp = "Integración"` para la única unidad extraída del CSN. Esto es **incorrecto** porque el CSN coordina las 5 etapas del ciclo FASP simultáneamente — es un órgano transversal de coordinación interinstitucional. La clasificación inicial por keywords solo es monoetiqueta por construcción.

**Detección**: el texto del CSN contiene palabras como "integración", "coordinación", "evaluación", "seguimiento" — todas etapas del ciclo. El score máximo fue "Integración" pero conceptualmente la unidad pertenece a las 5 etapas.

**Mitigación actual** (mientras LLM-2 no está implementado):
- Detectar manualmente: si el texto menciona "Consejo", "Comité", "Coordinación", "Secretariado" o más de 3 etapas del ciclo en el mismo párrafo, marcar como transversal.
- Actualizar `norma_unidades.etapa_ciclo_fasp` con todas las 5 etapas separadas por comas (el schema permite esto si se cambia de TEXT a TEXT con validación).

**Mitigación futura** (cuando LLM-2 se implemente):
- LLM-2 debe identificar unidades transversales y asignar las 5 etapas simultáneamente.

## Cómo reproducir el caso

```bash
PY=/tmp/pdfkg-venv/bin/python
PDF=/Users/adominguezdia/ComfyUI-Manager/.hermes/desktop-attachments/CSN.pdf
DB=/tmp/fasp-csn-test.db
JOB=csn-$(date +%s | tail -c 6)

# Limpiar
rm -f $DB
rm -rf /tmp/csn-test
mkdir -p /tmp/csn-test
cp "$PDF" /tmp/csn-test/norma.pdf

# Pipeline
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/db_init.py --db $DB
$PY ~/.hermes/skills/productivity/pdf-to-knowledge-graph/scripts/pdf_to_md.py \
    --input /tmp/csn-test/norma.pdf --output /tmp/csn-test/jobs/$JOB/ --job-id $JOB \
    --layer normativo --prompt v1
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/llm-1-parser-juridico.py \
    --md /tmp/csn-test/jobs/$JOB/$JOB.md --db $DB
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/py-1-estructuracion.py \
    --db $DB --anexo1 /tmp/csn-test/anexo1_ficha_tecnica.md --id-evaluacion EVAL-2026
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/nomenclatura.py \
    construir --producto P1 --edo NAL --tipo INFORME --version V1.0 --ext .md
$PY ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/checkpoint.py \
    --db $DB --etapa etapa_1_documental --perfil coordinadora \
    --anexo "Anexo 1" --decision aprobado --aprobador "Janett Salvador Martinez"

# Verificar
sqlite3 $DB "SELECT COUNT(*) FROM normas"           # → 1
sqlite3 $DB "SELECT COUNT(*) FROM norma_unidades"   # → 1
sqlite3 $DB "SELECT COUNT(*) FROM checkpoints"      # → 1
```