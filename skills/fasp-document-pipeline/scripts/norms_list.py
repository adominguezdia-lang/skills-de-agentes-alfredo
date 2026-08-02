#!/usr/bin/env python3
"""
norms_list.py — Lista las normas ingestadas con sus parametros de conversion
y metricas de calidad por conversion.

Lee la BD SQLite del skill y muestra una tabla con:
  - job_id, filename, fecha, layer, method, prompt_version
  - cobertura, similitud de texto, preservacion de keywords
  - score global de calidad

Uso:
    python3 norms_list.py --db ./fasp.db

    # Filtrar por layer:
    python3 norms_list.py --db ./fasp.db --layer normativo

    # Exportar a CSV:
    python3 norms_list.py --db ./fasp.db --output-csv ./normas.csv

    # Exportar a JSON:
    python3 norms_list.py --db ./fasp.db --output-json ./normas.json
"""
from __future__ import annotations
import argparse, csv, json, pathlib, re, sys, unicodedata
from collections import Counter
from difflib import SequenceMatcher

try:
    import fitz  # pymupdf
except ImportError:
    sys.exit("pymupdf no instalado. Ejecuta: pip install pymupdf")


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:5000], b[:5000]).ratio()


def find_pdf(filename: str) -> pathlib.Path | None:
    """Busca el PDF en ubicaciones comunes."""
    if not filename:
        return None
    home = pathlib.Path.home()
    bases = [
        pathlib.Path.cwd(),
        home / "Downloads",
        home / "Documents",
        home / "Desktop",
        pathlib.Path("/Users/adominguezdia/Downloads"),
        pathlib.Path("/Users/adominguezdia/Downloads/CSN-evaluacion-FASP"),
        pathlib.Path("/tmp"),
    ]
    for base in bases:
        if not base.exists():
            continue
        cand = base / filename
        if cand.exists() and cand.suffix.lower() == ".pdf":
            return cand
        # Busqueda recursiva limitada
        try:
            for pdf in base.rglob(filename):
                if pdf.suffix.lower() == ".pdf":
                    return pdf
        except (PermissionError, OSError):
            continue
    return None


def extract_pdf_text(pdf_path: pathlib.Path) -> str:
    doc = fitz.open(pdf_path)
    parts = [p.get_text() for p in doc]
    doc.close()
    return "\n\n".join(parts)


def compute_keyword_preservation(pdf_text: str, md_text: str, n: int = 20) -> dict:
    long_caps = re.findall(r"\b[A-ZÁÉÍÓÚÑ]{5,}\b", pdf_text)
    counter = Counter(long_caps)
    top = [w for w, _ in counter.most_common(n)]
    preserved = [w for w in top if w in md_text]
    missing = [w for w in top if w not in md_text]
    return {
        "preservation_rate": round(len(preserved) / len(top), 3) if top else 0,
        "missing": missing,
    }


def find_md_for_job(job_dir: pathlib.Path) -> pathlib.Path | None:
    """Encuentra el .md en un directorio de job."""
    mds = list(job_dir.glob("*.md"))
    if not mds:
        return None
    # Preferir el que cumple la nomenclatura FASP_2026_
    for m in mds:
        if m.name.startswith("FASP_2026_"):
            return m
    return mds[0]


def analyze_job(job_dir: pathlib.Path) -> dict:
    """Analiza un job y devuelve metricas de calidad."""
    metas = list(job_dir.glob("*.meta.json"))
    validations = list(job_dir.glob("*.validation.json"))

    if not metas:
        return {"error": "no .meta.json"}

    meta = json.loads(metas[0].read_text(encoding="utf-8"))
    validation = json.loads(validations[0].read_text(encoding="utf-8")) if validations else {}

    md_path = find_md_for_job(job_dir)
    md_text = md_path.read_text(encoding="utf-8") if md_path else ""

    # Buscar PDF
    pdf = find_pdf(meta.get("filename", ""))
    pdf_metrics = {}
    keyword_pres = {"preservation_rate": 0, "missing": []}

    if pdf:
        pdf_text = extract_pdf_text(pdf)
        pdf_metrics = {
            "pdf_path": str(pdf),
            "pdf_size_bytes": pdf.stat().st_size,
            "pdf_words": len(pdf_text.split()),
        }
        keyword_pres = compute_keyword_preservation(pdf_text, md_text)

    # Score
    coverage = validation.get("coverage", 0)
    similarity = text_similarity(pdf_text, md_text) if pdf else 0
    preservation = keyword_pres.get("preservation_rate", 0)
    issues_count = len(validation.get("issues", []))

    score = (
        coverage * 40 +
        preservation * 30 +
        similarity * 20 +
        max(0, 10 - issues_count * 2)
    )

    return {
        "job_id": job_dir.name,
        "filename": meta.get("filename"),
        "created_at": meta.get("created_at"),
        "layer": meta.get("layer"),
        "user_id": meta.get("user_id"),
        "method": meta.get("method"),
        "prompt_version": meta.get("prompt_version"),
        "n_pages": meta.get("n_pages"),
        "n_blocks": meta.get("n_blocks"),
        "metrics": {
            "coverage": coverage,
            "text_similarity": round(similarity, 3),
            "keyword_preservation": preservation,
            "issues_count": issues_count,
            "issues": validation.get("issues", []),
            "missing_keywords": keyword_pres.get("missing", [])[:5],
            "pdf_words": pdf_metrics.get("pdf_words"),
            "md_words": len(md_text.split()) if md_text else 0,
            "md_chars": len(md_text) if md_text else 0,
        },
        "score": round(score, 2),
        "rating": "EXCELENTE" if score >= 85 else "BUENO" if score >= 70 else "ACEPTABLE" if score >= 50 else "BAJA",
    }


