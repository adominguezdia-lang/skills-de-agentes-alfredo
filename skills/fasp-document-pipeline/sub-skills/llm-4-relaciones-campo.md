# LLM-4 — Extractor de relaciones y atributos

**Estado:** Placeholder documentado.

## Identificación

| Campo | Valor |
|---|---|
| Módulo | LLM-4 |
| Nombre | Extractor de relaciones y atributos |
| Etapa | 2 — Trabajo de campo + ARS |
| Producto | Edge list preliminar (Anexo 4 entrada) |
| Checkpoint | Analista Senior redes + Analistas Junior grafos |

## Entradas

- Transcripciones de entrevistas semiestructuradas y grupos de enfoque.
- Directorio preliminar (Anexo 3) con IDs de actores.

## Tareas

1. **Reconocer actores** mencionados en las transcripciones (unidades, cargos, niveles de gobierno) y **mapearlos a los IDs del directorio**.
2. **Extraer relaciones**: quién se coordina con quién, para qué etapa del FASP, con qué frecuencia, por qué canal.
3. **Etiquetar tipo de vínculo**: Formal / Informal / Jerárquico / Operativo / Consultivo.
4. **Construir lista preliminar de aristas** con: origen, destino, tipo, peso (intensidad 0-10), direccionalidad.

## Salida

- Edge list (CSV/JSON) con columnas según `schemas/anexos/anexo4-matriz-adyacencia.json`.

## Prompt sugerido

```text
Eres un asistente especializado en análisis de redes de coordinación intergubernamental.

Recibes:
1. Un directorio de actores (cada uno con id_actor, nombre_oficial, nivel_gobierno).
2. Una o más transcripciones de entrevistas semiestructuradas con actores del FASP.

Tu tarea: extraer TODAS las relaciones de coordinación mencionadas en las transcripciones.

Para cada relación, devuelve un objeto JSON con:
- origen: id_actor (del directorio)
- destino: id_actor (del directorio)
- peso: número 0-10 según la frecuencia e intensidad mencionadas en la entrevista
- tipo_vinculo: "Formal" | "Informal" | "Jerárquico" | "Operativo" | "Consultivo"
- direccionalidad: "unidireccional" | "bidireccional"
- frecuencia: "diaria" | "semanal" | "mensual" | "trimestral" | "ocasional"
- canal: "oficial" | "informal" | "electrónico" | "presencial" | "mixto"
- etapa_ciclo: "Integración" | "Distribución" | "Administración" | "Supervisión" | "Seguimiento"
- evidencia_doc_id: id del documento de transcripción de donde se extrajo

Si un actor mencionado no está en el directorio, propón un nombre provisional y marcalo
como "actor_no_catalogado": true para revisión humana.

Directorio:
---
{directorio}
---

Transcripciones:
---
{transcripciones}
---
```

## Validación

```bash
python3 scripts/validate_taxonomias.py --input ./edge_list.json --tipo aristas
```

## Limitaciones conocidas

- Las transcripciones tienen oralidad, muletas, repeticiones. El LLM debe limpiarlas implícitamente.
- La intensidad (peso 0-10) es subjetiva. Recomendable revisión humana para outliers.
- Los actores "no catalogados" requieren actualización del directorio antes de cerrar la Etapa 2.