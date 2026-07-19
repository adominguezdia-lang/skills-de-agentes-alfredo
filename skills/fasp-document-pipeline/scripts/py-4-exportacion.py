#!/usr/bin/env python3
"""
py-4-exportacion.py — PY-4 del skill FASP.

Consolida tablas, matrices y sociogramas en formatos abiertos para
soporte de replicabilidad (Anexo 8). Exporta todo el contenido de la BD
como un paquete portable.

Uso:
    python3 py-4-exportacion.py --db ./fasp.db --output ./export/
"""
from __future__ import annotations
import argparse, csv, json, pathlib, sqlite3, sys
from datetime import datetime


TABLAS_EXPORTAR = [
    "documentos", "normas", "norma_unidades",
    "actores", "actor_etapas", "aristas", "metricas_ars",
    "fichas", "checkpoints", "audit_log",
]


def exportar_csv_por_tabla(db_path: pathlib.Path, output_dir: pathlib.Path) -> dict:
    """Exporta cada tabla como CSV."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    output_dir.mkdir(parents=True, exist_ok=True)

    counts = {}
    for tabla in TABLAS_EXPORTAR:
        cur = conn.execute(f"SELECT * FROM {tabla}")
        rows = cur.fetchall()
        if not rows:
            counts[tabla] = 0
            continue
        cols = rows[0].keys()
        path = output_dir / f"tabla_{tabla}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(cols))
            w.writeheader()
            for r in rows:
                w.writerow(dict(r))
        counts[tabla] = len(rows)

    conn.close()
    return counts


def generar_anexo8(db_path: pathlib.Path, output_dir: pathlib.Path) -> dict:
    """Genera Anexo 8 — Metodología para la replicabilidad."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cur = conn.execute("SELECT value FROM _meta WHERE key='schema_version'")
    schema_version = cur.fetchone()
    schema_version = schema_version[0] if schema_version else "?"

    cur = conn.execute("SELECT value FROM _meta WHERE key='created_at'")
    created_at = cur.fetchone()
    created_at = created_at[0] if created_at else "?"

    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in TABLAS_EXPORTAR if conn.execute(
                  f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()}

    md = [
        "# Anexo 8 — Metodología para la replicabilidad",
        "",
        f"**Versión del pipeline:** {schema_version}  ",
        f"**Fecha de exportación:** {datetime.now().isoformat()}  ",
        f"**BD creada:** {created_at}  ",
        "",
        "## Composición del paquete exportable",
        "",
        "Este anexo describe los pasos para reproducir el análisis a partir de la BD exportada.",
        "",
        "### Tablas exportadas (formato CSV)",
        "",
    ]
    for tabla, n in counts.items():
        md.append(f"- `{tabla}`: {n} filas")
    md.append("")
    md.append("### Pasos de codificación")
    md.append("")
    md.append("1. **Recolección documental (Etapa 1):** PDFs de normas + convenios FASP en `corpus/normas/`.")
    md.append("2. **Conversión PDF→MD:** skill `pdf-to-knowledge-graph` para extracción inicial.")
    md.append("3. **Parser jurídico (LLM-1):** segmentación por artículos/fracciones. Ver `scripts/llm-1-parser-juridico.py`.")
    md.append("4. **Construcción de matrices (PY-2):** adyacencia + incidencia. Ver `scripts/py-2-matrices-red.py`.")
    md.append("5. **Métricas ARS (PY-3):** 8 métricas según Anexo 5. Ver `scripts/py-3-metricas-ars.py`.")
    md.append("6. **Triangulación (Etapa 3):** cruce norma-red-campo. Ver prompt `sub-skills/llm-7-triangulador.md`.")
    md.append("")
    md.append("### Reproducibilidad")
    md.append("")
    md.append("- **Esquema de la BD:** ver `scripts/db_init.py` (función `SCHEMA_SQL`).")
    md.append("- **Validación de taxonomías:** ver `schemas/taxonomias.json`.")
    md.append("- **Schemas de anexos:** ver `schemas/anexos/`.")
    md.append("- **Pruebas automatizadas:** `tests/test_smoke.py`.")
    md.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "anexo8_metodologia_replicabilidad.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    conn.close()

    return {"path": str(md_path), "tablas": counts}


def main():
    p = argparse.ArgumentParser(description="PY-4 Exportación y soporte de replicabilidad")
    p.add_argument("--db", required=True)
    p.add_argument("--output", required=True, help="Directorio de salida")
    args = p.parse_args()

    output_dir = pathlib.Path(args.output)

    print("Exportando tablas a CSV...")
    counts = exportar_csv_por_tabla(output_dir / "csv", output_dir)
    for tabla, n in counts.items():
        print(f"  - {tabla}: {n} filas")

    print("Generando Anexo 8 — Metodología...")
    a8 = generar_anexo8(pathlib.Path(args.db), output_dir)
    print(f"  ✓ {a8['path']}")

    print(f"\n✓ Paquete completo en {output_dir}/")


if __name__ == "__main__":
    main()