# LLM-5 — Normalizador de nodos

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-5 |
| Nombre | Normalizador de nodos |
| Etapa | 2 — Trabajo de campo + ARS |
| Producto | Diccionario de nodos unificado |
| Checkpoint | Analistas Junior grafos |

## Entradas

- Edge list preliminar de LLM-4.
- Directorio de actores (Anexo 3).

## Tareas

1. **Detectar duplicados semánticos**: "SSPC" vs "Secretaría de Seguridad y Protección Ciudadana".
2. **Detectar variantes**: "Fiscalía del Estado de México" vs "FEM" vs "Fiscalía Edomex".
3. **Proponer unificación**: cada nodo debe corresponder a una única unidad administrativa.
4. **Mantener trazabilidad**: el nodo original no se borra, se marca como alias.

## Salida

- Diccionario de nodos con IDs unificados.
- Tabla `actores` con campo `alias_conocidos` poblado.

## Prompt sugerido

```text
Recibes:
1. Una lista de actores únicos (con id_actor, nombre_oficial, alias_conocidos si los hay).
2. Una lista de aristas (origen, destino) que pueden mencionar actores con nombres
   ligeramente distintos a los del catálogo.

Tu tarea:
1. Para cada arista, identificar si el origen o destino corresponde a un actor del catálogo,
   a una variante (alias conocido), o a un actor nuevo.
2. Si es variante, proponer la normalización al id del catálogo.
3. Si es actor nuevo, proponer un nuevo id_actor (formato: ACT-XXXXXXXXXX) y dejarlo
   marcado como "requiere_revision_humana": true.

Devuelve una lista de objetos JSON con los reemplazos propuestos:
- arista_id
- campo ("origen" | "destino")
- valor_actual
- valor_normalizado (id_actor del catálogo o null si es nuevo)
- es_alias_conocido (bool)
- es_nuevo (bool)
- requiere_revision_humana (bool)
```

## Validación

Post-LLM, ejecutar:
```bash
python3 scripts/py-1-estructuracion.py --db ./fasp.db --solo-ids
```

Esto unifica los IDs y registra los duplicados como alias.