#!/usr/bin/env python3
"""
fasp_sync_drive.py — Sincronización incremental desde Google Drive para la Etapa 1 del FASP.

Recorre las 8 carpetas de estados + normatividad federal en Drive, descarga los PDFs
nuevos (filtra los "FASP Registro Normatividad.xlsx"), los convierte a Markdown con
pdf_to_md.py, y mantiene una tabla de hashes SHA-256 para no reprocesar.

Uso:
    # Sincronizar todo (8 estados + normatividad federal)
    python3 fasp_sync_drive.py

    # Solo un estado
    python3 fasp_sync_drive.py --edo MEX

    # Modo dry-run (solo reporta, no descarga)
    python3 fasp_sync_drive.py --dry-run

    # Forzar reprocesamiento de un archivo (borrar de seen y volver a correr)
    python3 fasp_sync_drive.py --force <FILE_ID>

Archivos generados:
    ~/.hermes/state/fasp_drive_seen.json     # Tabla de hashes (file_id -> {hash, name, edo, mtime})
    ~/Downloads/FASP/09 FASP/<EDO>/corpus/   # PDFs descargados
    ~/Downloads/FASP/09 FASP/<EDO>/jobs/     # MDs generados por pdf_to_md.py

Estados soportados (mapeo clave -> folder_id):
    MEX, HID, MIC, QRO, CHI, TAB, TAM, ZAC
    NAL (normatividad federal)

Excluidos automáticamente:
    - Cualquier archivo cuyo nombre contenga 'FASP Registro Normatividad'
      (es el consolidado de la BD, ya lo manejamos aparte).
    - Cualquier archivo que no sea PDF.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests

# === Paths ===
HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
TOKEN_PATH = HERMES_HOME / "google_token.json"
SEEN_FILE = HERMES_HOME / "state" / "fasp_drive_seen.json"
FASP_CORPUS_ROOT = Path(os.environ.get(
    "FASP_CORPUS_ROOT",
    str(Path.home() / "Documents" / "FASP" / "09 FASP")
))
PDF_TO_MD = Path.home() / ".hermes" / "skills" / "productivity" / "pdf-to-knowledge-graph" / "scripts" / "pdf_to_md.py"

# === Mapeo Drive (carpeta raíz 1fMCP-xvtUfvUMO8h0pMi3V4nFbqnUG85) ===
DRIVE_ROOT = "1fMCP-xvtUfvUMO8h0pMi3V4nFbqnUG85"

ESTADOS = {
    # clave  : (nombre_display,         folder_id)
    "NAL": ("Normatividad federal",     "1npFabPvvmfuu60Qhgop78MKoNxKqIOv4"),
    "MEX": ("EdoMex",                  "1nlBoq8QeVFyc6IwPytRgTIYH49gmB7fo"),
    "HID": ("Hidalgo",                 "14VbekDpDFHbBevQCKyx26L1dVYmZBGXe"),
    "MIC": ("Michoacán",               "1grtO2xTl9sia6nZWC998KVMeoOAisw2R"),
    "QRO": ("Querétaro",               "1_NMoR3A_7RziAB_Ud6O0pYKm6gCufoTw"),
    "CHI": ("Chiapas",                 "1s89r9l2ukjLtjyRTuQrIk0SoL9Puba58"),
    "TAB": ("Tabasco",                 "19kduuCIus4Fr_g5bI5_EE-Myqo3XGK4I"),
    "TAM": ("Tamaulipas",               "1adFk_AUK_OljewlvIlPsDBBMbxB0Na9s"),
    "ZAC": ("Zacatecas",               "1VSn0E9uHCCvwjTJgwMoDCTGlz1YX6U82"),
}

# Carpetas de bibliografía y normatividad federal dentro de la raiz NAL.
# Tienen subcarpetas propias (01 Bibliografia, 02 Normatividad federal) y NO
# se procesan con la logica por estado porque su estructura difiere.
CARPETAS_FEDERALES = [
    # (clave,       nombre_display,        folder_id,                                subcarpeta_destino)
    ("BIB",        "Bibliografia",        "1CLaQLTYBiFGO38bW1sBjK272TyIAn8Ai",   "Bibliografia"),
    ("NORFED",     "Normatividad federal", "1KcSU_qF49ntIDObY_4UG76qhefSRDuC_",   "NormatividadFederal"),
]

# Subcarpetas a sincronizar dentro de cada estado. Si la subcarpeta no existe,
# se omite (es informativo, no error).
SUBCARPETAS = ["00 Tdr", "01 Normatividad estatal"]

# === Drive API helpers ===
_token_cache: dict = {}


def get_token_data() -> dict:
    return json.loads(TOKEN_PATH.read_text())


def get_headers() -> dict:
    if not _token_cache:
        td = get_token_data()
        # El token puede estar en 'token' (nuestro formato) o 'access_token' (formato google-auth)
        _token_cache.update(td)
        _token_cache["access_token"] = td.get("access_token") or td.get("token", "")
    return {"Authorization": f"Bearer {_token_cache['access_token']}"}


def refresh_token() -> None:
    td = get_token_data()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": td["client_id"],
        "client_secret": td["client_secret"],
        "refresh_token": td["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=15)
    r.raise_for_status()
    new = r.json()
    _token_cache.clear()
    _token_cache.update(td)
    _token_cache["access_token"] = new["access_token"]
    td["token"] = new["access_token"]
    if "access_token" in td:
        td["access_token"] = new["access_token"]
    TOKEN_PATH.write_text(json.dumps(td, indent=2))


def drive_list(folder_id: str, recursive: bool = False) -> Iterator[dict]:
    """Yield todos los files de una carpeta (recursivo opcional)."""
    def _walk(fid: str):
        page_token = None
        while True:
            params = {
                "q": f"'{fid}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, modifiedTime)",
                "pageSize": 200,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                params["pageToken"] = page_token
            r = requests.get("https://www.googleapis.com/drive/v3/files",
                             headers=get_headers(), params=params, timeout=30)
            if r.status_code == 401:
                refresh_token()
                r = requests.get("https://www.googleapis.com/drive/v3/files",
                                 headers=get_headers(), params=params, timeout=30)
            r.raise_for_status()
            for f in r.json().get("files", []):
                yield f
                if recursive and f["mimeType"] == "application/vnd.google-apps.folder":
                    yield from _walk(f["id"])
            page_token = r.json().get("nextPageToken")
            if not page_token:
                break
    yield from _walk(folder_id)


def drive_download(file_id: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}",
                     headers=get_headers(), params={"alt": "media"},
                     timeout=300, stream=True)
    if r.status_code == 401:
        refresh_token()
        r = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}",
                         headers=get_headers(), params={"alt": "media"},
                         timeout=300, stream=True)
    r.raise_for_status()
    with dest.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    return dest


# === Seen table ===
def load_seen() -> dict:
    if not SEEN_FILE.exists():
        return {}
    return json.loads(SEEN_FILE.read_text())


def save_seen(seen: dict) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2, ensure_ascii=False))


def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# === Filter logic ===
def is_excluded(name: str) -> bool:
    """Excluir el consolidado 'FASP Registro Normatividad' (xlsx) y no-PDFs."""
    if "FASP Registro Normatividad" in name:
        return True
    return False


def is_pdf(f: dict) -> bool:
    return f["mimeType"] == "application/pdf" or f["name"].lower().endswith(".pdf")


# === Main ===
def process_estado(edo: str, edo_name: str, folder_id: str, seen: dict,
                   dry_run: bool = False, force_ids: set = None) -> dict:
    """Sincroniza un estado. Devuelve stats {nuevos, ya_vistos, errores, omitidos}."""
    stats = {"nuevos": 0, "ya_vistos": 0, "errores": 0, "omitidos": 0, "detalles": []}
    force_ids = force_ids or set()

    print(f"\n=== {edo} ({edo_name})  folder={folder_id[:12]}... ===")

    # Para NAL, listar solo al primer nivel (las subcarpetas las procesa
    # process_carpeta_federal por separado). Para estados, recursivo.
    recursive = edo != "NAL"
    try:
        all_files = list(drive_list(folder_id, recursive=recursive))
    except Exception as e:
        print(f"  ✗ Error listando carpeta: {e}", file=sys.stderr)
        stats["errores"] += 1
        return stats

    # Filtrar: PDFs, no excluidos, solo en subcarpetas permitidas
    candidates = []
    for f in all_files:
        if not is_pdf(f):
            continue
        if is_excluded(f["name"]):
            stats["omitidos"] += 1
            continue
        candidates.append(f)

    if not candidates:
        print(f"  (sin PDFs nuevos)")
        return stats

    for f in candidates:
        fid = f["id"]
        fname = f["name"]
        mtime = f.get("modifiedTime", "")

        prev = seen.get(fid)
        needs_process = False
        reason = ""

        if fid in force_ids:
            needs_process = True
            reason = "forced"
        elif prev is None:
            needs_process = True
            reason = "nuevo"
        else:
            stats["ya_vistos"] += 1
            print(f"  ↻ (ya visto, hash={prev['hash'][:12]}…) {fname}")
            continue

        # Decidir subcarpeta local (buscar el path del archivo en Drive)
        # El archivo vive en <estado>/<subcarpeta>/<archivo>; necesitamos saber
        # la subcarpeta para nombrarlo con FASP_2026.
        # Simplificación: usamos el nombre del archivo para inferir
        # (TDR <EDO>.pdf -> FASP_2026_P1_<EDO>_TDR_V1.0.pdf).
        # Para archivos más complejos, el usuario puede ajustar manualmente.
        target_name = _infer_target_name(fname, edo)
        corpus_dir = FASP_CORPUS_ROOT / edo_name / "corpus"
        jobs_dir = FASP_CORPUS_ROOT / edo_name / "jobs"
        corpus_dir.mkdir(parents=True, exist_ok=True)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        local_pdf = corpus_dir / target_name

        if dry_run:
            print(f"  [dry-run] {reason}: {fname} -> {target_name}")
            stats["nuevos"] += 1
            seen[fid] = {"hash": "(dry-run)", "name": fname, "edo": edo,
                         "target": target_name, "mtime": mtime, "downloaded_at": None}
            continue

        # Descargar
        try:
            drive_download(fid, local_pdf)
        except Exception as e:
            print(f"  ✗ Error descargando {fname}: {e}", file=sys.stderr)
            stats["errores"] += 1
            continue

        # Calcular hash y registrar
        h = hash_file(local_pdf)
        seen[fid] = {
            "hash": h,
            "name": fname,
            "edo": edo,
            "target": target_name,
            "mtime": mtime,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "size": local_pdf.stat().st_size,
        }
        stats["nuevos"] += 1
        print(f"  ↓ {reason}: {fname} -> {target_name}  ({local_pdf.stat().st_size:,} bytes)")

        # Convertir PDF -> MD con pdf_to_md.py
        try:
            job_id = f"fasp_{edo}_{local_pdf.stem}_{h[:8]}"
            cmd = [
                sys.executable, str(PDF_TO_MD),
                "--input", str(local_pdf),
                "--output", str(jobs_dir),
                "--job-id", job_id,
                "--prompt", "v1",
                "--layer", "normativo",
                "--user-id", "fasp-sync",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"    ⚠ pdf_to_md.py exit {result.returncode}: {result.stderr[:200]}")
            else:
                md_path = jobs_dir / f"{job_id}.md"
                if md_path.exists():
                    print(f"    ✓ MD: {md_path.relative_to(FASP_CORPUS_ROOT)}")
                else:
                    print(f"    ⚠ No se generó MD esperado en {md_path}")
            stats["detalles"].append({"fid": fid, "target": target_name,
                                      "job_id": job_id, "md": str(jobs_dir / f"{job_id}.md")})
        except subprocess.TimeoutExpired:
            print(f"    ⚠ Timeout en pdf_to_md.py para {fname}")
            stats["errores"] += 1
        except Exception as e:
            print(f"    ⚠ Error en conversión: {e}")
            stats["errores"] += 1

    return stats


def _infer_target_name(fname: str, edo: str) -> str:
    """
    Mapea nombre de archivo Drive → nombre FASP_2026.

    Reglas:
      'TDR EDOMX.pdf' / 'TDR MICH.pdf' -> FASP_2026_P1_<EDO>_TDR_V1.0.pdf
      'FASP_2026_P1_MEX_TDR_V1.0.pdf' (ya prefijado) -> mismo
      otros PDFs -> FASP_2026_P1_<EDO>_<TIPO>_V1.0.pdf (tipo derivado del nombre)

    Logica:
      1. Si ya tiene FASP_2026_P1_<EDO>_<algo>, dejarlo igual
      2. Si empieza con FASP_2026_P1_<EDO> pero sin categoria, regenerar con categoria
      3. TDRs -> FASP_2026_P1_<EDO>_TDR_V1.0.pdf
      4. Otros -> FASP_2026_P1_<EDO>_<TIPO>_V1.0.pdf
    """
    base = fname.rsplit(".", 1)[0]

    # Caso 1: ya tiene el prefijo completo FASP_2026_P1_<EDO>_<cualquier_cosa>
    if re.match(rf"^FASP_2026_P1_{re.escape(edo)}_", base, re.IGNORECASE):
        return fname

    # TDR
    if base.upper().startswith("TDR"):
        return f"FASP_2026_P1_{edo}_TDR_V1.0.pdf"

    # Si tiene el nombre del estado, asumimos normatividad
    return f"FASP_2026_P1_{edo}_{re.sub(r'[^A-Za-z0-9]+', '_', base).strip('_').upper()}_V1.0.pdf"


def _infer_target_name_federal(fname: str, clave: str) -> str:
    """
    Mapea nombre de archivo de Bibliografía/Normatividad federal → FASP_2026.

    BIB (Bibliografía):    FASP_2026_P1_NAL_BIB_<TIPO>_V1.0.pdf
    NORFED (Normatividad): FASP_2026_P1_NAL_NORFED_<TIPO>_V1.0.pdf

    Logica:
      1. Si el archivo YA tiene el prefijo completo (BIB_ o NORFED_), dejarlo igual
      2. Si tiene FASP_2026_P1_NAL_ sin categoria, agregar la categoria del folder
      3. Si no tiene prefijo, generarlo
    """
    base = fname.rsplit(".", 1)[0]

    # Caso 1: ya tiene categoria explicita (BIB o NORFED) -> dejar igual
    # Match con _ o - despues de la categoria (porque algunos archivos
    # tienen el kebab-case oficial con -)
    if re.match(r"^FASP_2026_P1_NAL_(BIB|NORFED)[_-]", base, re.IGNORECASE):
        return fname

    # Caso 2: tiene FASP_2026_P1_NAL_ pero sin categoria -> agregar categoria del folder
    m = re.match(r"^FASP_2026_P1_NAL_(.+)$", base, re.IGNORECASE)
    if m:
        tipo = m.group(1)
        # Normalizar tipo
        tipo = re.sub(r"[^A-Za-z0-9]+", "_", tipo).strip("_").upper()
        return f"FASP_2026_P1_NAL_{clave}_{tipo}_V1.0.pdf"

    # Caso 3: no tiene prefijo, generarlo desde cero
    tipo = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").upper()
    for pref in ["LINEAMIENTOS_", "CRITERIOS_", "REGLAMENTO_", "LEY_"]:
        if tipo.startswith(pref):
            tipo = tipo[len(pref):]
            break
    if not tipo:
        tipo = "DOC"
    return f"FASP_2026_P1_NAL_{clave}_{tipo}_V1.0.pdf"


def process_carpeta_federal(clave: str, display: str, folder_id: str,
                            destino_subcarpeta: str, seen: dict,
                            dry_run: bool = False, force_ids: set = None) -> dict:
    """Sincroniza una carpeta federal (Bibliografía o Normatividad federal)."""
    stats = {"nuevos": 0, "ya_vistos": 0, "errores": 0, "omitidos": 0, "detalles": []}
    force_ids = force_ids or set()

    print(f"\n=== NAL/{display}  folder={folder_id[:12]}... ===")

    try:
        all_files = list(drive_list(folder_id, recursive=True))
    except Exception as e:
        print(f"  ✗ Error listando carpeta: {e}", file=sys.stderr)
        stats["errores"] += 1
        return stats

    candidates = [f for f in all_files if is_pdf(f) and not is_excluded(f["name"])]

    if not candidates:
        print(f"  (sin PDFs nuevos)")
        return stats

    for f in candidates:
        fid = f["id"]
        fname = f["name"]
        mtime = f.get("modifiedTime", "")

        prev = seen.get(fid)
        if fid in force_ids:
            needs_process = True
            reason = "forced"
        elif prev is None:
            needs_process = True
            reason = "nuevo"
        else:
            stats["ya_vistos"] += 1
            print(f"  ↻ (ya visto, hash={prev['hash'][:12]}…) {fname}")
            continue

        target_name = _infer_target_name_federal(fname, clave)
        # Las carpetas federales se depositan bajo NAL/<display>/
        corpus_dir = FASP_CORPUS_ROOT / "Normatividad federal" / destino_subcarpeta / "corpus"
        jobs_dir = FASP_CORPUS_ROOT / "Normatividad federal" / destino_subcarpeta / "jobs"
        corpus_dir.mkdir(parents=True, exist_ok=True)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        local_pdf = corpus_dir / target_name

        if dry_run:
            print(f"  [dry-run] {reason}: {fname} -> {target_name}")
            stats["nuevos"] += 1
            seen[fid] = {"hash": "(dry-run)", "name": fname, "edo": f"NAL-{clave}",
                         "target": target_name, "mtime": mtime, "downloaded_at": None}
            continue

        try:
            drive_download(fid, local_pdf)
        except Exception as e:
            print(f"  ✗ Error descargando {fname}: {e}", file=sys.stderr)
            stats["errores"] += 1
            continue

        h = hash_file(local_pdf)
        seen[fid] = {
            "hash": h,
            "name": fname,
            "edo": f"NAL-{clave}",
            "target": target_name,
            "mtime": mtime,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "size": local_pdf.stat().st_size,
        }
        stats["nuevos"] += 1
        print(f"  ↓ {reason}: {fname} -> {target_name}  ({local_pdf.stat().st_size:,} bytes)")

        # Convertir PDF -> MD
        try:
            job_id = f"fasp_NAL_{clave}_{local_pdf.stem}_{h[:8]}"
            cmd = [
                sys.executable, str(PDF_TO_MD),
                "--input", str(local_pdf),
                "--output", str(jobs_dir),
                "--job-id", job_id,
                "--prompt", "v1",
                "--layer", "normativo" if clave == "NORFED" else "bibliografico",
                "--user-id", "fasp-sync",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"    ⚠ pdf_to_md.py exit {result.returncode}: {result.stderr[:200]}")
            else:
                md_path = jobs_dir / f"{job_id}.md"
                if md_path.exists():
                    rel = md_path.relative_to(FASP_CORPUS_ROOT)
                    print(f"    ✓ MD: {rel}")
                else:
                    print(f"    ⚠ No se generó MD esperado en {md_path}")
            stats["detalles"].append({"fid": fid, "target": target_name,
                                      "job_id": job_id, "md": str(jobs_dir / f"{job_id}.md")})
        except Exception as e:
            print(f"    ⚠ Error en conversión: {e}")
            stats["errores"] += 1

    return stats


def main():
    ap = argparse.ArgumentParser(description="Sincronizar PDFs de FASP desde Drive")
    ap.add_argument("--edo",
                    help="Solo procesar este destino: NAL, MEX, HID, MIC, QRO, CHI, TAB, TAM, ZAC, BIB, NORFED")
    ap.add_argument("--dry-run", action="store_true", help="Solo listar, no descargar ni convertir")
    ap.add_argument("--force", action="append", default=[],
                    help="Forzar reprocesamiento de un file_id (repetible)")
    ap.add_argument("--reset-seen", action="store_true", help="Borrar la tabla de hashes y empezar de cero")
    args = ap.parse_args()

    if not TOKEN_PATH.exists():
        print(f"ERROR: no hay token en {TOKEN_PATH}", file=sys.stderr)
        sys.exit(2)
    if not PDF_TO_MD.exists():
        print(f"ERROR: pdf_to_md.py no encontrado en {PDF_TO_MD}", file=sys.stderr)
        sys.exit(2)

    if args.reset_seen and SEEN_FILE.exists():
        SEEN_FILE.unlink()
        print(f"⚠ Tabla de hashes borrada: {SEEN_FILE}")

    seen = load_seen()
    print(f"📋 Tabla de hashes: {len(seen)} archivos conocidos en {SEEN_FILE}")

    force_ids = set(args.force)

    total = {"nuevos": 0, "ya_vistos": 0, "errores": 0, "omitidos": 0}

    # Estados (incluye NAL que apunta a la raiz 00 Bibliografía y normatividad federal)
    estados_targets = ESTADOS if not args.edo else (
        {args.edo: ESTADOS[args.edo]} if args.edo in ESTADOS else {}
    )
    for edo, (name, fid) in estados_targets.items():
        stats = process_estado(edo, name, fid, seen, dry_run=args.dry_run, force_ids=force_ids)
        for k in total:
            total[k] += stats.get(k, 0)

    # Carpetas federales (Bibliografía, Normatividad federal)
    fed_targets = []
    if not args.edo:
        fed_targets = CARPETAS_FEDERALES
    elif args.edo in ("BIB", "NORFED"):
        fed_targets = [t for t in CARPETAS_FEDERALES if t[0] == args.edo]

    for clave, display, fid, destino in fed_targets:
        stats = process_carpeta_federal(
            clave, display, fid, destino, seen,
            dry_run=args.dry_run, force_ids=force_ids,
        )
        for k in total:
            total[k] += stats.get(k, 0)

    save_seen(seen)

    print(f"\n=== RESUMEN ===")
    print(f"  Nuevos:      {total['nuevos']}")
    print(f"  Ya vistos:   {total['ya_vistos']}")
    print(f"  Omitidos:    {total['omitidos']}  (FASP Registro Normatividad.xlsx)")
    print(f"  Errores:     {total['errores']}")
    print(f"  Tabla:       {SEEN_FILE}  ({len(seen)} archivos)")
    print(f"  Corpus:      {FASP_CORPUS_ROOT}")


if __name__ == "__main__":
    main()
