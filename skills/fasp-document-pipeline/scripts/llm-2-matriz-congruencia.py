#!/usr/bin/env python3
"""
llm-2-matriz-congruencia.py — Analisis normativo apartados 5 y 6 (version 2).

Lee el corpus COMPLETO de extracciones (Extraccion_<Estado>/) en lugar de
solo el JSON de citas. Por cada norma, identifica los articulos que
tocan al FASP (programas federales / FASP) usando keywords especificas,
y construye un prompt con esos articulos para que el LLM produzca:

  1. Cuadro analitico por norma (art, naturaleza, facultado, accion, plazo, responsable)
  2. Parrafo narrativo introductorio (200-400 palabras)
  3. Tipologia de obligaciones (mandatorias/facultativas/recomendatorias)

Uso:
    python3 llm-2-matriz-congruencia.py \\
        --extraccion /Users/.../Extraccion_Qro \\
        --estado Queretaro \\
        --model MiniMax-Text-01 \\
        --output ./apartados_5y6_Queretaro.md
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, subprocess, sys, urllib.error, urllib.request
from collections import Counter


# === Keywords que indican que un articulo toca FASP/programas federales ===
KEYWORDS_FASP = [
    # Programa federal / FASP directo
    r"\bFASP\b",
    r"Fondo de Aportaciones para la Seguridad",
    r"Fondo de Aportaciones",
    r"Aportaciones Federales",
    r"Recursos Federales",
    r"Transferencias Federales",
    r"Subsidios Federales",
    r"Convenio de Coo?rdinacio?n",
    r"Anexo Te?cnico",
    r"Convenios de Coo?rdinacio?n",
    # Coordinacion intergubernamental
    r"Coordinacio?n Interinstitucional",
    r"Coordinacio?n Intergubernamental",
    r"Coordinacio?n con (?:la|el) Federacio?n",
    r"Coordinacio?n con (?:las|los) (?:entidades|municipios|ayuntamientos)",
    # Atribuciones ejecutivas relevantes
    r"Gobernador.*celebr.*acuerdos",
    r"Gobernador.*celebr.*convenios",
    r"Representacio?n legal del Estado",
    r"Secretari?a de (Planeacio?n|Finanzas|Gobernacio?n|Seguridad)",
    r"Secretari?a de Seguridad (?:Ciudadana|Pu?blica)",
    r"Atribuciones de (?:la|el) Gobernador",
    r"Refrendar.*(?:decretos|acuerdos|reglamentos)",
    # Plazos / obligatoriedad
    r"plazo de \d+ d[ií]as",
    r"plazo de \d+ meses",
    r"dentro de los \d+",
    r"antes del (?:31|15) de (?:diciembre|marzo|enero)",
    # Seguridad publica
    r"Seguridad Pu?blica",
    r"Prevencio?n del Delito",
    r"Reclusorio|Penitenciari|Ce?rcar|Reinsencio?n",
    r"Procuradur[ií]a|Fiscal[ií]a",
    # Planeacion y presupuesto
    r"Presupuesto de Egresos",
    r"Programas (?:con|de) Recursos Federales",
    r"Ejercicio y Control del Presupuesto",
    r"Rendicio?n de Cuentas",
    r"Transparencia",
    # Sistema nacional / estatal
    r"Sistema Nacional de Seguridad",
    r"Sistema Estatal de Seguridad",
    r"\bSESNSP\b",
    r"Secretariado Ejecutivo",
    r"Consejo (?:Estatal|Nacional) de Seguridad",
    r"Conferencia Nacional",
    # Publicacion / vigencia
    r"entrada en vigor",
    r"vigencia",
    r"publicaci[oó]n",
]

KEYWORDS_FASP_COMPILED = [re.compile(kw, re.IGNORECASE) for kw in KEYWORDS_FASP]


def leer_extraccion(path: pathlib.Path) -> tuple[str, list[tuple[int, str]]]:
    """Lee un .txt de extraccion. Retorna (texto_completo, [(num_pagina, texto_pagina)])."""
    texto = path.read_text(encoding="utf-8", errors="replace")
    # Dividir por paginas usando el marker "--- Página N ---"
    paginas = re.split(r"---\s*Página\s+(\d+)\s*---", texto)
    lista_paginas = []
    # paginas[0] = preambulo, luego alterna (num, texto)
    for i in range(1, len(paginas) - 1, 2):
        num = int(paginas[i])
        contenido = paginas[i + 1].strip()
        lista_paginas.append((num, contenido))
    return texto, lista_paginas


def extraer_articulos(paginas: list[tuple[int, str]]) -> list[dict]:
    """Extrae todos los articulos del texto. Cada articulo = {numero, pagina, texto, fraccion?}.

    Patron: busca 'ARTICULO N' o 'Artículo N' o 'ARTÍCULO N' (con acento o sin).
    """
    articulos = []
    # Patron: "ARTÍCULO N" o "ARTICULO N" o "Artículo N" o "Articulo N"
    patron = re.compile(
        r"(?:ART[ÍI]CULO|Art[íi]culo)\s+(\d+(?:[o\.\u00ba])?)\s*\.?\s*[:\.\-]?\s*",
        re.IGNORECASE,
    )
    for num_pagina, contenido in paginas:
        for match in patron.finditer(contenido):
            num_str = match.group(1).rstrip("o.\u00ba")
            try:
                num = int(num_str)
            except ValueError:
                continue
            # Texto del articulo: desde el match hasta el siguiente marcador
            inicio = match.end()
            # Buscar fin: siguiente ARTICULO, o fin de pagina
            fin = len(contenido)
            for sig in patron.finditer(contenido, pos=inicio):
                fin = sig.start()
                break
            texto = contenido[inicio:fin].strip()
            # Limpiar: cortar en marcadores de fraccion si el articulo es muy largo
            articulos.append({
                "numero": num,
                "pagina": num_pagina,
                "texto": texto[:2000],  # limite de seguridad
                "match_start": match.start(),
            })
    return articulos


def calcular_relevancia_fasp(texto: str) -> int:
    """Score de cuantos keywords FASP aparecen en el texto del articulo."""
    score = sum(1 for kw_compiled in KEYWORDS_FASP_COMPILED if kw_compiled.search(texto))
    return score


def seleccionar_articulos_fasp(articulos: list[dict], min_score: int = 1, max_por_norma: int = 8) -> list[dict]:
    """Filtra los articulos relevantes al FASP y devuelve los mejores."""
    scored = []
    for a in articulos:
        s = calcular_relevancia_fasp(a["texto"])
        if s >= min_score:
            a_scored = dict(a)
            a_scored["_score_fasp"] = s
            scored.append(a_scored)
    # Ordenar por score descendente, luego por numero de articulo
    scored.sort(key=lambda a: (-a["_score_fasp"], a["numero"]))
    return scored[:max_por_norma]


def analizar_norma(path: pathlib.Path) -> dict:
    """Lee una norma y extrae articulos relevantes al FASP."""
    nombre_archivo = path.name
    # Limpiar nombre para mostrar
    nombre_limpio = re.sub(r"^FASP_\d{4}_P[123]_[A-Z]+_(NOR|DOC)-", "", nombre_archivo)
    nombre_limpio = re.sub(r"_V\d+\.txt$", "", nombre_limpio)
    nombre_limpio = nombre_limpio.replace("-", " ").strip()

    texto, paginas = leer_extraccion(path)
    articulos = extraer_articulos(paginas)
    relevantes = seleccionar_articulos_fasp(articulos)

    return {
        "archivo": nombre_archivo,
        "nombre": nombre_limpio,
        "ruta": str(path),
        "total_articulos": len(articulos),
        "articulos_relevantes": relevantes,
    }


def construir_prompt(estado: str, normas: list[dict]) -> str:
    """Construye el prompt con los articulos relevantes de cada norma."""
    nombre_estado = estado

    # Bloque de normas con sus articulos
    normas_bloques = []
    total_articulos = 0
    for n in normas:
        arts = n["articulos_relevantes"]
        if not arts:
            continue
        total_articulos += len(arts)
        arts_texto = []
        for a in arts:
            arts_texto.append(
                f"  - **Articulo {a['numero']}** (pag {a['pagina']}, score FASP={a['_score_fasp']}):\n"
                f"    {a['texto'][:1500]}"
            )
        normas_bloques.append(
            f"### {n['nombre']}\n"
            + f"({n['total_articulos']} articulos en total; {len(arts)} relevantes para FASP)\n"
            + "\n\n".join(arts_texto)
        )

    normas_texto = "\n\n".join(normas_bloques)

    return f"""Eres un analista juridico especializado en evaluacion de politicas publicas
