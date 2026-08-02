# Errores comunes en el pipeline FASP

Recopilación de errores observados durante la sesión de desarrollo del skill, con su causa raíz y la solución concreta.

## IntegrityError: CHECK constraint failed

**Síntoma:**
```
sqlite3.IntegrityError: CHECK constraint failed: etapa_ciclo IN ('Integración','Distribución','Administración','Supervisión','Seguimiento')
sqlite3.IntegrityError: CHECK constraint failed: tipo_vinculo IN ('Formal','Informal','Jerárquico','Operativo','Consultivo')
sqlite3.IntegrityError: CHECK constraint failed: nivel IN ('Federal','Estatal','Municipal')
```

**Causa raíz:** Insertaste un valor sin tilde o con acento incorrecto en alguna columna con `CHECK` constraint. Los valores válidos están en `schemas/taxonomias.json` y se usan literalmente en `scripts/db_init.py`:

```python
CHECK (nivel IN ('Federal','Estatal','Municipal'))
CHECK (etapa_ciclo IN ('Integración','Distribución','Administración','Supervisión','Seguimiento'))
CHECK (tipo_vinculo IN ('Formal','Informal','Jerárquico','Operativo','Consultivo'))
CHECK (tipo_competencia IN ('Exclusiva','Concurrente','Complementaria'))
CHECK (nivel_obligatoriedad IN ('Mandatoria','Facultativa','Recomendatoria'))
CHECK (naturaleza IN ('Formal','Informal'))
CHECK (direccionalidad IN ('unidireccional','bidireccional'))
CHECK (frecuencia IN ('diaria','semanal','mensual','trimestral','ocasional'))
CHECK (canal IN ('oficial','informal','electrónico','presencial','mixto'))
```

**Solución:** Copia el valor exacto del schema. Errores típicos:
- `"Jerarquico"` → debe ser `"Jerárquico"`
- `"Distribucion"` → `"Distribución"`
- `"Electronico"` → `"electrónico"` (canal va con tilde)

**Prevención:** Si escribes un script Python que inserte valores de taxonomía, usa una constante:

```python
ETAPAS_FASP = ["Integración", "Distribución", "Administración", "Supervisión", "Seguimiento"]
TIPOS_VINCULO = ["Formal", "Informal", "Jerárquico", "Operativo", "Consultivo"]
```

O lee del schema:

```python
import json
tax = json.loads(open("schemas/taxonomias.json").read())
TIPOS_VINCULO = tax["tipos_vinculo_ars"]
```

## No such column / table missing

**Síntoma:**
```
sqlite3.OperationalError: no such table: aristas
sqlite3.OperationalError: no such column: edo
```

**Causa raíz:** No ejecutaste `db_init.py` antes de los otros scripts, o creaste la BD con una versión vieja del schema.

**Solución:**

```bash
# Si la BD está corrupta o desactualizada:
rm fasp.db
python3 scripts/db_init.py --db ./fasp.db
```

**Si modificas el schema** (añades columnas, cambias CHECK constraints, renombras tablas), añade un mecanismo de migración. La versión actual no lo tiene; si lo necesitas, crea `scripts/db_migrate.py` con una lista de migraciones incrementales.

## FileNotFoundError en scripts

