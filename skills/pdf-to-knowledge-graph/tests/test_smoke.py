#!/usr/bin/env python3
"""
test_smoke.py — Smoke tests para pdf-to-knowledge-graph.

Ejecuta las 3 etapas con datos sintéticos (sin PDFs reales) y verifica
que los artefactos producidos cumplan los schemas mínimos y que el pipeline
no se rompa en los casos comunes.

Uso:
    python3 tests/test_smoke.py
    # Exit code 0 = OK, 1 = algún test falló

Requisitos:
    - pymupdf, networkx instalados en el python que ejecuta.
    - Los scripts del skill en scripts/ (mismo nivel que tests/).
"""
from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile, shutil
import ast

SCRIPTS_DIR = pathlib.Path(__file__).parent.parent / "scripts"
SCHEMAS_DIR = pathlib.Path(__file__).parent.parent / "schemas"

PYTHON = sys.executable  # usa el python que corre el test


def run_script(script_name: str, *args: str, cwd: pathlib.Path = None) -> subprocess.CompletedProcess:
    """Ejecuta un script del skill y retorna el resultado."""
    script_path = SCRIPTS_DIR / script_name
    return subprocess.run(
        [PYTHON, str(script_path), *args],
        capture_output=True, text=True, cwd=cwd or SCRIPTS_DIR.parent
    )


def assert_(condition: bool, msg: str):
    if not condition:
        raise AssertionError(msg)


def test_syntax_all_scripts():
    """T1: Cada script del skill debe parsear como Python válido."""
    print("T1: Sintaxis de scripts...")
    for script in SCRIPTS_DIR.glob("*.py"):
        try:
            ast.parse(script.read_text())
            print(f"  ✓ {script.name}")
        except SyntaxError as e:
            raise AssertionError(f"{script.name}: {e}")


def test_schemas_valid_json():
    """T2: Cada schema JSON debe parsear y tener 'required' + 'properties'."""
    print("T2: Schemas JSON válidos...")
    for schema_path in SCHEMAS_DIR.glob("*.json"):
        schema = json.loads(schema_path.read_text())
        assert_(isinstance(schema, dict), f"{schema_path.name}: no es objeto")
        assert_("required" in schema, f"{schema_path.name}: falta 'required'")
        assert_("properties" in schema, f"{schema_path.name}: falta 'properties'")
        print(f"  ✓ {schema_path.name} ({len(schema['required'])} required, {len(schema['properties'])} properties)")


def test_diccionario_carga():
    """T3: El diccionario debe existir, tener entradas válidas y comentarios permitidos."""
    print("T3: Diccionario de gobernanza...")
    dic_path = pathlib.Path(__file__).parent.parent / "references" / "diccionario_gobernanza_mx.txt"
    assert_(dic_path.exists(), f"No existe {dic_path}")

    lines = dic_path.read_text().splitlines()
    entries = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    assert_(len(entries) >= 30, f"Diccionario tiene solo {len(entries)} entradas (esperaba ≥30)")

    # Verificar que no hay duplicados (case-insensitive)
    seen = set()
    for e in entries:
        e_lower = e.lower()
        assert_(e_lower not in seen, f"Duplicado en diccionario: '{e}'")
        seen.add(e_lower)
    print(f"  ✓ {len(entries)} entradas únicas")


