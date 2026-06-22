#!/usr/bin/env python3
"""
generar_licencia.py — Genera un archivo de licencia Pro para un cliente.

Uso:
    python scripts/generar_licencia.py cliente@empresa.com
    # Imprime el JSON en pantalla.

    python scripts/generar_licencia.py cliente@empresa.com --out cliente.json
    # Guarda el archivo.

Después enviás el archivo al cliente y él lo copia a ~/.api-explorer-license
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Permitimos ejecutar este script directamente sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from explorer.licencia import generar_firma  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(
        prog="generar-licencia",
        description="Genera una licencia Pro para api-explorer.",
    )
    p.add_argument("email", help="Email del cliente (ej. juan@empresa.com)")
    p.add_argument("--out", metavar="ARCHIVO",
                   help="Ruta donde guardar la licencia (default: stdout)")
    args = p.parse_args()

    issued = date.today().isoformat()
    sig = generar_firma(args.email, "pro", issued)

    licencia = {
        "email": args.email,
        "tier": "pro",
        "issued": issued,
        "sig": sig,
    }

    texto = json.dumps(licencia, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(texto, encoding="utf-8")
        print(f"[OK] Licencia guardada en {args.out}", file=sys.stderr)
        print(f"[OK] Para activar: el cliente debe copiar a "
              f"~/.api-explorer-license", file=sys.stderr)
    else:
        print(texto)


if __name__ == "__main__":
    main()
