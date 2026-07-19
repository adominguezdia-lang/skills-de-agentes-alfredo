#!/usr/bin/env python3
"""
py-1-estructuracion.py — PY-1 del skill FASP.

Asigna identificadores únicos (ID) a cada actor (precondición para el sociograma)
y genera la Ficha técnica del FASP (Anexo 1) a partir de la BD.

Uso:
    python3 py-1-estructuracion.py --db ./fasp.db --anexo1 ./anexos/anexo1.md
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sqlite3, sys
from datetime import datetime, timezone


def make_actor_id(nombre_oficial: str) -> str:
    """ID estable a partir del nombre oficial."""
    h = hashlib.sha256(nombre_oficial.encode("utf-8")).hexdigest()[:10].upper()
    return f"ACT-{h}"


def assign_ids_to_actores(db_path: pathlib.Path) -> dict:
    """Asigna IDs únicos a cada actor del directorio. Crea alias si hay duplicados."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Verificar tabla existe
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actores'")
    if not cur.fetchone():
        conn.close()
        sys.exit("La tabla 'actores' no existe. Ejecuta LLM-3 primero.")

    # Listar actores sin ID o con duplicados
    cur.execute("SELECT rowid, nombre_oficial FROM actores ORDER BY rowid")
    rows = cur.fetchall()
    seen = {}
    n_updated = 0

    for rowid, nombre in rows:
        if not nombre:
            continue
        if nombre in seen:
            # Duplicado: añadir como alias del primero
            first_id = seen[nombre]
            cur.execute("SELECT alias_conocidos FROM actores WHERE id_actor = ?", (first_id,))
            aliases = json.loads(cur.fetchone()[0] or "[]")
            aliases.append(nombre)
            cur.execute("UPDATE actores SET alias_conocidos = ? WHERE id_actor = ?",
                        (json.dumps(aliases), first_id))
        else:
            new_id = make_actor_id(nombre)
            seen[nombre] = new_id
            cur.execute("UPDATE actores SET id_actor = ? WHERE rowid = ?", (new_id, rowid))
            n_updated += 1

    conn.commit()
    n_actores = len(seen)
    conn.close()

    return {"actores_con_id": n_actores, "actualizados": n_updated}


