#!/usr/bin/env python3
"""
py-3-sociograma.py — Genera el sociograma del FASP aplicando los 3 criterios formales
de visualizacion del Plan de Trabajo (seccion V.G, Tabla 5):

  1. Tamano del nodo: proporcional a Betweenness (centralidad de intermediacion).
  2. Color del nodo: categorico por nivel de gobierno (Federal/Estatal/Municipal).
  3. Grosor de aristas: proporcional al peso del vinculo (weight).

Salidas (con nomenclatura FASP_2026):
  <directorio_salida>/FASP_2026_<PRODUCTO>_<EDO>_INFORME_V<X>.html
  <directorio_salida>/FASP_2026_<PRODUCTO>_<EDO>_INFORME_V<X>.png  (si matplotlib disponible)

Uso:
    python3 py-3-sociograma.py --db ./fasp.db \\
        --producto P2 --edo CHI --version V1.0 \\
        --output ./entregables/

    python3 py-3-sociograma.py --db ./fasp.db --edo NAL \\
        --producto P2 --output ./entregables/
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys
from datetime import datetime

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx no instalado. pip install networkx")

# Importar el helper de nomenclatura
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from nomenclatura import construir


# Paleta recomendada segun memoria_codificacion.json
PALETA_NIVEL = {
    "Federal": "#1a4480",
    "Estatal": "#7a3e9d",
    "Municipal": "#b5651d",
    "Desconocido": "#888888",
}


def cargar_grafo(db_path: pathlib.Path) -> tuple[nx.DiGraph, dict]:
    """Carga el grafo desde la BD y une informacion de nivel_gobierno por nodo."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    G = nx.DiGraph()

    # Nodos con metadata (nivel_gobierno)
    nivel_por_actor = {}
    for r in conn.execute("SELECT id_actor, nombre_oficial, nivel_gobierno FROM actores"):
        G.add_node(r[0], label=r[1], nivel_gobierno=r[2] or "Desconocido")
        nivel_por_actor[r[0]] = r[2] or "Desconocido"

    # Aristas
    for r in conn.execute("SELECT origen, destino, peso, tipo_vinculo FROM aristas"):
        G.add_edge(r[0], r[1], weight=r[2], tipo_vinculo=r[3])

    conn.close()
    return G, nivel_por_actor


def calcular_tamanos(G: nx.DiGraph, factor: float = 3000) -> dict:
    """Tamano del nodo proporcional a Betweenness."""
    if G.number_of_nodes() == 0:
        return {}
    try:
        betweenness = nx.betweenness_centrality(G, weight="weight")
    except Exception:
        betweenness = {n: 0 for n in G.nodes}
    # nodo_base + factor * betweenness (asegura nodos visibles)
    return {n: 200 + factor * betweenness.get(n, 0) for n in G.nodes}


def calcular_grosores(G: nx.DiGraph, factor: float = 2.5) -> dict:
    """Grosor de aristas proporcional al peso."""
    return {(u, v): 0.5 + factor * d.get("weight", 0) / 10 for u, v, d in G.edges(data=True)}