del Fondo de Aportaciones para la Seguridad Publica (FASP) en Mexico.

OBJETIVO:
Generar el ANALISIS NORMATIVO de los apartados 5 y 6 del Producto 1 (TdR)
para el estado de {nombre_estado}. Se incluyen SOLO articulos que mencionan
palabras clave del FASP (Convenios de Coordinacion, Anexos Tecnicos, recursos
federales, seguridad publica, atribuciones del Gobernador/Secretarias).

CONTEXTO INSTITUCIONAL:
- Estado evaluado: {nombre_estado}
- El FASP es un FONDO FEDERAL que se transfiere a las entidades federativas
  mediante Convenios de Coordinacion y Anexos Tecnicos anuales.
- 5 etapas del ciclo FASP: Integracion, Distribucion, Administracion, Supervision, Seguimiento.
- 3 tipos de competencia: Exclusiva, Concurrente, Complementaria.
- 3 niveles de obligatoriedad: Mandatoria, Facultativa, Recomendatoria.

ARTICULOS RELEVANTES PARA FASP EN {nombre_estado} ({total_articulos} articulos):

{normas_texto}

PRODUCE TRES COMPONENTES EN ESTE ORDEN EXACTO:

## 1. CUADRO ANALITICO POR NORMA

Para CADA norma listada, genera una fila Markdown con estas columnas:
| Articulo | Naturaleza | Quien es facultado/obligado | Accion concreta | Plazo (si la norma lo senala) | Responsable |

