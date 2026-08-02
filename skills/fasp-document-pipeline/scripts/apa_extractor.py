#!/usr/bin/env python3
"""
apa_extractor.py — Extrae metadatos bibliográficos estilo APA 7 de un PDF o MD del FASP.

Heuristicas:
  - Titulo: primera linea no vacia en mayusculas con patron "X DE Y DE Z"
            o primera linea >= 30 chars sin ser заголовок estandar
  - Autor / Organo emisor: lineas que contengan SECRETARIADO, CONSEJO, COMISION, INSTITUTO,
            GOBERNACION, CONGRESO, PRESIDENCIA, o "emitido por"
  - Fecha de publicacion: regex de fechas (DD de MES de YYYY, YYYY-MM-DD, DD/MM/YYYY)
  - Lugar: "Mexico", "Ciudad de Mexico", o nombre del estado (top 10)
  - Medio de publicacion: "Diario Oficial", "Periodico Oficial", "Gaceta"
  - Tipo de documento: buscar primera coincidencia con vocabulario cerrado
  - Numero de norma: regex de "No. XXX", "Numero XXX", "Articulo X"
  - URL: primera URL http(s):// en el documento

Uso:
    python3 apa_extractor.py --pdf /path/to/file.pdf [--edo MEX] [--json]
    python3 apa_extractor.py --md /path/to/file.md [--edo MEX] [--json]

Salida JSON con campos:
    {
      "titulo": str | None,
      "autor": str | None,         # organo emisor
      "fecha_publicacion": str | None,  # ISO YYYY-MM-DD si se pudo parsear
      "fecha_original": str | None,     # texto crudo
      "lugar": str | None,
      "medio_publicacion": str | None,
      "tipo_documento": str | None,
      "numero_norma": str | None,
      "url": str | None,
      "anio": int | None,
      "ambito": "FED" | "EST" | "MUN" | None,
      "clave_edo": str | None,
      "formato_cita_apa": str | None,
    }
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None  # Algunas funciones (CrossRef, fetch_url) no estaran disponibles

# === Vocabularios cerrados (del xlsx hoja 'Listas') ===
TIPOS_DOCUMENTO = [
    "Constitución", "Ley", "Código", "Reglamento", "Manual de organización",
    "Lineamiento", "Convenio", "Acuerdo", "Criterio", "Manual", "Norma",
    "Decreto", "Otro",
]

ORGANOS_EMISORES = [
    "SECRETARIADO EJECUTIVO DEL SISTEMA NACIONAL DE SEGURIDAD PÚBLICA",
    "CONGRESO DE LA UNIÓN",
    "PRESIDENCIA DE LA REPÚBLICA",
    "SECRETARÍA DE GOBERNACIÓN",
    "SECRETARÍA DE SEGURIDAD Y PROTECCIÓN CIUDADANA",
    "CONSEJO NACIONAL DE SEGURIDAD PÚBLICA",
    "CÁMARA DE DIPUTADOS",
    "SENADO DE LA REPÚBLICA",
    "COMISIÓN PERMANENTE",
    "INSTITUTO NACIONAL",
    "AUDITORÍA SUPERIOR DE LA FEDERACIÓN",
]

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}

ENTIDADES_FEDERATIVAS = {
    "AGU": "Aguascalientes", "BCN": "Baja California", "BCS": "Baja California Sur",
    "CAM": "Campeche", "COA": "Coahuila", "COL": "Colima", "CHI": "Chiapas",
    "CHH": "Chihuahua", "CMX": "Ciudad de México", "DUR": "Durango",
    "MEX": "Estado de México", "GUA": "Guanajuato", "GRO": "Guerrero",
    "HID": "Hidalgo", "JAL": "Jalisco", "MIC": "Michoacán", "MOR": "Morelos",
    "NAY": "Nayarit", "NLE": "Nuevo León", "OAX": "Oaxaca", "PUE": "Puebla",
    "QUE": "Querétaro", "ROO": "Quintana Roo", "SLP": "San Luis Potosí",
    "SIN": "Sinaloa", "SON": "Sonora", "TAB": "Tabasco", "TAM": "Tamaulipas",
    "TLA": "Tlaxcala", "VER": "Veracruz", "YUC": "Yucatán", "ZAC": "Zacatecas",
    "NAL": "Nacional",
}


def get_text_from_pdf(pdf_path: Path, max_pages: int = 3) -> tuple[str, dict]:
    """Extrae texto embebido de las primeras N paginas del PDF + metadata."""
    try:
        import fitz
    except ImportError:
        sys.exit("pymupdf no instalado. Ejecuta: pip install pymupdf")
    doc = fitz.open(pdf_path)
    pages_to_read = min(max_pages, doc.page_count)
    text = "\n".join(doc[i].get_text() for i in range(pages_to_read))
    metadata = dict(doc.metadata) if doc.metadata else {}
    doc.close()
    return text, metadata


def extract_titulo_cientifico(text: str) -> Optional[str]:
    """Heuristica para papers cientificos: detectar titulo y autor.

    Patron academico:
    - Keywords (Palabras clave/Key words) en lineas tempranas
    - Autor marcado con asterisco * al final del nombre (nota al pie)
    - Titulo: las lineas inmediatamente ANTES del autor, en MAYUSCULAS
      o con interrogacion/tilde, longitud corta a mediana

    Devuelve (titulo, autor) si los encuentra.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Buscar keywords en las primeras 10 lineas (señal de paper academico)
    has_keywords = any(re.search(
        r"^\s*(palabras clave|key words)",
        line, re.IGNORECASE
    ) for line in lines[:10])

    if not has_keywords:
        return None

    # Buscar autor: linea que termine con * (nota al pie academica)
    autor = None
    autor_idx = None
    for idx, line in enumerate(lines[:50]):
        # Patron: "Nombre Apellido*" o "Nombre Apellido1*"
        if re.search(r"[A-Za-zÀ-ÿ]\s*\*\s*$", line) and 5 <= len(line) <= 80 \
                and not line.endswith("**") \
                and not line.startswith("Cómo") \
                and not line.startswith("Como"):
            autor = line.rstrip("*").strip()
            autor_idx = idx
            break

    if autor is None:
        return None

    # Titulo: las 1-3 lineas inmediatamente antes del autor
    # que parezcan un titulo (no Resumen/Abstract, no paragrapho largo)
    titulo_lines = []
    for idx in range(autor_idx - 1, max(0, autor_idx - 6), -1):
        line = lines[idx]
        # Filtrar cosas que no son titulo
        if re.match(r"^\s*(resumen|abstract|summary|introducción|introduccion)", line, re.IGNORECASE):
            break
        # Si la linea es muy larga (>150 chars), probablemente es parrafo, no titulo
        if len(line) > 150:
            break
        # Si la linea es muy corta (<5), probablemente es numero de pagina
        if len(line) < 5:
            break
        # Si contiene '@' o '.mx' o palabras de email/nota al pie, parar
        if "@" in line or ".mx" in line or ".com" in line or ".unam" in line:
            break
        # Si parece nota al pie (palabras clave academicas)
        if re.search(r"\b(doctor|doctorado|investigaci[oó]n|profesor|instituto|universidad|correo|electr[oó]nico)\b",
                     line, re.IGNORECASE):
            break
        titulo_lines.insert(0, line)

    if not titulo_lines:
        return None

    titulo = " ".join(titulo_lines).strip()
    titulo = re.sub(r"\s+", " ", titulo)
    if 15 <= len(titulo) <= 300:
        return (titulo, autor)
    return None


