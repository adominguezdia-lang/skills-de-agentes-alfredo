#!/usr/bin/env python3
"""
py-2-matrices-red.py — PY-2 del skill FASP.

Genera la Matriz de adyacencia (Actor-Actor) y la Matriz de incidencia
(Actor-Proceso) en formatos abiertos (CSV) a partir de la BD.

Uso:
    python3 py-2-matrices-red.py --db ./fasp.db --output ./anexos/
"""
from __future__ import annotations
import argparse, csv, json, pathlib, sqlite3, sys
from datetime import datetime


def matriz_adyacencia(db_path: pathlib.Path, output_dir: pathlib.Path) -> dict:
    """Genera Anexo 4 — Matriz de adyacencia Actor-Actor."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    aristas = [dict(r) for r in conn.execute("""
        SELECT origen, destino, peso, tipo_vinculo, direccionalidad,
               frecuencia, canal, etapa_ciclo, evidencia_doc_id
        FROM aristas
        ORDER BY origen, destino
    """)]
    nodos = [r[0] for r in conn.execute("""
        SELECT DISTINCT id_actor FROM actores
        UNION
        SELECT DISTINCT origen FROM aristas
        UNION
        SELECT DISTINCT destino FROM aristas
        ORDER BY 1
    """)]

    conn.close()
    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV de aristas (formato largo)
    csv_path = output_dir / "anexo4_matriz_adyacencia_aristas.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "origen", "destino", "peso", "tipo_vinculo", "direccionalidad",
            "frecuencia", "canal", "etapa_ciclo", "evidencia_doc_id"
        ])
        w.writeheader()
        for a in aristas:
            w.writerow(a)

    # CSV matriz cuadrada (formato ancho, sparse-friendly)
    matrix_path = output_dir / "anexo4_matriz_adyacencia_cuadrada.csv"
    with open(matrix_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["origen\\destino"] + nodos)
        for o in nodos:
            row = [o]
            for d in nodos:
                matching = [a for a in aristas if a["origen"] == o and a["destino"] == d]
                if matching:
                    row.append(matching[0]["peso"])
                else:
                    row.append("")
            w.writerow(row)

    return {"nodos": len(nodos), "aristas": len(aristas),
            "csv_largo": str(csv_path), "csv_cuadrada": str(matrix_path)}


def matriz_incidencia(db_path: pathlib.Path, output_dir: pathlib.Path) -> dict:
    """Genera matriz de incidencia Actor-Etapa del ciclo FASP."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    nodos = [r[0] for r in conn.execute("SELECT id_actor FROM actores ORDER BY 1")]
    etapas = ["Integración", "Distribución", "Administración", "Supervisión", "Seguimiento"]

    # Incidencia desde aristas: si un actor aparece en una arista con etapa_ciclo=X,
    # entonces tiene incidencia en esa etapa.
    incidencia = {n: set() for n in nodos}
    for r in conn.execute("SELECT origen, destino, etapa_ciclo FROM aristas"):
        if r["origen"] in incidencia:
            incidencia[r["origen"]].add(r["etapa_ciclo"])
        if r["destino"] in incidencia:
            incidencia[r["destino"]].add(r["etapa_ciclo"])

    # Incidencia desde actores.actor_etapas
    for r in conn.execute("SELECT id_actor, etapa_ciclo FROM actor_etapas"):
        if r["id_actor"] in incidencia:
            incidencia[r["id_actor"]].add(r["etapa_ciclo"])

    conn.close()

    csv_path = output_dir / "anexo4_matriz_incidencia_actor_etapa.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id_actor"] + etapas + ["total_etapas"])
        for n in nodos:
            row = [n] + [("X" if e in incidencia[n] else "") for e in etapas]
            row.append(len(incidencia[n]))
            w.writerow(row)

    return {"path": str(csv_path), "nodos": len(nodos)}


def main():
    p = argparse.ArgumentParser(description="PY-2 Constructor de matrices de red ARS")
    p.add_argument("--db", required=True)
    p.add_argument("--output", required=True, help="Directorio de salida para los CSV")
    args = p.parse_args()

    output_dir = pathlib.Path(args.output)

    print("Generando matriz de adyacencia (Anexo 4)...")
    adj = matriz_adyacencia(pathlib.Path(args.db), output_dir)
    print(f"  ✓ {adj['nodos']} nodos, {adj['aristas']} aristas")
    print(f"  - {adj['csv_largo']}")
    print(f"  - {adj['csv_cuadrada']}")

    print("Generando matriz de incidencia...")
    inc = matriz_incidencia(pathlib.Path(args.db), output_dir)
    print(f"  ✓ {inc['nodos']} actores, archivo: {inc['path']}")


if __name__ == "__main__":
    main()