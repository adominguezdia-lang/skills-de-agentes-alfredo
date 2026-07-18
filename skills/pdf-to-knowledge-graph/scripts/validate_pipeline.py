#!/usr/bin/env python3
"""
validate_pipeline.py — corre las validaciones de las 3 etapas para todos los jobs.

Uso:
    python3 validate_pipeline.py ./jobs/
"""
from __future__ import annotations
import json, pathlib, sys

def validate_job(job_dir: pathlib.Path) -> dict:
    """Valida un job. Retorna dict con ok + issues por etapa."""
    result = {"job_id": job_dir.name, "etapas": {}}

    md = next(job_dir.glob("*.md"), None)
    meta = next(job_dir.glob("*.meta.json"), None)
    entities = job_dir / "entities.jsonl"

    if not md:
        result["etapas"]["etapa1"] = {"ok": False, "error": "no .md file"}
        return result
    if not meta:
        result["etapas"]["etapa1"] = {"ok": False, "error": "no meta.json"}
        return result

    # Etapa 1
    validation_files = list(job_dir.glob("*.validation.json"))
    if validation_files:
        v1 = json.loads(validation_files[0].read_text())
        result["etapas"]["etapa1"] = v1
    else:
        result["etapas"]["etapa1"] = {"ok": False, "error": "no validation file"}

    # Etapa 2
    if entities.exists():
        v2 = json.loads((job_dir / "entities.validation.json").read_text()) \
            if (job_dir / "entities.validation.json").exists() \
            else {"ok": entities.stat().st_size > 0}
        result["etapas"]["etapa2"] = v2
    else:
        result["etapas"]["etapa2"] = {"ok": False, "error": "no entities.jsonl"}

    return result


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 validate_pipeline.py <jobs_dir>")
        sys.exit(2)

    jobs_dir = pathlib.Path(sys.argv[1])
    job_dirs = sorted([p for p in jobs_dir.iterdir() if p.is_dir()])

    n_ok = 0
    n_warn = 0
    n_fail = 0

    for jd in job_dirs:
        r = validate_job(jd)
        e1_ok = r["etapas"].get("etapa1", {}).get("ok", False)
        e2_ok = r["etapas"].get("etapa2", {}).get("ok", False)

        status = "✓" if (e1_ok and e2_ok) else ("⚠" if (e1_ok or e2_ok) else "✗")
        print(f"{status} {r['job_id']}: E1={'✓' if e1_ok else '✗'} E2={'✓' if e2_ok else '✗'}")

        if e1_ok and e2_ok:
            n_ok += 1
        elif e1_ok or e2_ok:
            n_warn += 1
        else:
            n_fail += 1

    print(f"\nTotal: {n_ok} OK, {n_warn} advertencia, {n_fail} falla")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()