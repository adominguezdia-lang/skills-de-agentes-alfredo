#!/usr/bin/env python3
"""
fasp_dashboard.py — Dashboard HTML con tabs para el pipeline FASP.

Genera un HTML autocontenido (sin servidor, sin frameworks externos) con
4 pestañas: Resumen, Etapa 1, Etapa 2, Etapa 3. Cada tab muestra:
  - Métricas globales en el tab Resumen
  - Los 5 gates de cada etapa en su tab correspondiente
  - Tabla de entidades federativas + timeline en cada tab

Uso:
    python3 fasp_dashboard.py --db ./fasp.db --output ./dashboard.html
"""
from __future__ import annotations
import argparse, pathlib, sqlite3
from datetime import datetime


PIPELINE_GATES = [
    ("etapa_1_documental", "coordinadora", "Revision general de la Ficha tecnica FASP y coherencia global"),
    ("etapa_1_documental", "analista_senior_juridico", "Revision de la matriz de congruencia y directorio preliminar"),
    ("etapa_1_documental", "coordinacion_evaluacion", "Validacion de los 8 Informes 1 antes de entrega al SESNSP"),
    ("etapa_1_documental", "coordinadora", "Validacion de la Ficha tecnica administrativa (Anexo 11)"),
    ("etapa_1_documental", "analista_senior_juridico", "Validacion del Catalogo de unidades administrativas"),
    ("etapa_2_campo_ars", "coordinadora", "Validacion del Producto 2 (Hallazgos de Campo + Grupos de Enfoque)"),
    ("etapa_2_campo_ars", "analista_senior_redes", "Validacion de edge list, matrices y metricas ARS"),
    ("etapa_2_campo_ars", "analistas_junior_grafos", "Verificacion de nodos, aristas y clasificacion de relaciones"),
    ("etapa_2_campo_ars", "analista_senior_redes", "Validacion de la memoria algoritmica (Anexo 5)"),
    ("etapa_2_campo_ars", "analistas_junior_grafos", "Validacion del Diccionario de atributos (Anexo 6)"),
    ("etapa_3_triangulacion", "coordinadora", "Validacion de triangulaciones y ajustes de recomendaciones"),
    ("etapa_3_triangulacion", "coordinacion_evaluacion", "Validacion del Informe Final y Estrategia de Consolidacion"),
    ("etapa_3_triangulacion", "coordinacion_evaluacion", "Validacion de las fichas del Anexo 10"),
    ("etapa_3_triangulacion", "coordinadora", "Validacion del Glosario especializado (Anexo 7)"),
    ("etapa_3_triangulacion", "coordinacion_evaluacion", "Validacion de la Metodologia de replicabilidad (Anexo 8)"),
]

ENTIDADES_FEDERATIVAS = [
    ("MEX", "Estado de Mexico"),
    ("CHI", "Chiapas"),
    ("MIC", "Michoacan de Ocampo"),
    ("TAM", "Tamaulipas"),
    ("HID", "Hidalgo"),
    ("QRO", "Queretaro"),
    ("TAB", "Tabasco"),
    ("ZAC", "Zacatecas"),
    ("NAL", "Agregacion Nacional"),
]

PERFILES_LABEL = {
    "coordinadora": "Coordinadora",
    "analista_senior_juridico": "Analista Senior Juridico",
    "analista_senior_redes": "Analista Senior Redes",
    "analistas_junior_grafos": "Analistas Junior Grafos",
    "coordinacion_evaluacion": "Coordinacion de Evaluacion",
}

ETAPAS_TABS = [
    ("resumen", "Resumen"),
    ("etapa_1", "Etapa 1: Documental"),
    ("etapa_2", "Etapa 2: Campo + ARS"),
    ("etapa_3", "Etapa 3: Triangulacion"),
]

ETAPA_KEY_BY_TAB = {
    "etapa_1": "etapa_1_documental",
    "etapa_2": "etapa_2_campo_ars",
    "etapa_3": "etapa_3_triangulacion",
}


