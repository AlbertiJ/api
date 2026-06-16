#!/usr/bin/env python3
"""
cli.py — Entry point de línea de comando.

Uso:
    python cli.py --url http://api.cliente.com/datos --responsable "Juan" --cliente "Biblioteca San Martín"
    python cli.py --url http://api.cliente.com --formato todos
    python cli.py --demo   (usa JSON de ejemplo)
"""
import argparse
import sys
from pathlib import Path

from inspector.core import inspeccionar, ErrorInspeccion


def main():
    p = argparse.ArgumentParser(
        prog="api-inspector",
        description="Auditor forense de migración de datos entre APIs/DBs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python cli.py --url http://api.cliente.com --responsable "Juan Alberti" --cliente "Natatorio Olivos"
  python cli.py --demo
  python cli.py --url https://api.example.com --formato todos
        """,
    )
    p.add_argument("--url", help="URL de la API a inspeccionar")
    p.add_argument("--responsable", default="no_especificado", help="Quién corre la auditoría")
    p.add_argument("--cliente", default="no_especificado", help="Cliente dueño de la DB")
    p.add_argument(
        "--formato",
        choices=["json", "csv", "html", "todos"],
        default="todos",
        help="Formato de exportación (default: todos)",
    )
    p.add_argument(
        "--salida",
        default="salidas",
        help="Directorio donde guardar los archivos (default: salidas)",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Correr con un JSON de ejemplo (ejemplos/natatorio.json)",
    )

    args = p.parse_args()

    if not args.url and not args.demo:
        p.print_help()
        sys.exit(1)

    if args.demo:
        ruta_demo = Path(__file__).parent / "ejemplos" / "natatorio.json"
        if not ruta_demo.exists():
            print(f"❌ No encuentro el archivo demo: {ruta_demo}")
            sys.exit(1)
        # Levanta un mini server? No, leemos el archivo y lo parseamos.
        import json
        from inspector.core import _descargar, _calcular_hash
        from inspector.detectar import detectar_tipo_api
        from inspector.campos import inspeccionar_campos, detectar_faltantes
        from inspector.sensibles import detectar_pii, evaluar_menores
        from inspector.exportar import exportar_json, exportar_csv, exportar_html
        from inspector.informe import generar_informe
        from datetime import datetime, timezone

        with open(ruta_demo, "r", encoding="utf-8") as f:
            data = json.load(f)

        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        tipo, conf, pistas = detectar_tipo_api(data, "natatorio")
        estructura = inspeccionar_campos(data)
        pii = detectar_pii(data)
        menores = evaluar_menores(data, pii, tipo)
        faltantes = detectar_faltantes(estructura, tipo)

        payload = {
            "url": f"file://{ruta_demo}",
            "timestamp_utc": timestamp,
            "responsable": args.responsable,
            "cliente": args.cliente,
            "tipo_detectado": tipo,
            "confianza_deteccion": conf,
            "pistas_deteccion": pistas,
            "estructura": estructura,
            "pii_detectado": pii,
            "reglas_menores": menores,
            "faltantes_reportados": faltantes,
            "resumen": {
                "total_registros": estructura.get("total_registros", 0),
                "total_campos": estructura.get("total_campos_unicos", 0),
                "campos_faltantes": len(faltantes),
                "datos_sensibles_encontrados": pii.get("total_hallazgos", 0),
                "menores_detectados": menores.get("total_menores", 0),
            },
        }
        hash_aud = _calcular_hash(payload)
        payload["hash_sha256"] = hash_aud

        rutas = []
        if args.formato in ("json", "todos"):
            rutas.append(exportar_json(payload, args.salida))
        if args.formato in ("csv", "todos"):
            rutas.append(exportar_csv(payload, args.salida))
        if args.formato in ("html", "todos"):
            rutas.append(exportar_html(payload, args.salida))

        payload["_rutas_generadas"] = rutas
        informe = generar_informe(payload)
        print(informe)
        return

    try:
        resultado = inspeccionar(
            url=args.url,
            responsable=args.responsable,
            cliente=args.cliente,
            exportar_a=args.formato,
            directorio_salida=args.salida,
        )
        resultado["auditoria"]["_rutas_generadas"] = resultado["archivos_generados"]
        print(generar_informe(resultado["auditoria"]))
    except ErrorInspeccion as e:
        print(f"❌ Error de inspección: {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n⛔ Cancelado por el usuario.")
        sys.exit(130)


if __name__ == "__main__":
    main()
