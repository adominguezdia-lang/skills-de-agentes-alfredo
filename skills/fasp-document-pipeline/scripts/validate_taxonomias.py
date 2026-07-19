#!/usr/bin/env python3
"""
validate_taxonomias.py — Valida que los valores de un JSON pertenezcan a las
taxonomías cerradas del FASP.

Uso:
    python3 validate_taxonomias.py --input ./file.json --tipo matriz_congruencia
    python3 validate_taxonomias.py --input ./anexo3.json --tipo directorio_actores
"""
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).parent.parent
TAX_PATH = ROOT / "schemas" / "taxonomias.json"


def load_taxonomias() -> dict:
    return json.loads(TAX_PATH.read_text(encoding="utf-8"))


def validate_matriz_congruencia(data: dict, tax: dict) -> list[str]:
    """Valida un objeto matriz de congruencia (Anexo 2)."""
    issues = []
    valid_etapa = set(tax["etapas_ciclo_fasp"])
    valid_dim = set(tax["dimensiones_ciclo"])
    valid_comp = set(tax["tipos_competencia"])
    valid_oblig = set(tax["niveles_obligatoriedad"])
    valid_nivel = set(tax["niveles_gobierno"])

    for i, fila in enumerate(data.get("filas", [])):
        for field, valid_set in [
            ("etapa_ciclo_fasp", valid_etapa),
            ("dimension_ciclo", valid_dim),
            ("tipo_competencia", valid_comp),
            ("nivel_obligatoriedad", valid_oblig),
            ("nivel", valid_nivel),
        ]:
            val = fila.get(field)
            if val is None:
                continue  # opcional
            if val not in valid_set:
                issues.append(f"Fila {i}: '{field}={val}' no está en taxonomía {sorted(valid_set)}")

    return issues


def validate_directorio(data: dict, tax: dict) -> list[str]:
    issues = []
    valid_nivel = set(tax["niveles_gobierno"])
    valid_nat = set(tax["naturaleza_actor"])
    valid_etapas = set(tax["etapas_ciclo_fasp"])

    for i, actor in enumerate(data.get("actores", [])):
        for field, valid_set in [
            ("nivel_gobierno", valid_nivel),
            ("naturaleza", valid_nat),
        ]:
            val = actor.get(field)
            if val is None:
                continue
            if val not in valid_set:
                issues.append(f"Actor {i}: '{field}={val}' no está en taxonomía {sorted(valid_set)}")

        for etapa in actor.get("etapas_ciclo_participa", []):
            if etapa not in valid_etapas:
                issues.append(f"Actor {i}: etapa '{etapa}' no está en taxonomía")

    return issues


def validate_aristas(data: dict, tax: dict) -> list[str]:
    issues = []
    valid_vinculo = set(tax["tipos_vinculo_ars"])

    for i, arista in enumerate(data.get("matriz", [])):
        val = arista.get("tipo_vinculo")
        if val is None:
            continue
        if val not in valid_vinculo:
            issues.append(f"Arista {i}: 'tipo_vinculo={val}' no está en {sorted(valid_vinculo)}")

    return issues


def validate_fichas(data: dict, tax: dict) -> list[str]:
    issues = []
    valid_cats = {"Normativo", "Organizacional", "Capacidades", "Canales de comunicación"}
    valid_prioridad = {"Alta", "Media", "Baja"}

    for i, ficha in enumerate(data.get("fichas", [])):
        cat = ficha.get("categoria_tematica")
        if cat and cat not in valid_cats:
            issues.append(f"Ficha {i}: categoria_tematica '{cat}' no válida")

        pri = ficha.get("prioridad")
        if pri and pri not in valid_prioridad:
            issues.append(f"Ficha {i}: prioridad '{pri}' no válida")

        for v_field in ["viabilidad_claridad", "viabilidad_relevancia",
                       "viabilidad_justificacion", "viabilidad_factibilidad"]:
            v = ficha.get(v_field)
            if v is not None and (not isinstance(v, int) or v < 1 or v > 5):
                issues.append(f"Ficha {i}: {v_field}={v} fuera de rango 1-5")

    return issues


VALIDATORS = {
    "matriz_congruencia": validate_matriz_congruencia,
    "directorio_actores": validate_directorio,
    "aristas": validate_aristas,
    "fichas": validate_fichas,
}


def main():
    p = argparse.ArgumentParser(description="Validador de taxonomías FASP")
    p.add_argument("--input", required=True)
    p.add_argument("--tipo", required=True, choices=list(VALIDATORS.keys()))
    args = p.parse_args()

    data = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    tax = load_taxonomias()

    validator = VALIDATORS[args.tipo]
    issues = validator(data, tax)

    if not issues:
        print(f"✓ Todos los valores cumplen las taxonomías cerradas del FASP.")
        sys.exit(0)
    else:
        print(f"✗ {len(issues)} problemas encontrados:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)


if __name__ == "__main__":
    main()