def generar_html(G: nx.DiGraph, nivel_por_actor: dict, output_html: pathlib.Path,
                 titulo: str = "Sociograma FASP") -> dict:
    """Genera el sociograma como HTML interactivo con vis.js embebido."""
    if G.number_of_nodes() == 0:
        return {"ok": False, "razon": "Grafo vacio (sin nodos)"}

    sizes = calcular_tamanos(G)
    widths = calcular_grosores(G)

    # Construir nodos para vis.js
    nodes_json = []
    for n in G.nodes:
        d = G.nodes[n]
        nodes_json.append({
            "id": n,
            "label": d.get("label", n),
            "title": f"{d.get('label', n)} ({d.get('nivel_gobierno', 'Desconocido')})",
            "color": PALETA_NIVEL.get(d.get("nivel_gobierno", "Desconocido"), PALETA_NIVEL["Desconocido"]),
            "size": sizes.get(n, 200),
            "font": {"size": 12, "color": "#222"},
        })

    edges_json = []
    for u, v, d in G.edges(data=True):
        edges_json.append({
            "from": u,
            "to": v,
            "width": widths.get((u, v), 1.0),
            "title": f"{d.get('tipo_vinculo', 'N/D')} (peso={d.get('weight', 0)})",
            "color": {"color": "#999", "opacity": 0.5},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
        })

    # Estadísticas para el encabezado
    n_nodos = G.number_of_nodes()
    n_aristas = G.number_of_edges()
    densidad = nx.density(G)
    distribucion_niveles = {}
    for n in G.nodes:
        nv = G.nodes[n].get("nivel_gobierno", "Desconocido")
        distribucion_niveles[nv] = distribucion_niveles.get(nv, 0) + 1

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{titulo}</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1em; color: #222; background: #fafafa; }}
h1 {{ color: #1a4480; margin: 0 0 .5em 0; }}
.lead {{ color: #666; margin-bottom: 1em; }}
.legend {{ background: white; padding: 1em; border: 1px solid #ddd; border-radius: 4px;
           margin-bottom: 1em; }}
.legend span {{ display: inline-block; margin-right: 1.5em; font-size: .9em; }}
.dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%;
        vertical-align: middle; margin-right: 6px; border: 1px solid #333; }}
#network {{ width: 100%; height: 700px; background: white;
             border: 1px solid #ddd; border-radius: 4px; }}
table.stats {{ border-collapse: collapse; margin-top: .5em; font-size: .9em; }}
table.stats td, table.stats th {{ padding: .3em .8em; border: 1px solid #ddd; text-align: left; }}
</style>
</head>
<body>
<h1>{titulo}</h1>
<p class="lead">Sociograma generado el {datetime.now().strftime("%Y-%m-%d %H:%M")} | {n_nodos} nodos · {n_aristas} aristas · densidad {densidad:.4f}</p>

<div class="legend">
  <b>Leyenda de nodos (color = nivel de gobierno):</b>
  <span><span class="dot" style="background: {PALETA_NIVEL['Federal']}"></span>Federal</span>
  <span><span class="dot" style="background: {PALETA_NIVEL['Estatal']}"></span>Estatal</span>
  <span><span class="dot" style="background: {PALETA_NIVEL['Municipal']}"></span>Municipal</span>
  <span><span class="dot" style="background: {PALETA_NIVEL['Desconocido']}"></span>Desconocido</span>
  <br><br>
  <b>Leyenda de nodos (tamaño = centralidad de intermediación):</b> a mayor control sobre flujos de coordinación, nodo más grande.<br>
  <b>Leyenda de aristas (grosor = peso del vínculo):</b> interacciones más frecuentes e intensas, aristas más gruesas.
</div>

<div id="network"></div>

<table class="stats">
<tr><th>Distribucion por nivel de gobierno</th><th>Nodos</th></tr>
"""
    for nv, n in sorted(distribucion_niveles.items()):
        html += f"<tr><td>{nv}</td><td>{n}</td></tr>"
    html += f"""
</table>

<script>
const nodes = new vis.DataSet({json.dumps(nodes_json, ensure_ascii=False)});
const edges = new vis.DataSet({json.dumps(edges_json, ensure_ascii=False)});
const container = document.getElementById('network');
const data = {{ nodes: nodes, edges: edges }};
const options = {{
  physics: {{
    enabled: true,
    stabilization: {{ iterations: 200 }},
  }},
  interaction: {{ hover: true, tooltipDelay: 100 }},
  nodes: {{ borderWidth: 2, shadow: true }},
  edges: {{ smooth: {{ type: "continuous" }} }}
}};
new vis.Network(container, data, options);
</script>

</body>
</html>
"""

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
    return {"ok": True, "n_nodos": n_nodos, "n_aristas": n_aristas, "densidad": round(densidad, 4)}


def generar_png(G: nx.DiGraph, output_png: pathlib.Path) -> bool:
    """Genera PNG estatico con matplotlib si esta disponible."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    if G.number_of_nodes() == 0:
        return False

    sizes = calcular_tamanos(G, factor=1500)
    widths = calcular_grosores(G, factor=2.0)
    colors = [PALETA_NIVEL.get(G.nodes[n].get("nivel_gobierno", "Desconocido"), "#888")
              for n in G.nodes]
    width_list = [widths.get((u, v), 1.0) for u, v in G.edges()]

    # Layout: spring layout
    pos = nx.spring_layout(G.to_undirected(), seed=42, k=1.5)

    fig, ax = plt.subplots(figsize=(16, 12))
    nx.draw_networkx_nodes(G, pos, node_size=[sizes.get(n, 200) for n in G.nodes],
                           node_color=colors, alpha=0.85, edgecolors="black", linewidths=1.0, ax=ax)
    nx.draw_networkx_edges(G, pos, width=width_list, alpha=0.4, edge_color="#666",
                           arrows=True, arrowsize=15, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=8, font_color="#222", ax=ax)

    # Leyenda
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=c, label=k, edgecolor="black")
                       for k, c in PALETA_NIVEL.items()]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=10,
              title="Nivel de gobierno")
    ax.set_title(f"Sociograma FASP — {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas",
                 fontsize=14, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()

    output_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return True


def main():
    p = argparse.ArgumentParser(description="Genera el sociograma FASP con criterios topologicos")
    p.add_argument("--db", required=True)
    p.add_argument("--producto", default="P2", choices=["P1", "P2", "P3", "IF"])
    p.add_argument("--edo", default="NAL", help="Clave de la entidad federativa")
    p.add_argument("--version", default="V1.0")
    p.add_argument("--output", required=True, help="Directorio de salida")
    args = p.parse_args()

    db_path = pathlib.Path(args.db)
    output_dir = pathlib.Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    G, nivel_por_actor = cargar_grafo(db_path)
    print(f"Grafo cargado: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    if G.number_of_nodes() == 0:
        print("✗ Grafo vacio. Ejecuta PY-2 primero para tener aristas en la BD.")
        sys.exit(1)

    # Nombres con nomenclatura FASP_2026
    html_nombre = construir(args.producto, args.edo, "INFORME", args.version, ".html")
    png_nombre = construir(args.producto, args.edo, "INFORME", args.version, ".png")

    html_path = output_dir / html_nombre
    png_path = output_dir / png_nombre

    print(f"Generando HTML: {html_nombre}")
    r = generar_html(G, nivel_por_actor, html_path,
                     titulo=f"Sociograma FASP — {args.producto} {args.edo}")
    if not r["ok"]:
        print(f"✗ {r['razon']}")
        sys.exit(1)
    print(f"  ✓ {r['n_nodos']} nodos, {r['n_aristas']} aristas, densidad {r['densidad']}")

    print(f"Generando PNG: {png_nombre}")
    if generar_png(G, png_path):
        print(f"  ✓ {png_path}")
    else:
        print(f"  ⚠ matplotlib no disponible; solo HTML")

    print(f"\n✓ Sociograma(s) en {output_dir}/")


if __name__ == "__main__":
    main()