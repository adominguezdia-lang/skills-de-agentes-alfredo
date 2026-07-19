#!/usr/bin/env python3
"""
audit_conversions.py — Audita la calidad de cada conversion PDF->MD y muestra
los parametros y metricas por archivo.

Para cada job en ./jobs/ (o en la ruta indicada):
  1. Lee el .meta.json (parametros de conversion)
  2. Lee el .validation.json (cobertura, palabras, issues)
  3. Compara el .md con el texto extraido del PDF original
  4. Calcula metricas adicionales (preservacion de headings, secciones, tablas)
  5. Emite un reporte en consola + JSON

Uso:
    # Auditar todos los jobs de una carpeta:
    python3 audit_conversions.py --jobs-dir ./jobs/

    # Auditar un job especifico:
    python3 audit_conversions.py --jobs-dir ./jobs/ --job-id 4eef74991ac4

    # Guardar reporte en JSON:
    python3 audit_conversions.py --jobs-dir ./jobs/ --output-json ./audit.json
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys, unicodedata
from collections import Counter
from difflib import SequenceMatcher

try:
    import fitz  # pymupdf
except ImportError:
    sys.exit("pymupdf no instalado. Ejecuta: pip install pymupdf")


def normalize(s: str) -> str:
    s = s.lower().strip()
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def text_similarity(a: str, b: str) -> float:
    """Similitud 0-1 entre dos textos (basada en SequenceMatcher)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:5000], b[:5000]).ratio()


def load_meta(job_dir: pathlib.Path) -> dict:
    """Carga <job_id>.meta.json."""
    metas = list(job_dir.glob("*.meta.json"))
    if not metas:
        return {}
    return json.loads(metas[0].read_text(encoding="utf-8"))


def load_validation(job_dir: pathlib.Path) -> dict:
    """Carga <job_id>.validation.json."""
    vals = list(job_dir.glob("*.validation.json"))
    if not vals:
        return {}
    return json.loads(vals[0].read_text(encoding="utf-8"))


def load_md(job_dir: pathlib.Path) -> str:
    """Carga el <job_id>.md."""
    mds = list(job_dir.glob("*.md"))
    if not mds:
        return ""
    return mds[0].read_text(encoding="utf-8")


def find_pdf_for_job(job_dir: pathlib.Path, meta: dict) -> pathlib.Path | None:
    """Busca el PDF original asociado al job."""
    # Primero, buscar en meta.json si hay referencia
    for k, v in (meta or {}).items():
        if isinstance(v, str) and v.lower().endswith(".pdf"):
            p = pathlib.Path(v)
            if p.exists():
                return p
    # Buscar agresivamente: subir hasta encontrar el primer .pdf
    # que coincida con el filename del meta
    target_name = (meta or {}).get("filename", "")
    candidates = [job_dir]
    # Subir hasta 5 niveles
    for _ in range(5):
        candidates = list({c.parent for c in candidates})
    # Aplanar y agregar el directorio de descargas del usuario
    home = pathlib.Path.home()
    candidates.extend([
        home / "Downloads",
        home / "Documents",
        home / "Desktop",
        pathlib.Path("/Users/adominguezdia/Downloads"),
        pathlib.Path.cwd(),
    ])
    seen = set()
    for base in candidates:
        if not base or not base.exists():
            continue
        if base in seen:
            continue
        seen.add(base)
        # Busqueda directa
        if target_name:
            cand = base / target_name
            if cand.exists() and cand.suffix.lower() == ".pdf":
                return cand
        # Busqueda recursiva limitada
        try:
            for pdf in base.rglob(target_name or "*.pdf"):
                if pdf.suffix.lower() == ".pdf":
                    return pdf
        except (PermissionError, OSError):
            continue
    return None


def extract_pdf_text(pdf_path: pathlib.Path) -> str:
    """Extrae texto crudo del PDF."""
    doc = fitz.open(pdf_path)
    parts = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    return "\n\n".join(parts)


def compute_md_metrics(md: str) -> dict:
    """Calcula metricas estructurales del Markdown."""
    lines = md.split("\n")
    headings = Counter()
    list_items = 0
    table_rows = 0
    code_blocks = 0
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            if in_code:
                code_blocks += 1
            continue
        if in_code:
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if 1 <= level <= 6:
                headings[level] += 1
        elif line.strip().startswith(("- ", "* ", "1. ", "1) ")):
            list_items += 1
        if "|" in line and line.count("|") >= 2:
            table_rows += 1
    return {
        "total_lines": len(lines),
        "headings_by_level": dict(headings),
        "headings_total": sum(headings.values()),
        "list_items": list_items,
        "table_rows_approx": table_rows,
        "code_blocks": code_blocks,
    }


def compute_keyword_preservation(pdf_text: str, md_text: str, n: int = 20) -> dict:
    """Verifica que las palabras clave del PDF sobrevivieron en el MD."""
    # Palabras clave candidatas: largas, mayúsculas, en el PDF
    long_caps = re.findall(r"\b[A-ZÁÉÍÓÚÑ]{5,}\b", pdf_text)
    counter = Counter(long_caps)
    top = [w for w, _ in counter.most_common(n)]
    preserved = [w for w in top if w in md_text]
    missing = [w for w in top if w not in md_text]
    return {
        "top_keywords_count": len(top),
        "preserved": preserved,
        "missing": missing,
        "preservation_rate": round(len(preserved) / len(top), 3) if top else 0,
    }


