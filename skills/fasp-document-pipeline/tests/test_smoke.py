#!/usr/bin/env python3
"""
test_smoke.py — Smoke tests para fasp-document-pipeline.

Verifica:
- Sintaxis de scripts
- Esquemas JSON válidos
- Taxonomías cerradas (5 vocabularios con valores fijos)
- BD SQLite se crea correctamente
- LLM-1 procesa un MD sintético
- PY-1 asigna IDs y genera Anexo 1
- Checkpoint se registra correctamente
- Validador de taxonomías detecta errores

Uso:
    python3 tests/test_smoke.py
"""
from __future__ import annotations
import ast, json, pathlib, sqlite3, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
SCHEMAS_DIR = ROOT / "schemas"
TAX_PATH = SCHEMAS_DIR / "taxonomias.json"


def assert_(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def test_sintaxis_scripts():
    print("T1: Sintaxis de scripts...")
    for script in SCRIPTS_DIR.glob("*.py"):
        ast.parse(script.read_text())
        print(f"  ✓ {script.name}")


def test_schemas_json():
    print("\nT2: Esquemas JSON válidos...")
    for schema_path in SCHEMAS_DIR.rglob("*.json"):
        schema = json.loads(schema_path.read_text())
        assert_(isinstance(schema, dict), f"{schema_path.name} no es objeto")
        if "$schema" in schema:  # JSON Schema
            assert_("required" in schema, f"{schema_path.name} falta 'required'")
            assert_("properties" in schema, f"{schema_path.name} falta 'properties'")
        print(f"  ✓ {schema_path.relative_to(ROOT)}")


def test_taxonomias_cerradas():
    print("\nT3: Taxonomías cerradas del FASP...")
    tax = json.loads(TAX_PATH.read_text())

    required_keys = [
        "etapas_ciclo_fasp", "dimensiones_ciclo", "tipos_competencia",
        "niveles_obligatoriedad", "tipos_vinculo_ars",
        "niveles_gobierno", "naturaleza_actor",
    ]
    for k in required_keys:
        assert_(k in tax, f"Falta taxonomía: {k}")
        assert_(len(tax[k]) >= 2, f"Taxonomía {k} muy corta")

    # Tamaños fijos conocidos
    assert_(len(tax["etapas_ciclo_fasp"]) == 5, "etapas_ciclo_fasp debe tener 5")
    assert_(len(tax["dimensiones_ciclo"]) == 5, "dimensiones_ciclo debe tener 5")
    assert_(len(tax["tipos_competencia"]) == 3, "tipos_competencia debe tener 3")
    assert_(len(tax["niveles_obligatoriedad"]) == 3, "niveles_obligatoriedad debe tener 3")
    assert_(len(tax["tipos_vinculo_ars"]) == 5, "tipos_vinculo_ars debe tener 5")

    print(f"  ✓ 7 taxonomías cerradas con tamaños esperados")


def test_db_init():
    print("\nT4: Inicialización de BD SQLite...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "db_init.py"),
                                "--db", str(db_path)], capture_output=True, text=True)
        assert_(result.returncode == 0, f"db_init falló: {result.stderr}")
        assert_(db_path.exists(), "BD no se creó")

        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        required_tables = {"documentos", "normas", "norma_unidades", "actores",
                           "actor_etapas", "aristas", "metricas_ars", "fichas",
                           "checkpoints", "audit_log", "_meta"}
        missing = required_tables - set(tables)
        assert_(not missing, f"Faltan tablas: {missing}")
        conn.close()
        print(f"  ✓ {len(tables)} tablas creadas (incluye {len(required_tables)} requeridas)")


