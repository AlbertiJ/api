#!/usr/bin/env python3
"""
cli.py — Punto de entrada de línea de comando.

Uso:
    python cli.py --url http://api.cliente.com/datos --responsable "Juan" --cliente "Biblioteca San Martín"
    python cli.py --url http://api.cliente.com --formato todos
    python cli.py --demo
    python cli.py --url https://api.example.com --diff-con auditoria_vieja.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from explorer.core import ErrorExploracion, explorar
from explorer.diff import diff_forense, encadenar_hash, formatear_diff_texto
from explorer.informe import generar_informe


# ───────────────────── Tier Free: lista permitida ─────────────────────
# El tier Free solo puede explorar estas APIs públicas (mismas que el
# Manual 02). Cualquier otra URL requiere Pro ($20) o un archivo de
# licencia válido en el HOME del usuario.
FREE_ALLOWED_DOMAINS = frozenset({
    "jsonplaceholder.typicode.com",
    "randomuser.me",
    "dummyjson.com",
    "reqres.in",
})

URL_PARA_COMPRAR_PRO = "https://github.com/sponsors/AlbertiJ"  # placeholder


def _dominio_de_url(url: str) -> str:
    """Devuelve solo el netloc (dominio) de una URL, en minúsculas."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _tener_licencia_pro() -> tuple[bool, str]:
    """
    Devuelve (valida, mensaje) según el archivo `~/.api-explorer-license`.

    La firma se valida con HMAC-SHA256. Si el archivo no existe, devuelve
    (False, mensaje). Si existe pero la firma no coincide, también
    devuelve False con un mensaje específico (no damos pistas de si el
    formato está mal o la firma está mal — eso es bueno para no filtrar
    info a un atacante).
    """
    from explorer.licencia import validar_licencia_pro
    return validar_licencia_pro()


def _validar_acceso_url(url: str) -> tuple[bool, str]:
    """
    Decide si el usuario puede explorar esta URL bajo el tier actual.
    Devuelve (puede, motivo).
    """
    dominio = _dominio_de_url(url)

    if dominio in FREE_ALLOWED_DOMAINS:
        return True, f"Free — dominio {dominio} en lista permitida"

    licencia_valida, _msg = _tener_licencia_pro()
    if licencia_valida:
        return True, "Pro — licencia válida"

    return False, (
        f"el dominio '{dominio or '(inválido)'}' no está en la lista "
        f"permitida del tier Free"
    )


def _demo(args, ruta_demo: Path) -> None:
    """Carga un JSON de ejemplo y corre la exploración sobre él."""
    with open(ruta_demo, "r", encoding="utf-8") as f:
        data = json.load(f)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    # Importamos aquí para no cargar todo si no se usa el demo.
    from explorer.campos import detectar_faltantes, inspeccionar_campos
    from explorer.core import _calcular_hash
    from explorer.detectar import detectar_tipo_api
    from explorer.exportar import exportar_csv, exportar_html, exportar_json
    from explorer.sensibles import detectar_pii, evaluar_menores

    tipo, conf, pistas = detectar_tipo_api(data, "demo")
    estructura = inspeccionar_campos(data)
    # El demo siempre lee un archivo local JSON, así que pasamos
    # 'application/json' explícito para que la detección de PII corra.
    pii = detectar_pii(data, content_type="application/json")
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
        "metadata_paginacion": {
            "fuente_paginacion": "ninguna",
            "paginas_seguidas": 1,
            "total_registros_reales": estructura.get("total_registros", 0),
            "total_registros_analizados": estructura.get("total_registros", 0),
            "max_alcanzado": False,
        },
        "cadena_auditoria_previa": None,
        "resumen": {
            "total_registros_reales": estructura.get("total_registros", 0),
            "total_registros_analizados": estructura.get("total_registros", 0),
            "total_campos": estructura.get("total_campos_unicos", 0),
            "campos_faltantes": len(faltantes),
            "datos_sensibles_encontrados": pii.get("total_hallazgos", 0),
            "menores_detectados": menores.get("total_menores", 0),
            "fuente_paginacion": "ninguna",
            "pausa_entre_requests": 0,
        },
    }
    payload["hash_sha256"] = _calcular_hash(payload)

    rutas = []
    if args.formato in ("json", "todos"):
        rutas.append(exportar_json(payload, args.salida))
    if args.formato in ("csv", "todos"):
        rutas.append(exportar_csv(payload, args.salida))
    if args.formato in ("html", "todos"):
        rutas.append(exportar_html(payload, args.salida))

    payload["_rutas_generadas"] = rutas
    print(generar_informe(payload))

    if args.diff_con:
        _aplicar_diff(args, payload)


