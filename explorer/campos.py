"""
campos.py — Recorre la estructura y arma un mapa de campos con sus tipos.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _tipo(valor: Any) -> str:
    """Heurística simple para clasificar el tipo de un valor."""
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "boolean"
    if isinstance(valor, int):
        return "integer"
    if isinstance(valor, float):
        return "float"
    if isinstance(valor, str):
        s = valor.strip()
        try:
            int(s)
            return "string_integer"
        except ValueError:
            pass
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            return "string_date"
        if re.match(r"^\d{2}/\d{2}/\d{4}", s):
            return "string_date"
        if "@" in s and "." in s:
            return "string_email"
        return "string"
    if isinstance(valor, list):
        return "array"
    if isinstance(valor, dict):
        return "object"
    return type(valor).__name__


def inspeccionar_campos(data: Any) -> Dict:
    """
    Recorre la estructura y devuelve:
      {
        "total_registros": int,
        "total_campos_unicos": int,
        "campos": { nombre_campo: { tipo_mayoritario, muestras, nulos, tipos_vistos } },
        "campos_detectados": [ lista_plana_de_keys ]   # para gap analysis
      }
    """
    campos: Dict[str, Dict] = {}
    campos_detectados: List[str] = []
    total_registros = 0

    if isinstance(data, list):
        total_registros = len(data)
        for item in data:
            if isinstance(item, dict):
                for k, v in item.items():
                    t = _tipo(v)
                    if k not in campos:
                        campos[k] = {
                            "tipo_mayoritario": t,
                            "muestras": 0,
                            "nulos": 0,
                            "tipos_vistos": {},
                        }
                    campos[k]["muestras"] += 1
                    if v is None:
                        campos[k]["nulos"] += 1
                    campos[k]["tipos_vistos"][t] = (
                        campos[k]["tipos_vistos"].get(t, 0) + 1
                    )
                    if k not in campos_detectados:
                        campos_detectados.append(k)
    elif isinstance(data, dict):
        if any(isinstance(v, list) for v in data.values()):
            # Wrapper tipo {socios: [...], clases: [...]}
            for k, v in data.items():
                if isinstance(v, list):
                    total_registros += len(v)
                    for item in v:
                        if isinstance(item, dict):
                            for kk, vv in item.items():
                                t = _tipo(vv)
                                if kk not in campos:
                                    campos[kk] = {
                                        "tipo_mayoritario": t,
                                        "muestras": 0,
                                        "nulos": 0,
                                        "tipos_vistos": {},
                                    }
                                campos[kk]["muestras"] += 1
                                if vv is None:
                                    campos[kk]["nulos"] += 1
                                campos[kk]["tipos_vistos"][t] = (
                                    campos[kk]["tipos_vistos"].get(t, 0) + 1
                                )
                                if kk not in campos_detectados:
                                    campos_detectados.append(kk)
        else:
            # Entidad única
            total_registros = 1
            for k, v in data.items():
                t = _tipo(v)
                campos[k] = {
                    "tipo_mayoritario": t,
                    "muestras": 1,
                    "nulos": 1 if v is None else 0,
                    "tipos_vistos": {t: 1},
                }
                campos_detectados.append(k)

    # Elegir tipo mayoritario por si hay mezcla
    for k, info in campos.items():
        if info["tipos_vistos"]:
            tipo_top = max(info["tipos_vistos"].items(), key=lambda x: x[1])[0]
            info["tipo_mayoritario"] = tipo_top

    return {
        "total_registros": total_registros,
        "total_campos_unicos": len(campos),
        "campos": campos,
        "campos_detectados": campos_detectados,  # <-- agregado para gap
    }


def _cargar_patron_tipo(tipo: str) -> Dict:
    if tipo == "desconocido":
        return {}
    ruta = Path(__file__).parent.parent / "reglas" / "patrones_deteccion.json"
    with open(ruta, "r", encoding="utf-8") as f:
        patrones = json.load(f)
    return patrones.get(tipo, {})


def detectar_faltantes(estructura: Dict, tipo: str) -> List[Dict]:
    """
    Compara campos presentes vs campos esperados por el patrón del tipo detectado.
    """
    patron = _cargar_patron_tipo(tipo)
    if not patron:
        return []

    campos_presentes = set(estructura.get("campos", {}).keys())
    faltantes = []

    secciones = [
        ("campos_esperados", "general", True),
        ("campos_socio", "socio", False),
        ("campos_prestamo", "prestamo", False),
        ("campos_clase", "clase", False),
        ("campos_actividad", "actividad", False),
        ("campos_pedido", "pedido", False),
    ]

    for clave, seccion, _ in secciones:
        esperados = patron.get(clave, [])
        obligatorios = set(
            patron.get(f"obligatorios_{seccion}", patron.get("obligatorios", []))
        )
        for campo in esperados:
            if campo not in campos_presentes:
                faltantes.append({
                    "campo_esperado": campo,
                    "seccion": seccion,
                    "obligatorio": campo in obligatorios,
                    "encontrado": False,
                })

    return faltantes