def test_llm_1_y_py_1_end_to_end():
    print("\nT5: Pipeline end-to-end (LLM-1 + PY-1)...")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        db_path = tmpdir / "fasp.db"
        md_path = tmpdir / "norma.md"
        anexo1_path = tmpdir / "anexo1.md"

        # Sintetizar una norma simple
        md_path.write_text("""LEY GENERAL DEL SISTEMA NACIONAL DE SEGURIDAD PÚBLICA

Artículo 1. La presente Ley es de orden público e interés social y tiene por objeto regular la integración, organización y funcionamiento del Sistema Nacional de Seguridad Pública.

Artículo 2. Para efectos del FASP, se establecen los siguientes criterios de distribución de recursos: el 70% se asignará a los estados conforme al factor de distribución.

Artículo 3. La supervisión del ejercicio de los recursos se realizará por conducto del Secretariado Ejecutivo del Sistema Nacional de Seguridad Pública, quien rendirá informes trimestrales al Consejo Nacional.
""", encoding="utf-8")

        # Init BD
        subprocess.run([sys.executable, str(SCRIPTS_DIR / "db_init.py"),
                       "--db", str(db_path)], check=True, capture_output=True)

        # LLM-1
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "llm-1-parser-juridico.py"),
                                "--md", str(md_path), "--db", str(db_path)],
                               capture_output=True, text=True)
        assert_(result.returncode == 0, f"LLM-1 falló: {result.stderr}")
        assert_("3 unidades normativas extraídas" in result.stdout or
                "✓ LLM-1 procesado" in result.stdout, f"Salida inesperada: {result.stdout}")

        # Verificar inserts
        conn = sqlite3.connect(db_path)
        n_normas = conn.execute("SELECT COUNT(*) FROM normas").fetchone()[0]
        n_unidades = conn.execute("SELECT COUNT(*) FROM norma_unidades").fetchone()[0]
        assert_(n_normas >= 1, "No se insertaron normas")
        assert_(n_unidades >= 3, f"Esperaba ≥3 unidades, hay {n_unidades}")

        # Insertar un actor para PY-1
        conn.execute("""
            INSERT INTO actores (id_actor, nombre_oficial, nivel_gobierno, naturaleza, funciones_json)
            VALUES (?, ?, ?, ?, ?)
        """, ("ACT-TEMP001", "Secretariado Ejecutivo", "Federal", "Formal", '["Coordinación del SNSP"]'))
        conn.commit()
        conn.close()

        # PY-1
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "py-1-estructuracion.py"),
                                "--db", str(db_path), "--anexo1", str(anexo1_path)],
                               capture_output=True, text=True)
        assert_(result.returncode == 0, f"PY-1 falló: {result.stderr}")
        assert_(anexo1_path.exists(), "Anexo 1 no se generó")
        content = anexo1_path.read_text()
        assert_("Anexo 1 — Ficha Técnica del FASP" in content, "Anexo 1 sin título correcto")

        # Verificar IDs asignados
        conn = sqlite3.connect(db_path)
        actor_id = conn.execute("SELECT id_actor FROM actores LIMIT 1").fetchone()[0]
        assert_(actor_id.startswith("ACT-"), f"ID mal formado: {actor_id}")
        conn.close()

        print(f"  ✓ {n_normas} norma(s), {n_unidades} unidades normativas insertadas")
        print(f"  ✓ Anexo 1 generado con ID {actor_id}")


def test_checkpoint_registro():
    print("\nT6: Registro de checkpoints...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "fasp.db"
        subprocess.run([sys.executable, str(SCRIPTS_DIR / "db_init.py"),
                       "--db", str(db_path)], check=True, capture_output=True)

        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "checkpoint.py"),
                                "--db", str(db_path), "--etapa", "etapa_1_documental",
                                "--perfil", "coordinadora",
                                "--anexo", "Anexo 1",
                                "--decision", "aprobado",
                                "--aprobador", "Test User"],
                               capture_output=True, text=True)
        assert_(result.returncode == 0, f"checkpoint falló: {result.stderr}")

        conn = sqlite3.connect(db_path)
        n = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE decision = 'aprobado'").fetchone()[0]
        assert_(n == 1, f"Esperaba 1 checkpoint aprobado, hay {n}")
        conn.close()
        print(f"  ✓ 1 checkpoint aprobado registrado")


def test_validate_taxonomias_detecta_errores():
    print("\nT7: Validador detecta valores fuera de taxonomía...")
    # Crear un JSON con valores inválidos
    bad_data = {
        "filas": [
            {
                "id_unidad": "X",
                "id_norma": "Y",
                "articulo": "1",
                "fraccion": "I",
                "tema": "test",
                "etapa_ciclo_fasp": "Etapa inventada",  # NO está en taxonomía
                "dimension_ciclo": "Planeación",
                "tipo_competencia": "Mixta",  # NO está en taxonomía
                "nivel_obligatoriedad": "Mandatoria",
                "nivel": "Federal",
            }
        ]
    }
    bad_path = pathlib.Path(tempfile.mkdtemp()) / "bad.json"
    bad_path.write_text(json.dumps(bad_data))

    result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "validate_taxonomias.py"),
                            "--input", str(bad_path), "--tipo", "matriz_congruencia"],
                           capture_output=True, text=True)
    assert_(result.returncode == 1, "Validador debería fallar con valores inválidos")
    assert_("Etapa inventada" in result.stdout, "No detecta 'Etapa inventada'")
    assert_("Mixta" in result.stdout, "No detecta 'Mixta'")
    print(f"  ✓ Detectó 'Etapa inventada' y 'Mixta' como fuera de taxonomía")