def extract_titulo(text: str, filename_hint: Optional[str] = None) -> Optional[str]:
    """Heuristica: busca el titulo del documento entre las primeras lineas mayusculas.

    Estrategia en orden de prioridad:
    0. Si el texto parece un paper cientifico (tiene keywords), usar extract_titulo_cientifico.
    1. Si el texto tiene keywords de titulo (CRITERIOS, LINEAMIENTOS, etc.), usar el texto.
       Esto se prefiere sobre el filename_hint para evitar usar nombres basura.
    2. Si filename_hint tiene un slug razonable (>15 chars despues de quitar prefijo), usarlo.
    3. Si no, primera linea >= 30 chars con mayusculas predominantes.
    """
    # Estrategia 0: paper cientifico
    sci_result = extract_titulo_cientifico(text)
    if sci_result:
        return sci_result[0]

    skip_patterns = [
        r"^\s*p[aá]gina\s+\d+", r"^\s*\d+\s*de\s*\d+",
        r"^\s*(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+",
        r"^\s*am[eé]rica\s+no\.", r"^\s*col\.\s+los reyes", r"^\s*cp\.\s+\d",
        r"^\s*tel[eé]fono", r"^\s*www\.",
        r"^\s*con fundamento en",
        r"^\s*considerando",
        r"^\s*visto\s+",
        r"^\s*art[ií]culo\s+\d+",
    ]
    title_keywords = [
        "CRITERIOS GENERALES", "LINEAMIENTOS GENERALES", "LINEAMIENTOS PARA",
        "LINEAMIENTOS",  # Cualquier LINEAMIENTO (no solo GENERALES/PARA)
        "REGLAMENTO", "CONSTITUCIÓN POLÍTICA", "CÓDIGO", "LEY GENERAL",
        "MANUAL DE", "CONVENIO DE", "CONVENIO DE COORDINACIÓN",
        "ACUERDO POR EL QUE", "DECRETO POR EL QUE",
        "CRITERIOS PARA", "REGLAS DE",
        "TÉRMINOS DE REFERENCIA",
    ]
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Estrategia 1: buscar keyword de titulo en el texto (preferida sobre filename)
    # Track todas las candidatas y elegir la mejor (mas larga/especifica)
    candidatas = []
    prev_was_juridic = False  # Marca si la linea anterior fue marcada como skip_if_better
    for idx, line in enumerate(lines):
        if len(line) < 20:
            prev_was_juridic = False
            continue
        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            prev_was_juridic = False
            continue
        # Filtrar parrafos juridicos que mencionan leyes por casualidad
        if re.match(r"^\s*(con fundamento|visto\s+|considerando\s+|en ejercicio\s+de\s+las)",
                    line, re.IGNORECASE):
            prev_was_juridic = False
            continue
        upper_line = line.upper()
        if any(kw in upper_line for kw in title_keywords):
            # Filtrar lineas con muchos articulos/fracciones/numeros (probable parrafo juridico)
            juridicos = re.findall(r"\b(?:art[íi]culo|fracci[oó]n|inciso|numeral|apartado|literal|subnumeral)\b",
                                   line, re.IGNORECASE)
            if len(juridicos) >= 2:
                prev_was_juridic = True
                continue
            nums = re.findall(r"\b\d+\b|\b[IVX]+\b", line)
            if len(nums) >= 3:
                prev_was_juridic = True
                continue
            # Filtrar parrafos juridicos con muchas comas (formato de referencias)
            if line.count(",") + line.count(";") >= 4:
                prev_was_juridic = True
                continue
            # Filtrar lineas que sean solo "ANEXO X DEL ACUERDO"
            if re.match(r"^\s*(ANEXO\s+\d|ARTI?CULO\s+\d|CAP[IÍ]TULO\s+\d|SECCI[OÓ]N\s+[IVX]+)",
                        upper_line):
                prev_was_juridic = True
                continue
            # Filtrar lineas que son encabezados del medio de publicacion
            # Ej: "DOF: 22/01/2026" o "DIARIO OFICIAL DE LA FEDERACION"
            if re.match(r"^\s*(DOF|DIARIO\s+OFICIAL|Periodico\s+Oficial)\s*[:\.]?\s*\d",
                        line, re.IGNORECASE):
                prev_was_juridic = True
                continue
            # Filtrar referencias juridicas (Reglamento/Ley de...)
            if re.match(r"^\s*(Reglamento|Ley|Código|Constitución)\s+(de|del|de\s+la)\s+",
                        line, re.IGNORECASE):
                prev_was_juridic = True
                candidatas.append(("skip_if_better", line))
                continue
            # Filtrar continuacion de linea juridica
            if prev_was_juridic:
                if re.match(r"^\s*[IVX]+\s*,\s+\d", line):
                    continue
                if line and line[0].islower():
                    continue
            # Concatenar lineas siguientes que sean continuacion del titulo
            # (todas en MAYUSCULAS, sin punto final, sin keyword de inicio de seccion)
            full_title = line
            j = idx + 1
            while j < len(lines):
                next_line = lines[j]
                # Solo concatenar si:
                # - esta en MAYUSCULAS (mayoria)
                # - no es keyword de seccion
                # - no excede 350 chars total
                if (len(full_title) + len(next_line)) > 350:
                    break
                # Linea muy corta (ej. solo "2025"): concatenar si la anterior era titulo
                if len(next_line) < 30:
                    # No concatenar si es keyword de seccion
                    if re.match(r"^(CAP[ÍI]TULO|SECCI[OÓ]N|ART[ÍI]CULO|TRANSITORIO|DECRETA|APRUEBA)\s+",
                                next_line, re.IGNORECASE):
                        break
                    upper_chars = sum(1 for c in next_line if c.isupper() or c.isdigit())
                    if upper_chars >= len(next_line) * 0.7:
                        full_title = full_title + " " + next_line
                        j += 1
                        continue
                    else:
                        break
                # Si la linea siguiente empieza con minuscula, probable continuacion
                # del titulo (frase no terminada)
                if next_line and next_line[0].islower():
                    full_title = full_title + " " + next_line
                    j += 1
                    continue
                upper_next = next_line.upper()
                upper_chars = sum(1 for c in next_line if c.isupper())
                if upper_chars < len(next_line) * 0.5:
                    break
                if re.match(r"^(CAP[ÍI]TULO|SECCI[OÓ]N|ART[ÍI]CULO|TRANSITORIO|DECRETA|APRUEBA)\s+",
                            next_line, re.IGNORECASE):
                    break
                # Concatenar
                full_title = full_title + " " + next_line
                j += 1
            candidatas.append(("accept", full_title.strip()))
            prev_was_juridic = False

    # Si tenemos candidatas aceptadas, devolver la primera
    for tipo, line in candidatas:
        if tipo == "accept":
            return re.sub(r"\s+", " ", line).strip()

    # Si solo tenemos skip_if_better, devolver la primera
    if candidatas:
        return re.sub(r"\s+", " ", candidatas[0][1]).strip()

    # Estrategia 2: filename hint (solo si no se encontro nada en texto)
    if filename_hint:
        base = filename_hint.rsplit(".", 1)[0]
        base = re.sub(r"^[Ff][Aa][Ss][Pp]_[\d_]+(?:[A-Z_]+)_", "", base)
        if base.upper() in ("TDR_V1_0", "V1_0", "V1", ""):
            base = ""
        base = base.replace("_", " ").strip()
        replacements = [
            (r"\bEvaluaci n\b", "Evaluación"),
            (r"\bEvaluaci[oó]n\b", "Evaluación"),
            (r"\bAdministraci n\b", "Administración"),
            (r"\bPublicaci n\b", "Publicación"),
        ]
        for pat, rep in replacements:
            base = re.sub(pat, rep, base)
        if 15 <= len(base) <= 200 and not re.search(r"^\d+$", base):
            return base

    # Estrategia 3: primera linea con mayusculas predominantes
    for line in lines:
        if len(line) < 30:
            continue
        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            continue
        upper_chars = sum(1 for c in line if c.isupper() or c in "ÁÉÍÓÚÑ")
        if upper_chars > len(line) * 0.4:
            return re.sub(r"\s+", " ", line).strip()

    return None


