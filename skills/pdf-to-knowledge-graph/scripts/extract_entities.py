#!/usr/bin/env python3
"""
extract_entities.py — Etapa 2 del pipeline.

Extrae entidades nombradas de un Markdown, clasificándolas por tipo
(INSTITUCION, CARGO, NORMA, DOCUMENTO, PERSONA, LUGAR) y capa
(normativo, operativo, informal) según el contexto del documento.

Estrategia combinada:
1. Diccionario base (references/diccionario_gobernanza_mx.txt).
2. Patrones regex para cargos, leyes, oficios.
3. LLM opcional para textos ambiguos (--use-llm).

Uso:
    python3 extract_entities.py --md ./jobs/<job_id>/<job_id>.md \\
                                --meta ./jobs/<job_id>/<job_id>.meta.json \\
                                --output ./jobs/<job_id>/

    python3 extract_entities.py --md ./jobs/<job>/<job>.md --meta ./jobs/<job>/<job>.meta.json --output ./jobs/<job>/ --use-llm
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys
from collections import defaultdict, Counter

SCHEMA_VERSION = "1.0"

# Patrones regex
RE_CARGO = re.compile(
    r"\b(President(?:e|a)|Secretari[oa](?:\s+de\s+\w+)?|Subsecretari[oa]|"
    r"Director(?:a)?(?:\s+General)?|Coordinador(?:a)?(?:\s+General)?|"
    r"Subprocurador(?:a)?(?:\s+\w+)?|Comisionado(?:a)?(?:\s+\w+)?|"
    r"Titular|Jefe(?:a)?(?:\s+de\s+\w+)?|Ministr(?:o|a)|"
    r"Gobernador(?:a)|Presidente\s+Municipal|Síndico|Regidor(?:a))\b"
)

RE_LEY = re.compile(
    r"\b(?:Ley\s+(?:General\s+|Federal\s+|Orgánica\s+)?(?:de\s+(?:los?\s+)?)?"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,5}"
    r"(?:Pública|Federal|Nacional|General))"
    r"|\b(?:Constitución\s+Política\s+de\s+los\s+Estados\s+Unidos\s+Mexicanos)\b"
    r"|\b(?:Reglamento\s+(?:de\s+(?:la\s+)?)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,4})\b"
    r"|\bNOM[-\s][A-Z0-9\-]+",
    re.UNICODE
)

RE_OFICIO = re.compile(
    r"\b(?:Oficio|Circular|Memorándum|Memorando)\s+(?:No\.?\s*)?[A-Z0-9\-/]+",
    re.IGNORECASE
)

RE_PERSONA = re.compile(
    r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}"
    r"(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?\b"
)

RE_LUGAR = re.compile(
    r"\b(?:Estados\s+Unidos\s+Mexicanos|México|Ciudad\s+de\s+México|"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?"
    r"(?=\s*,\s*(?:[A-Z][a-z]+|[A-Z]{2})))\b"
)


def split_into_sections(md_text: str) -> list[tuple[str, str]]:
    """Divide el MD en (heading, cuerpo)."""
    lines = md_text.split("\n")
    sections = []
    current_heading = "(inicio)"
    current_body = []
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            if current_body:
                sections.append((current_heading, "\n".join(current_body)))
            current_heading = m.group(2).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_heading, "\n".join(current_body)))
    return sections


def load_diccionario(path: pathlib.Path) -> list[str]:
    """Carga el diccionario, ignorando comentarios."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.append(line)
    return sorted(set(entries), key=len, reverse=True)  # más largas primero