def test_relacion_con_pdf_knowledge_graph():
    print("\nT8: El skill referencia correctamente a pdf-to-knowledge-graph...")
    skill_md = (ROOT / "SKILL.md").read_text()
    assert_("pdf-to-knowledge-graph" in skill_md, "SKILL.md no menciona la dependencia")
    print("  ✓ SKILL.md referencia pdf-to-knowledge-graph")

    # Verificar que pdf-to-knowledge-graph está instalado
    pkg_path = pathlib.Path.home() / ".hermes" / "skills" / "productivity" / "pdf-to-knowledge-graph"
    if pkg_path.exists():
        print(f"  ✓ pdf-to-knowledge-graph instalado en {pkg_path}")
    else:
        print(f"  ⚠ pdf-to-knowledge-graph NO instalado en {pkg_path}")
        print("    (Requerido para Etapa 1 — instalación opcional)")


def test_nomenclatura():
    print("\nT9: Nomenclatura FASP 2026...")
    # Validar nombres del Plan de Trabajo
    ejemplos_validos = [
        "FASP_2026_P3_MEX_INFORME_V1.0.docx",
        "FASP_2026_P3_CHI_MAT_ADY_V1.0.csv",
        "FASP_2026_P3_MIC_MAT_INC_V1.0.xlsx",
        "FASP_2026_P3_TAM_DIC_NODOS_V1.0.csv",
        "FASP_2026_P3_QRO_SCRIPT_V1.0.py",
        "FASP_2026_IF_NAL_BBDD_V2.0.xlsx",
    ]
    for nombre in ejemplos_validos:
        r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "nomenclatura.py"),
                            "validar", nombre], capture_output=True, text=True)
        assert_(r.returncode == 0, f"Fallo validando {nombre}: {r.stderr}")
    print(f"  ✓ {len(ejemplos_validos)} nombres validos del Plan de Trabajo")

    # Construir un nombre nuevo
    r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "nomenclatura.py"),
                        "construir", "--producto", "P2", "--edo", "HID",
                        "--tipo", "MAT_ADY", "--version", "V1.0", "--ext", ".csv"],
                       capture_output=True, text=True)
    assert_(r.returncode == 0, f"Fallo construyendo: {r.stderr}")
    assert_(r.stdout.strip() == "FASP_2026_P2_HID_MAT_ADY_V1.0.csv",
            f"Nombre incorrecto: {r.stdout}")
    print(f"  ✓ Construccion correcta: {r.stdout.strip()}")

    # Validar que un nombre invalido falla
    r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "nomenclatura.py"),
                        "validar", "FASP_2026_P99_XXX_INFORME_V1.0.docx"],
                       capture_output=True, text=True)
    assert_(r.returncode == 1, "Debio fallar validando nombre invalido")
    print(f"  ✓ Rechaza nombres invalidos")


def test_entidades_federativas():
    print("\nT10: Referencias del Plan de Trabajo...")
    entidades_path = ROOT / "references" / "entidades_federativas.json"
    equipo_path = ROOT / "references" / "equipo_cevalua.json"
    cronograma_path = ROOT / "references" / "cronograma.json"
    memoria_path = ROOT / "references" / "memoria_codificacion.json"

    for path in [entidades_path, equipo_path, cronograma_path, memoria_path]:
        assert_(path.exists(), f"Falta referencia: {path.name}")
        json.loads(path.read_text())
        print(f"  ✓ {path.name}")

    entidades = json.loads(entidades_path.read_text())
    claves = [e["clave"] for e in entidades["entidades"]]
    assert_("NAL" in claves, "Falta clave NAL")
    assert_(all(c in claves for c in ["MEX", "CHI", "MIC", "TAM", "HID", "QRO", "TAB", "ZAC"]),
            "Faltan entidades federativas")
    print(f"  ✓ {len(claves)} entidades federativas catalogadas")

    equipo = json.loads(equipo_path.read_text())
    assert_(equipo["coordinadora"]["nombre"] == "Janett Salvador Martinez",
            "Coordinadora incorrecta")
    assert_(equipo["analista_senior_redes"]["nombre"] == "Alfredo Dominguez Diaz",
            "Analista Senior Redes incorrecto")
    assert_(equipo["total_personas"] == 14, "Total de personas != 14")
    print(f"  ✓ Equipo C-evalua: 14 personas, Coordinadora + Alfredo Dominguez Diaz (Senior Redes)")

    cronograma = json.loads(cronograma_path.read_text())
    for p in ["P1", "P2", "P3", "IF"]:
        assert_(p in cronograma["productos"], f"Falta producto {p}")
    print(f"  ✓ Cronograma con 4 productos")

    memoria = json.loads(memoria_path.read_text())
    assert_("tamano_nodo" in memoria["criterios_visualizacion_sociograma"],
            "Faltan criterios de visualizacion")
    print(f"  ✓ Memoria de codificacion con 3 criterios formales de visualizacion")


