"""
paginacion.py — Descarga siguiendo paginación de la API destino.

Soporta tres estilos comunes:
  - GitHub-style: header `Link: <url>; rel="next"`
  - Body cursor/next: `{"next": "https://..."}` o `{"next_cursor": "..."}`
  - Page-based: `{"page": N, "total": T, "data": [...]}`
  - results-based: `{"count": T, "results": [...], "next": "..."}`

Toda la descarga pasa por esperar() para mantener un ritmo humano.
"""
from __future__ import annotations

import json
import re
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import CFG, esperar, esperar_entre_paginas


class ErrorDescarga(Exception):
    pass


def _intentar_json(raw: bytes, content_type: str) -> Optional[Any]:
    """Devuelve el JSON parseado o None si no se puede."""
    if "json" not in content_type and not raw.strip().startswith((b"{", b"[")):
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def _parsear_link_next(header_link: str) -> Optional[str]:
    """
    GitHub style: `Link: <https://api.x.com/v1/items?page=2>; rel="next"`.
    Devuelve la URL del next si la encuentra.
    """
    if not header_link:
        return None
    match = re.search(r'<([^>]+)>;\s*rel="next"', header_link)
    return match.group(1) if match else None


def _acumular_pagina(
    body: Any,
    data_total: List[Any],
    meta: Dict[str, Any],
) -> Optional[str]:
    """
    Recibe el body parseado de UNA página, agrega a data_total,
    actualiza meta y devuelve la siguiente URL a pedir (o None si no hay).
    """
    if isinstance(body, list):
        # Lista pelada: una sola página, no seguimos.
        data_total.extend(body)
        meta["total_registros_reales"] = (
            len(body) if meta["total_registros_reales"] is None
            else meta["total_registros_reales"] + len(body)
        )
        meta["paginas_seguidas"] += 1
        return None

    if not isinstance(body, dict):
        # No sabemos qué es; lo dejamos tal cual y cortamos.
        if not data_total:
            data_total.append(body)
        return None

    # Wrapper estilo DRF / Generic
    if "results" in body and isinstance(body["results"], list):
        meta["fuente_paginacion"] = "drf"
        meta["total_registros_reales"] = body.get("count", len(body["results"]))
        data_total.extend(body["results"])
        meta["paginas_seguidas"] += 1
        return body.get("next")

    # Wrapper estilo {data: [...], page, total}
    if "data" in body and isinstance(body["data"], list):
        meta["fuente_paginacion"] = "page"
        if meta["total_registros_reales"] is None:
            meta["total_registros_reales"] = body.get("total", len(body["data"]))
        else:
            # Si la API no nos da total en c/página, vamos sumando.
            meta["total_registros_reales"] = (
                meta["total_registros_reales"] or len(body["data"])
            )
        data_total.extend(body["data"])
        meta["paginas_seguidas"] += 1
        return body.get("next") or body.get("next_cursor")

    # Wrapper estilo items / records
    for key in ("items", "records", "rows"):
        if key in body and isinstance(body[key], list):
            meta["fuente_paginacion"] = key
            data_total.extend(body[key])
            meta["paginas_seguidas"] += 1
            meta["total_registros_reales"] = (
                body.get("total", body.get("count"))
                if meta["total_registros_reales"] is None
                else meta["total_registros_reales"] + len(body[key])
            )
            return body.get("next")

    # No es wrapper → lo dejamos como está, no seguimos.
    if not data_total:
        # Si es un dict único (una sola entidad), lo envolvemos en lista
        # para que el resto del pipeline reciba siempre listas.
        data_total.append(body)
    return None


def descargar_con_paginacion(
    url: str,
    timeout: int = 15,
) -> Tuple[Any, Dict]:
    """
    Descarga la URL siguiendo paginación. Devuelve (data, metadata).

    La metadata incluye:
      - fuente_paginacion: "ninguna" | "drf" | "page" | "items" | ...
      - paginas_seguidas: int
      - total_registros_reales: int o None
      - total_registros_analizados: int
      - max_alcanzado: bool (si cortamos por tope)
    """
    data_total: List[Any] = []
    meta: Dict[str, Any] = {
        "fuente_paginacion": "ninguna",
        "paginas_seguidas": 0,
        "total_registros_reales": None,
        "total_registros_analizados": 0,
        "max_alcanzado": False,
    }

    siguiente = url
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": CFG.user_agent,
    }

    pagina_actual = 0
    while siguiente and pagina_actual < CFG.max_paginas:
        # Pausa humana antes de cada request (excepto el primero).
        if pagina_actual > 0:
            esperar_entre_paginas(pagina_actual)
        else:
            esperar(host=siguiente)

        try:
            req = Request(siguiente, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                link_header = resp.headers.get("Link", "")
                content_type = resp.headers.get("Content-Type", "")
                # Guardamos el Content-Type del primer response para que
                # el resto del pipeline sepa si la respuesta fue JSON o no
                # (usado por detectar_pii() para evitar falsos positivos).
                if pagina_actual == 0:
                    meta["content_type"] = content_type
        except (URLError, HTTPError, socket.timeout) as e:
            if pagina_actual == 0:
                raise ErrorDescarga(f"No pude conectar a {url}: {e}") from e
            # En páginas siguientes, cortamos silenciosamente.
            break

        body = _intentar_json(raw, content_type)

        if body is None:
            # No es JSON: devolvemos el texto crudo tal como llegó.
            if pagina_actual == 0:
                return raw.decode("utf-8", errors="replace"), meta
            break

        siguiente_body = _acumular_pagina(body, data_total, meta)

        # Si el header Link dice next, lo priorizamos.
        next_link = _parsear_link_next(link_header)
        if next_link:
            siguiente = next_link
        else:
            siguiente = siguiente_body

        meta["total_registros_analizados"] = len(data_total)
        pagina_actual += 1

        # Tope absoluto por seguridad
        if meta["total_registros_analizados"] >= CFG.max_registros:
            meta["max_alcanzado"] = True
            break

    # Si no acumulamos nada (caso raro), devolvemos None
    if not data_total:
        return None, meta

    # Si solo hay 1 elemento y la fuente era "ninguna", devolvemos el dict
    # original para no alterar la firma del pipeline.
    if meta["fuente_paginacion"] == "ninguna" and len(data_total) == 1:
        return data_total[0], meta

    return data_total, meta


# Compatibilidad con el nombre previo.
_descargar = descargar_con_paginacion