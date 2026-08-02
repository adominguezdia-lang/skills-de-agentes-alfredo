#!/usr/bin/env python3
"""
delimitar_normas_fasp.py — Delimita las normas que contribuyen al FASP
cruzando 3 fuentes:

  1. Guardarraíl (TABLA_Normatividad_<Estado>.md o
     LISTA_Normatividad_por_Carpeta.md) — qué normas pidio el cliente.
  2. Analisis del LLM-2 (apartados_5y6_<estado>.md) — que leyes
     encontro el LLM como relevantes al FASP.
  3. Corpus (Extraccion_<Estado>/) — que archivos hay realmente.

Genera una tabla clasificando cada norma en 4 categorias:

  MANTENER    - En guardarrail + en MD + en corpus. Cite con confianza.
  FALTANTE    - En guardarrail pero NO en corpus. Generar alerta.
  REVISAR     - En MD o en corpus pero NO en guardarrail. Decidir caso a caso.
  EXCLUIR     - En MD pero no contribuye al FASP (ej. programas estatales
                que no son FASP, acuerdos de violencia de genero, etc.).

Uso:
    python3 delimitar_normas_fasp.py \
        --estado Edomex \
        --tabla /path/TABLA_Normatividad_EdoMex.md \
        --md /path/apartados_5y6_Edomex.md \
        --corpus /path/Extraccion_Edo \
        --output ./delimitacion_Edomex.md
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys
import unicodedata
from collections import Counter


def normalize(s: str) -> str:
    """Normaliza string: lowercase, sin acentos, solo alfanumericos."""
    s = s.lower()
    nfkd = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def extraer_keywords(texto: str) -> set:
    """Extrae keywords significativos (palabras de 5+ letras) de un texto."""
    norm = normalize(texto)
    return {w for w in norm.split() if len(w) >= 5}


def overlap_significativo(texto1: str, texto2: str, minimo: int = 2) -> bool:
    """True si dos textos comparten al menos N keywords significativos."""
    k1 = extraer_keywords(texto1)
    k2 = extraer_keywords(texto2)
    return len(k1 & k2) >= minimo


def parsear_tabla_normatividad(path: pathlib.Path) -> list[dict]:
    """Parsea una TABLA_Normatividad_<Estado>.md o LISTA_Normatividad_por_Carpeta.md.

    Retorna lista de dicts: {apartado, num, norma, existe, carpeta, ubicacion, observacion}
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    normas = []
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        # Saltar lineas de separador
        if re.match(r"\|[\s\-:|]+\|", line):
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 3:
            continue
        # Detectar encabezado
        if cells[0] in ("Apartado", "#", ""):
            continue
        # Apartado | Núm | Norma | Existe | Carpeta | Ubicación | Observación
        # (algunas tablas tienen menos columnas)
        apartado = cells[0] if cells[0] != "#" else ""
        try:
            num = int(cells[1])
        except (ValueError, IndexError):
            # Si no hay num, intentar extraerlo de la primera columna
            num = 0
        norma = cells[2] if len(cells) > 2 else ""
        existe = cells[3] if len(cells) > 3 else ""
        carpeta = cells[4] if len(cells) > 4 else ""
        ubicacion = cells[5] if len(cells) > 5 else ""
        if not norma:
            continue
        normas.append({
            "apartado": apartado,
            "num": num,
            "norma": norma,
            "existe_texto": existe,
            "carpeta": carpeta,
            "ubicacion": ubicacion,
        })
    return normas