def list_jobs(jobs_dir: pathlib.Path, layer_filter: str = None) -> list[dict]:
    """Lista todos los jobs de una carpeta."""
    results = []
    for jd in sorted(jobs_dir.iterdir()):
        if not jd.is_dir():
            continue
        try:
            r = analyze_job(jd)
        except Exception as e:
            r = {"job_id": jd.name, "error": str(e)}
        if layer_filter and r.get("layer") and r["layer"] != layer_filter:
            continue
        results.append(r)
    return results


def render_table(results: list[dict]) -> str:
    """Renderiza los resultados como tabla en consola."""
    if not results:
        return "No se encontraron jobs."
    lines = []
    lines.append("=" * 120)
    lines.append(f"LISTA DE NORMAS Y CONVERSIONES ({len(results)} jobs)")
    lines.append("=" * 120)
    lines.append("")
    # Encabezado
    header = f"{'job_id':<14} {'filename':<22} {'layer':<12} {'method':<6} {'prompt':<7} {'pags':<5} {'cov':<5} {'sim':<5} {'kwp':<5} {'score':<6} {'rating':<10}"
    lines.append(header)
    lines.append("-" * 120)
    for r in results:
        if "error" in r:
            lines.append(f"[{r['job_id']}] ERROR: {r['error']}")
            continue
        m = r["metrics"]
        lines.append(
            f"{r['job_id']:<14} "
            f"{(r.get('filename') or '-')[:22]:<22} "
            f"{(r.get('layer') or '-')[:12]:<12} "
            f"{(r.get('method') or '-')[:6]:<6} "
            f"{(r.get('prompt_version') or '-')[:7]:<7} "
            f"{str(r.get('n_pages') or '-'):<5} "
            f"{m.get('coverage', 0):<5.3f} "
            f"{m.get('text_similarity', 0):<5.3f} "
            f"{m.get('keyword_preservation', 0):<5.3f} "
            f"{r.get('score', 0):<6.2f} "
            f"{r.get('rating', '-'):<10}"
        )
    lines.append("-" * 120)
    if results and "score" in results[0]:
        scores = [r["score"] for r in results if "score" in r]
        lines.append(f"\nScore promedio: {sum(scores)/len(scores):.2f}/100")
    return "\n".join(lines)


def render_csv(results: list[dict]) -> str:
    """Renderiza como CSV."""
    buf = []
    writer = csv.writer(buf)
    writer.writerow([
        "job_id", "filename", "created_at", "layer", "user_id", "method",
        "prompt_version", "n_pages", "n_blocks", "coverage", "text_similarity",
        "keyword_preservation", "issues_count", "missing_keywords",
        "md_words", "md_chars", "score", "rating"
    ])
    for r in results:
        if "error" in r:
            continue
        m = r["metrics"]
        writer.writerow([
            r.get("job_id", ""),
            r.get("filename", ""),
            r.get("created_at", ""),
            r.get("layer", ""),
            r.get("user_id", ""),
            r.get("method", ""),
            r.get("prompt_version", ""),
            r.get("n_pages", ""),
            r.get("n_blocks", ""),
            m.get("coverage", 0),
            m.get("text_similarity", 0),
            m.get("keyword_preservation", 0),
            m.get("issues_count", 0),
            ";".join(m.get("missing_keywords", [])),
            m.get("md_words", 0),
            m.get("md_chars", 0),
            r.get("score", 0),
            r.get("rating", ""),
        ])
    return "\n".join(buf)


def main():
    p = argparse.ArgumentParser(description="Lista normas con parametros de calidad por conversion")
    p.add_argument("--jobs-dir", required=True, help="Carpeta con subdirs de jobs")
    p.add_argument("--layer", default=None, help="Filtrar por layer (normativo/operativo/informal)")
    p.add_argument("--output-csv", default=None, help="Exportar a CSV")
    p.add_argument("--output-json", default=None, help="Exportar a JSON")
    args = p.parse_args()

    jobs_dir = pathlib.Path(args.jobs_dir)
    if not jobs_dir.is_dir():
        sys.exit(f"No es directorio: {jobs_dir}")

    results = list_jobs(jobs_dir, args.layer)
    print(render_table(results))

    if args.output_csv:
        csv_text = render_csv(results)
        pathlib.Path(args.output_csv).write_text(csv_text, encoding="utf-8")
        print(f"\nCSV guardado en {args.output_csv}")

    if args.output_json:
        pathlib.Path(args.output_json).write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"JSON guardado en {args.output_json}")


if __name__ == "__main__":
    main()