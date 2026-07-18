#!/usr/bin/env python3
"""
build_graph.py — Etapa 3 del pipeline.

Construye un grafo NetworkX a partir de los entities.jsonl de todos los jobs
procesados, calcula métricas de red y exporta a múltiples formatos.

Uso:
    python3 build_graph.py --corpus ./jobs/ --output ./grafo/

    # Validar un grafo existente:
    python3 build_graph.py --graph ./grafo/graph.graphml --validate
"""
from __future__ import annotations
import argparse, json, pathlib, sys
from collections import defaultdict, Counter
import unicodedata

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx no instalado. Ejecuta: pip install networkx")

SCHEMA_VERSION = "1.0"


def normalize(s: str) -> str:
    """Lowercase + strip accents para usar como ID de nodo."""
    s = s.strip().lower()
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def load_entities(corpus_dir: pathlib.Path) -> list[dict]:
    """Carga todas las entities.jsonl del corpus."""
    all_ents = []
    for jsonl in corpus_dir.rglob("entities.jsonl"):
        job_id = jsonl.parent.name
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                e["job_id"] = job_id
                all_ents.append(e)
    return all_ents


def build_graph(entities: list[dict], corpus_size: int) -> tuple[nx.Graph, dict]:
    """Construye el grafo de co-ocurrencia dentro de cada sección."""
    G = nx.Graph()

    # Agrupar por (job_id, section)
    by_section = defaultdict(list)
    for e in entities:
        key = (e["job_id"], e["section"])
        by_section[key].append(e)

    # Estadísticas de nodo
    node_types = defaultdict(Counter)
    node_layers = defaultdict(set)
    node_freq = Counter()
    node_display = {}  # forma canónica para mostrar
    node_first_layer = {}

    for e in entities:
        nid = normalize(e["entity"])
        node_freq[nid] += 1
        node_display[nid] = e["entity"]  # última forma vista
        node_types[nid][e["type"]] += 1
        node_layers[nid].add(e["layer"])
        if nid not in node_first_layer:
            node_first_layer[nid] = e["layer"]

    # Crear nodos
    for nid, freq in node_freq.items():
        G.add_node(nid,
                   label=node_display[nid],
                   type=node_types[nid].most_common(1)[0][0],
                   layer=node_first_layer[nid],
                   layers=sorted(node_layers[nid]),
                   frequency=freq)

    # Aristas: co-ocurrencia en la misma sección del mismo job
    edge_weight = Counter()
    edge_layers = defaultdict(set)
    edge_docs = defaultdict(set)

    for (job_id, section), ents in by_section.items():
        unique_nodes = list({normalize(e["entity"]) for e in ents})
        layers_in_section = {e["layer"] for e in ents}
        for i, n1 in enumerate(unique_nodes):
            for n2 in unique_nodes[i+1:]:
                edge_weight[(n1, n2)] += 1
                edge_layers[(n1, n2)] |= layers_in_section
                edge_docs[(n1, n2)].add(job_id)

    for (n1, n2), w in edge_weight.items():
        layers_combined = edge_layers[(n1, n2)]
        # Si hay múltiples capas, marcar como transversal
        is_transversal = len(layers_combined) > 1
        G.add_edge(n1, n2,
                   weight=w,
                   layers=sorted(layers_combined),
                   n_documents=len(edge_docs[(n1, n2)]),
                   transversal=is_transversal)

    # Métricas
    metrics = compute_metrics(G, corpus_size)
    return G, metrics


