#!/usr/bin/env python3
"""
fasp_dashboard.py — Dashboard HTML de seguimiento del pipeline FASP.

4 tabs: Resumen, Etapa 1, Etapa 2, Etapa 3.
El tab Resumen muestra la lista de normas/conversiones con sus parametros
y metricas de calidad (reemplaza la antigua vista de gates).
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys, time, unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher

try:
    import sqlite3
except ImportError:
    sys.exit("sqlite3 no disponible")

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None  # El dashboard funciona sin PDF si no hay pymupdf


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:5000], b[:5000]).ratio()


def find_pdf(filename: str) -> pathlib.Path | None:
    if not filename:
        return None
    home = pathlib.Path.home()
    bases = [
        pathlib.Path.cwd(),
        home / "Downloads",
        home / "Documents",
        home / "Desktop",
        pathlib.Path("/Users/adominguezdia/Downloads"),
        pathlib.Path("/tmp"),
    ]
    for base in bases:
        if not base.exists():
            continue
        cand = base / filename
        if cand.exists() and cand.suffix.lower() == ".pdf":
            return cand
        try:
            for pdf in base.rglob(filename):
                if pdf.suffix.lower() == ".pdf":
                    return pdf
        except (PermissionError, OSError):
            continue
    return None


def extract_pdf_text(pdf_path: pathlib.Path) -> str:
    if not fitz:
        return ""
    doc = fitz.open(pdf_path)
    parts = [p.get_text() for p in doc]
    doc.close()
    return "\n\n".join(parts)


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

ETAPAS_TABS = [
    ("resumen", "Resumen"),
    ("etapa_1", "Etapa 1: Documental"),
    ("etapa_2", "Etapa 2: Campo + ARS"),
    ("etapa_3", "Etapa 3: Triangulacion"),
    ("ayuda", "Ayuda del proceso"),
]


def query_db(db_path: pathlib.Path) -> dict:
    if not db_path.exists():
        return {"existe": False}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        meta = {}
        for r in conn.execute("SELECT key, value FROM _meta"):
            meta[r["key"]] = r["value"]

        # Normas/conversiones
        normas = []
        for r in conn.execute("""
            SELECT id_norma, id_documento, nombre_norma, nivel, jerarquia, fuente
            FROM normas ORDER BY id_norma
        """):
            normas.append(dict(r))

        metricas = {
            "documentos": conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0],
            "normas": conn.execute("SELECT COUNT(*) FROM normas").fetchone()[0],
            "unidades": conn.execute("SELECT COUNT(*) FROM norma_unidades").fetchone()[0],
            "actores": conn.execute("SELECT COUNT(*) FROM actores").fetchone()[0],
            "aristas": conn.execute("SELECT COUNT(*) FROM aristas").fetchone()[0],
            "fichas": conn.execute("SELECT COUNT(*) FROM fichas").fetchone()[0],
        }

        # Audit log
        audit = []
        for r in conn.execute("""
            SELECT timestamp, modulo, accion, tabla, detalle
            FROM audit_log ORDER BY id DESC LIMIT 20
        """):
            audit.append(dict(r))

        return {
            "existe": True,
            "meta": meta,
            "metricas": metricas,
            "normas": normas,
            "audit": audit,
        }
    finally:
        conn.close()


def analyze_norma_conversion(norma: dict, db_path: pathlib.Path) -> dict:
    """Calcula las metricas de calidad para una norma si el MD existe."""
    # Buscar el MD asociado por nombre de la norma o por id_documento
    home = pathlib.Path.home()
    bases = [
        db_path.parent / "jobs",
        home / "Downloads",
        home / "Downloads" / "fasp-jobs",
        pathlib.Path("/tmp"),
    ]
    md_text = ""
    md_path = None
    meta_info = {}
    # Construir identificadores candidatos para el job
    candidates_id = []
    for key in ("id_documento", "id_norma"):
        v = norma.get(key)
        if v:
            candidates_id.append(v)
    fuente = norma.get("fuente", "")
    if fuente:
        if fuente.endswith(".md"):
            candidates_id.append(fuente[:-3])
        else:
            candidates_id.append(fuente)

    # Busqueda recursiva limitada a 3 niveles
    for base in bases:
        if not base.exists():
            continue
        try:
            for jd in base.glob("*/jobs/*") if base.name != "jobs" else base.glob("*/"):
                if not jd.is_dir():
                    continue
                if jd.name in candidates_id:
                    md_path = next(iter(jd.glob("FASP_2026_*.md")), None) or next(iter(jd.glob("*.md")), None)
                    meta_path = next(iter(jd.glob("*.meta.json")), None)
                    if md_path and meta_path:
                        md_text = md_path.read_text(encoding="utf-8")
                        meta_info = json.loads(meta_path.read_text(encoding="utf-8"))
                        break
        except (PermissionError, OSError):
            continue
        if md_text:
            break

    # Fallback: busqueda recursiva completa (más exhaustiva)
    if not md_text:
        for base in bases:
            if not base.exists():
                continue
            try:
                for md_path in base.rglob("*.md"):
                    if md_path.parent.name in candidates_id:
                        meta_path = md_path.parent / "*.meta.json"
                        meta_files = list(md_path.parent.glob("*.meta.json"))
                        if meta_files:
                            md_text = md_path.read_text(encoding="utf-8")
                            meta_info = json.loads(meta_files[0].read_text(encoding="utf-8"))
                            break
            except (PermissionError, OSError):
                continue
            if md_text:
                break

    if not md_text:
        return {
            "id_norma": norma.get("id_norma"),
            "nombre": norma.get("nombre_norma"),
            "nivel": norma.get("nivel"),
            "jerarquia": norma.get("jerarquia"),
            "fuente": norma.get("fuente"),
            "score": None,
            "rating": "Sin MD",
            "available": False,
        }
    pdf = find_pdf(meta_info.get("filename", ""))
    pdf_text = extract_pdf_text(pdf) if pdf else ""
    coverage = 0
    similarity = 0
    keyword_pres = 0
    missing_keywords = []

    if pdf_text:
        similarity = text_similarity(pdf_text, md_text)
        long_caps = re.findall(r"\b[A-ZÁÉÍÓÚÑ]{5,}\b", pdf_text)
        top = [w for w, _ in Counter(long_caps).most_common(20)]
        preserved = [w for w in top if w in md_text]
        missing_keywords = [w for w in top if w not in md_text]
        keyword_pres = round(len(preserved) / len(top), 3) if top else 0

    # Leer validation
    issues_count = 0
    val_path = md_path.with_suffix(".validation.json")
    if md_path.name.startswith("FASP_2026_"):
        # nomenclatura FASP: <basename>.validation.json
        val_path = md_path.parent / (md_path.stem + ".validation.json")
    if val_path.exists():
        v = json.loads(val_path.read_text(encoding="utf-8"))
        coverage = v.get("coverage", 0)
        issues_count = len(v.get("issues", []))

    score = (
        coverage * 40 +
        keyword_pres * 30 +
        similarity * 20 +
        max(0, 10 - issues_count * 2)
    )
    return {
        "id_norma": norma.get("id_norma"),
        "nombre": norma.get("nombre_norma"),
        "nivel": norma.get("nivel"),
        "jerarquia": norma.get("jerarquia"),
        "fuente": norma.get("fuente"),
        "filename": meta_info.get("filename"),
        "method": meta_info.get("method"),
        "prompt_version": meta_info.get("prompt_version"),
        "layer": meta_info.get("layer"),
        "n_pages": meta_info.get("n_pages"),
        "n_blocks": meta_info.get("n_blocks"),
        "created_at": meta_info.get("created_at"),
        "metrics": {
            "coverage": coverage,
            "text_similarity": round(similarity, 3),
            "keyword_preservation": keyword_pres,
            "issues_count": issues_count,
            "missing_keywords": missing_keywords[:5],
        },
        "score": round(score, 2),
        "rating": "EXCELENTE" if score >= 85 else "BUENO" if score >= 70 else "ACEPTABLE" if score >= 50 else "BAJA",
        "available": True,
    }


def render_norms_table(normas: list, db_path: pathlib.Path) -> str:
    if not normas:
        return '<div class="empty">Sin normas ingestadas.</div>'
    rows = []
    for n in normas:
        a = analyze_norma_conversion(n, db_path)
        if not a.get("available"):
            score_cell = '<span class="badge gray">Sin MD</span>'
            rating_cell = "—"
            color = ""
        else:
            m = a["metrics"]
            color = "#10b981" if a["score"] >= 85 else "#f59e0b" if a["score"] >= 50 else "#ef4444"
            score_cell = f'<strong style="color:{color}">{a["score"]:.1f}</strong>'
            rating_cell = a["rating"]

        rows.append(f"""<tr>
            <td><code>{a.get("id_norma", "-")[:14]}</code></td>
            <td>{(a.get("nombre") or "-")[:40]}</td>
            <td>{a.get("nivel", "-")}</td>
            <td>{a.get("jerarquia", "-")}</td>
            <td>{a.get("filename", "-")}</td>
            <td>{a.get("prompt_version", "-")}</td>
            <td>{a.get("n_pages", "-")}</td>
            <td>{a.get("metrics", {}).get("coverage", "—")}</td>
            <td>{a.get("metrics", {}).get("text_similarity", "—")}</td>
            <td>{score_cell}</td>
            <td>{rating_cell}</td>
        </tr>""")
    return "\n".join(rows)


def render_norms_detail(normas: list, db_path: pathlib.Path) -> str:
    """Renderiza un panel expandible con detalles por norma."""
    cards = []
    for n in normas:
        a = analyze_norma_conversion(n, db_path)
        if not a.get("available"):
            continue
        m = a["metrics"]
        color = "#10b981" if a["score"] >= 85 else "#f59e0b" if a["score"] >= 50 else "#ef4444"
        missing = ", ".join(m.get("missing_keywords", [])) or "ninguna"

        cards.append(f"""<div class="norma-card">
            <div class="norma-card-header">
                <div>
                    <div class="norma-id">{a["id_norma"]}</div>
                    <div class="norma-nombre">{a["nombre"][:60]}</div>
                </div>
                <div class="norma-score" style="background:{color}">
                    {a["score"]:.1f}<br><span class="norma-rating">{a["rating"]}</span>
                </div>
            </div>
            <div class="norma-params">
                <div><b>Layer:</b> {a.get("layer", "-")}</div>
                <div><b>Method:</b> {a.get("method", "-")}</div>
                <div><b>Prompt:</b> {a.get("prompt_version", "-")}</div>
                <div><b>Paginas:</b> {a.get("n_pages", "-")}</div>
                <div><b>Bloques:</b> {a.get("n_blocks", "-")}</div>
                <div><b>Fecha:</b> {(a.get("created_at") or "-")[:10]}</div>
            </div>
            <div class="norma-metrics">
                <div class="metric-pill">
                    <span>Cobertura</span>
                    <strong>{m.get("coverage", 0):.3f}</strong>
                </div>
                <div class="metric-pill">
                    <span>Similitud texto</span>
                    <strong>{m.get("text_similarity", 0):.3f}</strong>
                </div>
                <div class="metric-pill">
                    <span>Preservacion keywords</span>
                    <strong>{m.get("keyword_preservation", 0):.3f}</strong>
                </div>
                <div class="metric-pill">
                    <span>Issues</span>
                    <strong>{m.get("issues_count", 0)}</strong>
                </div>
            </div>
            <div class="norma-missing">
                <b>Keywords faltantes:</b> {missing}
            </div>
        </div>""")
    if not cards:
        return '<div class="empty">No hay normas con MD asociado para inspeccionar.</div>'
    return "\n".join(cards)


def render_audit(audit: list) -> str:
    if not audit:
        return '<div class="empty">Sin eventos.</div>'
    entries = []
    for e in audit:
        detalle = (e["detalle"] or "")[:80]
        entries.append(f"""<div class="timeline-entry">
            <div class="time">{e["timestamp"]}</div>
            <span class="mod">{e["modulo"]}</span> · {e["accion"]} en {e["tabla"]}
            {f'<div class="detalle">{detalle}</div>' if detalle else ""}
        </div>""")
    return "\n".join(entries)


def render_entidades_table(m) -> str:
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
    normas = data.get("normas", [])

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
           background: #f5f7fa; color: #1f2937; line-height: 1.5; }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .header { background: linear-gradient(135deg, #1a4480 0%, #2d5e8e 100%);
              color: white; padding: 32px; border-radius: 12px; margin-bottom: 16px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .header h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
    .header .subtitle { opacity: 0.9; font-size: 14px; }
    .header .meta { display: flex; gap: 24px; flex-wrap: wrap; font-size: 13px; margin-top: 12px; }
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
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px; margin-bottom: 24px; }
    .card { background: white; border-radius: 10px; padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 4px solid #1a4480; }
    .card .label { font-size: 11px; color: #6b7280; text-transform: uppercase;
                   letter-spacing: 0.05em; font-weight: 600; margin-bottom: 8px; }
    .card .value { font-size: 32px; font-weight: 700; color: #111827; line-height: 1; }
    .section { background: white; border-radius: 0 0 10px 10px; padding: 24px;
               box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 16px; }
    .section h2 { font-size: 18px; color: #111827; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; }
    th { background: #f9fafb; font-weight: 600; color: #374151; font-size: 11px;
         text-transform: uppercase; letter-spacing: 0.04em; }
    tr:hover { background: #f9fafb; }
    /* Norma cards */
    .norma-card { background: white; border-radius: 10px; padding: 20px;
                  margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
                  border-left: 4px solid #1a4480; }
    .norma-card-header { display: flex; justify-content: space-between;
                          align-items: flex-start; margin-bottom: 12px; }
    .norma-id { font-family: monospace; font-size: 12px; color: #6b7280; }
    .norma-nombre { font-size: 15px; font-weight: 600; color: #111827;
                     margin-top: 2px; }
    .norma-score { color: white; padding: 12px 18px; border-radius: 8px;
                    text-align: center; font-size: 24px; font-weight: 700;
                    line-height: 1.1; min-width: 90px; }
    .norma-rating { font-size: 9px; font-weight: 600; text-transform: uppercase;
                     letter-spacing: 0.05em; opacity: 0.95; }
    .norma-params { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                     gap: 8px 16px; font-size: 12px; color: #4b5563; margin-bottom: 12px;
                     padding: 12px; background: #f9fafb; border-radius: 6px; }
    .norma-metrics { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .metric-pill { display: flex; flex-direction: column; align-items: center;
                    padding: 8px 12px; background: #f3f4f6; border-radius: 6px;
                    min-width: 80px; }
    .metric-pill span { font-size: 10px; color: #6b7280; text-transform: uppercase;
                        letter-spacing: 0.04em; }
    .metric-pill strong { font-size: 16px; color: #111827; margin-top: 2px; }
    .norma-missing { font-size: 12px; color: #4b5563;
                      padding: 8px 12px; background: #fef3c7; border-radius: 6px; }
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
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
             font-size: 11px; font-weight: 600; }
    .badge.green { background: #d1fae5; color: #065f46; }
    .badge.gray { background: #f3f4f6; color: #6b7280; }
    code { background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
    """

    # Tabs
    tabs_html = []
    for tab_id, tab_label in ETAPAS_TABS:
        active = " active" if tab_id == "resumen" else ""
        tabs_html.append(f'<div class="tab{active}" data-tab="{tab_id}">{tab_label}</div>')

    # Contenido de cada tab
    tab_resumen = f"""
    <div id="tab-resumen" class="tab-content active">
        <div class="grid">
            <div class="card"><div class="label">Normas procesadas</div><div class="value">{m['normas']}</div></div>
            <div class="card"><div class="label">Unidades normativas</div><div class="value">{m['unidades']}</div></div>
            <div class="card"><div class="label">Actores en directorio</div><div class="value">{m['actores']}</div></div>
            <div class="card"><div class="label">Aristas ARS</div><div class="value">{m['aristas']}</div></div>
            <div class="card"><div class="label">Fichas Anexo 10</div><div class="value">{m['fichas']}</div></div>
            <div class="card"><div class="label">Documentos ingestados</div><div class="value">{m['documentos']}</div></div>
        </div>
        <div class="section">
            <h2>Lista de normas y conversiones ({len(normas)})</h2>
            <p style="color:#6b7280;font-size:13px;margin-bottom:12px">
                Parametros de cada conversion PDF -> MD y metricas de calidad.
                Click en una norma para ver el detalle expandido.
            </p>
            <table>
                <thead>
                    <tr>
                        <th>id_norma</th><th>Nombre</th><th>Nivel</th><th>Jerarquia</th>
                        <th>Archivo</th><th>Prompt</th><th>Pags</th>
                        <th>Cov</th><th>Sim</th><th>Score</th><th>Rating</th>
                    </tr>
                </thead>
                <tbody>{render_norms_table(normas, db_path)}</tbody>
            </table>
        </div>
        <div class="section">
            <h2>Detalle de cada norma</h2>
            {render_norms_detail(normas, db_path)}
        </div>
        <div class="section">
            <h2>Entidades federativas evaluadas</h2>
            <table>
                <thead><tr><th>Clave</th><th>Estado</th><th>Estatus</th><th>Documentos</th></tr></thead>
                <tbody>{render_entidades_table(m)}</tbody>
            </table>
        </div>
        <div class="section">
            <h2>Timeline de eventos</h2>
            <div class="timeline">{render_audit(data['audit'])}</div>
        </div>
    </div>
    """

    # Tabs de etapa (más simples, muestran conteo de entidades por etapa)
    def tab_etapa(tab_key, title, descripcion):
        return f"""
        <div id="tab-{tab_key}" class="tab-content">
            <div class="section">
                <h2>{title}</h2>
                <p style="color:#6b7280">{descripcion}</p>
                <p style="color:#9ca3af;font-size:13px;margin-top:24px">
                    Para ver las normas/conversiones de esta etapa, ve al tab <b>Resumen</b>.
                </p>
            </div>
        </div>
        """

    tab_etapa_1 = tab_etapa("etapa_1", "Etapa 1: Analisis Documental",
                            f"{m['normas']} normas procesadas, {m['unidades']} unidades normativas extraidas, {m['actores']} actores en directorio.")
    tab_etapa_2 = tab_etapa("etapa_2", "Etapa 2: Campo + ARS",
                            f"{m['aristas']} aristas ARS registradas.")
    tab_etapa_3 = tab_etapa("etapa_3", "Etapa 3: Triangulacion",
                            f"{m['fichas']} fichas de hallazgos generadas.")

    # Tab Ayuda: documentacion operativa del proceso
    tab_ayuda = render_ayuda()

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
</div>

