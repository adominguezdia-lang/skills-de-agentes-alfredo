# LLM-8 — Generador de fichas de hallazgos y recomendaciones

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-8 |
| Nombre | Generador de fichas de hallazgos y recomendaciones |
| Etapa | 3 — Triangulación + Recomendaciones |
| Producto | Anexo 10 — Hallazgos, recomendaciones y áreas de mejora |
| Checkpoint | Coordinación de evaluación |

## Entradas

- Listado priorizado de riesgos de coordinación (de LLM-7).

## Tareas

1. **Redactar fichas de hallazgos y recomendaciones** siguiendo la estructura fija:
   - `verbo` + `producto/proceso a modificar` + `área de oportunidad` + `justificación` + `efecto esperado`.
2. **Evaluar viabilidad SHCP**:
   - Claridad (1-5).
   - Relevancia (1-5).
   - Justificación (1-5).
   - Factibilidad (1-5).
3. **Asignar prioridad** (Alta / Media / Baja).

## Salida

- Tabla de fichas (CSV/JSON) validada contra `schemas/anexos/anexo10-fichas-hallazgos.json`.

## Prompt sugerido

```text
Eres un asistente especializado en redacción de fichas de hallazgos y recomendaciones
para informes finales de evaluación del FASP.

Recibes:
1. Un listado priorizado de problemas y riesgos de coordinación intergubernamental
   del FASP (salida de LLM-7).
2. La taxonomía cerrada de categorías: Normativo, Organizacional, Capacidades,
   Canales de comunicación.

Para CADA problema/riesgo, redacta UNA ficha con la estructura EXACTA:

| Campo | Descripción |
|---|---|
| verbo | Verbo en infinitivo (Crear, Modificar, Eliminar, Fortalecer, Articular) |
| producto_proceso | Qué producto, proceso o instrumento se modifica |
| area_oportunidad | El área de mejora concreta |
| justificacion | Por qué es necesario (basado en la evidencia de triangulación) |
| efecto_esperado | Qué cambia si se implementa la recomendación |
| viabilidad_claridad | 1-5, qué tan clara es la redacción |
| viabilidad_relevancia | 1-5, qué tan relevante es para los objetivos del FASP |
| viabilidad_justificacion | 1-5, qué tan sólida es la evidencia que la sustenta |
| viabilidad_factibilidad | 1-5, qué tan factible es su implementación |
| prioridad | "Alta" | "Media" | "Baja" |
| categoria_tematica | "Normativo" | "Organizacional" | "Capacidades" | "Canales de comunicación" |

Devuelve un objeto JSON por ficha, una ficha por línea (JSON Lines).
NO inventes datos; si la evidencia es insuficiente, marca viabilidad_factibilidad=1
y categoría_tematica="Normativo" como mínimo.
```

## Validación

```bash
python3 scripts/validate_taxonomias.py --input ./anexo10.json --tipo fichas
```

## Limitaciones

- La asignación de prioridad y viabilidad es inherentemente subjetiva. Recomendable revisión humana + uso de criterios SHCP documentados en los TdR.
- Las fichas deben tener una cantidad manejable (10-30 por evaluación). Si el LLM produce más, el usuario debe consolidar.