Donde:
- Naturaleza = Mandatoria | Facultativa | Recomendatoria
- "Quien es facultado/obligado" = sujeto juridico (Gobernador, Congreso, SSPC, SESNSP, etc.)
- "Accion concreta" = accion habilitada o impuesta por el articulo, en lenguaje claro
- "Plazo" = periodo en dias/meses/anios si la norma lo senala explicitamente; "NR" si no aparece
- "Responsable" = unidad o cargo que ejecuta la accion

Una tabla por norma, separadas por titulo h4 con el nombre de la norma.
Incluye TODOS los articulos listados (no solo uno por norma).

## 2. PARRAFO NARRATIVO INTRODUCTORIO

Un parrafo de 200-400 palabras que integre los hallazgos del cuadro en prosa
fluida. Debe:
- Comenzar con la norma mas relevante para el FASP (Convenio de Coordinacion o
  Ley que lo reglamente).
- Vincular cada articulo con la etapa del ciclo FASP que corresponde.
- Distinguir entre facultades del Ejecutivo (Gobernador, Secretarias) y del
  Legislativo (Congreso) cuando aplique.
- Si las normas mencionan una Secretaria especifica (Planeacion y Finanzas,
  Seguridad Ciudadana, Gobierno), explica su rol en la radicacion o
  formalizacion de recursos del FASP.
- Cerrar con cita bibliografica: (Congreso del Estado de {nombre_estado}, <anio>)

## 3. TIPOLOGIA DE OBLIGACIONES

Clasifica las obligaciones detectadas en tres bloques:
- **Mandatorias**: las que la ley obliga explicitamente.
- **Facultativas**: las que la norma permite pero no obliga.
- **Recomendatorias**: las que provienen de lineamientos o mejores practicas.

Para cada bloque, lista las normas aplicables y los articulos relevantes.