**Síntoma:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/Users/.../fasp.db'
FileNotFoundError: [Errno 2] No such file or directory: '/Users/.../jobs/abc/abc.md'
```

**Causa raíz:** Pasaste una ruta absoluta que no existe, o la BD no fue inicializada, o el PDF no fue procesado por `pdf_to_md.py` antes de pasar el MD a `llm-1-parser-juridico.py`.

**Solución — checklist:**

1. ¿Existe `$DB`? `ls -la $DB`
2. ¿Existe el MD? `ls -la ./jobs/$JOB/$JOB.md`
3. ¿El job_id del paso 2 (pdf_to_md) coincide con el del paso 3 (llm-1)?

## Nomenclatura inválida

**Síntoma:**
```
✗ FASP_2026_P99_XXX_INFORME_V1.0.docx: No cumple el patron FASP_2026_PROD_EDO_TIPO_Vx.y.ext
```

**Causa raíz:** Al menos un campo del nombre está fuera de los enums válidos:
- `PRODUCTO` debe ser `P1`, `P2`, `P3`, o `IF`
- `EDO` debe ser uno de los 9 códigos (MEX/CHI/MIC/TAM/HID/QRO/TAB/ZAC/NAL)
- `TIPO_ARCHIVO` debe ser `INFORME`, `MAT_ADY`, `MAT_INC`, `DIC_NODOS`, `SCRIPT`, o `BBDD`
- `VERSION` debe tener formato `V\d+\.\d+` (ej. `V1.0`, `V2.3`)
- `EXT` debe ser una de: `.docx`, `.pdf`, `.csv`, `.xlsx`, `.py`, `.md`, `.txt`, `.html`, `.png`, `.json`

**Solución:** usa `scripts/nomenclatura.py construir --producto P1 --edo CHI ...` para generar el nombre válido.

## LLM-1 clasifica unidades transversales con etapa única

**Síntoma:** Una unidad normativa sobre el CSN, SESNSP, Comités de Coordinación, o cualquier órgano que coordina **todas** las etapas del FASP queda etiquetada con una sola etapa (la que tiene el score más alto de palabras clave).

**Causa raíz:** `llm-1-parser-juridico.py` usa `max(scores, key=scores.get)` para asignar la etapa, lo que produce clasificación monoetiqueta. Para órganos institucionales transversales esto es incorrecto.

**Solución:** marca manualmente o re-etiqueta en SQL:

```sql
-- Identificar unidades transversales candidatas
SELECT id, id_norma, articulo, texto
FROM norma_unidades
WHERE texto LIKE '%Consejo%'
   OR texto LIKE '%Comit%Cordinaci%'
   OR texto LIKE '%Secretariado Ejecutivo%'
   OR texto LIKE '%Seguimiento%';
```

**Workaround hasta que LLM-2 esté implementado:** el parser detecta el problema pero no lo arregla automáticamente. Etiquetar manualmente las que correspondan a las 5 etapas.

**Fix definitivo (cuando LLM-2 esté implementado):** LLM-2 debe detectar estas unidades y asignar `etapa_ciclo_fasp = NULL` o un campo nuevo `etapas_ciclo_fasp = ["Integración", "Distribución", ...]` que represente multi-etiqueta. Mientras tanto, documentar el hallazgo en `audit_log` vía el campo `detalle`.

## Dashboard no muestra gates actualizados

**Síntoma:** Generas el dashboard pero los gates siguen apareciendo como "PENDIENTE" aunque ya firmaste checkpoints.

**Causa:** El dashboard lee el **último estado por gate** usando:
```sql
SELECT decision, aprobador, fecha FROM checkpoints
WHERE etapa = ? AND perfil = ? ORDER BY id DESC LIMIT 1
```

Esto funciona SI los nombres `etapa` y `perfil` en tus INSERTs coinciden **exactamente** con los del array `PIPELINE_GATES` del script.

**Valores válidos de `etapa`:**
- `etapa_1_documental`
- `etapa_2_campo_ars`
- `etapa_3_triangulacion`

**Valores válidos de `perfil`:**
- `coordinadora`
- `analista_senior_juridico`
- `analista_senior_redes`
- `analistas_junior_grafos`
- `coordinacion_evaluacion`

Si escribiste `Etapa 1` con espacio y mayúscula en vez de `etapa_1_documental`, el dashboard no encuentra el gate.

**Solución:** usa el script `checkpoint.py` en vez de INSERTs manuales:

```bash
python3 scripts/checkpoint.py --db fasp.db \
    --etapa etapa_1_documental --perfil coordinadora \
    --anexo "Anexo 1" --decision aprobado --aprobador "Nombre Apellido"
