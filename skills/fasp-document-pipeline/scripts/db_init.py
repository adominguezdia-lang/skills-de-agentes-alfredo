#!/usr/bin/env python3
"""
db_init.py — Inicializa la BD SQLite del skill FASP con el esquema para los
12 anexos, las taxonomías cerradas, y los checkpoints humanos.

Uso:
    python3 db_init.py --db ./fasp.db [--reset]

Esquema (tablas principales):
    documentos          — PDFs/transcripciones ingestados
    normas              — normas segmentadas por artículo/fracción
    actores             — directorio preliminar (Anexo 3)
    matriz_congruencia  — filas de la matriz (Anexo 2)
    aristas             — edge list con tipo de vínculo (Anexo 4)
    metricas_ars        — métricas por nodo (Anexo 6)
    fichas              — hallazgos y recomendaciones (Anexo 10)
    checkpoints         — aprobaciones por perfil y etapa
    audit_log           — trazabilidad de cambios
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"

SCHEMA_SQL = """
-- ============================================================
-- Documentos ingestados (entrada del pipeline)
-- ============================================================
CREATE TABLE IF NOT EXISTS documentos (
    id              TEXT PRIMARY KEY,
    nombre_archivo  TEXT NOT NULL,
    tipo_documento  TEXT NOT NULL,  -- FK conceptual a taxonomias.tipos_documento_entrada
    nivel_gobierno  TEXT,           -- Federal | Estatal | Municipal
    fuente_url      TEXT,
    fecha_ingesta   TEXT NOT NULL,
    md_path         TEXT,
    estado          TEXT NOT NULL DEFAULT 'ingesta',  -- ingesta|extraccion|clasificacion|checkpoint_pendiente|aprobado|rechazado|publicado
    job_id_pdfkg    TEXT,           -- job_id del skill pdf-to-knowledge-graph si se usó
    meta_json       TEXT
);

-- ============================================================
-- Normas segmentadas (salida de LLM-1)
-- ============================================================
CREATE TABLE IF NOT EXISTS normas (
    id_norma            TEXT PRIMARY KEY,
    id_documento        TEXT NOT NULL,
    nombre_norma        TEXT NOT NULL,
    nivel               TEXT NOT NULL CHECK (nivel IN ('Federal','Estatal','Municipal')),
    jerarquia           TEXT,        -- Constitución|Ley|Reglamento|NOM|Otro
    vigencia            TEXT,        -- texto libre (ej. "Vigente desde 2009")
    fecha_publicacion   TEXT,
    fuente              TEXT,
    FOREIGN KEY (id_documento) REFERENCES documentos(id)
);

CREATE TABLE IF NOT EXISTS norma_unidades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_norma            TEXT NOT NULL,
    articulo            TEXT NOT NULL,
    fraccion            TEXT,
    inciso              TEXT,
    texto               TEXT NOT NULL,
    tema                TEXT,
    etapa_ciclo_fasp    TEXT NOT NULL CHECK (etapa_ciclo_fasp IN ('Integración','Distribución','Administración','Supervisión','Seguimiento')),
    dimension_ciclo     TEXT NOT NULL CHECK (dimension_ciclo IN ('Planeación','Asignación','Ejecución','Seguimiento','Rendición de cuentas')),
    tipo_competencia    TEXT NOT NULL CHECK (tipo_competencia IN ('Exclusiva','Concurrente','Complementaria')),
    nivel_obligatoriedad TEXT NOT NULL CHECK (nivel_obligatoriedad IN ('Mandatoria','Facultativa','Recomendatoria')),
    referencia_coordinacion TEXT,
    FOREIGN KEY (id_norma) REFERENCES normas(id_norma)
);

-- ============================================================
-- Actores / directorio (Anexo 3, salida de LLM-3)
-- ============================================================
CREATE TABLE IF NOT EXISTS actores (
    id_actor             TEXT PRIMARY KEY,
    nombre_oficial       TEXT NOT NULL,
    nivel_gobierno       TEXT NOT NULL CHECK (nivel_gobierno IN ('Federal','Estatal','Municipal')),
    entidad_federativa   TEXT,
    naturaleza           TEXT NOT NULL CHECK (naturaleza IN ('Formal','Informal')),
    funciones_json       TEXT NOT NULL,    -- JSON array de strings
    mapeado_a_id_norma   TEXT,            -- JSON array de id_norma
    alias_conocidos      TEXT,            -- JSON array de strings (siglas, nombres cortos)
    fuente_documento     TEXT,            -- id_documento del que se extrajo
    FOREIGN KEY (fuente_documento) REFERENCES documentos(id)
);

CREATE TABLE IF NOT EXISTS actor_etapas (
    id_actor    TEXT NOT NULL,
    etapa_ciclo TEXT NOT NULL CHECK (etapa_ciclo IN ('Integración','Distribución','Administración','Supervisión','Seguimiento')),
    PRIMARY KEY (id_actor, etapa_ciclo),
    FOREIGN KEY (id_actor) REFERENCES actores(id_actor)
);

