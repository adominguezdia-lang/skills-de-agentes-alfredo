# LLM-3 — Generador del directorio preliminar de actores

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-3 |
| Nombre | Generador del directorio preliminar de actores |
| Etapa | 1 — Análisis documental |
| Producto | Anexo 3 — Directorio preliminar de actores |
| Checkpoint | Coordinadora + Analista Senior jurídico |

## Entradas

- Normas clasificadas por LLM-2.
- Convenios FASP.
- Catálogo base de unidades administrativas (`references/catalogo_unidades_administrativas.txt`).

## Tareas

1. Identificar unidades administrativas federales, estatales y municipales con atribuciones en alguna etapa del FASP (Integración / Distribución / Administración / Supervisión / Seguimiento).
2. Para cada actor:
   - Nombre oficial completo
   - Nivel de gobierno (Federal / Estatal / Municipal)
   - Entidad federativa (si Estatal)
   - Naturaleza (Formal / Informal)
   - Funciones principales
   - Etapas del ciclo en que participa
   - Norma que lo sustenta
   - Alias conocidos (siglas, nombres cortos)

## Salida

- Base de datos editable (CSV/XLSX) con columnas según `schemas/anexos/anexo3-directorio-actores.json`.
- Validar contra la taxonomía cerrada (`schemas/taxonomias.json`).

## Prompt sugerido

```text
Eres un asistente especializado en estructura orgánica del Estado mexicano.

A partir de las normas listadas abajo y del catálogo base de unidades administrativas
que también te proporciono, identifica TODAS las unidades administrativas (federales,
estatales, municipales) con atribuciones en alguna etapa del FASP (Integración,
Distribución, Administración, Supervisión, Seguimiento).

Para cada actor, devuelve un objeto JSON con:
- nombre_oficial (string, tal como aparece en la norma)
- nivel_gobierno: "Federal" | "Estatal" | "Municipal"
- entidad_federativa (string, solo si Estatal; "" si Federal o Municipal)
- naturaleza: "Formal" (en norma) | "Informal" (mencionado pero sin atribución expresa)
- funciones (array de strings, extraídas literalmente de la norma)
- etapas_ciclo_participa (array de: "Integración" | "Distribución" | "Administración" | "Supervisión" | "Seguimiento")
- mapeado_a_id_norma (array de IDs de norma origen)
- alias_conocidos (array de siglas o nombres cortos)

Usa SOLO los valores listados. NO inventes categorías.

Catálogo base:
---
{catalogo}
---

Normas clasificadas (salida de LLM-2):
---
{output_llm_2}
---
```

## Validación

```bash
python3 scripts/validate_taxonomias.py --input ./anexo3.json --tipo directorio_actores
```

## Limitaciones conocidas (v1.0)

- Para una evaluación completa se necesitan ~150+ actores; el catálogo base incluye ~60 federales/estatales. El usuario debe extender el catálogo antes de invocar el LLM.
- La distinción Formal/Informal es delicada y depende de si la atribución está literalmente en una norma o se infiere del contexto. Recomendable revisión humana para casos ambiguos.
- No hay detección automática de duplicados; el LLM puede proponer el mismo actor con dos nombres. PY-1 los unifica vía hash + alias.