def audit_one_job(job_dir: pathlib.Path) -> dict:
    """Audita un job individual."""
    job_id = job_dir.name
    meta = load_meta(job_dir)
    validation = load_validation(job_dir)
    md = load_md(job_dir)
    md_metrics = compute_md_metrics(md)

    # Buscar PDF
    pdf = find_pdf_for_job(job_dir, meta)
    pdf_comparison = {}
    keyword_pres = {}

    if pdf:
        pdf_text = extract_pdf_text(pdf)
        # Similitud
        pdf_comparison = {
            "pdf_path": str(pdf),
            "pdf_size_bytes": pdf.stat().st_size,
            "pdf_words": len(pdf_text.split()),
            "md_words": len(md.split()),
            "text_similarity": round(text_similarity(pdf_text, md), 3),
        }
        # Preservacion de keywords
        keyword_pres = compute_keyword_preservation(pdf_text, md)

    # Score global
    coverage = validation.get("coverage", 0)
    issues_count = len(validation.get("issues", []))
    preservation = keyword_pres.get("preservation_rate", 0)
    similarity = pdf_comparison.get("text_similarity", 0)

    # Score compuesto: 40% coverage + 30% keyword preservation + 20% similarity + 10% no issues
    score = (
        coverage * 40 +
        preservation * 30 +
        similarity * 20 +
        max(0, 10 - issues_count * 2)  # 10 base, -2 por issue
    )

    return {
        "job_id": job_id,
        "parameters": {
            "method": meta.get("method"),
            "prompt_version": meta.get("prompt_version"),
            "layer": meta.get("layer"),
            "user_id": meta.get("user_id"),
            "filename": meta.get("filename"),
            "n_pages": meta.get("n_pages"),
            "n_blocks": meta.get("n_blocks"),
        },
        "metrics": {
            "coverage": coverage,
            "pdf_words": pdf_comparison.get("pdf_words"),
            "md_words": pdf_comparison.get("md_words"),
            "text_similarity": similarity,
            "keyword_preservation_rate": preservation,
            "issues_count": issues_count,
            "issues": validation.get("issues", []),
            "missing_keywords_sample": keyword_pres.get("missing", [])[:5],
            "md_structure": md_metrics,
        },
        "score": round(score, 2),
        "rating": "EXCELENTE" if score >= 85 else "BUENO" if score >= 70 else "ACEPTABLE" if score >= 50 else "BAJA",
    }


def main():
    p = argparse.ArgumentParser(description="Audita la calidad de las conversiones PDF->MD")
    p.add_argument("--jobs-dir", required=True, help="Carpeta con subdirs de jobs")
    p.add_argument("--job-id", default=None, help="Auditar solo este job_id")
    p.add_argument("--output-json", default=None, help="Guardar reporte en JSON")
    args = p.parse_args()

    jobs_dir = pathlib.Path(args.jobs_dir)
    if not jobs_dir.is_dir():
        sys.exit(f"No es directorio: {jobs_dir}")

    if args.job_id:
        job_dirs = [jobs_dir / args.job_id]
    else:
        job_dirs = sorted([d for d in jobs_dir.iterdir() if d.is_dir()])

    if not job_dirs:
        sys.exit(f"No se encontraron jobs en {jobs_dir}/")

    results = []
    for jd in job_dirs:
        try:
            r = audit_one_job(jd)
            results.append(r)
        except Exception as e:
            results.append({"job_id": jd.name, "error": str(e)})

    # Reporte en consola
    print("=" * 80)
    print(f"AUDITORIA DE CONVERSIONES PDF -> MD  ({len(results)} jobs)")
    print("=" * 80)
    print()

    for r in results:
        if "error" in r:
            print(f"[{r['job_id']}] ERROR: {r['error']}")
            continue
        print(f"## {r['job_id']}")
        print()
        print(f"  Parametros de conversion:")
        for k, v in r["parameters"].items():
            print(f"    {k:<18} = {v}")
        print()
        print(f"  Metricas:")
        m = r["metrics"]
        print(f"    Cobertura              = {m.get('coverage')}  (ratio palabras_md / palabras_pdf)")
        if m.get("pdf_words"):
            print(f"    Palabras PDF           = {m['pdf_words']}")
        if m.get("md_words"):
            print(f"    Palabras MD            = {m['md_words']}")
        if m.get("text_similarity") is not None:
            print(f"    Similitud texto        = {m['text_similarity']}  (0-1, SequenceMatcher)")
        if m.get("keyword_preservation_rate") is not None:
            print(f"    Preservacion keywords  = {m['keyword_preservation_rate']}  (palabras en mayusculas del PDF que sobreviven)")
        if m.get("missing_keywords_sample"):
            print(f"    Keywords faltantes     = {m['missing_keywords_sample']}")
        print(f"    Issues detectados      = {m.get('issues_count')}")
        if m.get("issues"):
            for issue in m["issues"][:5]:
                print(f"      - {issue}")
        struct = m["md_structure"]
        print(f"    Estructura MD:")
        print(f"      total_lines           = {struct['total_lines']}")
        print(f"      headings              = {struct['headings_total']}  (por nivel: {struct['headings_by_level']})")
        print(f"      list_items            = {struct['list_items']}")
        print(f"      table_rows_approx     = {struct['table_rows_approx']}")
        print(f"      code_blocks           = {struct['code_blocks']}")
        print()
        print(f"  >>> SCORE COMPUESTO = {r['score']} / 100  -> {r['rating']}")
        print()
        print("-" * 80)
        print()

    # Resumen
    if results and "error" not in results[0]:
        avg_score = sum(r["score"] for r in results if "score" in r) / sum(1 for r in results if "score" in r)
        print(f"\nSCORE PROMEDIO: {avg_score:.2f}/100")

    if args.output_json:
        pathlib.Path(args.output_json).write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"\nReporte JSON guardado en {args.output_json}")


if __name__ == "__main__":
    main()