def extract_organo_emisor(text: str) -> Optional[str]:
    """Busca los ORGANOS_EMISORES conocidos en las primeras paginas."""
    upper_text = text.upper()
    for organo in ORGANOS_EMISORES:
        if organo in upper_text:
            return organo.title().replace(" Del ", " del ").replace(" De ", " de ")
    # Heuristica secundaria: lineas que contengan SECRETARIADO/CONSEJO/COMISION
    for line in text.split("\n")[:50]:
        line_up = line.strip().upper()
        if any(k in line_up for k in ["SECRETARIADO", "CONSEJO", "CONGRESO", "PRESIDENCIA", "COMISIÓN PERMANENTE"]):
            cleaned = re.sub(r"\s+", " ", line.strip())
            if 10 <= len(cleaned) <= 150:
                return cleaned
    return None


def extract_fecha(text: str) -> tuple[Optional[str], Optional[str]]:
    """Devuelve (ISO YYYY-MM-DD, texto crudo). None si no se puede."""
    # Patron 1: "Sábado 27 de diciembre de 2025"
    m = re.search(
        r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES.keys()) + r")\s+de\s+(\d{4})\b",
        text, re.IGNORECASE,
    )
    if m:
        dia, mes_nombre, anio = m.groups()
        mes_num = MESES.get(mes_nombre.lower())
        if mes_num:
            iso = f"{anio}-{mes_num:02d}-{int(dia):02d}"
            return iso, m.group(0)

    # Patron 2: DD/MM/YYYY o DD-MM-YYYY
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", text)
    if m:
        d, mo, y = m.groups()
        iso = f"{y}-{int(mo):02d}-{int(d):02d}"
        return iso, m.group(0)

    # Patron 3: YYYY-MM-DD
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        y, mo, d = m.groups()
        iso = f"{y}-{int(mo):02d}-{int(d):02d}"
        return iso, m.group(0)

    # Patron 4: solo anio "ejercicio fiscal YYYY"
    m = re.search(r"ejercicio\s+fiscal\s+(\d{4})", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-01-01", m.group(0)

    return None, None


def extract_lugar(text: str) -> Optional[str]:
    """Heuristica: detecta Ciudad de Mexico, Mexico, o entidad federativa."""
    upper = text.upper()
    if "CIUDAD DE MÉXICO" in upper or "CIUDAD DE MEXICO" in upper:
        return "Ciudad de México"
    # Buscar el primer estado mencionado al inicio
    for edo_clave, edo_nombre in ENTIDADES_FEDERATIVAS.items():
        if edo_nombre.upper() in upper:
            return edo_nombre
    return None


def extract_medio_publicacion(text: str) -> Optional[str]:
    """Detecta el medio oficial de publicacion."""
    upper = text.upper()
    # Priorizar DOF
    if "DIARIO OFICIAL DE LA FEDERACIÓN" in upper or "DIARIO OFICIAL DE LA FEDERACION" in upper:
        return "Diario Oficial de la Federación"
    if "DIARIO OFICIAL" in upper:
        return "Diario Oficial de la Federación"
    if "PERIÓDICO OFICIAL" in upper or "PERIODICO OFICIAL" in upper:
        return "Periódico Oficial del Estado"
    if "GACETA" in upper:
        return "Gaceta de Gobierno"
    if "SITIO INSTITUCIONAL" in upper or "WWW.GOB.MX" in upper:
        return "Sitio institucional"
    return None


def extract_tipo_documento(text: str, filename_hint: Optional[str] = None) -> Optional[str]:
    """Detecta el tipo de documento segun vocabulario cerrado (orden de prioridad).

    Estrategia 0: si hay filename_hint, usar keywords del nombre del archivo
    Estrategia 1: buscar keywords en las primeras 5 lineas mayusculas (titulo probable)
    """
    priority_order = [
        "CRITERIOS GENERALES",  # -> Criterio
        "LINEAMIENTO",          # -> Lineamiento
        "CONSTITUCIÓN POLÍTICA",  # -> Constitución
        "REGLAMENTO",
        "CÓDIGO",
        "CONVENIO DE COORDINACIÓN",  # -> Convenio
        "CONVENIO",
        "ACUERDO",
        "MANUAL DE ORGANIZACIÓN",
        "MANUAL",
        "LEY GENERAL",          # -> Ley
        "DECRETO",
        "NORMA OFICIAL MEXICANA",  # -> Norma
    ]
    tipo_map = {
        "CRITERIOS GENERALES": "Criterio",
        "LINEAMIENTO": "Lineamiento",
        "CONSTITUCIÓN POLÍTICA": "Constitución",
        "REGLAMENTO": "Reglamento",
        "CÓDIGO": "Código",
        "CONVENIO DE COORDINACIÓN": "Convenio",
        "CONVENIO": "Convenio",
        "ACUERDO": "Acuerdo",
        "MANUAL DE ORGANIZACIÓN": "Manual de organización",
        "MANUAL": "Manual",
        "LEY GENERAL": "Ley",
        "DECRETO": "Decreto",
        "NORMA OFICIAL MEXICANA": "Norma",
    }

    # Estrategia 0: filename_hint
    if filename_hint:
        upper_hint = filename_hint.upper()
        for kw in priority_order:
            if kw in upper_hint:
                return tipo_map[kw]
        if "TDR" in upper_hint or "TÉRMINOS DE REFERENCIA" in upper_hint:
            return "Otro"

    # Estrategia 1: buscar en primeras lineas (donde estaria el titulo)
    lines = [l.strip().upper() for l in text.split("\n") if l.strip()][:30]
    head_text = "\n".join(lines)
    for kw in priority_order:
        if kw in head_text:
            return tipo_map[kw]
    return None


def extract_numero_norma(text: str) -> Optional[str]:
    """Detecta numero de norma o acuerdo."""
    # Evitar matches falsos como "No. 300" de direcciones
    patterns = [
        r"\bACUERDO\s+\d+[A-Z]*/[A-Z]+/\d{4}\b",  # ACUERDO 03/LII/2025
        r"\bDECRETO\s+(?:POR\s+EL\s+QUE\s+)?(?:SE\s+)?(?:REFORMA|ADICIONA|EXPIDE)\b",
        r"\bLINEAMIENTOS\s+(\d+/\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://[^\s\)\]<>\"']+", text)
    return m.group(0).rstrip(".,;") if m else None


def extract_doi(text: str, url: Optional[str] = None) -> Optional[str]:
    """Extrae un DOI del texto o de una URL dx.doi.org."""
    # DOI explícito en el texto (ej. "doi: 10.xxxx/yyyy")
    m = re.search(r"\b10\.\d{4,9}/[^\s\)\]<>\"']+", text)
    if m:
        return m.group(0).rstrip(".,;")
    # DOI dentro de una URL dx.doi.org
    if url and "dx.doi.org/" in url:
        return url.split("dx.doi.org/")[1].rstrip(".,;")
    # DOI dentro de una URL doi.org
    if url and "doi.org/" in url:
        return url.split("doi.org/")[1].rstrip(".,;")
    return None


def fetch_crossref_metadata(doi: str, timeout: int = 15) -> Optional[dict]:
    """Consulta la API de CrossRef para obtener metadata de un DOI.

    Devuelve dict con: titulo, autor, fecha_publicacion, anio, container, volumen, issue, page, publisher.
    Devuelve None si no se puede resolver o si requests no esta disponible.
    """
    if requests is None:
        return None
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=timeout)
        if r.status_code != 200:
            return None
        msg = r.json().get("message", {})

        # Titulo
        title_list = msg.get("title", [])
        titulo = title_list[0] if title_list else None

        # Autores (formato APA: "Apellido, N.")
        authors = msg.get("author", [])
        autor_parts = []
        for a in authors:
            given = a.get("given", "").strip()
            family = a.get("family", "").strip()
            if not family:
                continue
            if given:
                initials = " ".join(f"{n[0]}." for n in given.split() if n)
                autor_parts.append(f"{family}, {initials}")
            else:
                autor_parts.append(family)
        autor = ", ".join(autor_parts) if autor_parts else None

        # Año
        pub = msg.get("published-print") or msg.get("published-online") or msg.get("issued", {})
        date_parts_list = pub.get("date-parts", [[None]])
        try:
            year = date_parts_list[0][0] if date_parts_list and date_parts_list[0] else None
        except (IndexError, TypeError):
            year = None

        # Container
        container_list = msg.get("container-title", [])
        container = container_list[0] if container_list else None

        return {
            "titulo": titulo,
            "autor": autor,
            "anio": year,
            "fecha_publicacion": f"{year}-01-01" if year else None,
            "container": container,
            "volumen": msg.get("volume"),
            "issue": msg.get("issue"),
            "page": msg.get("page"),
            "publisher": msg.get("publisher"),
        }
    except Exception:
        return None