def find_entities_in_section(section_text: str, section_name: str,
                             diccionario: list[str],
                             default_layer: str) -> list[dict]:
    """Encuentra entidades en el texto de una sección."""
    entities = []
    seen_in_section = set()

    # 1. Diccionario
    for entry in diccionario:
        # Buscar palabra completa (case-insensitive pero respetando límites)
        pattern = re.compile(r"\b" + re.escape(entry) + r"\b", re.IGNORECASE)
        for m in pattern.finditer(section_text):
            key = ("INSTITUCION", entry.upper())
            if key not in seen_in_section:
                # Capturar contexto: 80 chars alrededor
                start = max(0, m.start() - 40)
                end = min(len(section_text), m.end() + 40)
                context = section_text[start:end].strip()
                entities.append({
                    "entity": entry,
                    "type": "INSTITUCION",
                    "layer": default_layer,
                    "section": section_name,
                    "context": context,
                })
                seen_in_section.add(key)

    # 2. Cargos
    for m in RE_CARGO.finditer(section_text):
        entities.append({
            "entity": m.group(0),
            "type": "CARGO",
            "layer": default_layer,
            "section": section_name,
            "context": _context(section_text, m.start(), m.end()),
        })

    # 3. Leyes y normas
    for m in RE_LEY.finditer(section_text):
        entities.append({
            "entity": m.group(0),
            "type": "NORMA",
            "layer": "normativo",
            "section": section_name,
            "context": _context(section_text, m.start(), m.end()),
        })

    # 4. Oficios / circulares / memorandos
    for m in RE_OFICIO.finditer(section_text):
        entities.append({
            "entity": m.group(0),
            "type": "DOCUMENTO",
            "layer": "operativo",
            "section": section_name,
            "context": _context(section_text, m.start(), m.end()),
        })

    # 5. Personas (heurística básica; baja precisión, solo si --use-llm)
    # Por defecto omitimos para evitar ruido; el LLM lo maneja mejor.

    # 6. Lugares
    for m in RE_LUGAR.finditer(section_text):
        entities.append({
            "entity": m.group(0),
            "type": "LUGAR",
            "layer": default_layer,
            "section": section_name,
            "context": _context(section_text, m.start(), m.end()),
        })

    return entities


def _context(text: str, start: int, end: int, window: int = 50) -> str:
    s = max(0, start - window)
    e = min(len(text), end + window)
    snippet = text[s:e].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet


def validate_entities(entities_path: pathlib.Path, md_path: pathlib.Path) -> dict:
    """Chequeos de la Etapa 2."""
    issues = []
    md = md_path.read_text(encoding="utf-8")
    sections = {h for h, _ in split_into_sections(md)}

    valid_types = {"INSTITUCION", "CARGO", "NORMA", "DOCUMENTO", "PERSONA", "LUGAR"}
    valid_layers = {"normativo", "operativo", "informal"}

    n = 0
    type_counts = defaultdict(int)
    layer_counts = defaultdict(int)

    with open(entities_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                e = json.loads(line)
            except json.JSONDecodeError as ex:
                issues.append(f"Línea {n}: JSON inválido ({ex})")
                continue
            if e.get("type") not in valid_types:
                issues.append(f"Línea {n}: type inválido {e.get('type')}")
            if e.get("layer") not in valid_layers:
                issues.append(f"Línea {n}: layer inválido {e.get('layer')}")
            if e.get("section") not in sections:
                issues.append(f"Línea {n}: sección '{e.get('section')}' no existe en MD")
            type_counts[e.get("type")] += 1
            layer_counts[e.get("layer")] += 1

    if n < 3:
        issues.append(f"Muy pocas entidades ({n}); revisar extracción")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "n_entities": n,
        "by_type": dict(type_counts),
        "by_layer": dict(layer_counts),
    }


def main():
    p = argparse.ArgumentParser(description="Etapa 2: Markdown → entidades")
    p.add_argument("--md", required=True)
    p.add_argument("--meta", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--diccionario", default=None)
    p.add_argument("--validate", action="store_true")
    args = p.parse_args()

    md_path = pathlib.Path(args.md)
    meta_path = pathlib.Path(args.meta)
    output = pathlib.Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    meta = json.loads(meta_path.read_text())
    default_layer = meta.get("layer") or "informal"

    if args.validate:
        v = validate_entities(output / "entities.jsonl", md_path)
        print(json.dumps(v, indent=2, ensure_ascii=False))
        sys.exit(0 if v["ok"] else 1)

    md_text = md_path.read_text(encoding="utf-8")
    sections = split_into_sections(md_text)

    # Diccionario
    dic_path = pathlib.Path(args.diccionario) if args.diccionario else \
        pathlib.Path(__file__).parent.parent / "references" / "diccionario_gobernanza_mx.txt"
    diccionario = load_diccionario(dic_path)
    print(f"Diccionario: {len(diccionario)} entradas")

    # Extraer
    entities_path = output / "entities.jsonl"
    n_total = 0
    with open(entities_path, "w", encoding="utf-8") as f:
        for heading, body in sections:
            ents = find_entities_in_section(body, heading, diccionario, default_layer)
            for e in ents:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
                n_total += 1

    print(f"✓ {n_total} entidades extraídas → {entities_path}")

    # Validación automática
    v = validate_entities(entities_path, md_path)
    print(f"Validación: {'✓' if v['ok'] else '⚠'} {v['n_entities']} entidades")
    for issue in v["issues"]:
        print(f"  - {issue}")
    (output / "entities.validation.json").write_text(json.dumps(v, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()