-- ============================================================
-- Aristas / relaciones ARS (Anexo 4, salida de LLM-4)
-- ============================================================
CREATE TABLE IF NOT EXISTS aristas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    origen          TEXT NOT NULL,
    destino         TEXT NOT NULL,
    peso            REAL NOT NULL CHECK (peso BETWEEN 0 AND 10),
    tipo_vinculo    TEXT NOT NULL CHECK (tipo_vinculo IN ('Formal','Informal','Jerárquico','Operativo','Consultivo')),
    direccionalidad TEXT NOT NULL CHECK (direccionalidad IN ('unidireccional','bidireccional')),
    frecuencia      TEXT NOT NULL CHECK (frecuencia IN ('diaria','semanal','mensual','trimestral','ocasional')),
    canal           TEXT NOT NULL CHECK (canal IN ('oficial','informal','electrónico','presencial','mixto')),
    etapa_ciclo     TEXT NOT NULL CHECK (etapa_ciclo IN ('Integración','Distribución','Administración','Supervisión','Seguimiento')),
    evidencia_doc_id TEXT,
    fuente_doc_id   TEXT,
    FOREIGN KEY (origen) REFERENCES actores(id_actor),
    FOREIGN KEY (destino) REFERENCES actores(id_actor),
    FOREIGN KEY (evidencia_doc_id) REFERENCES documentos(id),
    FOREIGN KEY (fuente_doc_id) REFERENCES documentos(id)
);

-- ============================================================
-- Métricas ARS por nodo (Anexo 6, salida de PY-3)
-- ============================================================
CREATE TABLE IF NOT EXISTS metricas_ars (
    id_actor              TEXT PRIMARY KEY,
    in_degree             REAL,
    out_degree            REAL,
    degree_centrality     REAL,
    betweenness           REAL,
    closeness             REAL,
    comunidad_id          INTEGER,
    FOREIGN KEY (id_actor) REFERENCES actores(id_actor)
);

-- ============================================================
-- Fichas de hallazgos y recomendaciones (Anexo 10, salida de LLM-8)
-- ============================================================
CREATE TABLE IF NOT EXISTS fichas (
    id_ficha              TEXT PRIMARY KEY,
    categoria_tematica    TEXT NOT NULL CHECK (categoria_tematica IN ('Normativo','Organizacional','Capacidades','Canales de comunicación')),
    verbo                 TEXT NOT NULL,
    producto_proceso      TEXT NOT NULL,
    area_oportunidad      TEXT NOT NULL,
    justificacion         TEXT NOT NULL,
    efecto_esperado       TEXT NOT NULL,
    viabilidad_claridad   INTEGER NOT NULL CHECK (viabilidad_claridad BETWEEN 1 AND 5),
    viabilidad_relevancia INTEGER NOT NULL CHECK (viabilidad_relevancia BETWEEN 1 AND 5),
    viabilidad_justificacion INTEGER NOT NULL CHECK (viabilidad_justificacion BETWEEN 1 AND 5),
    viabilidad_factibilidad  INTEGER NOT NULL CHECK (viabilidad_factibilidad BETWEEN 1 AND 5),
    prioridad             TEXT NOT NULL CHECK (prioridad IN ('Alta','Media','Baja')),
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Checkpoints humanos (5 perfiles × 3 etapas = 15 gates)
-- ============================================================
CREATE TABLE IF NOT EXISTS checkpoints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    etapa           TEXT NOT NULL CHECK (etapa IN ('etapa_1_documental','etapa_2_campo_ars','etapa_3_triangulacion')),
    perfil          TEXT NOT NULL CHECK (perfil IN ('coordinadora','analista_senior_juridico','analista_senior_redes','analistas_junior_grafos','coordinacion_evaluacion')),
    anexo           TEXT NOT NULL,  -- ej. 'Anexo 2'
    doc_id          TEXT,
    decision        TEXT NOT NULL CHECK (decision IN ('aprobado','rechazado','pendiente')),
    comentario      TEXT,
    aprobador       TEXT,
    fecha           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Audit log (trazabilidad)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    modulo      TEXT NOT NULL,  -- LLM-1, PY-2, checkpoint, etc.
    accion      TEXT NOT NULL,  -- 'insert', 'update', 'approve', etc.
    tabla       TEXT,
    row_id      TEXT,
    detalle     TEXT
);

-- ============================================================
-- Índices para queries frecuentes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_norma_unidades_etapa ON norma_unidades(etapa_ciclo_fasp);
CREATE INDEX IF NOT EXISTS idx_norma_unidades_tipo ON norma_unidades(tipo_competencia);
CREATE INDEX IF NOT EXISTS idx_aristas_origen ON aristas(origen);
CREATE INDEX IF NOT EXISTS idx_aristas_destino ON aristas(destino);
CREATE INDEX IF NOT EXISTS idx_aristas_tipo ON aristas(tipo_vinculo);
CREATE INDEX IF NOT EXISTS idx_checkpoints_etapa ON checkpoints(etapa);
CREATE INDEX IF NOT EXISTS idx_checkpoints_perfil ON checkpoints(perfil);
"""


def init_db(db_path: pathlib.Path, reset: bool = False) -> dict:
    """Inicializa la BD y devuelve estadísticas."""
    if reset and db_path.exists():
        db_path.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    # Verificar tablas creadas
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]

    # Metadata de versión
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("INSERT OR REPLACE INTO _meta VALUES (?, ?)", ("schema_version", SCHEMA_VERSION))
    conn.execute("INSERT OR REPLACE INTO _meta VALUES (?, ?)", ("created_at", datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    return {
        "db_path": str(db_path.absolute()),
        "schema_version": SCHEMA_VERSION,
        "tables_created": len(tables),
        "tables": tables,
    }


def main():
    p = argparse.ArgumentParser(description="Inicializa la BD SQLite del skill FASP")
    p.add_argument("--db", required=True, help="Ruta al archivo .db")
    p.add_argument("--reset", action="store_true", help="Borra y recrea la BD")
    args = p.parse_args()

    db_path = pathlib.Path(args.db)
    stats = init_db(db_path, reset=args.reset)

    print(f"✓ BD inicializada: {stats['db_path']}")
    print(f"  Schema version: {stats['schema_version']}")
    print(f"  Tablas ({stats['tables_created']}): {', '.join(stats['tables'])}")


if __name__ == "__main__":
    main()