def fetch_redalyc_metadata(redalyc_id: str, timeout: int = 15) -> Optional[dict]:
    """Scrapea metadata de un articulo de Redalyc por su ID numerico.

    Ejemplo: fetch_redalyc_metadata('357533674002')
    Devuelve dict con: titulo, autor, anio, container, fecha_publicacion.
    Devuelve None si no se puede resolver o si requests no esta disponible.
    """
    if requests is None:
        return None
    try:
        url = f"https://www.redalyc.org/articulo.oa?id={redalyc_id}"
        r = requests.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return None
        html = r.text

        def extract_meta(name):
            m = re.search(
                rf'<meta\s+name="{name}"\s+content="([^"]+)"',
                html, re.IGNORECASE,
            )
            return m.group(1) if m else None

        titulo = extract_meta("citation_title")
        autor = extract_meta("citation_author")
        if autor:
            autor = re.sub(r"\s+", " ", autor).strip()
        fecha = extract_meta("citation_publication_date")
        container = extract_meta("citation_journal_title")
        volumen = extract_meta("citation_volume")
        issue = extract_meta("citation_issue")
        firstpage = extract_meta("citation_firstpage")
        lastpage = extract_meta("citation_lastpage")

        page = None
        if firstpage and lastpage:
            page = f"{firstpage}-{lastpage}"
        elif firstpage:
            page = firstpage

        year = None
        if fecha:
            m = re.search(r"\d{4}", fecha)
            if m:
                year = int(m.group(0))

        if not titulo:
            return None

        return {
            "titulo": titulo,
            "autor": autor,
            "anio": year,
            "fecha_publicacion": f"{year}-01-01" if year else None,
            "container": container,
            "volumen": volumen,
            "issue": issue,
            "page": page,
            "publisher": None,
        }
    except Exception:
        return None


