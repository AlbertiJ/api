"""
core.py — Punto de entrada del recorrido sobre una API.

Recibe una URL, descarga la respuesta (con paginación si corresponde),
dispara todos los análisis y devuelve un informe firmado con SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import logging
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .campos import detectar_faltantes, inspeccionar_campos
from .config import CFG, esperar
from .detectar import detectar_tipo_api
from .exportar import exportar_csv, exportar_html, exportar_json
from .informe import generar_informe
from .paginacion import (
    descargar_con_paginacion,
    ErrorDescarga,
)
from .sensibles import detectar_pii, evaluar_menores

# Logger del módulo. Va a stderr. El usuario puede redirigirlo.
# Formato simple: timestamp | nivel | mensaje
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api-explorer")


class ErrorExploracion(Exception):
    """Se lanza cuando algo en la exploración falla de manera esperada."""


# Headers HTTP. Mantenemos Accept por las dudas y un User-Agent explícito.
# No nos hacemos pasar por navegador: somos lo que decimos ser, pero
# hablamos HTTP como un cliente maduro.
_HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "User-Agent": CFG.user_agent,
}


def _calcular_hash(payload_auditoria: Dict[str, Any]) -> str:
    """Hash SHA-256 sobre el payload canónico (claves ordenadas, UTF-8)."""
    canonico = json.dumps(
        payload_auditoria, sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def explorar(
    url: str,
    responsable: str = "no_especificado",
    cliente: str = "no_especificado",
    formato: str = "todos",
    directorio_salida: str = "salidas",
    campos_oficiales: Optional[List[str]] = None,
    auditoria_previa_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recorre una API pública y devuelve un mapa firmado de su estructura.

    Args:
        url: endpoint a explorar.
        responsable: nombre de quien corre la exploración.
        cliente: nombre del dueño de la API (para el informe).
        formato: 'json', 'csv', 'html' o 'todos'.
        directorio_salida: carpeta donde dejar los archivos.
        campos_oficiales: lista opcional de campos esperados (gap analysis).
        auditoria_previa_hash: si se encadena con una corrida anterior,
            se incluye en el hash final para detectar manipulación.

    Returns:
        Diccionario con la exploración completa + rutas de archivos.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    log.info("Iniciando exploración de %s (responsable=%s, cliente=%s)",
             url, responsable, cliente)

    # 1) Descargar (con paginación si la API la ofrece)
    try:
        data, meta_pag = descargar_con_paginacion(url, timeout=CFG.timeout)
    except ErrorDescarga as e:
        log.error("Descarga fallida: %s", e)
        raise ErrorExploracion(f"No pude conectar a {url}: {e}") from e

    ct = meta_pag.get("content_type", "")
    log.info("Descarga OK — content_type=%r, paginas=%s, total_registros=%s",
             ct, meta_pag.get("paginas_seguidas", 0),
             meta_pag.get("total_registros_reales"))

    # 2) Detectar el tipo de API
    tipo, confianza, pistas = detectar_tipo_api(data, url)
    log.info("Tipo detectado: %s (confianza %.2f)", tipo, confianza)

    # 3) Recorrer la estructura de campos
    estructura = inspeccionar_campos(data)

    # 4) Detectar datos sensibles (PII).
    # Le pasamos el content_type para que skipee si la respuesta no fue JSON
    # (caso real: el explorador contra clientes.credicuotas.com.ar detectó
    # "dni" en el HTML del home como PII — falso positivo arreglado).
    pii = detectar_pii(data, content_type=ct)
    if "skipped_reason" in pii:
        log.warning("PII skipeada: %s", pii["skipped_reason"])
    else:
        log.info("PII detectada: %d hallazgos", pii.get("total_hallazgos", 0))

    # 5) Evaluar reglas de menores si aplica
    menores = evaluar_menores(data, pii, tipo)
    if menores.get("alerta_menores"):
        log.warning("Alerta de menores: %d detectados, faltan %d campos de responsable",
                    menores.get("total_menores", 0),
                    len(menores.get("campos_responsable_faltantes", [])))

    # 6) Detectar campos faltantes contra el patrón del tipo detectado
    faltantes = detectar_faltantes(estructura, tipo)
    log.info("Campos faltantes respecto al patrón '%s': %d", tipo, len(faltantes))

    # 7) Componer el payload firmado
    payload = {
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
        "metadata_paginacion": meta_pag,
        "cadena_auditoria_previa": auditoria_previa_hash,
        "resumen": {
            "total_registros_reales": meta_pag.get("total_registros_reales", 0),
            "total_registros_analizados": meta_pag.get(
                "total_registros_analizados", estructura.get("total_registros", 0)
            ),
            "total_campos": estructura.get("total_campos_unicos", 0),
            "campos_faltantes": len(faltantes),
            "datos_sensibles_encontrados": pii.get("total_hallazgos", 0),
            "menores_detectados": menores.get("total_menores", 0),
            "fuente_paginacion": meta_pag.get("fuente_paginacion", "ninguna"),
            "pausa_entre_requests": CFG.pausa_minima,
        },
    }

    # 8) Hash SHA-256 sobre todo el payload
    payload["hash_sha256"] = _calcular_hash(payload)

    # 9) Exportar a los formatos pedidos
    rutas = []
    if formato in ("json", "todos"):
        rutas.append(exportar_json(payload, directorio_salida))
    if formato in ("csv", "todos"):
        rutas.append(exportar_csv(payload, directorio_salida))
    if formato in ("html", "todos"):
        rutas.append(exportar_html(payload, directorio_salida))

    # 10) Informe legible para consola
    informe = generar_informe(payload)

    return {
        "exploracion": payload,
        "informe_texto": informe,
        "archivos_generados": rutas,
    }


# Alias retrocompatible. Mantener nombre viejo evita romper
# consumidores externos que ya importaban la función vieja.
inspeccionar = explorar