# Patrón de directorios de trabajo

El skill fasp-document-pipeline se **instala en `~/.hermes/skills/productivity/fasp-document-pipeline/`** pero los archivos de trabajo (PDFs, jobs/, BD) viven en directorios distintos del usuario.

## Directorios de uso confirmado (este proyecto)

| Tipo | Ruta | Quién la usa |
|---|---|---|
| Skill (instalación) | `~/.hermes/skills/productivity/fasp-document-pipeline/` | Hermes Agent, scripts del skill |
| PDFs fuente | `/Users/adominguezdia/Downloads/FASP/` | Alfredo, cuando arrastra PDFs nuevos |
| Conversiones (jobs) | `/Users/adominguezdia/Downloads/FASP/jobs/<job_id>/` | Skill `pdf-to-knowledge-graph` |
| BD del pipeline | `/tmp/csn-restore.db`, `/Users/adominguezdia/Downloads/CSN-evaluacion-FASP/fasp_csn.db` | Scripts `db_init.py`, `llm-1-parser-juridico.py`, `py-*`, `fasp_dashboard.py` |
| Salida del dashboard | `/Users/adominguezdia/Downloads/CSN-evaluacion-FASP/dashboard.html` | Alfredo para revisión visual |
| Zip distribuible | `/tmp/fasp-document-pipeline.zip` | Flujo de release a GitHub |

## Por qué este patrón importa

El script `fasp_dashboard.py` necesita **encontrar el MD** de cada norma para calcular el score de calidad. El MD vive en `/Users/adominguezdia/Downloads/FASP/jobs/<job_id>/`, no en la ruta del skill. Si el script solo busca en rutas relativas a la BD, falla silenciosamente y muestra "Sin MD" para todas las normas.

## Receta: invocar el skill desde el directorio del usuario

**NO** ejecutes los scripts desde `~/.hermes/skills/productivity/fasp-document-pipeline/`. Ejecútalos desde el directorio donde están los datos:

```bash
# Cambiar al directorio de trabajo (donde están los PDFs)
cd /Users/adominguezdia/Downloads/FASP

# Invocar los scripts del skill por path absoluto
python3 ~/.hermes/skills/productivity/pdf-to-knowledge-graph/scripts/pdf_to_md.py \
    --scan . --output ./jobs --user-id alfredo

python3 ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/db_init.py \
    --db ./fasp.db

python3 ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/llm-1-parser-juridico.py \
    --md ./jobs/<job_id>/<job_id>.md --db ./fasp.db

# Generar el dashboard en el directorio de trabajo
python3 ~/.hermes/skills/productivity/fasp-document-pipeline/scripts/fasp_dashboard.py \
    --db ./fasp.db --output ./dashboard.html
```

**Beneficios**:
- Los paths relativos (`.`, `./jobs`, `./fasp.db`) son más legibles que paths absolutos.
- El script `pdf_to_md.py` crea `./jobs/<job_id>/` automáticamente sin permisos.
- El dashboard queda en el directorio de trabajo, fácil de compartir.

## Patrón de búsqueda del PDF

`audit_conversions.py` y `fasp_dashboard.py` buscan el PDF original en:

| Ruta base | Patrón |
|---|---|
| `pathlib.Path.cwd()` | Directorio actual (donde se ejecuta el script) |
| `~/Downloads` | Carpeta estándar de descargas |
| `~/Documents` | Si el usuario guarda PDFs ahí |
| `~/Desktop` | Si los pone en el escritorio |
| `/Users/adominguezdia/Downloads` | Hardcodeado como fallback para Alfredo |
| `/tmp` | Si el usuario trabaja en `/tmp` |

**Si el PDF no se encuentra en ninguno de estos lugares**: el script reporta `pdf_words: null, text_similarity: 0` y el score se reduce. La cobertura y preservación de keywords siguen funcionando. La similitud requiere PDF.

## Patrón de búsqueda del MD

`fasp_dashboard.py` busca el MD con la siguiente lógica (en orden):

1. Lee `id_documento`, `id_norma` y `fuente` de la tabla `normas`.
2. Construye candidatos de nombre de carpeta: el `id_documento`, el `id_norma`, y el `fuente` sin extensión `.md`.
3. Busca recursivamente (3 niveles) en: `db_path.parent/jobs`, `~/Downloads`, `~/Downloads/fasp-jobs`, `/tmp`.
4. Si no encuentra, busca recursivamente cualquier `*.md` cuyo directorio padre coincida con un candidato.
5. Fallback final: `rglob` completo en `~/Downloads` y `/tmp`.

**Si ninguno matchea**: la norma aparece en el dashboard con `rating: "Sin MD"` y `score: null`. Hay que verificar que la BD fue inicializada con `db_init.py` y que los jobs están en una de las rutas esperadas.

## Lección operativa para el agente

Cuando el usuario te diga "procesa este PDF con el skill FASP", **primero pregunta** o verifica:

1. ¿Dónde está el PDF? (`/Users/adominguezdia/Downloads/FASP/` por defecto)
2. ¿Dónde pongo los jobs? (mismo directorio que el PDF, subcarpeta `jobs/`)
3. ¿Dónde pongo la BD? (mismo directorio, archivo `fasp.db` o `evaluacion.db`)
4. ¿Dónde pongo el dashboard? (mismo directorio, archivo `dashboard.html`)

Si el usuario no especifica, asume el patrón por defecto:

```bash
PDFS_DIR=~/Downloads/FASP
DB=./fasp.db
OUT=./jobs
```

Y ejecuta desde el directorio `PDFS_DIR` para que los paths relativos funcionen.
