# FASP Document Pipeline

Pipeline LLM–Python–ARS para la Evaluación Estratégica de Coordinación al **FASP** (Fondo de Aportaciones para la Seguridad Pública). Materializa la arquitectura descrita en `docs/fasp-architecture-documental.md` con:

- **9 sub-skills LLM** (LLM-1 a LLM-9): 1 funcional, 8 con prompts documentados.
- **4 scripts Python** (PY-1 a PY-4): todos funcionales.
- **BD SQLite** con esquema para los 12 anexos, taxonomías cerradas y sistema de checkpoints.
- **3 placeholders rellenados** del paquete original (architecture doc, skill, system prompt).
- **Reutiliza** `pdf-to-knowledge-graph` para la Etapa 1 (PDF → MD).

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

# 5. Validar taxonomías
python3 scripts/validate_taxonomias.py --input ./anexo2.json --tipo matriz_congruencia

# 6. Checkpoint humano
python3 scripts/checkpoint.py --db ./fasp.db --gates
python3 scripts/checkpoint.py --db ./fasp.db \
    --etapa etapa_1_documental --perfil coordinadora \
    --anexo "Anexo 1" --decision aprobado --aprobador "María López"

# 7. Etapa 2: matrices ARS (requiere aristas en BD)
python3 scripts/py-2-matrices-red.py --db ./fasp.db --output ./anexos/
python3 scripts/py-3-metricas-ars.py --db ./fasp.db --output ./anexos/

# 8. Etapa 3: exportación y replicabilidad
python3 scripts/py-4-exportacion.py --db ./fasp.db --output ./export/
```

## Estructura

```
fasp-document-pipeline/
├── SKILL.md                              # definición del skill (frontmatter + reglas)
├── README.md                             # este archivo
├── references/
│   ├── catalogo_unidades_administrativas.txt   # ~60 unidades federales/estatales
│   └── patrones_juridicos.txt                  # regex para artículos/fracciones
├── schemas/
│   ├── taxonomias.json                    # las 5 taxonomías cerradas
│   ├── checkpoints.json                   # 5 perfiles × 3 etapas
│   └── anexos/
│       ├── anexo1-ficha-tecnica-fasp.json
│       ├── anexo2-matriz-congruencia.json
│       ├── anexo3-directorio-actores.json
│       ├── anexo4-matriz-adyacencia.json
│       ├── anexo5-memoria-algoritmica.json
│       ├── anexo6-diccionario-atributos.json
│       └── anexo10-fichas-hallazgos.json
├── scripts/
│   ├── db_init.py                        # crea BD con esquema completo
│   ├── llm-1-parser-juridico.py          # ✅ FUNCIONAL
│   ├── py-1-estructuracion.py            # ✅ FUNCIONAL
│   ├── py-2-matrices-red.py              # ✅ FUNCIONAL
│   ├── py-3-metricas-ars.py              # ✅ FUNCIONAL
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
│   └── test_smoke.py                     # verifica BD + taxonomías + scripts
└── examples/
    └── (próximamente)
```

## Dependencias

- Python 3.10+
- `networkx>=3.0` — grafos y métricas ARS.
- `pdf-to-knowledge-graph` (instalado en `~/.hermes/skills/productivity/`) — para Etapa 1.

## Estado de implementación

| Componente | Estado |
|---|---|
| BD SQLite con esquema para 12 anexos | ✅ Funcional |
| Taxonomías cerradas (5 vocabularios) | ✅ Funcional |
| LLM-1 Parser jurídico (regex + keywords) | ✅ Funcional |
| LLM-2 a LLM-9 | 📋 Prompts documentados, invocación manual |
| PY-1 Estructuración | ✅ Funcional |
| PY-2 Constructor matrices ARS | ✅ Funcional |
| PY-3 Métricas ARS | ✅ Funcional |
| PY-4 Exportación | ✅ Funcional |
| Checkpoints humanos (15 gates) | ✅ Funcional |
| Validador de taxonomías | ✅ Funcional |
| Detección patrones jurídicos | ✅ Funcional |
| Catálogo de unidades administrativas | 📋 ~60 entradas base |

## Documentos del paquete original

| Archivo | Estado |
|---|---|
| `docs/fasp-architecture-documental.md` | ✅ Migrado del .docx, 179 líneas |
| `skills/fasp-document-pipeline/SKILL.md` | ✅ Operativo, 12.6 KB |
| `system/fasp-implementer-system-prompt.md` | ✅ Rol + tareas + restricciones |

## Licencia

MIT.