def test_full_pipeline_synthetic():
    """T4: Ejecutar las 3 etapas con entities.jsonl sintéticas (sin PDF real)."""
    print("T4: Pipeline completo con datos sintéticos...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        corpus = tmp / "jobs"
        corpus.mkdir()
        grafo = tmp / "grafo"
        grafo.mkdir()

        # Generar 5 jobs sintéticos con 3 capas
        docs = {
            "doc001": ("normativo", [
                ("Ley General del Sistema Nacional de Seguridad Pública", "NORMA"),
                ("Constitución Política de los Estados Unidos Mexicanos", "NORMA"),
                ("Secretaría de Seguridad y Protección Ciudadana", "INSTITUCION"),
                ("Coordinación Nacional de Protección Civil", "INSTITUCION"),
            ]),
            "doc002": ("normativo", [
                ("Ley de Seguridad Nacional", "NORMA"),
                ("Reglamento de la Ley de Seguridad Nacional", "NORMA"),
                ("Centro Nacional de Inteligencia", "INSTITUCION"),
                ("Secretaría de la Defensa Nacional", "INSTITUCION"),
            ]),
            "doc003": ("operativo", [
                ("Secretaría de Seguridad y Protección Ciudadana", "INSTITUCION"),
                ("Coordinación Nacional de Protección Civil", "INSTITUCION"),
                ("Oficio SSP/2024/001", "DOCUMENTO"),
                ("Director General", "CARGO"),
            ]),
            "doc004": ("operativo", [
                ("Secretaría de Gobernación", "INSTITUCION"),
                ("Instituto Nacional de Migración", "INSTITUCION"),
                ("Memorándum INM/2024/012", "DOCUMENTO"),
            ]),
            "doc005": ("informal", [
                ("Secretaría de Seguridad y Protección Ciudadana", "INSTITUCION"),
                ("Coordinación Nacional de Protección Civil", "INSTITUCION"),
                ("Entrevista funcionario X", "PERSONA"),
                ("Ley General del Sistema Nacional de Seguridad Pública", "NORMA"),
            ]),
        }

        for doc_id, (layer, ents) in docs.items():
            jdir = corpus / doc_id
            jdir.mkdir()
            meta = {"job_id": doc_id, "filename": f"{doc_id}.pdf", "layer": layer,
                    "method": "text", "prompt_version": "v1", "user_id": "test",
                    "created_at": "2026-07-18T17:00:00Z"}
            (jdir / f"{doc_id}.meta.json").write_text(json.dumps(meta))
            with open(jdir / "entities.jsonl", "w", encoding="utf-8") as f:
                for ent, etype in ents:
                    f.write(json.dumps({"entity": ent, "type": etype, "layer": layer,
                                        "section": "Test", "context": f"context for {ent}"},
                                       ensure_ascii=False) + "\n")

        # Etapa 3
        r = run_script("build_graph.py", "--corpus", str(corpus),
                       "--output", str(grafo))
        assert_(r.returncode == 0, f"build_graph.py falló:\n{r.stderr}")

        # Validar outputs
        for required in ["graph.graphml", "nodes.csv", "edges.csv",
                         "metrics.json", "graph.html"]:
            assert_((grafo / required).exists(), f"Falta {required}")

        metrics = json.loads((grafo / "metrics.json").read_text())

        # Validar métricas mínimas
        assert_(metrics["nodos_totales"] >= 5, f"muy pocos nodos: {metrics['nodos_totales']}")
        assert_(metrics["aristas_totales"] >= 5, f"muy pocas aristas: {metrics['aristas_totales']}")
        assert_(0 <= metrics["densidad"] <= 1, f"densidad fuera de rango: {metrics['densidad']}")
        assert_("top_centralidad_grado" in metrics, "falta top_centralidad_grado")
        assert_("densidad_por_capa" in metrics, "falta densidad_por_capa")

        # Sin advertencia de corpus pequeño
        assert_(metrics.get("advertencia_corpus_pequeno") is None,
                f"warning inesperado: {metrics.get('advertencia_corpus_pequeno')}")

        # Validar contra schema de metrics
        schema = json.loads((SCHEMAS_DIR / "metrics.schema.json").read_text())
        for req_key in schema["required"]:
            assert_(req_key in metrics, f"metrics falta clave requerida '{req_key}'")

        # graph.graphml debe ser XML válido
        import xml.etree.ElementTree as ET
        try:
            ET.parse(grafo / "graph.graphml")
        except ET.ParseError as e:
            raise AssertionError(f"graph.graphml no es XML válido: {e}")

        print(f"  ✓ {metrics['nodos_totales']} nodos, {metrics['aristas_totales']} aristas, "
              f"densidad={metrics['densidad']}")
        print(f"  ✓ densidad_por_capa = {metrics['densidad_por_capa']}")
        print(f"  ✓ {len(metrics.get('actores_transversales', []))} actores transversales")


def test_entity_schema_compliance():
    """T5: Las entidades generadas deben cumplir el entity schema."""
    print("T5: Compliance de entidades con schema...")
    valid_types = {"INSTITUCION", "CARGO", "NORMA", "DOCUMENTO", "PERSONA", "LUGAR"}
    valid_layers = {"normativo", "operativo", "informal"}

    schema = json.loads((SCHEMAS_DIR / "entity.schema.json").read_text())
    required_keys = set(schema["required"])

    # Generar una entidad válida y verificar
    sample = {
        "entity": "Secretaría de Seguridad y Protección Ciudadana",
        "type": "INSTITUCION",
        "layer": "operativo",
        "section": "DE LA SECRETARÍA",
        "context": "contexto de prueba"
    }
    assert_(set(sample.keys()) >= required_keys, f"sample falta: {required_keys - set(sample.keys())}")
    assert_(sample["type"] in valid_types, f"type inválido: {sample['type']}")
    assert_(sample["layer"] in valid_layers, f"layer inválido: {sample['layer']}")
    print(f"  ✓ entity schema: required={sorted(required_keys)}")


def test_job_schema_compliance():
    """T6: El job meta debe cumplir el schema (validación estática)."""
    print("T6: Compliance de job meta con schema...")
    schema = json.loads((SCHEMAS_DIR / "job.schema.json").read_text())

    sample = {
        "job_id": "abc123def456",
        "filename": "test.pdf",
        "method": "text",
        "prompt_version": "v1",
        "created_at": "2026-07-18T17:00:00Z",
        "layer": "operativo",
        "user_id": "test",
    }
    for req_key in schema["required"]:
        assert_(req_key in sample, f"sample falta: {req_key}")

    # Validar enums
    assert_(sample["method"] in schema["properties"]["method"]["enum"], "method enum")
    assert_(sample["prompt_version"] in schema["properties"]["prompt_version"]["enum"], "prompt_version enum")
    assert_(sample["layer"] in schema["properties"]["layer"]["enum"], "layer enum")

    print(f"  ✓ job schema: {len(schema['required'])} required, enums validados")


def test_prompts_archivos_existen():
    """T7: Los prompts versionados referenciados en SKILL.md deben existir."""
    print("T7: Archivos de prompts versionados...")
    prompts_dir = pathlib.Path(__file__).parent.parent / "prompts"
    referenced = ["prompt_conversion_v1.md", "prompt_conversion_v2.md", "prompt_conversion_v3.md"]
    for p in referenced:
        path = prompts_dir / p
        assert_(path.exists(), f"Falta prompt: {path}")
        content = path.read_text()
        assert_(len(content) > 100, f"{p} parece vacío o muy corto ({len(content)} chars)")
        print(f"  ✓ {p} ({len(content)} chars)")


def main():
    tests = [
        test_syntax_all_scripts,
        test_schemas_valid_json,
        test_diccionario_carga,
        test_full_pipeline_synthetic,
        test_entity_schema_compliance,
        test_job_schema_compliance,
        test_prompts_archivos_existen,
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
            print(f"  ✗ ERROR INESPERADO: {type(e).__name__}: {e}")
            n_fail += 1

    print(f"\n{'=' * 60}")
    print(f"Resultado: {n_pass}/{len(tests)} tests OK, {n_fail} fallos")
    print('=' * 60)
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()