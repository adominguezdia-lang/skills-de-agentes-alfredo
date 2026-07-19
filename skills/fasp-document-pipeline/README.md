# FASP Document Pipeline

Pipeline LLM–Python–ARS para la Evaluación Estratégica de Coordinación al **FASP** (Fondo de Aportaciones para la Seguridad Pública). Materializa la arquitectura descrita en `docs/fasp-architecture-documental.md` con:

- **9 sub-skills LLM** (LLM-1 a LLM-9): 1 funcional, 8 con prompts documentados.
- **4 scripts Python** (PY-1 a PY-4): todos funcionales.
- **BD SQLite** con esquema para los 12 anexos, taxonomías cerradas y sistema de checkpoints.
- **Reutiliza** `pdf-to-knowledge-graph` para la Etapa 1 (PDF → MD).
- **Acoplado al Plan de Trabajo FASP 2026** (C-evalua / SESNSP): nomenclatura obligatoria, 8 entidades federativas, 14 personas del equipo, criterios formales de visualización del sociograma.

## Quick start

```bash
# 1. Instalar dependencias
pip install networkx

# 2. Inicializar la BD
python3 scripts/db_init.py --db ./fasp.db

# 3. Etapa 1: parsear una norma desde su MD
python3 scripts/llm-1-parser-juridico.py --md ./ejemplo_norma.md --db ./fasp.db

# 4. Asignar IDs únicos + generar Ficha técnica FASP (Anexo 1)
python3 scripts/py-1-estructuracion.py --db ./fasp.db --anexo1 ./anexos/anexo1.md

# 5. Validar nomenclatura de archivos generados
python3 scripts/nomenclatura.py validar ./anexos/FASP_2026_P3_MEX_INFORME_V1.0.docx

# 6. Validar taxonomías
python3 scripts/validate_taxonomias.py --input ./anexo2.json --tipo matriz_congruencia

# 7. Checkpoint humano
python3 scripts/checkpoint.py --db ./fasp.db --gates
python3 scripts/checkpoint.py --db ./fasp.db \
    --etapa etapa_1_documental --perfil coordinadora \
    --anexo "Anexo 1" --decision aprobado --aprobador "Maria Lopez"

# 8. Etapa 2: matrices ARS (requiere aristas en BD)
python3 scripts/py-2-matrices-red.py --db ./fasp.db --output ./anexos/
python3 scripts/py-3-metricas-ars.py --db ./fasp.db --output ./anexos/
python3 scripts/py-3-sociograma.py --db ./fasp.db \
    --producto P2 --edo CHI --output ./entregables/

# 9. Etapa 3: exportación y replicabilidad
python3 scripts/py-4-exportacion.py --db ./fasp.db --output ./export/
```

## Estructura