def parsear_md_llm2(path: pathlib.Path) -> list[dict]:
    """Parsea el MD generado por el LLM-2.

    Extrae las secciones ### con sus articulos mencionados.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    leyes = []
    secciones = re.split(r"^###\s+", text, flags=re.MULTILINE)
    for sec in secciones:
        if not sec.strip():
            continue
        nombre = sec.split("\n")[0].strip()
        if not nombre or nombre.startswith("#"):
            continue
        # Articulos mencionados en esta seccion
        arts = set()
        for m in re.finditer(r"Art[ií]culo\s+(\d+)", sec):
            arts.add(int(m.group(1)))
        leyes.append({
            "nombre": nombre,
            "articulos": sorted(arts),
        })
    return leyes


def parsear_lista_archivos(corpus_dir: pathlib.Path) -> list[str]:
    """Lista los archivos del corpus normalizados."""
    if not corpus_dir.exists():
        return []
    archivos = []
    for f in corpus_dir.glob("*.txt"):
        archivos.append(f.name)
    return archivos


def clasificar_norma(norma_guardarriel: dict,
                      leyes_llm: list[dict],
                      archivos_corpus: list[str],
                      guardarriel_solo_keywords: set) -> str:
    """Clasifica una norma del guardarriel en MANTENER/FALTANTE/REVISAR/EXCLUIR.

    Logica:
      - MANTENER si aparece en el MD del LLM-2 Y en el corpus.
      - FALTANTE si NO esta en el corpus.
      - REVISAR si esta en el corpus pero NO en el MD del LLM.
      - EXCLUIR si esta en el MD pero el matching es solo por palabras
        demasiado genericas.
    """
    nom_norma = norma_guardarriel["norma"]
    existe_texto = norma_guardarriel["existe_texto"]

    # Faltante si el guardarriel dice "No" o "No localizada"
    if "No" in existe_texto and "No localizada" in existe_texto:
        return "FALTANTE"

    # Buscar la norma en el MD del LLM
    en_llm = False
    nom_norma = norma_guardarriel["norma"]
    nom_norma_norm = normalize(nom_norma) if nom_norma else ""
    for ley in leyes_llm[:50]:  # Limitar iteraciones para velocidad
        if overlap_significativo(ley["nombre"], nom_norma, minimo=2):
            en_llm = True
            break

    # Buscar en el corpus
    en_corpus = False
    nom_norma_norm = normalize(nom_norma)
    for arch in archivos_corpus:
        arch_norm = normalize(arch)
        if overlap_significativo(nom_norma, arch, minimo=2):
            en_corpus = True
            break
        # Matching por fragmento de la norma
        palabras = [w for w in nom_norma_norm.split() if len(w) > 6]
        if palabras and all(p in arch_norm for p in palabras[:2]):
            en_corpus = True
            break

    if en_llm and en_corpus:
        return "MANTENER"
    if en_llm and not en_corpus:
        return "FALTANTE"
    if en_corpus and not en_llm:
        return "REVISAR"
    return "FALTANTE"


def clasificar_leyes_no_en_guardarriel(leyes_llm: list[dict],
                                       normas_guardarriel: list[dict]) -> list[dict]:
    """Clasifica las leyes del MD que NO estan en el guardarriel.

    Estas son candidatas a EXCLUIR si no son del FASP, o a MANTENER si el
    LLM las identifico correctamente como relevantes al FASP.
    """
    keywords_fasp = {"fasp", "fondo", "aportaciones", "seguridad", "publica",
                     "convenio", "anexo", "tecnico", "coordinacion",
                     "federales", "remanentes", "transferencias"}

    resultados = []
    for ley in leyes_llm:
        nom = ley["nombre"]
        nom_norm = normalize(nom)

        # Verificar si esta en el guardarriel
        en_guardarriel = False
        for n in normas_guardarriel:
            if overlap_significativo(n["norma"], nom, minimo=2):
                en_guardarriel = True
                break
            # Matching mas flexible: si la mayoria de las palabras coinciden
            palabras_norma = [w for w in normalize(n["norma"]).split() if len(w) > 5]
            palabras_ley = [w for w in nom_norm.split() if len(w) > 5]
            if palabras_norma and palabras_ley:
                comunes = set(palabras_norma) & set(palabras_ley)
                ratio = len(comunes) / min(len(palabras_norma), len(palabras_ley))
                if ratio >= 0.6:
                    en_guardarriel = True
                    break

        # Determinar si parece FASP
        keywords_encontrados = keywords_fasp & set(nom_norm.split())
        parece_fasp = len(keywords_encontrados) > 0

        if en_guardarriel:
            categoria = "EN_GUARDARRIEL"  # No listar aqui
        elif parece_fasp:
            categoria = "FASP_FUERA_GUARDARRIEL"  # Mantener (puede ser FASP relevante)
        else:
            # No esta en el guardarriel y no parece FASP
            # Probablemente es un programa estatal de violencia de genero,
            # desaparecidos, etc.
            categoria = "EXCLUIR"

        resultados.append({
            "nombre": nom,
            "articulos": ley["articulos"],
            "categoria": categoria,
            "keywords_fasp": sorted(keywords_encontrados),
        })
    return resultados


def generar_reporte(estado: str,
                    normas_guardarriel: list[dict],
                    leyes_llm: list[dict],
                    clasif_guardarriel: list[tuple[dict, str]],
                    clasif_extras: list[dict],
                    corpus_n: int) -> str:
    """Genera el reporte Markdown con las clasificaciones."""
    lines = []
    lines.append(f"# Delimitacion de normas FASP - {estado}")
    lines.append("")
    lines.append("Compara el **guardarriel** (normas que pidio el cliente), "
                 "el **analisis del LLM-2** (que leyes encontro como FASP) y "
                 "el **corpus** (archivos realmente disponibles).")
    lines.append("")

    # Resumen
    cnt = Counter(c for _, c in clasif_guardarriel)
    extras_cnt = Counter(e["categoria"] for e in clasif_extras)
    lines.append("## Resumen ejecutivo")
    lines.append("")
    lines.append(f"- **Normas en el guardarriel**: {len(normas_guardarriel)}")
    lines.append(f"  - MANTENER: {cnt.get('MANTENER', 0)}")
    lines.append(f"  - FALTANTE (no en corpus): {cnt.get('FALTANTE', 0)}")
    lines.append(f"  - REVISAR (en corpus pero no en MD): {cnt.get('REVISAR', 0)}")
    lines.append(f"- **Archivos en el corpus**: {corpus_n}")
    lines.append(f"- **Leyes identificadas por LLM-2**: {len(leyes_llm)}")
    lines.append(f"  - En el guardarriel: {extras_cnt.get('EN_GUARDARRIEL', 0)}")
    lines.append(f"  - FASP relevantes (fuera del guardarriel): {extras_cnt.get('FASP_FUERA_GUARDARRIEL', 0)}")
    lines.append(f"  - EXCLUIR (no FASP, programas estatales): {extras_cnt.get('EXCLUIR', 0)}")
    lines.append("")

    # Tabla del guardarriel
    lines.append("## Tabla cruzada: Normas del guardarriel")
    lines.append("")
    lines.append("| Apartado | Núm | Norma | Categoría |")
    lines.append("|---|---:|---|---|")
    for n, cat in clasif_guardarriel:
        emoji = {"MANTENER": "✅", "FALTANTE": "❌", "REVISAR": "⚠️"}.get(cat, "•")
        lines.append(f"| {n['apartado'][:30]} | {n['num']} | {n['norma'][:60]} | {emoji} {cat} |")
    lines.append("")

    # Tabla de leyes del LLM que no estan en el guardarriel
    extras_no_en_guardarriel = [e for e in clasif_extras if e["categoria"] != "EN_GUARDARRIEL"]
    if extras_no_en_guardarriel:
        lines.append("## Leyes del MD que NO estan en el guardarriel")
        lines.append("")
        lines.append("Estas leyes las identifico el LLM-2 pero no aparecen en el TABLA_Normatividad. "
                     "Decidir caso por caso si se incluyen o se excluyen.")
        lines.append("")
        lines.append("| Ley | Articulos | Categoria | Keywords FASP |")
        lines.append("|---|---|---|---|")
        for e in extras_no_en_guardarriel[:30]:  # Limitar a 30
            kw = ", ".join(e["keywords_fasp"]) if e["keywords_fasp"] else "(ninguno)"
            arts = ", ".join(str(a) for a in e["articulos"][:10])
            if len(e["articulos"]) > 10:
                arts += f" ... (+{len(e['articulos']) - 10})"
            lines.append(f"| {e['nombre'][:60]} | {arts} | {e['categoria']} | {kw} |")
        if len(extras_no_en_guardarriel) > 30:
            lines.append(f"| ... | (mostrando 30 de {len(extras_no_en_guardarriel)}) | | |")
        lines.append("")

    # Recomendaciones
    lines.append("## Recomendaciones")
    lines.append("")
    mant = cnt.get("MANTENER", 0)
    falt = cnt.get("FALTANTE", 0)
    excl = extras_cnt.get("EXCLUIR", 0)
    if mant > 0:
        lines.append(f"1. **Mantener en el Word**: Las {mant} normas clasificadas como "
                     f"MANTENER son las que deben aparecer en el Producto 1 con citas directas.")
    if falt > 0:
        lines.append(f"2. **Alertar sobre faltantes**: Las {falt} normas del guardarriel "
                     f"que NO estan en el corpus requieren atencion del equipo C-evalua.")
    if excl > 0:
        lines.append(f"3. **Excluir del MD**: Las {excl} leyes del LLM que no son FASP "
                     f"y no estan en el guardarriel deben excluirse del analisis "
                     f"(ej. programas de violencia de genero, desaparecidos, etc.).")
    if extras_cnt.get("FASP_FUERA_GUARDARRIEL", 0) > 0:
        lines.append(f"4. **Revisar caso por caso**: {extras_cnt.get('FASP_FUERA_GUARDARRIEL', 0)} "
                     f"leyes parecen FASP pero no estan en el guardarriel. "
                     f"Confirmar con el cliente si aplican o no.")
    lines.append("")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Delimita normas FASP vs guardarriel")
    p.add_argument("--estado", required=True, help="Nombre del estado")
    p.add_argument("--tabla", required=True,
                   help="Path a TABLA_Normatividad_<Estado>.md o LISTA_Normatividad_por_Carpeta.md")
    p.add_argument("--md", required=True,
                   help="Path al apartados_5y6_<estado>.md (output de LLM-2)")
    p.add_argument("--corpus", required=True,
                   help="Path al directorio Extraccion_<Estado>/ con los .txt")
    p.add_argument("--output", required=True, help="Path del .md de salida")
    p.add_argument("--output-json", default=None,
                   help="Path opcional para exportar la tabla cruzada como JSON")
    args = p.parse_args()

    tabla_path = pathlib.Path(args.tabla)
    md_path = pathlib.Path(args.md)
    corpus_dir = pathlib.Path(args.corpus)
    output_path = pathlib.Path(args.output)

    print(f"Leyendo guardarriel desde {tabla_path}...")
    normas_guardarriel = parsear_tabla_normatividad(tabla_path)
    print(f"  {len(normas_guardarriel)} normas en el guardarriel")

    print(f"Leyendo MD del LLM-2 desde {md_path}...")
    leyes_llm = parsear_md_llm2(md_path)
    print(f"  {len(leyes_llm)} leyes en el MD")

    print(f"Leyendo corpus desde {corpus_dir}...")
    archivos_corpus = parsear_lista_archivos(corpus_dir)
    print(f"  {len(archivos_corpus)} archivos en el corpus")

    # Calcular keywords del guardarriel para matching
    guardarriel_keywords = set()
    for n in normas_guardarriel:
        guardarriel_keywords.update(extraer_keywords(n["norma"]))

    # Clasificar normas del guardarriel
    clasif_guardarriel = []
    for n in normas_guardarriel:
        cat = clasificar_norma(n, leyes_llm, archivos_corpus, guardarriel_keywords)
        clasif_guardarriel.append((n, cat))

    # Clasificar leyes del MD que no estan en el guardarriel
    clasif_extras = clasificar_leyes_no_en_guardarriel(leyes_llm, normas_guardarriel)

    # Generar reporte
    reporte = generar_reporte(args.estado, normas_guardarriel, leyes_llm,
                              clasif_guardarriel, clasif_extras, len(archivos_corpus))
    output_path.write_text(reporte, encoding="utf-8")
    print(f"\nOK Reporte guardado en {output_path}")

    # JSON opcional
    if args.output_json:
        json_path = pathlib.Path(args.output_json)
        data = {
            "estado": args.estado,
            "normas_guardarriel": len(normas_guardarriel),
            "leyes_llm": len(leyes_llm),
            "archivos_corpus": len(archivos_corpus),
            "clasificacion": [
                {"num": n["num"], "norma": n["norma"], "apartado": n["apartado"],
                 "categoria": cat}
                for n, cat in clasif_guardarriel
            ],
            "extras": [
                {"nombre": e["nombre"], "articulos": e["articulos"],
                 "categoria": e["categoria"], "keywords_fasp": e["keywords_fasp"]}
                for e in clasif_extras
            ],
        }
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK JSON guardado en {json_path}")


if __name__ == "__main__":
    main()