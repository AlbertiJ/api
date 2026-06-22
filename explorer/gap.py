"""
gap.py — Compara campos detectados contra una lista de campos "oficiales".

Caso de uso: el dueño de la API dice "estos son los campos que existen".
Cuando exploramos, encontramos otros. Algunos son extras (campos fantasma),
algunos faltan.
"""
from __future__ import annotations

from typing import Any, Dict, List


def analizar_brechas(
    estructura: Dict[str, Any], campos_oficiales: List[str]
) -> Dict[str, Any]:
    """
    Args:
        estructura: dict que viene de inspeccionar_campos() — tiene
            "campos" (con tipos) y "campos_detectados" (lista plana).
        campos_oficiales: lista de nombres de campos que la documentación
            dice que la API expone.

    Returns:
        {
            "campos_fantasma": [extras que aparecieron sin estar documentados],
            "campos_faltantes": [oficiales que NO aparecieron],
            "campos_validados": [oficiales que sí están],
            "total_reales": int,
            "total_oficiales": int,
            "porcentaje_coincidencia": float (0-100)
        }
    """
    campos_reales = set(estructura.get("campos_detectados", []))
    if not campos_reales:
        # Fallback por si viniera un dict con "campos" tipo dict, no lista
        campos_reales = set(estructura.get("campos", {}).keys())

    oficiales = {c.lower() for c in campos_oficiales}

    fantasma = campos_reales - oficiales
    faltantes = oficiales - campos_reales
    interseccion = campos_reales & oficiales

    pct = round((len(interseccion) / len(oficiales)) * 100, 2) if oficiales else 0

    return {
        "campos_fantasma": sorted(fantasma),
        "campos_faltantes": sorted(faltantes),
        "campos_validados": sorted(interseccion),
        "total_reales": len(campos_reales),
        "total_oficiales": len(oficiales),
        "porcentaje_coincidencia": pct,
    }