```
fasp-document-pipeline/
├── SKILL.md                              # definición del skill (frontmatter + reglas)
├── README.md                             # este archivo
├── references/
│   ├── catalogo_unidades_administrativas.txt   # ~60 unidades federales/estatales
│   ├── patrones_juridicos.txt                  # regex para artículos, fracciones
│   ├── entidades_federativas.json              # 8 estados + NAL (Plan de Trabajo)
│   ├── equipo_cevalua.json                     # 14 personas del equipo
│   ├── cronograma.json                         # fechas de entrega escalonadas
│   └── memoria_codificacion.json               # escala 0-10 + 3 criterios viz
├── schemas/
│   ├── taxonomias.json                    # 7 taxonomías cerradas (con entidades + nomenclatura)
│   ├── checkpoints.json                   # 5 perfiles × 3 etapas
│   └── anexos/                            # 9 JSON Schemas
│       ├── anexo1-ficha-tecnica-fasp.json
│       ├── anexo2-matriz-congruencia.json
│       ├── anexo3-directorio-actores.json
│       ├── anexo4-matriz-adyacencia.json
│       ├── anexo5-memoria-algoritmica.json
│       ├── anexo6-diccionario-atributos.json
│       ├── anexo10-fichas-hallazgos.json
│       ├── anexo11-ficha-tecnica-administrativa.json
│       └── anexo12-fuentes-informacion.json
├── scripts/
│   ├── db_init.py                        # crea BD con esquema completo
│   ├── llm-1-parser-juridico.py          # ✅ FUNCIONAL
│   ├── nomenclatura.py                   # ✅ FUNCIONAL — valida FASP_2026_*
│   ├── py-1-estructuracion.py            # ✅ FUNCIONAL
│   ├── py-2-matrices-red.py              # ✅ FUNCIONAL
│   ├── py-3-metricas-ars.py              # ✅ FUNCIONAL (8 métricas + geodesica_promedio)
│   ├── py-3-sociograma.py                # ✅ FUNCIONAL — 3 criterios topológicos del Plan
│   ├── py-4-exportacion.py               # ✅ FUNCIONAL
│   ├── checkpoint.py                     # ✅ FUNCIONAL
│   └── validate_taxonomias.py            # ✅ FUNCIONAL
├── sub-skills/
│   ├── llm-1-parser-juridico.md          # ✅ IMPLEMENTADO
│   ├── llm-2-matriz-congruencia.md       # 📋 prompt documentado
│   ├── llm-3-directorio-actores.md       # 📋 prompt documentado
│   ├── llm-4-relaciones-campo.md         # 📋 prompt documentado
│   ├── llm-5-normalizador-nodos.md       # 📋 prompt documentado
│   ├── llm-6-redactor-ars.md             # 📋 prompt documentado
│   ├── llm-7-triangulador.md             # 📋 prompt documentado
│   ├── llm-8-fichas-hallazgos.md         # 📋 prompt documentado
│   └── llm-9-informe-final.md            # 📋 prompt documentado
├── tests/
│   └── test_smoke.py                     # 12 tests: BD, taxonomías, nomenclatura, sociograma E2E
└── examples/
    └── (próximamente)
```

## Dependencias

- Python 3.10+
- `networkx>=3.0` — grafos y métricas ARS.
- `pdf-to-knowledge-graph` (instalado en `~/.hermes/skills/productivity/`) — para Etapa 1.
- Opcionales:
  - `matplotlib` — para sociograma en PNG (HTML no requiere).

## Estado de implementación (v1.1)

| Componente | Estado |
|---|---|
| `pdf-to-knowledge-graph` (sub-componente Etapa 1) | ✅ Funcional (reusado) |
| BD SQLite con esquema para 12 anexos | ✅ Funcional |
| Taxonomías cerradas (7 vocabularios) | ✅ Funcional (validables) |
| Nomenclatura FASP_2026 | ✅ Funcional (scripts/nomenclatura.py) |
| Referencias del Plan de Trabajo | ✅ 4 archivos JSON |
| LLM-1 Parser jurídico (regex + keywords) | ✅ Funcional |
| LLM-2 a LLM-9 | 📋 Prompts documentados, invocación manual |
| PY-1 Estructuración | ✅ Funcional |
| PY-2 Constructor matrices ARS | ✅ Funcional |
| PY-3 Métricas ARS (8 métricas) | ✅ Funcional |
| PY-3 Sociograma con criterios topológicos | ✅ Funcional |
| PY-4 Exportación | ✅ Funcional |
| Checkpoints humanos (15 gates) | ✅ Funcional |
| Validador de taxonomías | ✅ Funcional |
| Detección patrones jurídicos | ✅ Funcional |
| Catálogo de unidades administrativas | 📋 ~60 entradas base |

## Documentos del paquete original

| Archivo | Estado |
|---|---|
| `docs/fasp-architecture-documental.md` | ✅ Migrado del .docx, 179 líneas |
| `skills/fasp-document-pipeline/SKILL.md` | ✅ v1.1, acoplado al Plan de Trabajo |
| `system/fasp-implementer-system-prompt.md` | ✅ Rol + tareas + restricciones |

## Licencia

MIT.