#!/usr/bin/env python3
"""
llm-1-parser-juridico.py — Parser jurídico-documental del skill FASP.

Segmenta un Markdown (generado por pdf-to-knowledge-graph o por OCR) en
unidades normativas (artículos, fracciones, incisos) y extrae metadatos.

Como funciona este skill v1.0:
    1. Lee el MD del PDF ya convertido (entrada: archivo .md).
    2. Detecta bloques de tipo "Artículo N°", "Art. N", "Fracción X", etc.
       usando regex robustas (ver references/patrones_juridicos.txt).
    3. Infiere metadatos básicos: nombre de la norma (del título o primeras
       líneas), nivel de gobierno (de prefijos del texto), jerarquía
       ( Constitución | Ley | Reglamento | NOM | Lineamiento | Manual ).
    4. Clasifica cada unidad por etapa del ciclo FASP y dimensión del ciclo
       usando heurísticas de palabras clave (diccionario base).
    5. Persiste en la BD SQLite usando db_init.

Uso:
    # Modo CLI directo (sin LLM externo):
    python3 llm-1-parser-juridico.py --md ./jobs/<id>/<id>.md --db ./fasp.db

    # Modo LLM (opcional, requiere API key):
    ANTHROPIC_API_KEY=sk-... python3 llm-1-parser-juridico.py --md ./file.md --db ./fasp.db --use-llm

Salida:
    Inserta filas en tablas `normas` y `norma_unidades` de la BD.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, sqlite3, sys, unicodedata
from datetime import datetime, timezone

# === Taxonomías (duplicadas del schema para evitar import circular) ===
ETAPAS_FASP = ["Integración", "Distribución", "Administración", "Supervisión", "Seguimiento"]
DIMENSIONES = ["Planeación", "Asignación", "Ejecución", "Seguimiento", "Rendición de cuentas"]

# === Heurísticas para clasificar etapa del ciclo FASP por palabras clave ===
KEYWORDS_ETAPA = {
    "Integración":   ["integración", "integrar", "convenio", "acuerdo de coordinación",
                      "coordinación interinstitucional", "convenios de coordinación",
                      "marco de coordinación", "comisión permanente"],
    "Distribución":  ["distribución", "distribuir", "asignación de recursos",
                      "transferencia", "reparto", "cupo", "asignar recursos",
                      "monto asignado", "factor de distribución"],
    "Administración":["administración", "administrar", "ejercicio", "ejecución del gasto",
                      "operación", "operativo", "gestión administrativa",
                      "ministración", "manejo de recursos"],
    "Supervisión":   ["supervisión", "supervisar", "fiscalización", "auditoría",
                      "control", "inspección", "vigilancia", "monitoreo",
                      "verificación", "evaluación del desempeño"],
    "Seguimiento":   ["seguimiento", "rendición de cuentas", "transparencia",
                      "informes", "reportes", "indicadores", "sistema de evaluación",
                      "comités de evaluación", "comisión de seguimiento"],
}

# === Heurísticas para dimensión del ciclo ===
KEYWORDS_DIM = {
    "Planeación":              ["planeación", "plan", "programación", "anteproyecto",
                                "diagnóstico", "pronóstico", "estrategia"],
    "Asignación":              ["asignación", "presupuesto", "recursos", "transferencia",
                                "cupo", "factor de distribución", "monto"],
    "Ejecución":               ["ejecución", "operación", "implementación", "aplicación",
                                "ejercicio fiscal", "operativo", "funcionamiento"],
    "Seguimiento":             ["seguimiento", "monitoreo", "control", "fiscalización",
                                "auditoría", "supervisión", "indicadores"],
    "Rendición de cuentas":    ["rendición de cuentas", "transparencia", "informes",
                                "reportes", "publicación", "acceso a la información",
                                "comprobación", "cuenta pública"],
}

# === Regex para detectar unidades normativas ===
RE_ARTICULO = re.compile(
    r"^\s*(?:Art(?:ículo|\.)\s+)?(\d+(?:[º°])?(?:\s*(?:bis|ter|quater))?)\s*[\.:]?\s*",
    re.MULTILINE | re.IGNORECASE
)
RE_FRACCION = re.compile(
    r"^\s*([IVX]+|[a-z])\)\s+",  # I) II) a) b)
    re.MULTILINE
)
RE_INCISO = re.compile(
    r"^\s*([a-z]\.|\d+\.)\s+",
    re.MULTILINE
)
RE_TRANSITORIO = re.compile(
    r"\b(?:TRANSITORIO(?:S)?|Artículo\s+Transitorio)\b",
    re.IGNORECASE
)

# === Regex para metadatos ===
RE_NIVEL = re.compile(r"\b(DECRETO|LEY|REGLAMENTO|CONSTITUCI[ÓO]N|NOM|LINEAMIENTO|MANUAL|CONVENIO|ACUERDO)\b", re.IGNORECASE)
RE_FEDERAL = re.compile(r"\b(Federal|C[ÁM]MARA\s+DE\s+DIPUTADOS|C[ÁM]MARA\s+DE\s+SENADORES|PRESIDENCIA\s+DE\s+LA\s+REP[ÚU]BLICA)\b", re.IGNORECASE)
RE_ESTATAL = re.compile(r"\b(Estatal|GOBIERNO\s+DEL\s+ESTADO|CONGRESO\s+DEL\s+ESTADO)\b", re.IGNORECASE)
RE_MUNICIPAL = re.compile(r"\b(Municipal|Ayuntamiento)\b", re.IGNORECASE)


def normalize(s: str) -> str:
    """Lowercase + strip accents para matching."""
    s = s.lower().strip()
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def detect_etapa_ciclo(text: str) -> str:
    """Detecta la etapa del ciclo FASP con heurística de palabras clave."""
    text_norm = normalize(text)
    scores = {etapa: 0 for etapa in ETAPAS_FASP}
    for etapa, keywords in KEYWORDS_ETAPA.items():
        for kw in keywords:
            scores[etapa] += text_norm.count(normalize(kw))
    if max(scores.values()) == 0:
        return "Integración"  # default razonable
    return max(scores, key=scores.get)


def detect_dimension_ciclo(text: str) -> str:
    """Detecta la dimensión del ciclo."""
    text_norm = normalize(text)
    scores = {dim: 0 for dim in DIMENSIONES}
    for dim, keywords in KEYWORDS_DIM.items():
        for kw in keywords:
            scores[dim] += text_norm.count(normalize(kw))
    if max(scores.values()) == 0:
        return "Ejecución"  # default
    return max(scores, key=scores.get)


def detect_nivel(texto_md: str) -> str:
    """Detecta el nivel de gobierno del texto."""
    if RE_FEDERAL.search(texto_md):
        return "Federal"
    if RE_ESTATAL.search(texto_md):
        return "Estatal"
    if RE_MUNICIPAL.search(texto_md):
        return "Municipal"
    return "Federal"  # default razonable para FASP


def detect_jerarquia(texto_md: str) -> str:
    """Detecta la jerarquía normativa."""
    t = texto_md.upper()
    if "CONSTITUCIÓN" in t:
        return "Constitución"
    if "REGLAMENTO" in t:
        return "Reglamento"
    if "NOM-" in t or "NORMA OFICIAL MEXICANA" in t:
        return "NOM"
    if "LINEAMIENTO" in t:
        return "Lineamiento"
    if "MANUAL" in t:
        return "Manual"
    if "CONVENIO" in t:
        return "Convenio"
    if "ACUERDO" in t:
        return "Acuerdo"
    if "DECRETO" in t:
        return "Ley"
    if "LEY" in t:
        return "Ley"
    return "Otro"


def extract_nombre_norma(texto_md: str) -> str:
    """Extrae un nombre plausible de la norma del título o primeras líneas."""
    lines = [l.strip() for l in texto_md.split("\n") if l.strip()]
    for line in lines[:30]:
        # Heurística: líneas en mayúsculas con palabras como LEY, CÓDIGO, REGLAMENTO
        if re.match(r"^(LEY|CÓDIGO|REGLAMENTO|CONSTITUCIÓN|LINEAMIENTO|MANUAL|NOM)", line, re.IGNORECASE):
            return line[:200]
    return lines[0][:200] if lines else "Norma sin título"


def segmentar_unidades(texto_md: str) -> list[dict]:
    """
    Segmenta el MD en unidades normativas (artículos, fracciones).
    Estrategia: busca cada "Artículo N" o "Art. N" como punto de segmentación.
    """
    unidades = []

    # Dividir por marcadores de artículo
    matches = list(RE_ARTICULO.finditer(texto_md))

    if not matches:
        # No hay artículos explícitos: tratar todo como un bloque único
        return [{
            "articulo": "Único",
            "fraccion": None,
            "texto": texto_md[:1000].strip(),
            "tema": None,
        }]

    for i, m in enumerate(matches):
        art = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(texto_md)
        bloque = texto_md[start:end].strip()

        # Detectar fracciones dentro del bloque
        frac_matches = list(RE_FRACCION.finditer(bloque))
        if frac_matches:
            for j, fm in enumerate(frac_matches):
                frac = fm.group(1)
                fs = fm.end()
                fe = frac_matches[j + 1].start() if j + 1 < len(frac_matches) else len(bloque)
                frac_texto = bloque[fs:fe].strip()
                if frac_texto:
                    unidades.append({
                        "articulo": art,
                        "fraccion": frac,
                        "texto": frac_texto[:2000],
                        "tema": None,
                    })
        else:
            unidades.append({
                "articulo": art,
                "fraccion": None,
                "texto": bloque[:2000],
                "tema": None,
            })

    return unidades


def make_id(id_base: str) -> str:
    """Genera un ID estable a partir de un string."""
    h = hashlib.sha256(id_base.encode("utf-8")).hexdigest()[:12].upper()
    return f"NOR-{h}"


def process(md_path: pathlib.Path, db_path: pathlib.Path, fuente_doc_id: str = None) -> dict:
    """Procesa un MD y persiste en la BD."""
    if not md_path.exists():
        sys.exit(f"No existe {md_path}")

    text = md_path.read_text(encoding="utf-8")

    nombre = extract_nombre_norma(text)
    nivel = detect_nivel(text)
    jerarquia = detect_jerarquia(text)
    unidades = segmentar_unidades(text)

    id_norma = make_id(nombre)
    if fuente_doc_id is None:
        fuente_doc_id = make_id(md_path.name)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Insertar norma
    cur.execute("""
        INSERT OR REPLACE INTO normas
        (id_norma, id_documento, nombre_norma, nivel, jerarquia, fuente)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (id_norma, fuente_doc_id, nombre, nivel, jerarquia, md_path.name))

    # Insertar unidades
    for u in unidades:
        etapa = detect_etapa_ciclo(u["texto"])
        dim = detect_dimension_ciclo(u["texto"])

        cur.execute("""
            INSERT INTO norma_unidades
            (id_norma, articulo, fraccion, texto, tema,
             etapa_ciclo_fasp, dimension_ciclo, tipo_competencia, nivel_obligatoriedad,
             referencia_coordinacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_norma, u["articulo"], u["fraccion"], u["texto"], u["tema"],
            etapa, dim,
            "Concurrente",  # default razonable; LLM-2 lo ajustará
            "Mandatoria",   # default razonable; LLM-2 lo ajustará
            None,
        ))

    # Audit log
    cur.execute("""
        INSERT INTO audit_log (modulo, accion, tabla, row_id, detalle)
        VALUES (?, ?, ?, ?, ?)
    """, ("LLM-1", "insert", "normas", id_norma,
          json.dumps({"unidades_extraidas": len(unidades), "nivel": nivel, "jerarquia": jerarquia})))

    conn.commit()
    conn.close()

    return {
        "id_norma": id_norma,
        "nombre": nombre,
        "nivel": nivel,
        "jerarquia": jerarquia,
        "unidades_extraidas": len(unidades),
    }


def main():
    p = argparse.ArgumentParser(description="LLM-1 Parser jurídico-documental")
    p.add_argument("--md", required=True, help="Ruta al MD de entrada")
    p.add_argument("--db", required=True, help="Ruta a la BD SQLite")
    p.add_argument("--doc-id", default=None, help="ID del documento fuente (opcional)")
    p.add_argument("--use-llm", action="store_true", help="(placeholder) usar LLM externo para mejorar clasificación")
    args = p.parse_args()

    if args.use_llm:
        print("⚠ --use-llm es placeholder en v1.0. El script usa heurísticas de regex + keywords.")
        print("  Para invocación real de LLM, configura API key y extiende este script.")

    result = process(pathlib.Path(args.md), pathlib.Path(args.db), args.doc_id)
    print(f"✓ LLM-1 procesado")
    print(f"  Norma: {result['nombre'][:80]}")
    print(f"  ID:    {result['id_norma']}")
    print(f"  Nivel: {result['nivel']} | Jerarquía: {result['jerarquia']}")
    print(f"  Unidades normativas extraídas: {result['unidades_extraidas']}")


if __name__ == "__main__":
    main()