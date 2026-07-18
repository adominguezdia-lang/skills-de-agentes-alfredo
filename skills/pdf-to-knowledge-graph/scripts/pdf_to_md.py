#!/usr/bin/env python3
"""
pdf_to_md.py — Etapa 1 del pipeline pdf-to-knowledge-graph.

Convierte un PDF a Markdown estructurado usando pymupdf (texto embebido)
o tesseract (OCR para escaneos). Produce además metadata y layout JSON.

Uso:
    # Escanear carpeta y crear manifest:
    python3 pdf_to_md.py --scan ./corpus/ --output ./jobs/

    # Procesar un PDF individual:
    python3 pdf_to_md.py --input ./corpus/doc.pdf --output ./jobs/<job_id>/ \\
        --prompt v1 --layer operativo

    # Validar un job existente:
    python3 pdf_to_md.py --job ./jobs/<job_id>/ --validate

    # Forzar OCR:
    python3 pdf_to_md.py --input ./corpus/scan.pdf --output ./jobs/<id>/ --force-ocr
"""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys, uuid, hashlib
from datetime import datetime, timezone

try:
    import fitz  # pymupdf
except ImportError:
    sys.exit("pymupdf no instalado. Ejecuta: pip install pymupdf")

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "v1"
COVERAGE_MIN = 0.85  # palabras_md / palabras_pdf


def make_job_id() -> str:
    return uuid.uuid4().hex[:12]


def sha256_short(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def extract_text_pymupdf(pdf_path: pathlib.Path) -> tuple[str, list[dict]]:
    """Extrae texto + layout por bloque usando pymupdf."""
    doc = fitz.open(pdf_path)
    blocks = []
    full_text_parts = []

    for page_num, page in enumerate(doc, 1):
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # type 0 = text
                continue
            block_text_parts = []
            max_size = 0
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        block_text_parts.append(text)
                        max_size = max(max_size, span.get("size", 0))
            block_text = " ".join(block_text_parts).strip()
            if block_text:
                blocks.append({
                    "page": page_num,
                    "text": block_text,
                    "max_font_size": round(max_size, 1),
                    "bbox": [round(c, 1) for c in block.get("bbox", [])],
                })
                full_text_parts.append(block_text)

    doc.close()
    return "\n\n".join(full_text_parts), blocks


def extract_text_ocr(pdf_path: pathlib.Path) -> tuple[str, list[dict]]:
    """Fallback: renderiza cada página a PNG y aplica tesseract."""
    doc = fitz.open(pdf_path)
    blocks = []
    full_text_parts = []

    for page_num, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=200)
        tmp_png = pdf_path.with_suffix(f".page{page_num}.png")
        pix.save(tmp_png)

        try:
            result = subprocess.run(
                ["tesseract", str(tmp_png), "stdout", "-l", "spa"],
                capture_output=True, text=True, timeout=60
            )
            text = result.stdout.strip()
            if text:
                blocks.append({
                    "page": page_num,
                    "text": text,
                    "max_font_size": 12.0,  # unknown in OCR
                    "bbox": [0, 0, 0, 0],
                })
                full_text_parts.append(text)
        finally:
            if tmp_png.exists():
                tmp_png.unlink()

    doc.close()
    return "\n\n".join(full_text_parts), blocks


def classify_block_as_heading(block: dict) -> tuple[int, str]:
    """
    Heurística para detectar headings: tamaño de fuente, mayúsculas, longitud.
    Retorna (nivel, texto limpio).
    """
    text = block["text"]
    size = block["max_font_size"]
    n_words = len(text.split())

    # Detección por patrón (mayúsculas + corto) o por tamaño
    is_uppercase = text.isupper() and n_words < 20
    is_titlecase_short = text.istitle() and n_words < 10 and not text.endswith(".")

    if size >= 18 or (is_uppercase and n_words < 12):
        return 1, text
    if size >= 14 or (is_uppercase and n_words < 25):
        return 2, text
    if size >= 12 and (is_titlecase_short or is_uppercase) and n_words < 15:
        return 3, text
    return 0, text  # no es heading


def blocks_to_markdown(blocks: list[dict], prompt_version: str) -> str:
    """Convierte bloques a Markdown usando heurísticas de heading + listas."""
    lines = []
    for block in blocks:
        level, text = classify_block_as_heading(block)
        if level > 0:
            lines.append("")
            lines.append("#" * level + " " + text)
            lines.append("")
        else:
            # Detectar lista simple
            stripped = text.lstrip()
            if re.match(r"^[•·\-]\s+", stripped) or re.match(r"^\d+[\.)]\s+", stripped):
                # Normalizar marcador
                item = re.sub(r"^[•·\-]\s+", "- ", stripped)
                item = re.sub(r"^\d+[\.)]\s+", lambda m: f"{m.group(0).rstrip('). ')}. " if ')' in m.group(0) else m.group(0), stripped)
                lines.append(item)
            else:
                lines.append(text)
                lines.append("")
    return "\n".join(lines).strip()


def validate_markdown(md_path: pathlib.Path, pdf_text: str) -> dict:
    """Chequeos de la Etapa 1."""
    md = md_path.read_text(encoding="utf-8")
    issues = []

    if not md.startswith("#"):
        issues.append("MD no empieza con heading (#...)")
    if md.count("\n#") < 1:
        issues.append("MD no tiene headings secundarios (##, ###)")

    pdf_words = len(pdf_text.split())
    md_words = len(md.split())
    coverage = md_words / max(pdf_words, 1)

    if coverage < COVERAGE_MIN:
        issues.append(f"Cobertura baja: {coverage:.2f} < {COVERAGE_MIN}")

    # Palabras clave del PDF que deberían sobrevivir (top 20 long words)
    long_words = sorted({w for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ]{4,}\b", pdf_text)},
                        key=len, reverse=True)[:20]
    missing = [w for w in long_words if w not in md]

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "pdf_words": pdf_words,
        "md_words": md_words,
        "coverage": round(coverage, 3),
        "missing_keywords_sample": missing[:5],
    }