<div class="tabs">
    {''.join(tabs_html)}
</div>

{tab_resumen}
{tab_etapa_1}
{tab_etapa_2}
{tab_etapa_3}
{tab_ayuda}

<div class="footer">
    Generado por <code>fasp_dashboard.py</code> · Skill fasp-document-pipeline v1.1
</div>

</div>
{js}
</body>
</html>"""


def render_ayuda() -> str:
    """Renderiza el tab de Ayuda con la documentacion operativa del proceso."""
    return """
    <div id="tab-ayuda" class="tab-content">
        <div class="section">
            <h2>Como invocar el proceso desde el agente</h2>
            <p style="color:#6b7280">
                El skill opera como un pipeline de 3 etapas. Cada modulo LLM/PY
                se invoca con un comando CLI. El agente (Alfredo Dominguez Diaz)
                coordina el stack completo.
            </p>

            <h3 style="margin-top:24px">Convencion de nombres para prompts al agente</h3>
            <p>Cuando invoques un modulo LLM via el agente, usa el nombre exacto del sub-skill:</p>
            <table>
                <thead><tr><th>Comando del prompt</th><th>Modulo que dispara</th><th>Cuando invocarlo</th></tr></thead>
                <tbody>
                    <tr><td><code>"ejecuta LLM-1 sobre el MD"</code></td><td><code>llm-1-parser-juridico.py</code></td><td>Tras convertir PDF a MD (Etapa 1)</td></tr>
                    <tr><td><code>"ejecuta LLM-2 sobre la salida de LLM-1"</code></td><td><code>llm-2-matriz-congruencia</code> (prompt)</td><td>Tras LLM-1, para clasificar unidades</td></tr>
                    <tr><td><code>"ejecuta LLM-3 para el directorio de actores"</code></td><td><code>llm-3-directorio-actores</code> (prompt)</td><td>Tras LLM-1, paralelo a LLM-2</td></tr>
                    <tr><td><code>"ejecuta PY-1"</code></td><td><code>py-1-estructuracion.py</code></td><td>Cierre Etapa 1 (genera Anexo 1)</td></tr>
                    <tr><td><code>"ejecuta LLM-4 sobre las transcripciones"</code></td><td><code>llm-4-relaciones-campo</code> (prompt)</td><td>Etapa 2, inicio</td></tr>
                    <tr><td><code>"ejecuta LLM-5 para normalizar nodos"</code></td><td><code>llm-5-normalizador-nodos</code> (prompt)</td><td>Tras LLM-4</td></tr>
                    <tr><td><code>"ejecuta PY-2"</code></td><td><code>py-2-matrices-red.py</code></td><td>Tras LLM-5 (genera Anexos 4, matrices incidencia)</td></tr>
                    <tr><td><code>"ejecuta PY-3"</code></td><td><code>py-3-metricas-ars.py</code></td><td>Tras PY-2 (genera Anexos 5, 6 + memoria algoritmica)</td></tr>
                    <tr><td><code>"genera el sociograma"</code></td><td><code>py-3-sociograma.py</code></td><td>Tras PY-3</td></tr>
                    <tr><td><code>"ejecuta LLM-6 para redactar hallazgos ARS"</code></td><td><code>llm-6-redactor-ars</code> (prompt)</td><td>Tras PY-3 (Producto 2 narrativo)</td></tr>
                    <tr><td><code>"ejecuta LLM-7 para triangular"</code></td><td><code>llm-7-triangulador</code> (prompt)</td><td>Inicio Etapa 3</td></tr>
                    <tr><td><code>"ejecuta LLM-8 para fichas de hallazgos"</code></td><td><code>llm-8-fichas-hallazgos</code> (prompt)</td><td>Tras LLM-7</td></tr>
                    <tr><td><code>"ejecuta LLM-9 para el Informe Final"</code></td><td><code>llm-9-informe-final</code> (prompt)</td><td>Cierre Etapa 3</td></tr>
                    <tr><td><code>"ejecuta PY-4 para exportar"</code></td><td><code>py-4-exportacion.py</code></td><td>Tras LLM-9 (genera Anexo 8)</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Cuando cerrar una etapa y cuando continuar</h2>

            <h3 style="margin-top:20px">Regla de cierre por etapa</h3>
            <table>
                <thead><tr><th>Etapa</th><th>Se puede cerrar cuando...</th><th>Accion a tomar</th></tr></thead>
                <tbody>
                    <tr>
                        <td><b>Etapa 1 (Documental)</b></td>
                        <td>
                            (a) Todas las normas planeadas estan en la BD con sus unidades normativas.<br>
                            (b) El Anexo 1 (Ficha tecnica FASP) esta generado por PY-1.<br>
                            (c) <code>audit_log</code> tiene al menos 1 evento de LLM-1 y 1 de PY-1.
                        </td>
                        <td>
                            Ejecutar <code>checkpoint.py --etapa etapa_1_documental --perfil coordinadora --anexo "Anexo 1" --decision aprobado</code>
                        </td>
                    </tr>
                    <tr>
                        <td><b>Etapa 2 (Campo + ARS)</b></td>
                        <td>
                            (a) Las transcripciones de entrevistas estan ingestadas.<br>
                            (b) LLM-4 extrajo aristas y LLM-5 normalizo los nodos.<br>
                            (c) PY-2 genero la matriz de adyacencia.<br>
                            (d) PY-3 calculo las 8 metricas ARS y la memoria algoritmica.<br>
                            (e) LLM-6 redacto los borradores de hallazgos ARS.
                        </td>
                        <td>
                            Ejecutar <code>checkpoint.py --etapa etapa_2_campo_ars --perfil analista_senior_redes --anexo "Anexo 4" --decision aprobado</code>
                        </td>
                    </tr>
                    <tr>
                        <td><b>Etapa 3 (Triangulacion)</b></td>
                        <td>
                            (a) LLM-7 cruzo norma-red-campo.<br>
                            (b) LLM-8 genero las fichas de hallazgos.<br>
                            (c) LLM-9 redacto el Informe Final.<br>
                            (d) PY-4 exporto el paquete replicable (Anexo 8).
                        </td>
                        <td>
                            Ejecutar <code>checkpoint.py --etapa etapa_3_triangulacion --perfil coordinacion_evaluacion --anexo "Anexo 10" --decision aprobado</code>
                        </td>
                    </tr>
                </tbody>
            </table>

            <h3 style="margin-top:24px">Cuando NO continuar (bloqueos)</h3>
            <ul style="line-height:1.8">
                <li>LLM devuelve un valor fuera de la taxonomia cerrada (ej. <code>tipo_competencia: "Mixta"</code>) -> <b>NO continuar</b>, corregir el LLM o reintentar con prompt mas estricto.</li>
                <li>La cobertura del MD es &lt; 0.85 -> <b>NO continuar</b>, el PDF probablemente es escaneado y requiere OCR forzado.</li>
                <li>Un anexo no valida contra su schema JSON -> <b>NO continuar</b>, revisar la salida del LLM.</li>
                <li>El grafo ARS tiene &lt; 5 nodos -> <b>NO continuar</b>, el corpus es muy pequeno para metricas confiables.</li>
                <li>Hay un gate de control sin registrar para la etapa actual -> <b>NO cerrar la etapa</b>.</li>
            </ul>
        </div>

        <div class="section">
            <h2>Entradas, salidas y evidencias por etapa</h2>
            <p style="color:#6b7280">
                Cada modulo tiene un contrato claro de entradas, salidas y registros
                de evidencia que quedan en la BD para auditoria.
            </p>

            <h3 style="margin-top:20px">Etapa 1: Analisis Documental</h3>
            <table>
                <thead><tr><th>Modulo</th><th>Entradas</th><th>Salidas</th><th>Evidencia en BD</th></tr></thead>
                <tbody>
                    <tr>
                        <td><b>pdf-to-knowledge-graph</b> (reutilizado)</td>
                        <td>PDF del corpus normativo (ruta local)</td>
                        <td>
                            <code>&lt;job_id&gt;.md</code> en <code>jobs/&lt;job_id&gt;/</code><br>
                            <code>&lt;job_id&gt;.meta.json</code><br>
                            <code>&lt;job_id&gt;.layout.json</code><br>
                            <code>&lt;job_id&gt;.validation.json</code>
                        </td>
                        <td>Tabla <code>documentos</code> + <code>audit_log</code></td>
                    </tr>
                    <tr>
                        <td><b>LLM-1 Parser juridico</b></td>
                        <td>MD del PDF</td>
                        <td>
                            Filas en <code>normas</code> (1 por documento)<br>
                            Filas en <code>norma_unidades</code> (N por unidad detectada: articulo, fraccion)
                        </td>
                        <td><code>audit_log</code> con modulo='LLM-1'</td>
                    </tr>
                    <tr>
                        <td><b>LLM-2 Matriz de congruencia</b></td>
                        <td>Salida de LLM-1</td>
                        <td>Actualizacion de <code>norma_unidades</code> con tipo_competencia, nivel_obligatoriedad, dimension_ciclo</td>
                        <td><code>audit_log</code> con modulo='LLM-2'</td>
                    </tr>
                    <tr>
                        <td><b>LLM-3 Directorio de actores</b></td>
                        <td>Normas clasificadas</td>
                        <td>Filas en <code>actores</code> + <code>actor_etapas</code></td>
                        <td><code>audit_log</code> con modulo='LLM-3'</td>
                    </tr>
                    <tr>
                        <td><b>PY-1 Estructuracion</b></td>
                        <td>Salidas de LLM-1, LLM-2, LLM-3</td>
                        <td>
                            IDs unicos asignados (<code>id_actor</code>)<br>
                            <b>Anexo 1</b>: Ficha tecnica FASP (<code>FASP_2026_P1_&lt;EDO&gt;_INFORME_V1.0.md</code>)
                        </td>
                        <td><code>audit_log</code> con modulo='PY-1'</td>
                    </tr>
                </tbody>
            </table>

            <h3 style="margin-top:24px">Etapa 2: Campo + ARS</h3>
            <table>
                <thead><tr><th>Modulo</th><th>Entradas</th><th>Salidas</th><th>Evidencia en BD</th></tr></thead>
                <tbody>
                    <tr>
                        <td><b>LLM-4 Relaciones de campo</b></td>
                        <td>Transcripciones de entrevistas semiestructuradas</td>
                        <td>Filas en <code>aristas</code> (origen, destino, peso, tipo_vinculo, direccionalidad, frecuencia, canal, etapa_ciclo)</td>
                        <td><code>audit_log</code> con modulo='LLM-4'</td>
                    </tr>
                    <tr>
                        <td><b>LLM-5 Normalizador</b></td>
                        <td>Edge list preliminar + directorio de actores</td>
                        <td>Nodos unificados (alias colapsados, IDs consistentes)</td>
                        <td><code>audit_log</code> con modulo='LLM-5'</td>
                    </tr>
                    <tr>
                        <td><b>PY-2 Matrices de red</b></td>
                        <td>Edge list + diccionario de nodos</td>
                        <td>
                            <code>anexo4_matriz_adyacencia_aristas.csv</code><br>
                            <code>anexo4_matriz_adyacencia_cuadrada.csv</code><br>
                            <code>anexo4_matriz_incidencia_actor_etapa.csv</code>
                        </td>
                        <td><code>audit_log</code> con modulo='PY-2'</td>
                    </tr>
                    <tr>
                        <td><b>PY-3 Metricas ARS</b></td>
                        <td>Matrices de PY-2</td>
                        <td>
                            <code>anexo5_memoria_algoritmica.md</code><br>
                            <code>anexo6_diccionario_atributos.csv</code><br>
                            Persistencia en <code>metricas_ars</code>
                        </td>
                        <td><code>audit_log</code> con modulo='PY-3'</td>
                    </tr>
                    <tr>
                        <td><b>PY-3 Sociograma</b></td>
                        <td>BD con aristas y metricas</td>
                        <td>
                            <code>FASP_2026_&lt;PRODUCTO&gt;_&lt;EDO&gt;_INFORME_V1.0.html</code> (interactivo con vis.js)<br>
                            <code>FASP_2026_&lt;PRODUCTO&gt;_&lt;EDO&gt;_INFORME_V1.0.png</code> (estatico, si matplotlib)
                        </td>
                        <td>(archivo en disco, no BD)</td>
                    </tr>
                    <tr>
                        <td><b>LLM-6 Redactor ARS</b></td>
                        <td>Metricas + sociogramas</td>
                        <td>Borrador narrativo del Producto 2 (Informe de Hallazgos)</td>
                        <td><code>audit_log</code> con modulo='LLM-6'</td>
                    </tr>
                </tbody>
            </table>

            <h3 style="margin-top:24px">Etapa 3: Triangulacion</h3>
            <table>
                <thead><tr><th>Modulo</th><th>Entradas</th><th>Salidas</th><th>Evidencia en BD</th></tr></thead>
                <tbody>
                    <tr>
                        <td><b>LLM-7 Triangulador</b></td>
                        <td>Matriz Producto 1 + ARS Producto 2 + resumentes entrevistas</td>
                        <td>Coincidencias/divergencias norma-red-campo + diagnostico de riesgos</td>
                        <td>(archivo o BD externa)</td>
                    </tr>
                    <tr>
                        <td><b>LLM-8 Fichas hallazgos</b></td>
                        <td>Listado priorizado de problemas</td>
                        <td>Filas en tabla <code>fichas</code> (estructura: verbo + producto + oportunidad + justificacion + efecto)</td>
                        <td><code>audit_log</code> con modulo='LLM-8'</td>
                    </tr>
                    <tr>
                        <td><b>LLM-9 Informe Final</b></td>
                        <td>Diagnosticos + ARS + fichas validadas</td>
                        <td>
                            Informe Final narrativo (Producto 3)<br>
                            <b>Anexo 7</b>: Glosario especializado<br>
                            <b>Anexo 8</b>: Metodologia de replicabilidad (texto)
                        </td>
                        <td><code>audit_log</code> con modulo='LLM-9'</td>
                    </tr>
                    <tr>
                        <td><b>PY-4 Exportacion</b></td>
                        <td>Toda la BD</td>
                        <td>
                            <code>tabla_&lt;nombre&gt;.csv</code> por cada tabla<br>
                            <b>Anexo 8</b>: <code>anexo8_metodologia_replicabilidad.md</code><br>
                            Paquete replicable completo
                        </td>
                        <td><code>audit_log</code> con modulo='PY-4'</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Como se cierra una etapa (paso a paso)</h2>
            <ol style="line-height:1.8">
                <li>
                    <b>Verifica que todos los modulos de la etapa estan ejecutados.</b><br>
                    Revisa el tab <i>Resumen</i> de este dashboard: las normas/conversiones
                    deben tener score y rating. Si hay normas con "Sin MD", faltan conversiones.
                </li>
                <li>
                    <b>Verifica que los gates de control de la etapa estan registrados.</b><br>
                    Aunque el sistema actual no exige validacion de identidad, registra
                    los gates para mantener trazabilidad:
                    <pre style="background:#f3f4f6;padding:12px;border-radius:6px;margin:8px 0;font-size:12px"><code>python3 scripts/checkpoint.py --db ./fasp.db \\
    --etapa etapa_1_documental \\
    --perfil coordinadora \\
    --anexo "Anexo 1" \\
    --decision aprobado \\
    --aprobador "Alfredo Dominguez Diaz"</code></pre>
                </li>
                <li>
                    <b>Regenera este dashboard</b> con <code>python3 scripts/fasp_dashboard.py --db ./fasp.db --output ./dashboard.html</code>
                    para confirmar visualmente que la etapa aparece cerrada.
                </li>
                <li>
                    <b>Exporta el paquete replicable</b> con PY-4 al cierre de Etapa 3:
                    <pre style="background:#f3f4f6;padding:12px;border-radius:6px;margin:8px 0;font-size:12px"><code>python3 scripts/py-4-exportacion.py --db ./fasp.db --output ./export/</code></pre>
                </li>
            </ol>
        </div>

        <div class="section">
            <h2>Donde se ve la trazabilidad completa</h2>
            <table>
                <thead><tr><th>Que ver</th><th>Donde</th></tr></thead>
                <tbody>
                    <tr><td>Avance por etapa (cuantas normas, unidades, etc.)</td><td>Tab <b>Resumen</b> de este dashboard</td></tr>
                    <tr><td>Lista de normas con score de conversion</td><td>Tab <b>Resumen</b> -> seccion "Lista de normas y conversiones"</td></tr>
                    <tr><td>Detalle por norma (parametros, metricas, keywords faltantes)</td><td>Tab <b>Resumen</b> -> seccion "Detalle de cada norma"</td></tr>
                    <tr><td>Timeline de operaciones (cada insert/update)</td><td>Tab <b>Resumen</b> -> seccion inferior</td></tr>
                    <tr><td>Auditoria offline</td><td>SQLite directamente: <code>SELECT * FROM audit_log ORDER BY id DESC</code></td></tr>
                    <tr><td>Reporte en JSON</td><td><code>python3 scripts/norms_list.py --jobs-dir ./jobs/ --output-json ./audit.json</code></td></tr>
                    <tr><td>Auditoria de calidad por conversion</td><td><code>python3 scripts/audit_conversions.py --jobs-dir ./jobs/</code></td></tr>
                </tbody>
            </table>
        </div>
    </div>
    """
    p = argparse.ArgumentParser(description="Dashboard HTML del pipeline FASP")
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
        print(f"  Lista de normas: {len(data['normas'])}")

    print(f"OK Dashboard escrito en {output}")
    print(f"  Para abrirlo: open {output}")


def main():
    p = argparse.ArgumentParser(description="Dashboard HTML del pipeline FASP")
    p.add_argument("--db", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--watch", type=int, default=0, metavar="N",
                   help="Si se especifica, regenera el dashboard cada N segundos "
                        "cuando la BD cambia. Usar con --output fijo.")
    args = p.parse_args()

    db_path = pathlib.Path(args.db)
    output = pathlib.Path(args.output)

    if args.watch > 0:
        watch_mode(db_path, output, args.watch)
    else:
        generate_once(db_path, output)


def generate_once(db_path: pathlib.Path, output: pathlib.Path):
    """Genera el dashboard una vez."""
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
        print(f"  Lista de normas: {len(data['normas'])}")

    print(f"OK Dashboard escrito en {output}")


def watch_mode(db_path: pathlib.Path, output: pathlib.Path, interval: int):
    """Regenera el dashboard cada N segundos cuando la BD cambia.

    Detecta cambios comparando el mtime del archivo .db.
    Útil cuando un agente ejecuta módulos en otro proceso.
    """
    print(f"Modo watch: regenerando cada {interval}s si la BD cambia")
    print(f"  BD:    {db_path}")
    print(f"  HTML:  {output}")
    print(f"  Ctrl-C para salir.\n")

    last_mtime = None
    last_size = None

    while True:
        try:
            if db_path.exists():
                stat = db_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size
                if mtime != last_mtime or size != last_size:
                    generate_once(db_path, output)
                    last_mtime = mtime
                    last_size = size
                    print(f"  [watch] Regenerado a las {datetime.now().strftime('%H:%M:%S')}\n")
                else:
                    print(f"  [watch] Sin cambios ({datetime.now().strftime('%H:%M:%S')})")
            else:
                print(f"  [watch] BD no encontrada: {db_path}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[watch] Detenido por el usuario.")
            break
        except Exception as e:
            print(f"  [watch] Error: {e}")
            time.sleep(interval)


if __name__ == "__main__":
    main()