def slugify(text: str, max_len: int = 60) -> str:
    """Convierte un texto en un slug kebab-case para usar como codigo.

    'Altos funcionarios del estado y funcionamiento multinivel del Estado español'
    -> 'altos-funcionarios-estado-funcionamiento-multinivel-estado-espanol'

    Solo caracteres alfanumericos y guiones. Limita longitud.
    """
    import unicodedata
    # Normalizar acentos: 'español' -> 'espanol'
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # MAYUSCULAS (formato oficial FASP_2026 usa MAYUSCULAS en el slug)
    text = text.upper()
    # Solo [A-Z0-9], reemplazar resto con -
    import re as _re
    text = _re.sub(r"[^A-Z0-9]+", "-", text)
    # Limpiar guiones repetidos y de los extremos
    text = _re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] if text else "DOC"


def generate_codigo_archivo(meta: dict, filename_hint: Optional[str] = None,
                            edo_key: Optional[str] = None) -> str:
    """Genera un codigo de archivo limpio basado en la metadata real.

    Prioridad:
    1. Si tiene DOI: 'FASP_2026_P1_<EDO>_<DOI-slug>' (ej. FASP_2026_P1_NAL_10_5209_CGAP_62454)
    2. Si filename tiene Redalyc ID: 'FASP_2026_P1_<EDO>_REDALYC_<id>'
    3. Si tipo_documento es TDR/terminos: 'FASP_2026_P1_<EDO>_TDR_V1.0'
    4. Si tipo_documento es NORFED: 'FASP_2026_P1_NAL_NORFED_<slug>'
    5. Si tipo_documento es BIB o el filename esta en carpeta Bibliografia: 'FASP_2026_P1_<EDO>_BIB_<slug>'
    6. Slug del titulo (para normativas y otros)
    7. Fallback: nombre del archivo sin extension
    """
    # 1. DOI
    doi = meta.get("doi")
    edo = edo_key or meta.get("clave_edo", "NAL")
    if doi:
        doi_slug = doi.replace("/", "_").replace(".", "_").replace("-", "_")
        return f"FASP_2026_P1_{edo}_{doi_slug}"

    # 2. Redalyc ID (desde filename)
    if filename_hint:
        redalyc_id = extract_redalyc_id_from_filename(filename_hint)
        if redalyc_id:
            return f"FASP_2026_P1_{edo}_REDALYC_{redalyc_id}"
    # 3-6. Tipo de documento + slug
    tipo = meta.get("tipo_documento", "").lower() if meta.get("tipo_documento") else ""
    titulo = meta.get("titulo")
    slug = slugify(titulo, max_len=50) if titulo and len(titulo) > 15 else ""

    # Detectar TDR por nombre del archivo o tipo_documento
    is_tdr = False
    if filename_hint and "TDR" in filename_hint.upper():
        is_tdr = True
    if tipo in ("otro",) and filename_hint and "TDR" in filename_hint.upper():
        is_tdr = True

    # Detectar NORFED (normativa federal) por carpeta
    is_norfed = False
    if filename_hint and "NORFED" in filename_hint.upper():
        is_norfed = True

    # Detectar BIB (bibliografia) por carpeta o tipo
    is_bib = False
    if filename_hint and "BIB" in filename_hint.upper():
        is_bib = True

    if is_tdr:
        # TDRs escaneados no tienen texto. Usar file_id corto para unicidad.
        # Formato oficial: FASP_2026_P1_<EDO>_TDR-<SLUG>_V1.0
        # El script xlsx_writer puede pasar file_id_hint
        file_id_hint = meta.get("file_id_short") or "doc"
        # Si hay folder_name_hint (del folder padre), usarlo
        folder_hint = meta.get("folder_name_hint")
        if folder_hint:
            slug = slugify(folder_hint, max_len=40)
            if slug:
                return f"FASP_2026_P1_{edo}_TDR-{slug}_V1.0"
        return f"FASP_2026_P1_{edo}_TDR-{file_id_hint}_V1.0"
    if is_norfed and slug:
        return f"FASP_2026_P1_{edo}_NORFED-{slug}_V1.0"
    if is_bib and slug:
        return f"FASP_2026_P1_{edo}_BIB-{slug}_V1.0"
    if is_norfed:
        return f"FASP_2026_P1_{edo}_NORFED-DOC_V1.0"
    if is_bib:
        return f"FASP_2026_P1_{edo}_BIB-DOC_V1.0"

    # 7. Slug del titulo para normativas y otros
    if slug:
        return f"FASP_2026_P1_{edo}_{slug}_V1.0"

    # 8. Fallback: nombre del archivo sin extension
    if filename_hint:
        return filename_hint.rsplit(".", 1)[0]

    return f"FASP_2026_P1_{edo}_DOC"