def query_db(db_path: pathlib.Path) -> dict:
    if not db_path.exists():
        return {"existe": False}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        meta = {}
        for r in conn.execute("SELECT key, value FROM _meta"):
            meta[r["key"]] = r["value"]

        data = {
            "existe": True,
            "meta": meta,
            "metricas": {
                "documentos": conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0],
                "normas": conn.execute("SELECT COUNT(*) FROM normas").fetchone()[0],
                "unidades": conn.execute("SELECT COUNT(*) FROM norma_unidades").fetchone()[0],
                "actores": conn.execute("SELECT COUNT(*) FROM actores").fetchone()[0],
                "aristas": conn.execute("SELECT COUNT(*) FROM aristas").fetchone()[0],
                "checkpoints_aprobados": conn.execute("SELECT COUNT(*) FROM checkpoints WHERE decision='aprobado'").fetchone()[0],
                "checkpoints_pendientes": conn.execute("SELECT COUNT(*) FROM checkpoints WHERE decision='pendiente'").fetchone()[0],
                "checkpoints_rechazados": conn.execute("SELECT COUNT(*) FROM checkpoints WHERE decision='rechazado'").fetchone()[0],
                "fichas": conn.execute("SELECT COUNT(*) FROM fichas").fetchone()[0],
            },
            "gates": {},  # (etapa, perfil) -> {estado, fecha, aprobador}
            "audit": [],
            "metricas_por_etapa": {},
        }

        # Cargar último estado de cada gate conocido.
        for etapa, perfil, _ in PIPELINE_GATES:
            row = conn.execute("""
                SELECT decision, aprobador, fecha
                FROM checkpoints
                WHERE etapa = ? AND perfil = ?
                ORDER BY id DESC LIMIT 1
            """, (etapa, perfil)).fetchone()
            key = (etapa, perfil)
            if row:
                data["gates"][key] = dict(row)
            else:
                data["gates"][key] = None

        # Audit
        for r in conn.execute("""
            SELECT timestamp, modulo, accion, tabla, detalle
            FROM audit_log
            ORDER BY id DESC LIMIT 20
        """):
            data["audit"].append(dict(r))

        # Métricas por etapa (las que podemos calcular rápido)
        data["metricas_por_etapa"] = {
            "etapa_1": {
                "normas": data["metricas"]["normas"],
                "unidades": data["metricas"]["unidades"],
                "actores": data["metricas"]["actores"],
            },
            "etapa_2": {
                "aristas": data["metricas"]["aristas"],
            },
            "etapa_3": {
                "fichas": data["metricas"]["fichas"],
            },
        }

    finally:
        conn.close()
    return data


def render_gate(gate_state):
    """Renderiza un gate individual con su chip de estado."""
    if gate_state is None:
        chip = "pendiente"
        label = "PENDIENTE"
        fecha = ""
        aprobador = ""
    else:
        chip = gate_state["decision"]
        label = gate_state["decision"].upper()
        fecha = gate_state.get("fecha", "")[:10] if gate_state.get("fecha") else ""
        aprobador = gate_state.get("aprobador", "") or ""
    return f'<div class="gate"><span class="chip {chip}">{label}</span><div class="gate-meta">{fecha} · {aprobador}</div></div>'


def render_gates_list(gates_list, data):
    """Renderiza la lista de gates con su descripción y estado."""
    html = []
    for etapa, perfil, descripcion in gates_list:
        key = (etapa, perfil)
        state = data["gates"].get(key)
        chip_class = "pendiente"
        label = "PENDIENTE"
        fecha = "—"
        aprobador = "—"

        if state:
            chip_class = state["decision"]
            label = state["decision"].upper()
            fecha = (state.get("fecha") or "")[:10] or "—"
            aprobador = state.get("aprobador") or "—"

        html.append(f"""<div class="gate-card">
            <div class="gate-card-left">
                <span class="chip {chip_class}">{label}</span>
                <span class="gate-card-perfil">{PERFILES_LABEL[perfil]}</span>
            </div>
            <div class="gate-card-desc">{descripcion}</div>
            <div class="gate-card-right">
                <div class="gate-card-fecha">{fecha}</div>
                <div class="gate-card-aprobador">{aprobador}</div>
            </div>
        </div>""")
    return "\n".join(html)


def render_entidades_tabla(m):
    rows = []
    for edo, nombre in ENTIDADES_FEDERATIVAS:
        docs_edo = m["documentos"] if edo == "NAL" else 0
        estado_badge = '<span class="badge green">Activo</span>' if docs_edo > 0 else '<span class="badge gray">Sin datos</span>'
        rows.append(f"""<tr>
            <td><code>{edo}</code></td>
            <td>{nombre}</td>
            <td>{estado_badge}</td>
            <td>{docs_edo} docs</td>
        </tr>""")
    return "\n".join(rows)


