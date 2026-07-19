#!/usr/bin/env python3
"""
checkpoint.py — Registra aprobaciones humanas por perfil y etapa.

Uso:
    # Registrar un checkpoint:
    python3 checkpoint.py --db ./fasp.db --etapa etapa_1_documental \\
        --perfil coordinadora --anexo "Anexo 2" --doc-id NOR-ABC123 \\
        --decision aprobado --aprobador "María López"

    # Listar checkpoints pendientes:
    python3 checkpoint.py --db ./fasp.db --listar pendientes

    # Listar todos los checkpoints:
    python3 checkpoint.py --db ./fasp.db --listar todos
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys
from datetime import datetime, timezone


PERFILES_POR_ETAPA = {
    "etapa_1_documental": [
        ("coordinadora", "Revisión general de la Ficha técnica FASP y coherencia global"),
        ("analista_senior_juridico", "Revisión de la matriz de congruencia y directorio preliminar"),
    ],
    "etapa_2_campo_ars": [
        ("analista_senior_redes", "Validación de edge list, matrices y métricas ARS"),
        ("analistas_junior_grafos", "Verificación de nodos, aristas y clasificación de relaciones"),
    ],
    "etapa_3_triangulacion": [
        ("coordinacion_evaluacion", "Validación de narrativas, diagnósticos y recomendaciones"),
    ],
}


def registrar(db_path: pathlib.Path, etapa: str, perfil: str, anexo: str,
              doc_id: str, decision: str, aprobador: str, comentario: str = "") -> int:
    """Registra un checkpoint. Retorna el ID del checkpoint."""
    if decision not in ("aprobado", "rechazado", "pendiente"):
        sys.exit(f"Decisión inválida: {decision}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO checkpoints
        (etapa, perfil, anexo, doc_id, decision, comentario, aprobador, fecha)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (etapa, perfil, anexo, doc_id, decision, comentario, aprobador,
          datetime.now(timezone.utc).isoformat()))

    checkpoint_id = cur.lastrowid

    # Audit log
    cur.execute("""
        INSERT INTO audit_log (modulo, accion, tabla, row_id, detalle)
        VALUES (?, ?, ?, ?, ?)
    """, ("checkpoint", "insert", "checkpoints", str(checkpoint_id),
          json.dumps({"etapa": etapa, "perfil": perfil, "anexo": anexo, "decision": decision})))

    conn.commit()
    conn.close()
    return checkpoint_id


def listar(db_path: pathlib.Path, filtro: str):
    """Lista checkpoints."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if filtro == "pendientes":
        # Para cada gate, mostrar si hay decisión
        pendientes = []
        for etapa, gates in PERFILES_POR_ETAPA.items():
            for perfil, descripcion in gates:
                # Buscar si hay decisión registrada
                row = conn.execute("""
                    SELECT id, decision, aprobador, fecha
                    FROM checkpoints
                    WHERE etapa = ? AND perfil = ?
                    ORDER BY id DESC LIMIT 1
                """, (etapa, perfil)).fetchone()
                if not row or row["decision"] != "aprobado":
                    pendientes.append({
                        "etapa": etapa,
                        "perfil": perfil,
                        "descripcion": descripcion,
                        "ultimo_estado": row["decision"] if row else "nunca_registrado",
                    })
        return pendientes
    else:
        rows = conn.execute("""
            SELECT id, etapa, perfil, anexo, doc_id, decision, aprobador, fecha
            FROM checkpoints
            ORDER BY id DESC
        """).fetchall()
        return [dict(r) for r in rows]


def gates_esperados() -> dict:
    """Retorna la estructura completa de los 15 gates esperados."""
    total = sum(len(g) for g in PERFILES_POR_ETAPA.values())
    return {"total_gates": total, "por_etapa": {k: len(v) for k, v in PERFILES_POR_ETAPA.items()}}


def main():
    p = argparse.ArgumentParser(description="Sistema de checkpoints FASP")
    p.add_argument("--db", required=True)
    p.add_argument("--etapa", choices=list(PERFILES_POR_ETAPA.keys()))
    p.add_argument("--perfil")
    p.add_argument("--anexo")
    p.add_argument("--doc-id")
    p.add_argument("--decision", choices=["aprobado", "rechazado", "pendiente"])
    p.add_argument("--aprobador")
    p.add_argument("--comentario", default="")
    p.add_argument("--listar", choices=["todos", "pendientes"], help="Listar checkpoints")
    p.add_argument("--gates", action="store_true", help="Mostrar estructura de gates esperados")
    args = p.parse_args()

    db_path = pathlib.Path(args.db)

    if args.gates:
        g = gates_esperados()
        print(f"Total de gates esperados: {g['total_gates']}")
        for etapa, n in g["por_etapa"].items():
            print(f"  {etapa}: {n}")
            for perfil, desc in PERFILES_POR_ETAPA[etapa]:
                print(f"    - {perfil}: {desc}")
        return

    if args.listar:
        results = listar(db_path, args.listar)
        if not results:
            print("(sin resultados)")
            return
        for r in results:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    # Modo registro
    if not all([args.etapa, args.perfil, args.anexo, args.decision]):
        sys.exit("Para registrar un checkpoint, proporciona --etapa, --perfil, --anexo, --decision")

    # Validar que el perfil corresponde a la etapa
    perfiles_validos = {p for p, _ in PERFILES_POR_ETAPA[args.etapa]}
    if args.perfil not in perfiles_validos:
        sys.exit(f"Perfil '{args.perfil}' no válido para etapa '{args.etapa}'. "
                 f"Válidos: {sorted(perfiles_validos)}")

    cid = registrar(db_path, args.etapa, args.perfil, args.anexo,
                    args.doc_id or "N/A", args.decision,
                    args.aprobador or "sistema", args.comentario)
    print(f"✓ Checkpoint #{cid} registrado: {args.etapa} / {args.perfil} / {args.anexo} → {args.decision}")


if __name__ == "__main__":
    main()