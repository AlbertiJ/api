"""
core.py — Motor principal del inspector.
Conecta a una URL, descarga la respuesta, dispara todos los análisis.
"""
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import socket

from .detectar import detectar_tipo_api
from .campos import inspeccionar_campos, detectar_faltantes
from .sensibles import detectar_pii, evaluar_menores
from .exportar import exportar_json, exportar_csv, exportar_html
from .informe import generar_informe


class ErrorInspeccion(Exception):
    pass


def _descargar(url: str, timeout: int = 15) -> Any:
    """Descarga el contenido de la URL y devuelve data parseada o string."""
    try:
        req = Request(url, headers={"User-Agent": "API-Inspector/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except (URLError, HTTPError, socket.timeout) as e:
        raise ErrorInspeccion(f"No pude conectar a {url}: {e}")

    # Intentar JSON primero
    if "json" in content_type or raw.strip().startswith((b"{", b"[")):
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise ErrorInspeccion(f"La URL devolvió algo que no es JSON válido: {e}")

    # Si no es JSON, devolver texto crudo (HTML o CSV)
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return raw


def _calcular_hash(payload_auditoria: Dict[str, Any]) -> str:
    """Hash SHA-256 sobre los datos forenses de la auditoría."""
    canonico = json.dumps(payload_auditoria, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def inspeccionar(
    url: str,
    responsable: str = "no_especificado",
    cliente: str = "no_especificado",
    exportar_a: str = "json",
    directorio_salida: str = "salidas",
    payload_post: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Función principal. Inspecciona una URL-API y devuelve el informe completo.

    Args:
        url: Endpoint a inspeccionar.
        responsable: Quién corre la auditoría (vos / tu nombre / tu tool).
        cliente: Nombre del cliente dueño de la DB.
        exportar_a: 'json', 'csv', 'html' o 'todos'.
        directorio_salida: dónde guardar los archivos generados.

    Returns:
        Dict con toda la auditoría + rutas de archivos generados.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    # 1) Descargar
    data = _descargar(url)

    # 2) Detectar tipo de API
    tipo, confianza, pistas = detectar_tipo_api(data, url)

    # 3) Inspeccionar estructura de campos
    estructura = inspeccionar_campos(data)

    # 4) Detectar PII / sensibles
    pii = detectar_pii(data)

    # 5) Evaluar reglas de menores (si aplica)
    menores = evaluar_menores(data, pii, tipo)

    # 6) Detectar campos faltantes según el tipo detectado
    faltantes = detectar_faltantes(estructura, tipo)

    # 7) Componer payload forense
    payload_auditoria = {
        "url": url,
        "timestamp_utc": timestamp,
        "responsable": responsable,
        "cliente": cliente,
        "tipo_detectado": tipo,
        "confianza_deteccion": confianza,
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

    # 8) Calcular hash
    hash_auditoria = _calcular_hash(payload_auditoria)
    payload_auditoria["hash_sha256"] = hash_auditoria

    # 9) Exportar
    rutas = []
    if exportar_a in ("json", "todos"):
        rutas.append(exportar_json(payload_auditoria, directorio_salida))
    if exportar_a in ("csv", "todos"):
        rutas.append(exportar_csv(payload_auditoria, directorio_salida))
    if exportar_a in ("html", "todos"):
        rutas.append(exportar_html(payload_auditoria, directorio_salida))

    # 10) Informe forense (texto en pantalla)
    informe = generar_informe(payload_auditoria)

    return {
        "auditoria": payload_auditoria,
        "informe_texto": informe,
        "archivos_generados": rutas,
    }
