"""
detectar.py — Adivina el tipo de API combinando señales.

Las pistas vienen de tres lugares, con pesos distintos:
  - Segmentos de la URL (peso 2.0) — la URL es muy explícita cuando
    la API es minimal.
  - Keys de primer nivel del JSON (peso 1.5) — son nombres estables.
  - Valores del JSON (peso 1.0) — son ruidosos pero suman.

Devuelve (tipo, confianza 0-1, lista_de_pistas).
Las pistas indican de dónde salió cada match: "url:natacion",
"key:id_socio", "val:apto_medico".
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def _cargar_patrones() -> Dict:
    ruta = Path(__file__).parent.parent / "reglas" / "patrones_deteccion.json"
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _segmentos_url(url: str) -> Set[str]:
    """
    Divide la URL en segmentos normalizados.
    'https://api.biblioteca.com.ar/v1/socios/natacion' →
    {'biblioteca', 'com', 'ar', 'v1', 'socios', 'natacion'}
    """
    if not url:
        return set()
    path = url.split("://", 1)[-1]
    path = re.sub(r"[/\-_.?&=:]", " ", path)
    return {p for p in path.lower().split() if len(p) > 2}


def _keys_y_valores(data: Any, max_items: int = 50) -> Tuple[Set[str], List[str]]:
    """
    Devuelve (set_de_keys_de_primer_nivel, lista_de_valores_cortos).
    Considera keys de los primeros N items de cada lista.
    """
    keys: Set[str] = set()
    valores: List[str] = []

    def _agregar_de_item(item: Any) -> None:
        if isinstance(item, dict):
            for k in item.keys():
                if isinstance(k, str):
                    keys.add(k.lower())
            for v in item.values():
                if isinstance(v, (str, int, float)):
                    valores.append(str(v).lower())
                elif isinstance(v, bool):
                    valores.append(str(v).lower())

    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str):
                keys.add(k.lower())
            if isinstance(v, list):
                for item in v[:max_items]:
                    _agregar_de_item(item)
            else:
                _agregar_de_item({k: v})
    elif isinstance(data, list):
        for item in data[:max_items]:
            _agregar_de_item(item)

    return keys, valores


def detectar_tipo_api(data: Any, url: str = "") -> Tuple[str, float, List[str]]:
    """
    Devuelve (tipo, confianza 0-1, pistas que detectó).
    """
    patrones = _cargar_patrones()
    segmentos = _segmentos_url(url)
    keys, valores = _keys_y_valores(data)

    resultados: List[Tuple[str, float, List[str]]] = []

    for tipo, cfg in patrones.items():
        palabras = cfg.get("palabras_clave", [])
        score = 0.0
        matches: List[str] = []

        for p in palabras:
            # 1) Match en la URL
            if p in segmentos:
                score += 2.0
                matches.append(f"url:{p}")
                continue
            # 2) Match en keys de primer nivel
            if p in keys:
                score += 1.5
                matches.append(f"key:{p}")
                continue
            # 3) Match en valores (solo strings cortos para no enlentecer)
            for v in valores:
                if len(v) < 80 and p in v:
                    score += 1.0
                    matches.append(f"val:{p}")
                    break

        if matches:
            # Normalizar contra el "techo" de lo que se podría haber
            # conseguido si TODO el corpus matcheara en keys (1.5x).
            score_norm = min(score / (len(palabras) * 1.5), 1.0)
            resultados.append((tipo, round(score_norm, 2), matches))

    if not resultados:
        return ("desconocido", 0.0, [])

    resultados.sort(key=lambda x: x[1], reverse=True)
    tipo_top, score_top, pistas_top = resultados[0]
    return (tipo_top, score_top, pistas_top)