def compute_metrics(G: nx.Graph, corpus_size: int) -> dict:
    """Calcula las métricas clave del grafo."""
    n = G.number_of_nodes()
    m = G.number_of_edges()

    if n == 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "warning": "Grafo vacío (0 nodos). ¿Se ejecutó la Etapa 2?",
            "nodos_totales": 0,
            "aristas_totales": 0,
        }

    density = nx.density(G)

    # Componentes conexas
    components = list(nx.connected_components(G))
    n_components = len(components)

    # Comunidades (Louvain si está disponible; fallback: greedy modularity)
    communities = []
    try:
        from networkx.algorithms.community import louvain_communities
        communities = louvain_communities(G, seed=42)
        community_method = "louvain"
    except Exception:
        from networkx.algorithms.community import greedy_modularity_communities
        communities = greedy_modularity_communities(G)
        community_method = "greedy_modularity"

    n_communities = len(communities)

    # Top centralidad de grado
    degree_cent = nx.degree_centrality(G)
    top_degree = sorted(degree_cent.items(), key=lambda x: -x[1])[:10]

    # Top betweenness
    if n > 1:
        betweenness = nx.betweenness_centrality(G)
        top_betweenness = sorted(betweenness.items(), key=lambda x: -x[1])[:10]
    else:
        top_betweenness = []

    # Densidad por capa (subgrafo)
    density_by_layer = {}
    for layer in ["normativo", "operativo", "informal"]:
        sub_nodes = [n for n, d in G.nodes(data=True) if layer in d.get("layers", [])]
        if len(sub_nodes) >= 2:
            sub = G.subgraph(sub_nodes)
            density_by_layer[layer] = round(nx.density(sub), 4)
        else:
            density_by_layer[layer] = None

    # Actores transversales
    transversales = [
        {"nodo": n, "label": d.get("label", n), "capas": d.get("layers", []),
         "frecuencia": d.get("frequency", 0)}
        for n, d in G.nodes(data=True)
        if len(d.get("layers", [])) >= 2
    ]
    transversales.sort(key=lambda x: -x["frecuencia"])

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_size": corpus_size,
        "nodos_totales": n,
        "aristas_totales": m,
        "densidad": round(density, 4),
        "componentes_conexas": n_components,
        "comunidades": n_communities,
        "comunidad_method": community_method,
        "top_centralidad_grado": [{"nodo": n, "label": G.nodes[n].get("label", n), "valor": round(v, 4)}
                                  for n, v in top_degree],
        "top_betweenness": [{"nodo": n, "label": G.nodes[n].get("label", n), "valor": round(v, 4)}
                            for n, v in top_betweenness],
        "densidad_por_capa": density_by_layer,
        "actores_transversales": transversales[:10],
        "advertencia_corpus_pequeno": (
            f"Corpus tiene {corpus_size} docs; análisis de redes no es robusto con < 5."
            if corpus_size < 5 else None
        ),
    }


def export_graph(G: nx.Graph, output: pathlib.Path, metrics: dict):
    """Exporta el grafo a múltiples formatos."""
    output.mkdir(parents=True, exist_ok=True)

    # GraphML (universal) — GraphML no soporta listas/booleans como valores,
    # así que convertimos a strings antes de exportar.
    G_export = G.copy()
    for n, d in G_export.nodes(data=True):
        if isinstance(d.get("layers"), list):
            d["layers"] = "|".join(d["layers"])
        d["transversal"] = str(bool(d.get("transversal", False))).lower()
    for u, v, d in G_export.edges(data=True):
        if isinstance(d.get("layers"), list):
            d["layers"] = "|".join(d["layers"])
        d["transversal"] = str(bool(d.get("transversal", False))).lower()

    nx.write_graphml(G_export, output / "graph.graphml")

    # CSV: nodos y aristas
    with open(output / "nodes.csv", "w", encoding="utf-8") as f:
        f.write("id,label,type,layer,layers,frequency\n")
        for n, d in G.nodes(data=True):
            layers = "|".join(d.get("layers", []))
            label = (d.get("label", n) or "").replace('"', '""')
            f.write(f'"{n}","{label}",{d.get("type","")},{d.get("layer","")},"{layers}",{d.get("frequency",0)}\n')

    with open(output / "edges.csv", "w", encoding="utf-8") as f:
        f.write("source,target,weight,layers,n_documents,transversal\n")
        for u, v, d in G.edges(data=True):
            layers = "|".join(d.get("layers", []))
            f.write(f'"{u}","{v}",{d.get("weight",1)},"{layers}",{d.get("n_documents",1)},{d.get("transversal",False)}\n')

    # Metrics
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    # HTML visualización (intentar con pyvis; fallback: tabla HTML)
    try:
        from pyvis.network import Network
        net = Network(height="800px", width="100%", notebook=False, cdn_resources="remote")
        net.from_nx(G)
        net.show(str(output / "graph.html"))
    except Exception as ex:
        # Fallback: HTML simple con lista tabular
        html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Grafo de gobernanza</title>",
                "<style>body{font-family:system-ui,sans-serif;margin:2em;color:#222}",
                "h1{color:#1a4480} h2{color:#2d5e8e;margin-top:1.5em}",
                "table{border-collapse:collapse;margin-top:1em;width:100%}",
                "td,th{padding:.5em .8em;border:1px solid #ccc;text-align:left}",
                "th{background:#f0f4fa} tr:nth-child(even){background:#fafbfc}",
                ".layer-normativo{color:#1a4480;font-weight:bold}",
                ".layer-operativo{color:#7a3e9d}",
                ".layer-informal{color:#b5651d}",
                "</style></head><body>"]
        html.append(f"<h1>Grafo de gobernanza</h1>")
        html.append(f"<p><b>{G.number_of_nodes()}</b> nodos · <b>{G.number_of_edges()}</b> aristas · "
                    f"densidad <b>{nx.density(G):.4f}</b></p>")
        html.append("<h2>Top 30 nodos por centralidad de grado</h2>")
        html.append("<table><tr><th>#</th><th>Nodo</th><th>Tipo</th><th>Capa(s)</th><th>Frecuencia</th><th>Grado centralidad</th></tr>")
        degree_cent = nx.degree_centrality(G)
        for i, (n, v) in enumerate(sorted(degree_cent.items(), key=lambda x: -x[1])[:30], 1):
            d = G.nodes[n]
            layers_str = ", ".join(d.get("layers", []))
            html.append(f"<tr><td>{i}</td><td>{d.get('label', n)}</td>"
                        f"<td>{d.get('type', '')}</td>"
                        f"<td>{layers_str}</td>"
                        f"<td>{d.get('frequency', 0)}</td>"
                        f"<td>{v:.3f}</td></tr>")
        html.append("</table>")
        html.append("<h2>Métricas de red</h2><ul>")
        for k, v in metrics.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                html.append(f"<li><b>{k}</b>: <i>ver sección 'Top centralidad' abajo</i></li>")
            elif isinstance(v, (str, int, float)) or v is None:
                html.append(f"<li><b>{k}</b>: {v}</li>")
        html.append("</ul></body></html>")
        (output / "graph.html").write_text("\n".join(html), encoding="utf-8")
        print(f"  (pyvis no disponible: {type(ex).__name__}; usando fallback HTML)")

    print(f"✓ Exportado a {output}/:")
    print(f"  - graph.graphml")
    print(f"  - nodes.csv / edges.csv")
    print(f"  - metrics.json")
    print(f"  - graph.html")