def _aplicar_diff(args, payload_actual: Dict) -> None:
    """Si se pasó --diff-con, carga la previa y muestra el diff."""
    ruta_previa = Path(args.diff_con)
    if not ruta_previa.exists():
        print(f"❌ No encuentro el archivo previo: {ruta_previa}")
        return
    with open(ruta_previa, "r", encoding="utf-8") as f:
        payload_previo = json.load(f)
    diff = diff_forense(payload_actual, payload_previo)
    print()
    print(formatear_diff_texto(diff))


def main() -> None:
    p = argparse.ArgumentParser(
        prog="api-explorer",
        description=(
            "Explorador de APIs públicas: mapea estructura, detecta datos "
            "sensibles, sigue paginación y emite un informe firmado con SHA-256."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python cli.py --url https://api.example.com --responsable "Juan" --cliente "Cliente X"
  python cli.py --demo
  python cli.py --url https://api.example.com --formato html
  python cli.py --url https://api.example.com --diff-con salidas/vieja.json
        """,
    )
    p.add_argument("--url", help="URL de la API a explorar")
    p.add_argument("--responsable", default="no_especificado",
                   help="Quién corre la exploración")
    p.add_argument("--cliente", default="no_especificado",
                   help="Cliente dueño de la API")
    p.add_argument("--formato", choices=["json", "csv", "html", "todos"],
                   default="todos", help="Formato de exportación")
    p.add_argument("--salida", default="salidas",
                   help="Directorio donde guardar los archivos")
    p.add_argument("--demo", action="store_true",
                   help="Correr con el JSON de ejemplos/natatorio.json")
    p.add_argument("--diff-con", metavar="ARCHIVO_JSON",
                   help="Compara el resultado con una exploración previa")
    p.add_argument("--pausa-min", type=float, default=None,
                   help="Pausa mínima entre requests en segundos (override)")
    p.add_argument("--pausa-max", type=float, default=None,
                   help="Pausa máxima entre requests en segundos (override)")
    p.add_argument("--max-registros", type=int, default=None,
                   help="Tope absoluto de registros a analizar")
    # Nuevos flags (v0.3.0)
    p.add_argument("--discover", action="store_true",
                   help="Solo hacer recon de superficie (no analiza)")
    p.add_argument("--pipeline", action="store_true",
                   help="Pipeline completo: recon + análisis + informe consolidado")
    p.add_argument("--auth-bearer", metavar="TOKEN", default=None,
                   help="Bearer token para endpoints protegidos")
    p.add_argument("--auth-header", action="append", default=[],
                   metavar="CLAVE:VALOR",
                   help="Custom header (repetible). Ej: --auth-header 'Origin:https://www.ejemplo.com'")
    p.add_argument("--recon-paths", metavar="ARCHIVO", default=None,
                   help="Archivo con paths custom para recon (uno por línea)")
    p.add_argument("--max-endpoints", type=int, default=5,
                   help="Máximo de endpoints a analizar en modo --pipeline")
    # Nuevos flags (v0.4.0): template-driven discovery
    p.add_argument("--template", metavar="PLANTILLA", default=None,
                   help="Plantilla con variables para discovery dinámico. "
                        "Ej: '/v1/:modulo/:accion'. "
                        "Combinar con --slot-values para acotar la búsqueda.")
    p.add_argument("--slot-values", metavar="JSON", default=None,
                   help="Valores por slot, en JSON. "
                        'Ej: \'{"modulo":["users","products"],"accion":["list","get"]}\'. '
                        "Si no se pasa, se usan los valores default de reglas/plantillas.json.")
    p.add_argument("--max-combinaciones", type=int, default=None,
                   help="Tope de combinaciones a probar en modo --template "
                        "(default: sin tope).")

    args = p.parse_args()

    # Overrides de configuración desde CLI
    if args.pausa_min is not None or args.pausa_max is not None or args.max_registros is not None:
        from explorer import config as _cfg_mod
        object.__setattr__(_cfg_mod.CFG, "pausa_minima",
                          args.pausa_min if args.pausa_min is not None else _cfg_mod.CFG.pausa_minima)
        object.__setattr__(_cfg_mod.CFG, "pausa_maxima",
                          args.pausa_max if args.pausa_max is not None else _cfg_mod.CFG.pausa_maxima)
        if args.max_registros is not None:
            object.__setattr__(_cfg_mod.CFG, "max_registros", args.max_registros)

    if not args.url and not args.demo:
        p.print_help()
        sys.exit(1)

    # Parsear custom headers
    custom_headers = {}
    for h in args.auth_header:
        if ":" in h:
            k, v = h.split(":", 1)
            custom_headers[k.strip()] = v.strip()

    # Validar acceso según tier (Free vs Pro).
    # --demo y --url sin valor pasan siempre.
    if args.url and not args.demo:
        puede, motivo = _validar_acceso_url(args.url)
        if not puede:
            print(f"🔒 Acceso denegado: {motivo}.")
            print()
            print("Tier Free solo permite explorar estas APIs públicas:")
            for d in sorted(FREE_ALLOWED_DOMAINS):
                print(f"  · https://{d}")
            print()

            # Si hay archivo de licencia pero es inválido, decirlo explícito
            ruta_licencia = Path.home() / ".api-explorer-license"
            if ruta_licencia.exists():
                from explorer.licencia import validar_licencia_en_archivo
                _valida, msg = validar_licencia_en_archivo(ruta_licencia)
                print(f"⚠ Encontramos un archivo de licencia en HOME pero no es válido:")
                print(f"   {msg}")
                print()

            print(f"Para explorar cualquier URL, comprá Pro ($20 one-time):")
            print(f"  {URL_PARA_COMPRAR_PRO}")
            print()
            print("Si ya tenés Pro, asegurate de tener el archivo válido "
                  "~/.api-explorer-license en tu HOME.")
            sys.exit(3)
        else:
            print(f"✓ Acceso {motivo}.")
            print()

    if args.demo:
        ruta_demo = Path(__file__).parent / "ejemplos" / "natatorio.json"
        if not ruta_demo.exists():
            print(f"❌ No encuentro el archivo demo: {ruta_demo}")
            sys.exit(1)
        _demo(args, ruta_demo)
        return

    # MODO --discover: solo recon
    if args.discover:
        from explorer.discovery import discover, format_discovery_report
        from explorer.fetcher import FetcherConfig
        paths = None
        if args.recon_paths:
            with open(args.recon_paths, "r", encoding="utf-8") as f:
                paths = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        cfg = FetcherConfig()
        print(f"🔍 RECON: {args.url}")
        result = discover(
            base_url=args.url,
            paths=paths,
            cfg=cfg,
            bearer=args.auth_bearer,
            custom_headers=custom_headers or None,
            delay_between=args.pausa_min or 0.0,
            do_options=True,
            progress=True,
        )
        print()
        print(format_discovery_report(result))
        # Guardar JSON firmado
        import hashlib
        canonico = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str)
        result["hash_sha256"] = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = Path(args.salida) / f"recon-{timestamp}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\n[OK] Guardado en: {out_path}")
        return

    # MODO --template: discovery dinámico por plantilla con variables
    if args.template:
        from explorer.discovery import (
            _load_plantillas_default,
            descubrir_por_template,
            format_template_report,
        )
        from explorer.fetcher import FetcherConfig
        from explorer.templates import cargar_slot_values_desde_json

        # Parsear slot_values: --slot-values '{"modulo":["users"]}' o usar default
        slot_values = None
        if args.slot_values:
            try:
                slot_values = cargar_slot_values_desde_json(json.loads(args.slot_values))
            except (json.JSONDecodeError, ValueError) as e:
                print(f"❌ --slot-values inválido: {e}")
                print("   Formato: '{\"modulo\":[\"users\",\"products\"]}'")
                sys.exit(1)
        else:
            # Cargar valores default del JSON
            _, slot_values = _load_plantillas_default()

        cfg = FetcherConfig()
        print(f"🔍 TEMPLATE DISCOVERY: {args.url}")
        print(f"   Plantilla: {args.template}")
        result = descubrir_por_template(
            base_url=args.url,
            plantilla=args.template,
            slot_values=slot_values,
            cfg=cfg,
            bearer=args.auth_bearer,
            custom_headers=custom_headers or None,
            delay_between=args.pausa_min or 0.0,
            max_combinaciones=args.max_combinaciones,
            progress=True,
        )
        print()
        print(format_template_report(result))
        # Guardar JSON firmado
        import hashlib
        canonico = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str)
        result["hash_sha256"] = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = Path(args.salida) / f"template-discovery-{timestamp}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\n[OK] Guardado en: {out_path}")
        return

    # MODO --pipeline: recon + analyze + informe consolidado
    if args.pipeline:
        from explorer.pipeline import run_pipeline, format_pipeline_informe
        from explorer.fetcher import FetcherConfig
        cfg = FetcherConfig()
        result = run_pipeline(
            base_url=args.url,
            responsable=args.responsable,
            cliente=args.cliente,
            cfg=cfg,
            bearer=args.auth_bearer,
            origin=custom_headers.get("Origin"),
            max_endpoints_to_analyze=args.max_endpoints,
            delay_between=args.pausa_min or 0.5,
            do_discovery=True,
            do_analyze=True,
            progress=True,
        )
        print()
        print(format_pipeline_informe(result))
        # Guardar JSON firmado
        from dataclasses import asdict
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = Path(args.salida) / f"pipeline-{timestamp}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\n[OK] Guardado en: {out_path}")
        return

    try:
        resultado = explorar(
            url=args.url,
            responsable=args.responsable,
            cliente=args.cliente,
            formato=args.formato,
            directorio_salida=args.salida,
        )
        resultado["exploracion"]["_rutas_generadas"] = resultado["archivos_generados"]
        print(generar_informe(resultado["exploracion"]))

        if args.diff_con:
            _aplicar_diff(args, resultado["exploracion"])

    except ErrorExploracion as e:
        # Mensajes específicos por tipo de error para que el usuario sepa
        # qué pasó sin tener que pegarse con el stacktrace.
        msg = str(e).lower()
        if "404" in msg or "not found" in msg:
            print(f"❌ 404 — La URL {args.url} no existe en el servidor.")
            print("   Sugerencias:")
            print("   • Verificá la URL (typo, mayúsculas, slash final)")
            print("   • Probá primero con --recon para ver qué endpoints existen")
            print("   • Algunas APIs devuelven 404 si falta header Authorization")
        elif "403" in msg or "forbidden" in msg:
            print(f"❌ 403 — El servidor rechazó la petición a {args.url}.")
            print("   Sugerencias:")
            print("   • La API probablemente requiere autenticación")
            print("   • Probá con --auth-bearer TOKEN si tenés un token")
            print("   • Algunas APIs bloquean por User-Agent — estamos usando api-explorer/0.3")
        elif "401" in msg or "unauthorized" in msg:
            print(f"❌ 401 — La API requiere autenticación.")
            print("   Sugerencias:")
            print("   • Pasá --auth-bearer <token>")
            print("   • O configurá Authorization en el header custom")
        elif "timeout" in msg or "timed out" in msg:
            print(f"❌ Timeout — La API tardó más de {30}s en responder.")
            print("   Sugerencias:")
            print("   • La API está lenta o caída")
            print("   • Subí las pausas: --pausa-min 3 --pausa-max 6")
        elif "ssl" in msg or "certificate" in msg:
            print(f"❌ Error SSL al conectar a {args.url}.")
            print("   Sugerencias:")
            print("   • El certificado puede estar vencido o autofirmado")
            print("   • Si es una API interna de tu empresa, es esperable")
        elif "name or service not known" in msg or "no such host" in msg or "dns" in msg:
            print(f"❌ No se pudo resolver el DNS de {args.url}.")
            print("   Sugerencias:")
            print("   • Verificá que el dominio esté bien escrito")
            print("   • Si es una API interna, estás fuera de la VPN/red")
        elif "connection refused" in msg:
            print(f"❌ Conexión rechazada por {args.url}.")
            print("   Sugerencias:")
            print("   • El servidor puede estar caído")
            print("   • Verificá el puerto (¿http o https?)")
        else:
            print(f"❌ Error de exploración: {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n⛔ Cancelado por el usuario.")
        sys.exit(130)


if __name__ == "__main__":
    main()