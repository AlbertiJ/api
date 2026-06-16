"""
detectar.py — Detecta el tipo de API por palabras clave.
"""
import re
from typing import Any, Dict, List, Tuple
from pathlib import Path
import json


def _cargar_patrones() -> Dict:
    ruta = Path(__file__).parent.parent / "reglas" / "patrones_deteccion.json"
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _aplanar(data: Any) -> List[str]:
    """Convierte un JSON en una lista de strings (claves y valores cortos) para buscar."""
    encontrados: List[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            encontrados.append(str(k).lower())
            encontrados.extend(_aplanar(v))
    elif isinstance(data, list):
        for item in data[:50]:  # sample
            encontrados.extend(_aplanar(item))
    else:
        s = str(data).lower()
        if len(s) < 80:
            encontrados.append(s)
    return encontrados


def detectar_tipo_api(data: Any, url: str = "") -> Tuple[str, float, List[str]]:
    """
    Devuelve (tipo, confianza 0-1, pistas que detectó).
    """
    patrones = _cargar_patrones()
    corpus = " ".join(_aplanar(data)) + " " + url.lower()

    resultados: List[Tuple[str, float, List[str]]] = []

    for tipo, cfg in patrones.items():
        palabras = cfg.get("palabras_clave", [])
        matches = [p for p in palabras if re.search(rf"\b{re.escape(p)}\b", corpus)]
        if matches:
            score = len(matches) / len(palabras)
            resultados.append((tipo, score, matches))

    if not resultados:
        return ("desconocido", 0.0, [])

    resultados.sort(key=lambda x: x[1], reverse=True)
    tipo_top, score_top, pistas_top = resultados[0]
    return (tipo_top, round(score_top, 2), pistas_top)