def extract_redalyc_id_from_filename(filename: str) -> Optional[str]:
    """Si el filename contiene un numero de 10+ digitos, asumir que es un ID de Redalyc.

    Ejemplos:
        '357533674002.pdf' -> '357533674002'
        'FASP_2026_P1_NAL_BIB_357533674002_V1.0.pdf' -> '357533674002'
        'TDR_EDOMX.pdf' -> None
    """
    base = filename.rsplit(".", 1)[0]
    # Buscar secuencia de 10+ digitos consecutivos (entre separadores no-digit)
    m = re.search(r"(?:^|[^\d])(\d{10,})(?:[^\d]|$)", base)
    if m:
        return m.group(1)
    return None


def inferir_ambito_y_edo(carpetas_path: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Infiere ambito (FED/EST/MUN) y clave de estado desde el path del archivo."""
    # Buscar en el path alguna clave conocida
    path_str = "/".join(carpetas_path).upper()
    for edo_clave, edo_nombre in ENTIDADES_FEDERATIVAS.items():
        if edo_clave in path_str or edo_nombre.upper() in path_str:
            if edo_clave == "NAL":
                return "FED", "NAL"
            return "EST", edo_clave
    return None, None


def generar_cita_apa(meta: dict) -> Optional[str]:
    """Genera una cita en formato APA 7 a partir de los metadatos extraidos."""
    partes = []

    # Autor
    autor = meta.get("autor")
    if autor:
        # Si ya termina con punto (formato APA "Apellido, N."), no agregar otro
        if autor.endswith("."):
            partes.append(autor)
        else:
            partes.append(f"{autor}.")

    # Anio entre parentesis
    anio = meta.get("anio")
    if anio:
        partes.append(f"({anio}).")

    # Titulo en italica
    titulo = meta.get("titulo")
    if titulo:
        partes.append(f"*{titulo}*.")

    # Container (revista) - si existe, va despues del titulo en cursiva
    container = meta.get("container")
    volumen = meta.get("volumen")
    issue = meta.get("issue")
    page = meta.get("page")
    if container:
        container_str = f"*{container}*"
        if volumen and volumen.strip():
            container_str += f", {volumen}"
            if issue and issue.strip():
                container_str += f"({issue})"
        elif issue and issue.strip():
            container_str += f", {issue}"
        if page and page.strip():
            container_str += f", {page}"
        partes.append(container_str + ".")

    # Medio de publicacion
    medio = meta.get("medio_publicacion")
    lugar = meta.get("lugar")
    publisher = meta.get("editorial") or meta.get("publisher")
    if publisher and not container:
        # Si no hay container, usar publisher como editorial
        partes.append(f"{publisher}.")
    elif lugar and not container:
        partes.append(f"{lugar}.")
    elif container:
        # Si hay container (revista), no poner lugar aparte
        pass

    # URL
    url = meta.get("url")
    if url:
        partes.append(url)

    return " ".join(partes) if partes else None


def extract_from_text(text: str, edo_hint: Optional[str] = None,
                      filename_hint: Optional[str] = None,
                      pdf_metadata: Optional[dict] = None) -> dict:
    """Pipeline principal: extrae todos los campos del texto.

    Si pdf_metadata esta disponible y tiene title/author, los usa
    con prioridad sobre el texto y el nombre del archivo.
    """
    meta = {
        "titulo": None,
        "autor": None,
        "fecha_publicacion": None,
        "fecha_original": None,
        "lugar": None,
        "medio_publicacion": None,
        "tipo_documento": None,
        "numero_norma": None,
        "url": None,
        "anio": None,
        "ambito": None,
        "clave_edo": None,
        # Campos enriquecidos por CrossRef
        "container": None,
        "volumen": None,
        "issue": None,
        "page": None,
        "publisher": None,
    }

    # 1. PRIORIDAD: metadata del PDF (mas confiable)
    if pdf_metadata:
        pdf_title = pdf_metadata.get("title", "").strip()
        pdf_author = pdf_metadata.get("author", "").strip()
        pdf_subject = pdf_metadata.get("subject", "").strip()

        # Descartar titulos del PDF metadata que son del navegador web (no del documento)
        # Patron: "DOF - Diario Oficial...", "Gobierno de Mexico", "Sitio web", etc.
        metadata_titles_basura = [
            r"^DOF\s*[-–]\s*Diario Oficial",
            r"^Diario Oficial de la Federaci[oó]n$",
            r"^Gobierno\s+(de|del)\s+M[eé]xico",
            r"^Sitio\s+web",
            r"^Home\s*[-–]",
            r"^Portal\s+",
        ]
        is_metadata_basura = any(re.search(p, pdf_title, re.IGNORECASE)
                                   for p in metadata_titles_basura)

        if (pdf_title and len(pdf_title) > 5
                and not pdf_title.startswith("Microsoft")
                and not is_metadata_basura):
            # Limpiar prefijos de sistemas academicos (Redalyc. al inicio)
            pdf_title = re.sub(r"^(Redalyc|SCIELO|JSTOR|Springer)\.\s*", "", pdf_title)
            meta["titulo"] = pdf_title
        if pdf_author and len(pdf_author) > 3 and not pdf_author.startswith("Microsoft"):
            # Limpiar newlines al final del autor
            pdf_author = re.sub(r"\s+", " ", pdf_author).strip()
            meta["autor"] = pdf_author
        # Subject a veces contiene info de la publicacion
        if pdf_subject and pdf_subject != pdf_title:
            # Si el subject es descriptivo y parece un titulo largo, lo agregamos
            if "funcionarios" in pdf_subject.lower() or "coordinaci" in pdf_subject.lower():
                if not meta["titulo"]:
                    meta["titulo"] = pdf_subject.split(".")[0]

    # 2. Si no se encontro en metadata, usar heuristicas del texto/filename
    if not meta["titulo"]:
        titulo_sci = extract_titulo_cientifico(text)
        if titulo_sci:
            meta["titulo"], autor_sci = titulo_sci
            if not meta["autor"]:
                meta["autor"] = autor_sci
        else:
            meta["titulo"] = extract_titulo(text, filename_hint=filename_hint)
    if not meta["autor"]:
        meta["autor"] = extract_organo_emisor(text)

    # Resto de campos siempre desde el texto
    meta["lugar"] = extract_lugar(text)
    meta["medio_publicacion"] = extract_medio_publicacion(text)
    meta["tipo_documento"] = extract_tipo_documento(text, filename_hint=filename_hint)
    meta["numero_norma"] = extract_numero_norma(text)
    meta["url"] = extract_url(text)

    # Si hay DOI (en URL o texto), consultar CrossRef para metadata enriquecida
    doi = extract_doi(text, url=meta["url"])
    meta["doi"] = doi  # Guardar para generate_codigo_archivo
    crossref = None
    if doi:
        crossref = fetch_crossref_metadata(doi)

    # Si no hay DOI o CrossRef fallo, intentar Redalyc si filename parece ID
    if not crossref and filename_hint:
        redalyc_id = extract_redalyc_id_from_filename(filename_hint)
        if redalyc_id:
            crossref = fetch_redalyc_metadata(redalyc_id)

    if crossref:
        # CrossRef/Redalyc tiene prioridad sobre heuristicas del texto/filename
        if crossref.get("titulo"):
            meta["titulo"] = crossref["titulo"]
        if crossref.get("autor"):
            meta["autor"] = crossref["autor"]
        if crossref.get("anio"):
            meta["anio"] = crossref["anio"]
            meta["fecha_publicacion"] = crossref["fecha_publicacion"]
        if crossref.get("container"):
            # Usar la revista como lugar o editorial
            meta["container"] = crossref["container"]
            meta["editorial"] = crossref.get("publisher") or crossref["container"]
            meta["lugar"] = crossref["container"]
        # Guardar pagina, volumen, issue para la cita
        if crossref.get("page"):
            meta["page"] = crossref["page"]
        if crossref.get("volumen"):
            meta["volumen"] = crossref["volumen"]
        if crossref.get("issue"):
            meta["issue"] = crossref["issue"]

    # Fecha
    iso, original = extract_fecha(text)
    meta["fecha_publicacion"] = iso
    meta["fecha_original"] = original
    if iso:
        meta["anio"] = int(iso.split("-")[0])
    elif pdf_metadata and pdf_metadata.get("creationDate"):
        # Intentar extraer anio del creationDate del PDF
        m = re.search(r"(\d{4})", pdf_metadata["creationDate"])
        if m:
            meta["anio"] = int(m.group(1))
            meta["fecha_publicacion"] = f"{m.group(1)}-01-01"

    # Ambito y estado
    if edo_hint:
        if edo_hint.upper() == "NAL":
            meta["ambito"] = "FED"
        else:
            meta["ambito"] = "EST"
        meta["clave_edo"] = edo_hint.upper()

    # Cita APA
    meta["formato_cita_apa"] = generar_cita_apa(meta)

    return meta


def main():
    ap = argparse.ArgumentParser(description="Extractor de metadatos APA 7 para FASP")
    ap.add_argument("--pdf", help="Ruta al PDF")
    ap.add_argument("--md", help="Ruta al MD")
    ap.add_argument("--edo", help="Clave de estado (MEX, HID, NAL, etc.) para hint")
    ap.add_argument("--filename", help="Nombre del archivo original (hint para titulo/tipo)")
    ap.add_argument("--json", action="store_true", help="Salida JSON")
    args = ap.parse_args()

    if not args.pdf and not args.md:
        ap.error("Especifica --pdf o --md")

    if args.pdf:
        text, pdf_metadata = get_text_from_pdf(Path(args.pdf))
        # Si no se pasa --filename, usar el nombre del PDF
        filename_hint = args.filename or Path(args.pdf).name
    else:
        text = Path(args.md).read_text(encoding="utf-8")
        filename_hint = args.filename or Path(args.md).name
        pdf_metadata = None

    meta = extract_from_text(text, edo_hint=args.edo,
                             filename_hint=filename_hint,
                             pdf_metadata=pdf_metadata)

    if args.json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("METADATOS APA EXTRAÍDOS")
        print("=" * 60)
        for k, v in meta.items():
            label = k.replace("_", " ").title()
            if v is None:
                v_str = "(no detectado)"
            else:
                v_str = str(v)
            print(f"  {label:25s} {v_str}")
        print()
        if meta.get("formato_cita_apa"):
            print("CITA APA 7:")
            print(f"  {meta['formato_cita_apa']}")


if __name__ == "__main__":
    main()
