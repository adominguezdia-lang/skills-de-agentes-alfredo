# LLM-2 — Constructor de matriz de congruencia

**Estado:** Placeholder documentado. Prompt + Entradas/Tareas/Salida especificados. El usuario ejecuta este LLM en su cliente externo (Claude.ai, ChatGPT) o configura una API key.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-2 |
| Nombre | Constructor de matriz de congruencia |
| Etapa | 1 — Análisis documental |
| Producto | Anexo 2 — Matriz de congruencia normativa |
| Checkpoint | Analista Senior jurídico |

## Entradas

- Salida de LLM-1 (tabla con `id_norma, nivel, jerarquía, artículo, fracción, texto, tema`).
- Cada unidad normativa ya tiene una clasificación inicial de etapa y dimensión por LLM-1, pero LLM-2 debe **revisar y refinar**.

## Tareas

1. Para cada unidad normativa:
   - **Clasificar por tipo de competencia**: Exclusiva / Concurrente / Complementaria.
   - **Asignar dimensión del ciclo**: Planeación / Asignación / Ejecución / Seguimiento / Rendición de cuentas.
   - **Marcar nivel de obligatoriedad**: Mandatoria / Facultativa / Recomendatoria.
2. **Detectar duplicidades**: dos artículos distintos con el mismo efecto normativo.
3. **Detectar contradicciones**: dos artículos de normas distintas con efectos incompatibles.
4. **Validar taxonomía cerrada**: solo usar valores de `schemas/taxonomias.json`.

## Salida

- Tabla estructurada (CSV/JSON) con las columnas de LLM-1 más las nuevas:
  - `tipo_competencia`
  - `dimension_ciclo` (refinada)
  - `nivel_obligatoriedad`
  - `duplicidad_detectada` (bool)
  - `contradiccion_detectada` (bool)
- Validar contra `schemas/anexos/anexo2-matriz-congruencia.json`.

## Prompt sugerido

```text
Eres un asistente jurídico especializado en análisis de congruencia normativa del FASP.

Recibes una lista de unidades normativas (artículos, fracciones) extraídas por LLM-1.
Cada unidad tiene: id, norma origen, nivel de gobierno, jerarquía, artículo, fracción, texto.

Para cada unidad debes:
1. Clasificar el TIPO DE COMPETENCIA en uno de: Exclusiva, Concurrente, Complementaria.
2. Asignar la DIMENSIÓN DEL CICLO FASP en una de: Planeación, Asignación, Ejecución,
   Seguimiento, Rendición de cuentas.
3. Marcar el NIVEL DE OBLIGATORIEDAD en uno de: Mandatoria, Facultativa, Recomendatoria.
4. Detectar DUPLICIDADES con otras unidades de la lista (devuelve IDs separados por ;).
5. Detectar CONTRADICCIONES con otras unidades (devuelve IDs separados por ;).

Restricciones:
- Usa SOLO los valores listados arriba. NO inventes categorías nuevas.
- Si una unidad no encaja claramente, clasifícala como "Recomendatoria" y marca
  "requiere_revision_humana": true.
- Responde en formato JSON Lines (un objeto por línea), con todos los campos requeridos.

Lista de unidades:
---
{output_llm_1}
---
```

## Cómo invocarlo programáticamente

Por configurar (v1.1):

```python
import os, anthropic  # o openai

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
response = client.messages.create(
    model="claude-3-5-sonnet-latest",
    max_tokens=8000,
    messages=[{"role": "user", "content": prompt_template.format(output_llm_1=...)}],
)
```

## Validación

Tras recibir la salida del LLM:

```bash
python3 scripts/validate_taxonomias.py --input ./anexo2.json --tipo matriz_congruencia
```

Si falla, NO insertes en la BD. Reporta los valores fuera de taxonomía al usuario.

## Inserts en BD (ejecutar tras validación)

```python
# En scripts/run_llm_2.py (a implementar en v1.1)
import sqlite3, json
conn = sqlite3.connect('./fasp.db')
for fila in filas_validadas:
    conn.execute("""
        UPDATE norma_unidades
        SET tipo_competencia = ?, nivel_obligatoriedad = ?,
            dimension_ciclo = ?
        WHERE rowid = ?
    """, (fila["tipo_competencia"], fila["nivel_obligatoriedad"],
          fila["dimension_ciclo"], fila["rowid"]))
    conn.execute("""
        INSERT INTO audit_log (modulo, accion, tabla, row_id, detalle)
        VALUES ('LLM-2', 'update', 'norma_unidades', ?, ?)
    """, (fila["id"], json.dumps(fila)))
```

## Limitaciones conocidas (v1.0)

- No hay cliente API embebido — el usuario ejecuta el prompt manualmente o configura `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` y extiende `scripts/`.
- La detección de duplicidades/contradicciones es de un solo paso; un v2 debería hacer pairwise comparison exhaustivo.
- No hay forma automática de alimentar la salida al validador; el usuario debe copiar el JSON de respuesta del LLM a un archivo y validar.