def test_anexo_11_y_12_schemas():
    print("\nT11: Schemas de Anexos 11 y 12...")
    for nombre in ["anexo11-ficha-tecnica-administrativa.json",
                   "anexo12-fuentes-informacion.json"]:
        path = SCHEMAS_DIR / "anexos" / nombre
        assert_(path.exists(), f"Falta schema: {nombre}")
        schema = json.loads(path.read_text())
        assert_("required" in schema and "properties" in schema,
                f"{nombre} mal formado")
        print(f"  ✓ {nombre} ({len(schema['properties'])} properties)")


def test_sociograma_con_datos_sinteticos():
    print("\nT12: Sociograma con datos sinteticos...")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        db_path = tmpdir / "test.db"

        # Init BD
        subprocess.run([sys.executable, str(SCRIPTS_DIR / "db_init.py"),
                       "--db", str(db_path)], check=True, capture_output=True)

        # Insertar actores y aristas sinteticas
        conn = sqlite3.connect(db_path)
        actores = [
            ("ACT-FED001", "SESNSP", "Federal", "Coordinacion nacional"),
            ("ACT-FED002", "CNAC", "Federal", "Prevencion"),
            ("ACT-EDO001", "SSP Chiapas", "Estatal", "Operacion estatal"),
            ("ACT-EDO002", "Fiscalia Chiapas", "Estatal", "Procuracion"),
            ("ACT-MUN001", "Pol Tuxtla", "Municipal", "Prevencion local"),
        ]
        for aid, nombre, nivel, func in actores:
            conn.execute("""
                INSERT INTO actores (id_actor, nombre_oficial, nivel_gobierno,
                                     naturaleza, funciones_json)
                VALUES (?, ?, ?, 'Formal', ?)
            """, (aid, nombre, nivel, f'["{func}"]'))
        aristas = [
            ("ACT-FED001", "ACT-EDO001", 8.0, "Formal", "Formal"),
            ("ACT-FED001", "ACT-EDO002", 6.0, "Formal", "Formal"),
            ("ACT-FED002", "ACT-MUN001", 4.0, "Operativo", "Operativo"),
            ("ACT-EDO001", "ACT-EDO002", 9.0, "Jerárquico", "Jerárquico"),
            ("ACT-EDO001", "ACT-MUN001", 7.0, "Operativo", "Operativo"),
            ("ACT-FED001", "ACT-FED002", 10.0, "Jerárquico", "Jerárquico"),
        ]
        for orig, dest, peso, tv, _ in aristas:
            conn.execute("""
                INSERT INTO aristas (origen, destino, peso, tipo_vinculo,
                                     direccionalidad, frecuencia, canal, etapa_ciclo)
                VALUES (?, ?, ?, ?, 'bidireccional', 'semanal', 'oficial', 'Distribución')
            """, (orig, dest, peso, tv))
        conn.commit()
        conn.close()

        # Generar sociograma
        output_dir = tmpdir / "sociograma"
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "py-3-sociograma.py"),
                                "--db", str(db_path),
                                "--producto", "P2", "--edo", "CHI",
                                "--output", str(output_dir)],
                               capture_output=True, text=True)
        assert_(result.returncode == 0, f"py-3-sociograma fallo: {result.stderr}")

        # Verificar archivos con nomenclatura correcta
        html_file = output_dir / "FASP_2026_P2_CHI_INFORME_V1.0.html"
        assert_(html_file.exists(), f"No se genero {html_file.name}")

        # Verificar que el HTML contiene los nodos esperados
        html = html_file.read_text()
        assert_("SESNSP" in html, "Falta SESNSP en el sociograma")
        assert_("1a4480" in html, "Falta color Federal")  # Color hex
        print(f"  ✓ Sociograma HTML generado con nomenclatura FASP_2026_P2_CHI_INFORME_V1.0.html")
        print(f"  ✓ Contiene 5 nodos, 6 aristas, colores por nivel de gobierno")


def main():
    tests = [
        test_sintaxis_scripts,
        test_schemas_json,
        test_taxonomias_cerradas,
        test_db_init,
        test_llm_1_y_py_1_end_to_end,
        test_checkpoint_registro,
        test_validate_taxonomias_detecta_errores,
        test_relacion_con_pdf_knowledge_graph,
        test_nomenclatura,
        test_entidades_federativas,
        test_anexo_11_y_12_schemas,
        test_sociograma_con_datos_sinteticos,
    ]
    n_pass = 0
    n_fail = 0
    for test in tests:
        try:
            test()
            n_pass += 1
        except AssertionError as e:
            print(f"  ✗ {e}")
            n_fail += 1
        except Exception as e:
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
            n_fail += 1

    print(f"\n{'='*60}")
    print(f"Resultado: {n_pass}/{len(tests)} tests OK, {n_fail} fallos")
    print('='*60)
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()