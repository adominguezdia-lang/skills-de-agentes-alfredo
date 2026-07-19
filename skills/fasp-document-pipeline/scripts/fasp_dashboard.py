#!/usr/bin/env python3
"""
fasp_dashboard.py — Genera un dashboard HTML de seguimiento del pipeline FASP.

Lee la BD SQLite del skill y produce un HTML autocontenido (sin dependencias
externas, sin servidor web) que muestra:

  1. Header con metadata del programa
  2. Metricas globales (normas, unidades, actores, aristas, checkpoints, fichas)
  3. Estado de las 3 etapas con los 15 gates humanos (5 perfiles x 3 etapas)
  4. Tabla de las 8 entidades federativas con su estado
  5. Timeline de los ultimos 20 eventos del audit_log

Uso:
    python3 fasp_dashboard.py --db ./fasp.db --output ./dashboard.html
"""
from __future__ import annotations
import argparse, pathlib, sqlite3
from datetime import datetime


# 15 gates reales del Plan de Trabajo FASP 2026
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

ETAPAS_LABEL = {
    "etapa_1_documental": "Etapa 1: Analisis Documental",
    "etapa_2_campo_ars": "Etapa 2: Campo + ARS",
    "etapa_3_triangulacion": "Etapa 3: Triangulacion + Recomendaciones",
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
            "gates_aprobados": {},
            "gates_rechazados": {},
            "audit": [],
        }

        for etapa, perfil, _ in PIPELINE_GATES:
            row = conn.execute("""
                SELECT decision, aprobador, fecha
                FROM checkpoints
                WHERE etapa = ? AND perfil = ?
                ORDER BY id DESC LIMIT 1
            """, (etapa, perfil)).fetchone()
            if row:
                key = (etapa, perfil)
                if row["decision"] == "aprobado":
                    data["gates_aprobados"][key] = row
                elif row["decision"] == "rechazado":
                    data["gates_rechazados"][key] = row

        for r in conn.execute("""
            SELECT timestamp, modulo, accion, tabla, detalle
            FROM audit_log
            ORDER BY id DESC LIMIT 20
        """):
            data["audit"].append(dict(r))

    finally:
        conn.close()
    return data


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

    gates_por_etapa = {"etapa_1_documental": [], "etapa_2_campo_ars": [], "etapa_3_triangulacion": []}
    for etapa, perfil, descripcion in PIPELINE_GATES:
        key = (etapa, perfil)
        if key in data["gates_aprobados"]:
            estado = "aprobado"
            fecha = data["gates_aprobados"][key]["fecha"]
            aprobador = data["gates_aprobados"][key]["aprobador"]
        elif key in data["gates_rechazados"]:
            estado = "rechazado"
            fecha = data["gates_rechazados"][key]["fecha"]
            aprobador = data["gates_rechazados"][key]["aprobador"]
        else:
            estado = "pendiente"
            fecha = None
            aprobador = None
        gates_por_etapa[etapa].append({
            "etapa": etapa, "perfil": perfil, "descripcion": descripcion,
            "estado": estado, "fecha": fecha, "aprobador": aprobador
        })

    def pct(etapa):
        total = len(gates_por_etapa[etapa])
        ok = sum(1 for g in gates_por_etapa[etapa] if g["estado"] == "aprobado")
        return int(ok * 100 / total) if total > 0 else 0

    avance = {e: pct(e) for e in gates_por_etapa}
    avance_total = int(sum(avance.values()) / len(avance)) if avance else 0

    css = """
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
           margin: 0; padding: 0; background: #f5f7fa; color: #1f2937; }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .header { background: linear-gradient(135deg, #1a4480 0%, #2d5e8e 100%);
              color: white; padding: 32px; border-radius: 12px;
              margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .header h1 { margin: 0 0 8px 0; font-size: 28px; font-weight: 700; }
    .header .subtitle { opacity: 0.9; font-size: 14px; }
    .header .meta { display: flex; gap: 24px; margin-top: 16px; flex-wrap: wrap; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px; margin-bottom: 24px; }
    .card { background: white; border-radius: 10px; padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 4px solid #1a4480; }
    .card .label { font-size: 11px; color: #6b7280; text-transform: uppercase;
                   letter-spacing: 0.05em; font-weight: 600; margin-bottom: 8px; }
    .card .value { font-size: 32px; font-weight: 700; color: #111827; line-height: 1; }
    .stages { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
    @media (max-width: 900px) { .stages { grid-template-columns: 1fr; } }
    .stage { background: white; border-radius: 10px; padding: 20px;
             box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
    .stage h3 { margin: 0 0 12px 0; font-size: 16px; color: #111827; }
    .stage .progress { height: 8px; background: #e5e7eb; border-radius: 4px;
                       overflow: hidden; margin-bottom: 12px; }
    .stage .progress-bar { height: 100%; transition: width 0.3s; }
    .stage .progress-bar.green { background: #10b981; }
    .stage .progress-bar.yellow { background: #f59e0b; }
    .stage .progress-bar.red { background: #ef4444; }
    .gate { display: flex; align-items: center; gap: 8px; padding: 8px 12px;
            margin-bottom: 6px; background: #f9fafb; border-radius: 6px;
            font-size: 13px; }
    .gate .chip { padding: 2px 10px; border-radius: 12px; font-size: 11px;
                  font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
                  white-space: nowrap; }
    .gate .chip.green { background: #d1fae5; color: #065f46; }
    .gate .chip.yellow { background: #fef3c7; color: #92400e; }
    .gate .chip.red { background: #fee2e2; color: #991b1b; }
    .gate .desc { flex: 1; color: #4b5563; }
    .gate .meta-info { font-size: 11px; color: #9ca3af; }
    .section { background: white; border-radius: 10px; padding: 24px;
               box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 24px; }
    .section h2 { margin: 0 0 16px 0; font-size: 18px; color: #111827; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; }
    th { background: #f9fafb; font-weight: 600; color: #374151; font-size: 12px; }
    tr:hover { background: #f9fafb; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge.green { background: #d1fae5; color: #065f46; }
    .badge.gray { background: #f3f4f6; color: #6b7280; }
    .timeline-entry { padding: 10px 12px; border-left: 3px solid #e5e7eb;
                       margin-bottom: 6px; background: #f9fafb; border-radius: 0 6px 6px 0; }
    .timeline-entry .time { font-size: 11px; color: #9ca3af; }
    .timeline-entry .mod { font-weight: 600; color: #1a4480; }
    .empty { color: #9ca3af; font-style: italic; padding: 12px; text-align: center;
             background: #f9fafb; border-radius: 6px; }
    .footer { text-align: center; padding: 24px; color: #9ca3af; font-size: 12px; }
    .progress-global { margin-top: 16px; }
    .progress-global .bar { height: 12px; background: rgba(255,255,255,0.2);
                            border-radius: 6px; overflow: hidden; margin-top: 8px; }
    .progress-global .fill { height: 100%; background: #10b981; border-radius: 6px; }
    """

    def render_gate(g):
        chip_class = {"aprobado": "green", "pendiente": "yellow", "rechazado": "red"}[g["estado"]]
        meta_info = ""
        if g["estado"] == "aprobado" and g["fecha"]:
            fecha_corta = g["fecha"][:10]
            meta_info = f'<span class="meta-info">{fecha_corta} · {g["aprobador"] or ""}</span>'
        return f"""<div class="gate">
            <span class="chip {chip_class}">{g["estado"]}</span>
            <span class="desc">{PERFILES_LABEL[g["perfil"]]}: {g["descripcion"]}</span>
            {meta_info}
        </div>"""

    def render_stage(etapa_key, gates):
        pct_val = avance[etapa_key]
        bar_class = "green" if pct_val == 100 else ("yellow" if pct_val >= 50 else "red")
        ok = sum(1 for g in gates if g["estado"] == "aprobado")
        pend = sum(1 for g in gates if g["estado"] == "pendiente")
        rech = sum(1 for g in gates if g["estado"] == "rechazado")
        return f"""
        <div class="stage">
            <h3>{ETAPAS_LABEL[etapa_key]}</h3>
            <div class="progress"><div class="progress-bar {bar_class}" style="width: {pct_val}%"></div></div>
            <div class="pct">{ok}/{len(gates)} gates aprobados · {pend} pendientes · {rech} rechazados</div>
            {''.join(render_gate(g) for g in gates)}
        </div>"""

    def render_entidades():
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

    def render_audit():
        if not data["audit"]:
            return '<div class="empty">Sin eventos registrados aun.</div>'
        entries = []
        for e in data["audit"]:
            detalle = (e["detalle"] or "")[:80]
            entries.append(f"""<div class="timeline-entry">
                <div class="time">{e["timestamp"]}</div>
                <span class="mod">{e["modulo"]}</span> · {e["accion"]} en {e["tabla"]}
                {f'<div style="color:#6b7280;font-size:12px;margin-top:4px">{detalle}</div>' if detalle else ""}
            </div>""")
        return "\n".join(entries)

    avance_global_html = ""
    if avance_total > 0:
        avance_global_html = f"""
        <div class="progress-global">
            <div style="font-size:13px;opacity:0.9">Avance global del pipeline</div>
            <div class="bar"><div class="fill" style="width: {avance_total}%"></div></div>
            <div style="font-size:11px;opacity:0.8;margin-top:4px">{avance_total}% ({m['checkpoints_aprobados']} gates firmados de 15)</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>FASP — Dashboard de Seguimiento</title>
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
    {avance_global_html}
</div>

<div class="grid">
    <div class="card"><div class="label">Normas procesadas</div><div class="value">{m['normas']}</div></div>
    <div class="card"><div class="label">Unidades normativas</div><div class="value">{m['unidades']}</div></div>
    <div class="card"><div class="label">Actores en directorio</div><div class="value">{m['actores']}</div></div>
    <div class="card"><div class="label">Aristas ARS</div><div class="value">{m['aristas']}</div></div>
    <div class="card"><div class="label">Checkpoints firmados</div><div class="value" style="color:#10b981">{m['checkpoints_aprobados']}</div></div>
    <div class="card"><div class="label">Fichas de hallazgos</div><div class="value">{m['fichas']}</div></div>
</div>

<h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827;">Estado de las 3 etapas del pipeline</h2>
<div class="stages">
    {render_stage("etapa_1_documental", gates_por_etapa["etapa_1_documental"])}
    {render_stage("etapa_2_campo_ars", gates_por_etapa["etapa_2_campo_ars"])}
    {render_stage("etapa_3_triangulacion", gates_por_etapa["etapa_3_triangulacion"])}
</div>

<div class="section">
    <h2>Entidades federativas evaluadas</h2>
    <table>
        <thead><tr><th>Clave</th><th>Estado</th><th>Estatus</th><th>Documentos</th></tr></thead>
        <tbody>{render_entidades()}</tbody>
    </table>
</div>

<div class="section">
    <h2>Timeline de eventos recientes (audit_log)</h2>
    <div class="timeline">{render_audit()}</div>
</div>

<div class="footer">
    Generado por <code>fasp_dashboard.py</code> · Skill fasp-document-pipeline v1.1
</div>

</div>
</body>
</html>"""


def main():
    p = argparse.ArgumentParser(description="Dashboard HTML de seguimiento del pipeline FASP")
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
        print(f"  Checkpoints: {m['checkpoints_aprobados']} aprobados, "
              f"{m['checkpoints_pendientes']} pendientes")

    print(f"OK Dashboard escrito en {output}")
    print(f"  Para abrirlo: open {output}")


if __name__ == "__main__":
    main()