def generar_ficha_tecnica(db_path: pathlib.Path, output_path: pathlib.Path,
                          id_evaluacion: str, anio_fiscal: int,
                          dependencia_coordinadora: str = "SESNSP",
                          responsable: str = "Coordinadora de la Evaluación") -> dict:
    """Genera el Anexo 1 — Ficha técnica del FASP."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Estadísticas de la BD
    n_docs = cur.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    n_normas = cur.execute("SELECT COUNT(*) FROM normas").fetchone()[0]
    n_unidades = cur.execute("SELECT COUNT(*) FROM norma_unidades").fetchone()[0]
    n_actores = cur.execute("SELECT COUNT(*) FROM actores").fetchone()[0]

    id_ficha = f"FASP-{anio_fiscal}-{id_evaluacion}"

    ficha = {
        "id_ficha": id_ficha,
        "id_evaluacion": id_evaluacion,
        "nombre_programa": "Fondo de Aportaciones para la Seguridad Pública",
        "anio_fiscal": anio_fiscal,
        "rama": "Seguridad Pública",
        "dependencia_coordinadora": dependencia_coordinadora,
        "fecha_elaboracion": datetime.now().strftime("%Y-%m-%d"),
        "responsable": responsable,
        "marco_normativo_general": [
            "Ley de Coordinación Fiscal (art. 25 fracción III y 44)",
            "Ley General del Sistema Nacional de Seguridad Pública",
            "Presupuesto de Egresos de la Federación",
        ],
        "objetivos_evaluacion": [
            "Diagnosticar el marco normativo, funcional y de actores del FASP",
            "Identificar hallazgos de coordinación entre los tres niveles de gobierno",
            "Proponer recomendaciones y áreas de mejora",
        ],
        "alcance": "Federal+Estatal+Municipal",
        "metodologia": "Análisis normativo+ARS+triangulación",
        "_stats": {
            "documentos_ingestados": n_docs,
            "normas_procesadas": n_normas,
            "unidades_normativas": n_unidades,
            "actores_en_directorio": n_actores,
        },
    }

    # Render a Markdown
    md_lines = [
        f"# Anexo 1 — Ficha Técnica del FASP",
        "",
        f"**ID de ficha:** {ficha['id_ficha']}  ",
        f"**ID de evaluación:** {ficha['id_evaluacion']}  ",
        f"**Programa:** {ficha['nombre_programa']}  ",
        f"**Año fiscal:** {ficha['anio_fiscal']}  ",
        f"**Rama:** {ficha['rama']}  ",
        f"**Dependencia coordinadora:** {ficha['dependencia_coordinadora']}  ",
        f"**Fecha de elaboración:** {ficha['fecha_elaboracion']}  ",
        f"**Responsable:** {ficha['responsable']}  ",
        "",
        "## Marco normativo general",
        "",
    ]
    for n in ficha["marco_normativo_general"]:
        md_lines.append(f"- {n}")
    md_lines.append("")
    md_lines.append("## Objetivos de la evaluación")
    md_lines.append("")
    for o in ficha["objetivos_evaluacion"]:
        md_lines.append(f"- {o}")
    md_lines.append("")
    md_lines.append(f"## Alcance: {ficha['alcance']}")
    md_lines.append("")
    md_lines.append(f"## Metodología: {ficha['metodologia']}")
    md_lines.append("")
    md_lines.append("## Estado del pipeline al cierre de la Ficha")
    md_lines.append("")
    md_lines.append(f"- Documentos ingestados: **{ficha['_stats']['documentos_ingestados']}**")
    md_lines.append(f"- Normas procesadas: **{ficha['_stats']['normas_procesadas']}**")
    md_lines.append(f"- Unidades normativas extraídas: **{ficha['_stats']['unidades_normativas']}**")
    md_lines.append(f"- Actores en directorio preliminar: **{ficha['_stats']['actores_en_directorio']}**")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append(f"")
    md_lines.append(f"*Generado automáticamente por `py-1-estructuracion.py` — {datetime.now().isoformat()}*")
    md_lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Audit log
    cur2 = sqlite3.connect(db_path).cursor()
    cur2.execute("""
        INSERT INTO audit_log (modulo, accion, tabla, row_id, detalle)
        VALUES (?, ?, ?, ?, ?)
    """, ("PY-1", "generate", "anexo1", id_ficha, json.dumps(ficha["_stats"])))
    sqlite3.connect(db_path).commit()

    conn.close()

    return {
        "id_ficha": id_ficha,
        "output_path": str(output_path.absolute()),
        "stats": ficha["_stats"],
    }


def main():
    p = argparse.ArgumentParser(description="PY-1 Estructuración de bases y Ficha técnica FASP")
    p.add_argument("--db", required=True)
    p.add_argument("--anexo1", required=True, help="Ruta de salida para el Anexo 1 (.md)")
    p.add_argument("--id-evaluacion", default="EVAL-001")
    p.add_argument("--anio-fiscal", type=int, default=datetime.now().year)
    p.add_argument("--dependencia", default="SESNSP")
    p.add_argument("--responsable", default="Coordinadora de la Evaluación")
    p.add_argument("--solo-ids", action="store_true", help="Solo asignar IDs, no generar Ficha")
    args = p.parse_args()

    db_path = pathlib.Path(args.db)

    # 1. Asignar IDs a actores
    print("Asignando IDs únicos a actores...")
    id_stats = assign_ids_to_actores(db_path)
    print(f"  ✓ {id_stats['actores_con_id']} actores con ID, {id_stats['actualizados']} actualizados")

    if args.solo_ids:
        return

    # 2. Generar Ficha técnica (Anexo 1)
    print("Generando Anexo 1 — Ficha técnica FASP...")
    result = generar_ficha_tecnica(
        db_path, pathlib.Path(args.anexo1),
        args.id_evaluacion, args.anio_fiscal,
        args.dependencia, args.responsable,
    )
    print(f"  ✓ Ficha {result['id_ficha']} escrita en {result['output_path']}")
    print(f"  Stats: {result['stats']}")


if __name__ == "__main__":
    main()