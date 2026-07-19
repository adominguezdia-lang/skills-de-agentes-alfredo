#!/usr/bin/env python3
"""
nomenclatura.py — Implementa la nomenclatura obligatoria de archivos del FASP
segun el Plan de Trabajo (seccion V.H, Tabla 6):

    [PROGRAMA]_[PRODUCTO]_[EDO]_[TIPO_ARCHIVO]_V[X].[EXT]

Donde:
    PROGRAMA: FASP_2026 (fijo)
    PRODUCTO: P1 | P2 | P3 | IF
    EDO:      MEX | CHI | MIC | TAM | HID | QRO | TAB | ZAC | NAL
    TIPO:     INFORME | MAT_ADY | MAT_INC | DIC_NODOS | SCRIPT
    VERSION:  V1.0, V1.1, V2.0, ...
    EXT:      .docx | .pdf | .csv | .xlsx | .py

Uso:
    # Validar un nombre existente:
    python3 nomenclatura.py validar FASP_2026_P3_MEX_INFORME_V1.0.docx

    # Construir un nombre desde partes:
    python3 nomenclatura.py construir --producto P3 --edo MEX --tipo INFORME \\
        --version V1.0 --ext .docx

    # Renombrar archivos de un directorio segun la nomenclatura:
    python3 nomenclatura.py renombrar --directorio ./anexos/ --mapa mapa.json

    # Como modulo (importable):
    from nomenclatura import construir, validar, renombrar
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys

# Valores validos para cada campo
PRODUCTOS_VALIDOS = ["P1", "P2", "P3", "IF"]
EDOS_VALIDOS = ["MEX", "CHI", "MIC", "TAM", "HID", "QRO", "TAB", "ZAC", "NAL"]
TIPOS_VALIDOS = ["INFORME", "MAT_ADY", "MAT_INC", "DIC_NODOS", "SCRIPT", "BBDD"]
EXTS_VALIDAS = [".docx", ".pdf", ".csv", ".xlsx", ".py", ".md", ".txt", ".html", ".png", ".json"]
PROGRAMA_FIJO = "FASP_2026"

# Regex del nombre completo
NOMENCLATURA_RE = re.compile(
    r"^FASP_2026_(?P<producto>P1|P2|P3|IF)_(?P<edo>MEX|CHI|MIC|TAM|HID|QRO|TAB|ZAC|NAL)"
    r"_(?P<tipo>INFORME|MAT_ADY|MAT_INC|DIC_NODOS|SCRIPT|BBDD)_V(?P<version>\d+\.\d+)(?P<ext>\.[a-z]+)$"
)


def validar(nombre: str) -> dict:
    """Valida que un nombre cumpla la nomenclatura FASP. Retorna dict con ok + campos."""
    m = NOMENCLATURA_RE.match(nombre)
    if not m:
        return {"ok": False, "razon": "No cumple el patron FASP_2026_PROD_EDO_TIPO_Vx.y.ext", "nombre": nombre}
    return {
        "ok": True,
        "nombre": nombre,
        "programa": PROGRAMA_FIJO,
        "producto": m.group("producto"),
        "edo": m.group("edo"),
        "tipo": m.group("tipo"),
        "version": f"V{m.group('version')}",
        "ext": m.group("ext"),
    }


def construir(producto: str, edo: str, tipo: str, version: str = "V1.0", ext: str = ".docx") -> str:
    """Construye un nombre valido. Lanza ValueError si algun campo no es valido."""
    if producto not in PRODUCTOS_VALIDOS:
        raise ValueError(f"producto '{producto}' no valido. Opciones: {PRODUCTOS_VALIDOS}")
    if edo not in EDOS_VALIDOS:
        raise ValueError(f"edo '{edo}' no valido. Opciones: {EDOS_VALIDOS}")
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo '{tipo}' no valido. Opciones: {TIPOS_VALIDOS}")
    if not re.match(r"^V\d+\.\d+$", version):
        raise ValueError(f"version '{version}' no valida. Formato: V1.0, V1.1, V2.0, ...")
    if ext not in EXTS_VALIDAS:
        raise ValueError(f"ext '{ext}' no valida. Opciones: {EXTS_VALIDAS}")

    return f"{PROGRAMA_FIJO}_{producto}_{edo}_{tipo}_{version}{ext}"


def parsear(nombre: str) -> dict:
    """Alias de validar. Mantengo nombre por compatibilidad."""
    return validar(nombre)


def renombrar(directorio: pathlib.Path, mapeo: dict) -> list[dict]:
    """
    Renombra archivos en un directorio segun un mapeo {nombre_original: nombre_nuevo}.
    Valida cada nombre nuevo antes de renombrar.
    Devuelve lista de operaciones (exitosas + fallidas).
    """
    resultados = []
    for nombre_orig, nombre_nuevo in mapeo.items():
        ruta_orig = directorio / nombre_orig
        ruta_nueva = directorio / nombre_nuevo

        if not ruta_orig.exists():
            resultados.append({"ok": False, "op": "renombrar", "from": nombre_orig,
                               "to": nombre_nuevo, "razon": "archivo_origen_no_existe"})
            continue

        v = validar(nombre_nuevo)
        if not v["ok"]:
            resultados.append({"ok": False, "op": "renombrar", "from": nombre_orig,
                               "to": nombre_nuevo, "razon": v["razon"]})
            continue

        ruta_orig.rename(ruta_nueva)
        resultados.append({"ok": True, "op": "renombrar", "from": nombre_orig, "to": nombre_nuevo})

    return resultados


def main():
    p = argparse.ArgumentParser(description="Nomenclatura obligatoria FASP 2026")
    sub = p.add_subparsers(dest="cmd")

    v = sub.add_parser("validar", help="Valida un nombre existente")
    v.add_argument("nombre")

    c = sub.add_parser("construir", help="Construye un nombre valido")
    c.add_argument("--producto", required=True, choices=PRODUCTOS_VALIDOS)
    c.add_argument("--edo", required=True, choices=EDOS_VALIDOS)
    c.add_argument("--tipo", required=True, choices=TIPOS_VALIDOS)
    c.add_argument("--version", default="V1.0")
    c.add_argument("--ext", default=".docx", choices=EXTS_VALIDAS)

    r = sub.add_parser("renombrar", help="Renombra archivos segun mapeo JSON")
    r.add_argument("--directorio", required=True)
    r.add_argument("--mapa", required=True, help="Archivo JSON con mapeo {orig: nuevo}")

    args = p.parse_args()

    if args.cmd == "validar":
        result = validar(args.nombre)
        if result["ok"]:
            print(f"✓ {args.nombre}")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"✗ {args.nombre}: {result['razon']}")
            sys.exit(1)

    elif args.cmd == "construir":
        try:
            nombre = construir(args.producto, args.edo, args.tipo, args.version, args.ext)
            print(nombre)
        except ValueError as e:
            print(f"✗ {e}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "renombrar":
        directorio = pathlib.Path(args.directorio)
        if not directorio.is_dir():
            sys.exit(f"No es directorio: {directorio}")
        mapeo = json.loads(pathlib.Path(args.mapa).read_text())
        resultados = renombrar(directorio, mapeo)
        for r in resultados:
            status = "✓" if r["ok"] else "✗"
            extra = f" ({r.get('razon','')})" if not r["ok"] else ""
            print(f"{status} {r.get('from')} -> {r.get('to')}{extra}")
        n_ok = sum(1 for r in resultados if r["ok"])
        print(f"\n{n_ok}/{len(resultados)} renombrados exitosamente")
        sys.exit(0 if n_ok == len(resultados) else 1)

    else:
        p.print_help()


if __name__ == "__main__":
    main()