REGLAS:
- Espanol, tono tecnico-institucional.
- Sin meta-comentarios ni notas al pie.
- Sin inventar plazos: si la norma no lo senala, usa "NR".
- Cita los articulos por su numero exacto.
"""


def llamar_llm(prompt: str, model: str) -> str:
    """Llama al LLM con cadena de fallbacks.

    Prioridad:
      1. MiniMax API directa (MINIMAX_API_KEY + MINIMAX_BASE_URL)
      2. OpenRouter (OPENROUTER_API_KEY + OPENROUTER_BASE_URL)
      3. Hermes CLI (hermes chat -q prompt -m minimax/<model>)
    """
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    base_url = os.environ.get("MINIMAX_BASE_URL", "")

    if api_key and base_url:
        print("  [1/3] MiniMax API directa...")
        result = _llm_api_direct(prompt, model, api_key, base_url,
                                  model_name=model)
        if result:
            return result
        print("  [1/3] fallo, intentando OpenRouter...")

    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    or_url = os.environ.get("OPENROUTER_BASE_URL", "")
    if or_key and or_url:
        print("  [2/3] OpenRouter...")
        or_model = os.environ.get("OPENROUTER_MODEL", "minimax/minimax-m3")
        result = _llm_api_direct(prompt, model, or_key, or_url,
                                  model_name=or_model)
        if result:
            return result
        print("  [2/3] fallo, intentando Hermes CLI...")

    return llamar_llm_via_hermes(prompt, model)


def _llm_api_direct(prompt: str, model: str, api_key: str, base_url: str,
                    model_name: str = None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "model": model_name or model,
        "max_tokens": 8000,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": "Eres un analista juridico del FASP mexicano. Responde SOLO el analisis final."},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [API directa] Error: {e}")
        return ""


def llamar_llm_via_hermes(prompt: str, model: str) -> str:
    print(f"  [fallback] Invocando Hermes con model=minimax/{model}...")
    result = subprocess.run(
        ["hermes", "chat", "-q", prompt, "-m", f"minimax/{model}"],
        capture_output=True, text=True, timeout=240,
    )
    if result.returncode != 0:
        sys.exit(f"Error en Hermes: {result.stderr}")
    return result.stdout.strip()


def limpiar_respuesta(respuesta: str) -> str:
    """Quita razonamiento embebido, ruido de CLI y secciones previas al output real."""
    import re as _re

    # Quitar bloques de razonamiento de MiniMax-M3
    respuesta = _re.sub(r"<think>.*?</think>", "", respuesta, flags=_re.DOTALL).strip()

    # Limpiar envolturas tipo "Query: ... Response: ..."
    if "Query:" in respuesta and "Response:" in respuesta:
        m = _re.search(r"Response:\s*(.*)", respuesta, flags=_re.DOTALL)
        if m:
            respuesta = m.group(1).strip()

    # Buscar el primer marcador valido de output real (despues de los 200 chars)
    marcadores_inicio = [
        r"^ANÁLISIS NORMATIVO",
        r"^ANALISIS NORMATIVO",
        r"^## 1\. CUADRO",
        r"^## 1\.",
        r"^1\. CUADRO",
    ]
    inicio_idx = None
    for patron in marcadores_inicio:
        m = _re.search(patron, respuesta, _re.IGNORECASE | _re.MULTILINE)
        if m and m.start() > 200:
            if inicio_idx is None or m.start() < inicio_idx:
                inicio_idx = m.start()
    if inicio_idx:
        respuesta = respuesta[inicio_idx:].strip()
    return respuesta


def main():
    p = argparse.ArgumentParser(description="Analisis normativo apartados 5 y 6 (LLM-2 v2)")
    p.add_argument("--extraccion", required=True,
                   help="Directorio con archivos .txt de extraccion")
    p.add_argument("--estado", required=True, help="Nombre del estado")
    p.add_argument("--model", default="MiniMax-Text-01",
                   choices=["MiniMax-Text-01", "MiniMax-M3"])
    p.add_argument("--output", default=None, help="Archivo de salida .md")
    p.add_argument("--max-normas", type=int, default=15,
                   help="Maximo de normas a incluir (default 15)")
    p.add_argument("--max-articulos-por-norma", type=int, default=5,
                   help="Maximo de articulos relevantes por norma (default 5)")
    p.add_argument("--dry-run", action="store_true", help="Solo analizar, no llamar al LLM")
    args = p.parse_args()

    extraccion_dir = pathlib.Path(args.extraccion)
    if not extraccion_dir.is_dir():
        sys.exit(f"No es directorio: {extraccion_dir}")

    output_path = pathlib.Path(args.output) if args.output else pathlib.Path(f"./apartados_5y6_{args.estado}.md")

    print(f"Leyendo extracciones desde {extraccion_dir}...")
    archivos_txt = sorted(extraccion_dir.glob("*.txt"))
    print(f"  Archivos encontrados: {len(archivos_txt)}")

    normas = []
    for txt in archivos_txt:
        info = analizar_norma(txt)
        if info["articulos_relevantes"]:
            normas.append(info)
        if len(normas) >= args.max_normas:
            break

    total_art_relevantes = sum(len(n["articulos_relevantes"]) for n in normas)
    print(f"  Normas con articulos relevantes: {len(normas)}")
    print(f"  Articulos relevantes para FASP: {total_art_relevantes}")

    if not normas:
        sys.exit("Ningun articulo resulto relevante para FASP. Ajustar keywords o corpus.")

    for n in normas[:5]:
        print(f"  {n['nombre']}: {len(n['articulos_relevantes'])} articulos relevantes")

    print(f"\nConstruyendo prompt...")
    prompt = construir_prompt(args.estado, normas)

    if args.dry_run:
        print("\n=== PROMPT (primeras 1500 chars) ===\n")
        print(prompt[:1500])
        print(f"\n... (total: {len(prompt)} chars)")
        sys.exit(0)

    print(f"Llamando al LLM ({args.model})...")
    respuesta = llamar_llm(prompt, args.model)
    if not respuesta:
        sys.exit("LLM no devolvio respuesta.")

    respuesta = limpiar_respuesta(respuesta)

    # Encabezado
    encabezado = (
        f"# Apartados 5 y 6 — Analisis normativo ({args.estado})\n\n"
        f"**Estado:** {args.estado}  \n"
        f"**Modelo:** {args.model}  \n"
        f"**Normas relevantes para FASP:** {len(normas)}  \n"
        f"**Articulos relevantes para FASP:** {total_art_relevantes}  \n"
        f"**Fuente:** {extraccion_dir.name}/  \n\n"
        f"---\n\n"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(encabezado + respuesta, encoding="utf-8")
    palabras = len(respuesta.split())
    print(f"OK Analisis ({palabras} palabras) guardado en {output_path}")


if __name__ == "__main__":
    main()