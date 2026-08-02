#!/usr/bin/env python3
"""
regenerar_dashboard.py — Helper para que el agente regenere el dashboard
despues de cualquier operacion del pipeline.

Uso desde el shell:
    python3 regenerar_dashboard.py                  # usa ./fasp.db
    python3 regenerar_dashboard.py --abrir          # ademas abre el navegador
    python3 regenerar_dashboard.py --db otra.db

Uso desde Python (cuando el agente lo invoca como subproceso):
    import subprocess
    subprocess.run(["python3", "regenerar_dashboard.py", "--abrir"])
"""
import argparse, subprocess, sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Regenera el dashboard del pipeline FASP")
    p.add_argument("--db", default="./fasp.db", help="Ruta a la BD SQLite (default: ./fasp.db)")
    p.add_argument("--output", default="./dashboard.html", help="Ruta del HTML (default: ./dashboard.html)")
    p.add_argument("--abrir", action="store_true", help="Abrir el HTML en el navegador al terminar")
    args = p.parse_args()

    script = Path(__file__).parent / "fasp_dashboard.py"
    if not script.exists():
        sys.exit(f"No se encontro {script}")

    print(f"Regenerando dashboard desde {args.db}...")
    result = subprocess.run(
        ["python3", str(script), "--db", args.db, "--output", args.output],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    if args.abrir:
        subprocess.run(["open", args.output])
        print(f"Abierto en navegador: {args.output}")


if __name__ == "__main__":
    main()
