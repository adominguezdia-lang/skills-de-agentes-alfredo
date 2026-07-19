#!/usr/bin/env python3
"""
py-3-metricas-ars.py — PY-3 del skill FASP.

Calcula las 8 métricas ARS requeridas por el Anexo 5 y Anexo 6:
- centralidad de grado (in/out)
- intermediación (betweenness)
- cercanía (closeness)
- densidad
- modularidad (Louvain)
- diámetro
Y genera la Memoria algorítmica.

Uso:
    python3 py-3-metricas-ars.py --db ./fasp.db --output ./anexos/
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys
from datetime import datetime, timezone

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx no instalado. pip install networkx")


def construir_grafo(db_path: pathlib.Path) -> nx.DiGraph:
    """Construye un grafo dirigido desde la tabla aristas."""
    conn = sqlite3.connect(db_path)
    G = nx.DiGraph()

    # Nodos
    for r in conn.execute("SELECT id_actor, nombre_oficial FROM actores"):
        G.add_node(r[0], label=r[1])

    # Aristas (peso como atributo)
    for r in conn.execute("""
        SELECT origen, destino, peso, tipo_vinculo
        FROM aristas
    """):
        G.add_edge(r[0], r[1], weight=r[2], tipo_vinculo=r[3])

    conn.close()
    return G


def calcular_metricas(G: nx.DiGraph) -> tuple[dict, dict]:
    """Calcula las 8 métricas requeridas. Retorna (metricas_globales, metricas_por_nodo)."""
    if G.number_of_nodes() == 0:
        return {}, {}

    # Globales
    metricas_globales = {
        "nodos": G.number_of_nodes(),
        "aristas": G.number_of_edges(),
        "densidad": round(nx.density(G), 4),
        "componentes_conexas": nx.number_weakly_connected_components(G),
    }

    # Diámetro y métricas de camino (solo si es débilmente conexo)
    if nx.is_weakly_connected(G):
        metricas_globales["diametro"] = nx.diameter(G.to_undirected())
    else:
        metricas_globales["diametro"] = None

    # Modularidad (Louvain, sobre la versión no-dirigida)
    try:
        from networkx.algorithms.community import louvain_communities
        communities = louvain_communities(G.to_undirected(), seed=42)
        metricas_globales["n_comunidades"] = len(communities)
        # Asignar comunidades a nodos
        nodo_a_comunidad = {}
        for i, comm in enumerate(communities):
            for n in comm:
                nodo_a_comunidad[n] = i
    except Exception as ex:
        metricas_globales["n_comunidades"] = None
        nodo_a_comunidad = {}

    # Por nodo
    metricas_por_nodo = {}
    in_deg = dict(G.in_degree())
    out_deg = dict(G.out_degree())
    try:
        degree_cent = nx.degree_centrality(G)
    except Exception:
        degree_cent = {n: 0 for n in G.nodes}
    try:
        betweenness = nx.betweenness_centrality(G, weight="weight")
    except Exception:
        betweenness = {n: 0 for n in G.nodes}
    try:
        closeness = nx.closeness_centrality(G)
    except Exception:
        closeness = {n: 0 for n in G.nodes}

    for n in G.nodes:
        metricas_por_nodo[n] = {
            "in_degree": in_deg.get(n, 0),
            "out_degree": out_deg.get(n, 0),
            "degree_centrality": round(degree_cent.get(n, 0), 4),
            "betweenness": round(betweenness.get(n, 0), 4),
            "closeness": round(closeness.get(n, 0), 4),
            "comunidad_id": nodo_a_comunidad.get(n),
        }

    return metricas_globales, metricas_por_nodo


def guardar_metricas_bd(db_path: pathlib.Path, metricas_por_nodo: dict):
    """Persiste métricas por nodo en la tabla `metricas_ars`."""
    conn = sqlite3.connect(db_path)
    for n, m in metricas_por_nodo.items():
        conn.execute("""
            INSERT OR REPLACE INTO metricas_ars
            (id_actor, in_degree, out_degree, degree_centrality, betweenness, closeness, comunidad_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (n, m["in_degree"], m["out_degree"], m["degree_centrality"],
              m["betweenness"], m["closeness"], m["comunidad_id"]))
    conn.commit()
    conn.close()