def main():
    p = argparse.ArgumentParser(description="Etapa 3: entidades → grafo + métricas")
    p.add_argument("--corpus", required=True, help="Directorio raíz con subdirs de jobs")
    p.add_argument("--output", required=True)
    p.add_argument("--graph", default=None, help="(para --validate) ruta a graph.graphml")
    p.add_argument("--validate", action="store_true")
    args = p.parse_args()

    if args.validate and args.graph:
        G = nx.read_graphml(args.graph)
        # Reconvertir tipos booleanos (GraphML los pierde)
        for n, d in G.nodes(data=True):
            if "layers" in d and isinstance(d["layers"], str):
                d["layers"] = d["layers"].split("|") if d["layers"] else []
            d["transversal"] = str(d.get("transversal", "False")).lower() == "true"
        n = G.number_of_nodes()
        print(f"Grafo: {n} nodos, {G.number_of_edges()} aristas")
        print(f"Densidad: {nx.density(G):.4f}")
        print(f"Componentes conexas: {nx.number_connected_components(G)}")
        sys.exit(0)

    corpus = pathlib.Path(args.corpus)
    output = pathlib.Path(args.output)

    # Detectar tamaño del corpus (número de jobs)
    corpus_size = sum(1 for _ in corpus.rglob("entities.jsonl"))

    if corpus_size == 0:
        sys.exit(f"No se encontraron entities.jsonl en {corpus}/")

    print(f"Cargando entidades de {corpus_size} jobs...")
    entities = load_entities(corpus)
    print(f"  {len(entities)} entidades en total")

    print("Construyendo grafo...")
    G, metrics = build_graph(entities, corpus_size)

    export_graph(G, output, metrics)

    # Resumen
    print("\n=== Resumen de métricas ===")
    print(f"  Nodos: {metrics['nodos_totales']}")
    print(f"  Aristas: {metrics['aristas_totales']}")
    print(f"  Densidad: {metrics.get('densidad', 'N/A')}")
    print(f"  Comunidades: {metrics.get('comunidades', 'N/A')}")
    print(f"  Top actor (grado): {metrics['top_centralidad_grado'][0] if metrics.get('top_centralidad_grado') else 'N/A'}")
    if metrics.get("advertencia_corpus_pequeno"):
        print(f"  ⚠ {metrics['advertencia_corpus_pequeno']}")


if __name__ == "__main__":
    main()