```

## El zip del skill no incluye los archivos nuevos

**Síntoma:** Modificas `scripts/fasp_dashboard.py`, lo pruebas localmente, pero cuando publicas el zip `fasp-document-pipeline.zip` y otro usuario lo instala, le falta la versión nueva.

**Causa raíz:** Empaquetaste desde un directorio viejo (ej. `/tmp/pdf-to-knowledge-graph/`) en vez del directorio del skill (`/tmp/fasp-document-pipeline/`).

**Solución:** siempre ejecuta el flujo en este orden:

1. Edita en `~/.hermes/skills/productivity/fasp-document-pipeline/`
2. `cp -r ~/.hermes/skills/... /tmp/fasp-document-pipeline`
3. `cd /tmp && zip -qr fasp-document-pipeline.zip fasp-document-pipeline/`
4. Verifica: `unzip -l fasp-document-pipeline.zip | grep <archivo_nuevo>`
5. Publica en GitHub y propaga a Downloads

Si modificas `~/.hermes/skills/...` directamente sin re-empaquetar, el zip queda con la versión anterior.

## `normas.fuente` no es el nombre del job; es el nombre del MD

**Síntoma:**
- `fasp_dashboard.py` o `norms_list.py` no encuentra el MD asociado a una norma (devuelve "Sin MD" / `available: false` aunque el MD existe en el filesystem).
- Coincidencias que fallan: `jd.name == id_documento` (no coincide), `meta.filename in normas.fuente` (no coincide porque `fuente` es el MD, no el PDF).

**Causa raíz:** `llm-1-parser-juridico.py` inserta en `normas.fuente` el `md_path.name` (ej. `"csn-39021.md"`), no el nombre del job ni el nombre del PDF. Y el `id_documento` de la tabla `normas` se genera con `make_id(md_path.name)`, dando algo como `NOR-5F97B713703B` que no tiene relación con el nombre del job.

**Cómo se hace bien el lookup en `fasp_dashboard.py` y `norms_list.py`:**

```python
# Construir lista de IDs candidatos para el job
candidates_id = []
for key in ("id_documento", "id_norma"):
    v = norma.get(key)
    if v:
        candidates_id.append(v)

# La fuente es el nombre del MD → strip .md para obtener el nombre del job
fuente = norma.get("fuente", "")
if fuente:
    if fuente.endswith(".md"):
        candidates_id.append(fuente[:-3])  # "csn-39021.md" → "csn-39021"
    else:
        candidates_id.append(fuente)

# Buscar job_dir por nombre
for jd in base.iterdir():
    if jd.is_dir() and jd.name in candidates_id:
        md_path = next(iter(jd.glob("FASP_2026_*.md")), None) or next(iter(jd.glob("*.md")), None)
        ...
```

**Lección acoplada:** Cualquier script que necesite cruzar `BD.normas` con archivos del filesystem tiene que pasar por el strip `.md` de `fuente`. No confíes en `id_documento` ni en `id_norma` para encontrar el job dir — son IDs internos de la BD, no nombres de archivo.

## `git push` falla por timeout del shell

**Síntoma:** el comando `git push origin main` excede los 180s del timeout de `terminal` en sesiones largas, especialmente con repos clonados a `/tmp/`.

**Causa raíz:** el timeout de 180s del shell es generoso para un commit, pero si el repo es grande o la red está lenta, no alcanza.

**Solución:** ejecutar el push en comandos separados y cortos:

```bash
# Paso 1: stage
cd /tmp/gh-work && git add skills/fasp-document-pipeline && git status --short

# Paso 2: commit
git commit -m "feat(skill): ..."

# Paso 3: push (puede ser lento)
git push origin main
```

Si el push sigue fallando, considera:
- Subir el repo a una ruta persistente (`~/gh-work` en vez de `/tmp/gh-work`).
- Hacer push desde la GUI de GitHub Desktop.
- Hacer push de un commit con menos archivos (más frecuente).