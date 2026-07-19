# LLM-1 — Parser jurídico-documental

**Estado:** ✅ FUNCIONAL (implementado en `scripts/llm-1-parser-juridico.py`).

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-1 |
| Nombre | Parser jurídico-documental |
| Etapa | 1 — Análisis documental |
| Producto | Tabla `normas` y `norma_unidades` en BD |
| Checkpoint | (previo al de LLM-2) |

## Entradas

- MD generado por `pdf-to-knowledge-graph` (o cualquier MD de norma).
- Tipos: normas federales, estatales y municipales; convenios FASP; manuales; lineamientos.

## Tareas

1. Extraer metadatos: nombre de norma, nivel de gobierno, jerarquía, vigencia.
2. Segmentar en unidades normativas (artículos, fracciones, incisos).
3. Etiquetar cada unidad por tema de coordinación y etapa del ciclo FASP (Integración, Distribución, Administración, Supervisión, Seguimiento).

## Salida

- Tabla estructurada (CSV/JSON) con campos:
  - `id_norma`, `nivel`, `jerarquía`, `artículo`, `fracción`, `texto`, `tema`,
    `etapa_ciclo_fasp`, `dimension_ciclo`, `tipo_competencia`, `nivel_obligatoriedad`.
- Alimenta la matriz de congruencia (LLM-2).

## Uso

```bash
python3 scripts/llm-1-parser-juridico.py --md ./jobs/<job_id>/<job_id>.md --db ./fasp.db
```

## Implementación v1.0

Usa **regex + heurísticas de palabras clave**, no un LLM externo. Esto lo hace:

- **Reproducible**: misma entrada → misma salida.
- **Auditable**: cada clasificación viene de una palabra clave explícita.
- **Sin costo de API**.
- **Limitado**: no captura ironía, sarcasmo, contexto implícito.

## Limitaciones

- Heurística de palabras clave para etapa/dimensión puede equivocarse en textos ambiguos. LLM-2 refina la clasificación con mejor contexto.
- La detección de vigencia ("Vigente desde 2009") es regex simple; un LLM externo podría extraer fechas más sofisticadas.
- Sin soporte para tablas en el MD (las tablas jurídicas complejas se manejan mejor con un LLM).

## Mejoras futuras (v1.1+)

- Cliente API integrado (Anthropic, OpenAI, Ollama) opcional.
- Detección de vigencia con LLM.
- Manejo de tablas jurídicas.
- Soporte para notas al pie y referencias cruzadas entre artículos.