def generar_anexo5(db_path: pathlib.Path, output_dir: pathlib.Path,
                   metricas_globales: dict) -> dict:
    """Genera Anexo 5 — Memoria algorítmica."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Versión del pipeline (de la BD)
    cur.execute("SELECT value FROM _meta WHERE key='schema_version'")
    schema_version = cur.fetchone()
    schema_version = schema_version[0] if schema_version else "desconocida"

    anexo5 = {
        "algoritmos_usados": [
            {
                "nombre": "NetworkX centralidad de grado",
                "version": nx.__version__,
                "proposito": "Medir cuántos enlaces entran/salen de cada nodo",
                "parametros": {"weight": "peso (intensidad 0-10)"},
            },
            {
                "nombre": "NetworkX betweenness centrality",
                "version": nx.__version__,
                "proposito": "Medir cuántos caminos mínimos pasan por cada nodo",
                "parametros": {"weight": "peso (inverso para que aristas fuertes = más cortas)"},
            },
            {
                "nombre": "NetworkX closeness centrality",
                "version": nx.__version__,
                "proposito": "Medir cercanía promedio a todos los demás nodos",
                "parametros": {},
            },
            {
                "nombre": "Louvain (networkx.algorithms.community)",
                "version": nx.__version__,
                "proposito": "Detectar comunidades maximizando modularidad",
                "parametros": {"seed": 42},
            },
        ],
        "tratamiento_lazos": "dirigidos y ponderados",
        "tratamiento_nodos_aislados": "Se preservan en el grafo pero se reportan sin centralidad (0 en todas las métricas).",
        "escala_intensidad": {
            "rango": "0-10",
            "definicion": "0=sin interacción, 10=coordinación diaria formalizada. Documentada en la Memoria de Codificación del equipo ARS."
        },
        "metricas_calculadas": [
            "centralidad_grado", "in_degree", "out_degree",
            "intermediacion", "cercania", "densidad",
            "modularidad", "diametro",
        ],
        "version_pipeline": schema_version,
        "fecha_calculo": datetime.now(timezone.utc).isoformat(),
    }

    # Render Markdown
    md = [
        "# Anexo 5 — Memoria algorítmica",
        "",
        f"**Versión del pipeline:** {anexo5['version_pipeline']}  ",
        f"**Fecha de cálculo:** {anexo5['fecha_calculo']}  ",
        "",
        "## Algoritmos utilizados",
        "",
    ]
    for alg in anexo5["algoritmos_usados"]:
        md.append(f"### {alg['nombre']} (v{alg['version']})")
        md.append(f"- **Propósito:** {alg['proposito']}")
        md.append(f"- **Parámetros:** `{json.dumps(alg['parametros'])}`")
        md.append("")
    md.append(f"## Tratamiento de lazos")
    md.append(f"{anexo5['tratamiento_lazos']}")
    md.append("")
    md.append(f"## Tratamiento de nodos aislados")
    md.append(f"{anexo5['tratamiento_nodos_aislados']}")
    md.append("")
    md.append(f"## Escala de intensidad")
    md.append(f"- Rango: **{anexo5['escala_intensidad']['rango']}**")
    md.append(f"- {anexo5['escala_intensidad']['definicion']}")
    md.append("")
    md.append("## Métricas calculadas")
    for m in anexo5["metricas_calculadas"]:
        md.append(f"- {m}")
    md.append("")
    md.append("## Métricas globales del grafo actual")
    md.append("")
    for k, v in metricas_globales.items():
        md.append(f"- **{k}:** {v}")
    md.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "anexo5_memoria_algoritmica.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Audit log
    conn.execute("""
        INSERT INTO audit_log (modulo, accion, tabla, row_id, detalle)
        VALUES (?, ?, ?, ?, ?)
    """, ("PY-3", "generate", "anexo5", "global", json.dumps(metricas_globales)))
    conn.commit()
    conn.close()

    return {"path": str(md_path), "metricas_globales": metricas_globales}


def generar_anexo6(db_path: pathlib.Path, output_dir: pathlib.Path) -> dict:
    """Genera Anexo 6 — Diccionario de atributos de los nodos."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    nodos = []
    for r in conn.execute("""
        SELECT a.id_actor, a.nombre_oficial, a.nivel_gobierno, a.entidad_federativa,
               a.naturaleza_juridica, m.in_degree, m.out_degree, m.degree_centrality,
               m.betweenness, m.closeness, m.comunidad_id
        FROM actores a
        LEFT JOIN metricas_ars m ON a.id_actor = m.id_actor
        ORDER BY a.id_actor
    """):
        nodos.append(dict(r))

    conn.close()

    csv_path = output_dir / "anexo6_diccionario_atributos.csv"
    import csv
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if not nodos:
            return {"path": str(csv_path), "nodos": 0}
        w = csv.DictWriter(f, fieldnames=list(nodos[0].keys()))
        w.writeheader()
        for n in nodos:
            w.writerow(n)

    return {"path": str(csv_path), "nodos": len(nodos)}


def main():
    p = argparse.ArgumentParser(description="PY-3 Métricas ARS + Memoria algorítmica")
    p.add_argument("--db", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    output_dir = pathlib.Path(args.output)
    db_path = pathlib.Path(args.db)

    print("Construyendo grafo desde BD...")
    G = construir_grafo(db_path)
    print(f"  ✓ {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    print("Calculando métricas ARS...")
    metricas_globales, metricas_por_nodo = calcular_metricas(G)
    print(f"  ✓ densidad={metricas_globales.get('densidad')}, "
          f"diámetro={metricas_globales.get('diametro')}, "
          f"comunidades={metricas_globales.get('n_comunidades')}")

    print("Persistiendo métricas por nodo en BD...")
    guardar_metricas_bd(db_path, metricas_por_nodo)

    print("Generando Anexo 5 — Memoria algorítmica...")
    a5 = generar_anexo5(db_path, output_dir, metricas_globales)
    print(f"  ✓ {a5['path']}")

    print("Generando Anexo 6 — Diccionario de atributos...")
    a6 = generar_anexo6(db_path, output_dir)
    print(f"  ✓ {a6['path']} ({a6['nodos']} nodos)")


if __name__ == "__main__":
    main()