def cmd_scan(args):
    corpus = pathlib.Path(args.scan)
    output = pathlib.Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(corpus.rglob("*.pdf"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_path": str(corpus.absolute()),
        "n_pdfs": len(pdfs),
        "jobs": [],
    }
    for pdf in pdfs:
        rel = pdf.relative_to(corpus)
        manifest["jobs"].append({
            "job_id": make_job_id(),
            "filename": pdf.name,
            "rel_path": str(rel),
            "abs_path": str(pdf.absolute()),
            "sha256_short": sha256_short(pdf),
            "layer": None,  # usuario debe llenar
            "user_id": args.user_id,
            "status": "pending",
        })

    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"✓ manifest.json con {len(pdfs)} PDFs en {output}/")
    print(f"  Siguiente paso: editar manifest.json y llenar 'layer' por documento.")


def cmd_process(args):
    output = pathlib.Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    pdf_path = pathlib.Path(args.input)
    job_id = args.job_id or make_job_id()

    print(f"[{job_id}] Procesando {pdf_path.name}...")

    # Intentar texto embebido primero
    raw_text, blocks = extract_text_pymupdf(pdf_path)
    method = "text"

    if not raw_text.strip() or args.force_ocr:
        print(f"  Sin texto embebido. Aplicando OCR...")
        raw_text, blocks = extract_text_ocr(pdf_path)
        method = "ocr"

    # Convertir a Markdown
    md = blocks_to_markdown(blocks, args.prompt)
    md_path = output / f"{job_id}.md"
    md_path.write_text(md, encoding="utf-8")

    # Metadata
    doc_meta = fitz.open(pdf_path).metadata or {}
    meta = {
        "job_id": job_id,
        "filename": pdf_path.name,
        "method": method,
        "prompt_version": args.prompt,
        "layer": args.layer,
        "user_id": args.user_id,
        "n_pages": len(blocks) and max(b["page"] for b in blocks),
        "n_blocks": len(blocks),
        "pdf_metadata": {k: v for k, v in doc_meta.items() if v},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (output / f"{job_id}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # Layout
    layout = {
        "job_id": job_id,
        "prompt_version": args.prompt,
        "blocks": blocks,
    }
    (output / f"{job_id}.layout.json").write_text(json.dumps(layout, indent=2, ensure_ascii=False))

    # Validación
    validation = validate_markdown(md_path, raw_text)
    (output / f"{job_id}.validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False))

    status = "✓" if validation["ok"] else "⚠"
    print(f"  {status} {md_path.name} ({method}, {len(blocks)} bloques, cobertura={validation['coverage']})")
    if not validation["ok"]:
        for issue in validation["issues"]:
            print(f"    - {issue}")


def cmd_validate(args):
    job_dir = pathlib.Path(args.job)
    md_path = next(job_dir.glob("*.md"), None)
    pdf_meta = next(job_dir.glob("*.meta.json"), None)

    if not md_path:
        sys.exit(f"No se encontró .md en {job_dir}")

    # Re-leer PDF asociado
    if pdf_meta:
        meta = json.loads(pdf_meta.read_text())
        # Necesitamos el PDF original; intentar deducir
        pdf_candidate = pathlib.Path("corpus") / meta["filename"]
        if pdf_candidate.exists():
            raw_text, _ = extract_text_pymupdf(pdf_candidate)
        else:
            raw_text = md_path.read_text(encoding="utf-8")
    else:
        raw_text = md_path.read_text(encoding="utf-8")

    v = validate_markdown(md_path, raw_text)
    print(json.dumps(v, indent=2, ensure_ascii=False))
    sys.exit(0 if v["ok"] else 1)


def main():
    p = argparse.ArgumentParser(description="Etapa 1: PDF → Markdown")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("--scan", help="Escanear carpeta y crear manifest")
    s.add_argument("--scan", required=True)
    s.add_argument("--output", required=True)
    s.add_argument("--user-id", default="default")

    pr = sub.add_parser("--input", help="Procesar un PDF")
    pr.add_argument("--input", required=True)
    pr.add_argument("--output", required=True)
    pr.add_argument("--job-id", default=None)
    pr.add_argument("--prompt", default=PROMPT_VERSION, choices=["v1", "v2", "v3"])
    pr.add_argument("--layer", default=None, choices=["normativo", "operativo", "informal"])
    pr.add_argument("--user-id", default="default")
    pr.add_argument("--force-ocr", action="store_true")

    v = sub.add_parser("--job", help="Validar un job existente")
    v.add_argument("--job", required=True)
    v.add_argument("--validate", action="store_true")

    # Backwards-compat: top-level flags
    p.add_argument("--scan", default=None)
    p.add_argument("--input", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--job-id", default=None)
    p.add_argument("--prompt", default=PROMPT_VERSION)
    p.add_argument("--layer", default=None)
    p.add_argument("--user-id", default="default")
    p.add_argument("--force-ocr", action="store_true")
    p.add_argument("--job", default=None)
    p.add_argument("--validate", action="store_true")

    args = p.parse_args()

    # Dispatch manual
    if args.input:
        cmd_process(args)
    elif args.scan and args.output and not args.job:
        cmd_scan(args)
    elif args.job and args.validate:
        cmd_validate(args)
    else:
        p.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()