def render_timeline(audit):
    if not audit:
        return '<div class="empty">Sin eventos registrados aun.</div>'
    entries = []
    for e in audit:
        detalle = (e["detalle"] or "")[:100]
        entries.append(f"""<div class="timeline-entry">
            <div class="time">{e["timestamp"]}</div>
            <span class="mod">{e["modulo"]}</span> · {e["accion"]} en {e["tabla"]}
            {f'<div class="detalle">{detalle}</div>' if detalle else ""}
        </div>""")
    return "\n".join(entries)


def render_html(data: dict, db_path: pathlib.Path) -> str:
    if not data["existe"]:
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>FASP — Dashboard</title>
<style>body{{font-family:system-ui;margin:2em;background:#fff5f5;padding:2em;border:1px solid #fcc;border-radius:8px}}
h1{{color:#a00}}</style></head>
<body><h1>BD no encontrada</h1>
<p>El archivo <code>{db_path}</code> no existe.</p>
<p>Ejecuta primero <code>python3 db_init.py --db {db_path}</code>.</p>
</body></html>"""

    m = data["metricas"]
    meta = data.get("meta", {})

    # Calcular avance por etapa
    def pct_etapa(tab_key):
        etapa_key = ETAPA_KEY_BY_TAB[tab_key]
        gates_etapa = [(e, p, d) for e, p, d in PIPELINE_GATES if e == etapa_key]
        ok = sum(1 for e, p, _ in gates_etapa if data["gates"].get((e, p)) and data["gates"][(e, p)]["decision"] == "aprobado")
        return ok, len(gates_etapa)
    _ = pct_etapa  # evitar warning de no usado

    # Gates por etapa para los tabs
    gates_por_etapa = {
        "etapa_1_documental": [(e, p, d) for e, p, d in PIPELINE_GATES if e == "etapa_1_documental"],
        "etapa_2_campo_ars": [(e, p, d) for e, p, d in PIPELINE_GATES if e == "etapa_2_campo_ars"],
        "etapa_3_triangulacion": [(e, p, d) for e, p, d in PIPELINE_GATES if e == "etapa_3_triangulacion"],
    }

    avance_total = sum(1 for k, v in data["gates"].items()
                       if v and v["decision"] == "aprobado")

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
           background: #f5f7fa; color: #1f2937; line-height: 1.5; }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .header { background: linear-gradient(135deg, #1a4480 0%, #2d5e8e 100%);
              color: white; padding: 32px; border-radius: 12px; margin-bottom: 16px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .header h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
    .header .subtitle { opacity: 0.9; font-size: 14px; margin-bottom: 16px; }
    .header .meta { display: flex; gap: 24px; flex-wrap: wrap; font-size: 13px; }
    .header .meta span { opacity: 0.9; }
    .progress-global { margin-top: 16px; }
    .progress-global .label { font-size: 13px; opacity: 0.9; margin-bottom: 6px; }
    .progress-global .bar { height: 12px; background: rgba(255,255,255,0.2);
                            border-radius: 6px; overflow: hidden; }
    .progress-global .fill { height: 100%; background: #10b981; border-radius: 6px;
                              transition: width 0.4s; }
    /* Tabs */
    .tabs { display: flex; gap: 0; border-bottom: 2px solid #e5e7eb; margin-bottom: 24px;
            background: white; border-radius: 10px 10px 0 0; padding: 0 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
    .tab { padding: 14px 22px; cursor: pointer; font-size: 14px; font-weight: 600;
           color: #6b7280; border-bottom: 3px solid transparent; margin-bottom: -2px;
           transition: all 0.15s; user-select: none; }
    .tab:hover { color: #1a4480; background: #f9fafb; }
    .tab.active { color: #1a4480; border-bottom-color: #1a4480; background: white; }
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.3s; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
    /* Cards */
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px; margin-bottom: 24px; }
    .card { background: white; border-radius: 10px; padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 4px solid #1a4480; }
    .card .label { font-size: 11px; color: #6b7280; text-transform: uppercase;
                   letter-spacing: 0.05em; font-weight: 600; margin-bottom: 8px; }
    .card .value { font-size: 32px; font-weight: 700; color: #111827; line-height: 1; }
    /* Tabla */
    .section { background: white; border-radius: 0 0 10px 10px; padding: 24px;
               box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 16px; }
    .section h2 { font-size: 18px; color: #111827; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; }
    th { background: #f9fafb; font-weight: 600; color: #374151; font-size: 12px; }
    tr:hover { background: #f9fafb; }
    /* Gate card */
    .gate-card { display: grid; grid-template-columns: 280px 1fr 200px; gap: 16px;
                 padding: 14px 16px; margin-bottom: 8px; background: #f9fafb;
                 border-radius: 8px; align-items: center; }
    .gate-card:hover { background: #f3f4f6; }
    .gate-card-left { display: flex; align-items: center; gap: 10px; }
    .gate-card-perfil { font-weight: 600; font-size: 13px; color: #1f2937; }
    .gate-card-desc { font-size: 13px; color: #4b5563; }
    .gate-card-right { text-align: right; font-size: 11px; color: #9ca3af; }
    .gate-card-fecha { font-weight: 600; color: #4b5563; }
    .gate-card-aprobador { color: #6b7280; }
    /* Chips */
    .chip { display: inline-block; padding: 3px 10px; border-radius: 12px;
            font-size: 10px; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.05em; white-space: nowrap; }
    .chip.aprobado { background: #d1fae5; color: #065f46; }
    .chip.pendiente { background: #fef3c7; color: #92400e; }
    .chip.rechazado { background: #fee2e2; color: #991b1b; }
    /* Badges */
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
             font-size: 11px; font-weight: 600; }
    .badge.green { background: #d1fae5; color: #065f46; }
    .badge.gray { background: #f3f4f6; color: #6b7280; }
    /* Timeline */
    .timeline-entry { padding: 10px 12px; border-left: 3px solid #e5e7eb;
                       margin-bottom: 6px; background: #f9fafb;
                       border-radius: 0 6px 6px 0; }
    .timeline-entry .time { font-size: 11px; color: #9ca3af; }
    .timeline-entry .mod { font-weight: 600; color: #1a4480; }
    .timeline-entry .detalle { color: #6b7280; font-size: 12px; margin-top: 4px; }
    .empty { color: #9ca3af; font-style: italic; padding: 12px; text-align: center;
             background: #f9fafb; border-radius: 6px; }
    .footer { text-align: center; padding: 24px; color: #9ca3af; font-size: 12px; }
    /* Etiqueta de etapa */
    .etapa-tag { display: inline-block; padding: 4px 12px; border-radius: 6px;
                 background: #dbeafe; color: #1e40af; font-size: 12px;
                 font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
    .etapa-tag.e1 { background: #dbeafe; color: #1e40af; }
    .etapa-tag.e2 { background: #ede9fe; color: #5b21b6; }
    .etapa-tag.e3 { background: #fef3c7; color: #92400e; }
    .etapa-progress { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
    .etapa-progress .bar { flex: 1; height: 10px; background: #e5e7eb;
                            border-radius: 5px; overflow: hidden; }
    .etapa-progress .fill { height: 100%; transition: width 0.3s; }
    .etapa-progress .fill.green { background: #10b981; }
    .etapa-progress .fill.yellow { background: #f59e0b; }
    .etapa-progress .fill.red { background: #ef4444; }
    .etapa-progress .pct { font-weight: 700; font-size: 14px; min-width: 40px; text-align: right; }
    """

    # Stats por etapa para mostrar
    def stats_etapa(tab):
        if tab == "etapa_1":
            return [
                ("Normas procesadas", m['normas']),
                ("Unidades normativas", m['unidades']),
                ("Actores en directorio", m['actores']),
            ]
        elif tab == "etapa_2":
            return [
                ("Aristas ARS", m['aristas']),
                ("Gates Etapa 2 registrados",
                 sum(1 for e, p in data["gates"] if e == "etapa_2_campo_ars"
                     and data["gates"][(e, p)] and data["gates"][(e, p)]["decision"] == "aprobado")),
            ]
        elif tab == "etapa_3":
            return [
                ("Fichas de hallazgos (Anexo 10)", m['fichas']),
                ("Gates Etapa 3 registrados",
                 sum(1 for e, p in data["gates"] if e == "etapa_3_triangulacion"
                     and data["gates"][(e, p)] and data["gates"][(e, p)]["decision"] == "aprobado")),
            ]
        return []

    # Generar contenido de cada tab
    def tab_content_resumen():
        ok = sum(1 for k, v in data["gates"].items() if v and v["decision"] == "aprobado")
        total = len(data["gates"])
        return f"""
        <div id="tab-resumen" class="tab-content active">
            <div class="grid">
                <div class="card"><div class="label">Normas procesadas</div><div class="value">{m['normas']}</div></div>
                <div class="card"><div class="label">Unidades normativas</div><div class="value">{m['unidades']}</div></div>
                <div class="card"><div class="label">Actores en directorio</div><div class="value">{m['actores']}</div></div>
                <div class="card"><div class="label">Aristas ARS</div><div class="value">{m['aristas']}</div></div>
                <div class="card"><div class="label">Gates registrados</div>
                    <div class="value" style="color:#10b981">{ok}/{total}</div></div>
                <div class="card"><div class="label">Fichas de hallazgos</div><div class="value">{m['fichas']}</div></div>
            </div>
            <div class="section">
                <h2>Entidades federativas evaluadas</h2>
                <table>
                    <thead><tr><th>Clave</th><th>Estado</th><th>Estatus</th><th>Documentos</th></tr></thead>
                    <tbody>{render_entidades_tabla(m)}</tbody>
                </table>
            </div>
            <div class="section">
                <h2>Timeline de eventos recientes</h2>
                <div class="timeline">{render_timeline(data['audit'])}</div>
            </div>
        </div>
        """

    def tab_content_etapa(tab):
        etapa_key = ETAPA_KEY_BY_TAB[tab]
        gates_etapa = gates_por_etapa[etapa_key]
        ok = sum(1 for e, p, _ in gates_etapa if data["gates"].get((e, p)) and data["gates"][(e, p)]["decision"] == "aprobado")
        total = len(gates_etapa)
        pct_val = int(ok * 100 / total) if total else 0
        bar_class = "green" if pct_val == 100 else ("yellow" if pct_val >= 50 else "red")
        clase = tab.replace("etapa_", "e")

        stats_html = ""
        for label, val in stats_etapa(tab):
            stats_html += f'<div class="card"><div class="label">{label}</div><div class="value">{val}</div></div>'

        gates_html = render_gates_list(gates_etapa, data)

        return f"""
        <div id="tab-{tab}" class="tab-content">
            <div class="etapa-progress">
                <span class="etapa-tag {clase}">{tab.replace('_', ' ').upper()}</span>
                <div class="bar"><div class="fill {bar_class}" style="width: {pct_val}%"></div></div>
                <div class="pct">{pct_val}%</div>
            </div>
            <div class="grid">{stats_html}</div>
            <div class="section">
                <h2>Gates de control registrados ({ok}/{total})</h2>
                {gates_html}
            </div>
        </div>
        """

    # Tabs
    tabs_html = []
    for tab_id, tab_label in ETAPAS_TABS:
        active = " active" if tab_id == "resumen" else ""
        tabs_html.append(f'<div class="tab{active}" data-tab="{tab_id}">{tab_label}</div>')

    # JavaScript para los tabs
    js = """
    <script>
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });
    </script>
    """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>FASP — Dashboard</title>
<style>{css}</style>
</head>
<body>
<div class="container">

<div class="header">
    <h1>Dashboard FASP — Evaluacion de Coordinacion</h1>
    <div class="subtitle">Fondo de Aportaciones para la Seguridad Publica · Plan de Trabajo 2026</div>
    <div class="meta">
        <span><b>Programa:</b> {meta.get('programa', 'FASP')}</span>
        <span><b>Ano fiscal:</b> {meta.get('anio_fiscal', '2026')}</span>
        <span><b>BD:</b> <code>{db_path.name}</code></span>
        <span><b>Generado:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
    </div>
    <div class="progress-global">
        <div class="label">Avance global del pipeline: {avance_total} de 15 gates registrados</div>
        <div class="bar"><div class="fill" style="width: {int(avance_total/15*100)}%"></div></div>
    </div>
</div>

<div class="tabs">
    {''.join(tabs_html)}
</div>

{tab_content_resumen()}
{tab_content_etapa("etapa_1")}
{tab_content_etapa("etapa_2")}
{tab_content_etapa("etapa_3")}

<div class="footer">
    Generado por <code>fasp_dashboard.py</code> · Skill fasp-document-pipeline v1.1
</div>

</div>
{js}
</body>
</html>"""


def main():
    p = argparse.ArgumentParser(description="Dashboard HTML con tabs para el pipeline FASP")
    p.add_argument("--db", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    db_path = pathlib.Path(args.db)
    output = pathlib.Path(args.output)

    print(f"Leyendo {db_path}...")
    data = query_db(db_path)

    print(f"Generando dashboard en {output}...")
    html = render_html(data, db_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")

    if data["existe"]:
        m = data["metricas"]
        print(f"  Metricas: {m['normas']} normas, {m['unidades']} unidades, "
              f"{m['actores']} actores, {m['aristas']} aristas")

    print(f"OK Dashboard escrito en {output}")
    print(f"  Para abrirlo: open {output}")


if __name__ == "__main__":
    main()