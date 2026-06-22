"""
sensibles.py — Detecta PII y aplica reglas de menores de edad.

Orden de detección:
  1) Por VALOR (regex agnóstica al nombre del campo). Captura datos sensibles
     incluso si el campo se llama raro (ej. "x", "v").
  2) Por NOMBRE de campo, como refuerzo (ej. un campo llamado "apto_medico"
     se reporta aunque el valor esté vacío).
  3) Los valores se normalizan antes de la regex para evitar evasión por
     caracteres invisibles o separadores visuales.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from .normalizar import fue_normalizado, normalizar_para_pii


def _cargar_reglas() -> Dict:
    ruta = Path(__file__).parent.parent / "reglas" / "sensibles.json"
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _aplanar_con_path(data: Any, path: str = "") -> List[Dict]:
    """Genera lista de {path, valor} para todos los nodos hoja."""
    out: List[Dict] = []
    if isinstance(data, dict):
        for k, v in data.items():
            out.extend(_aplanar_con_path(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            out.extend(_aplanar_con_path(item, f"{path}[{i}]"))
    else:
        out.append({"path": path, "valor": str(data) if data is not None else ""})
    return out


def _coincide_por_nombre_campo(nombre_campo: str, lista: List[str]) -> bool:
    nombre = nombre_campo.lower().split(".")[-1]
    return any(p in nombre for p in lista)


def _resultado_skipped(content_type: str) -> Dict:
    """Devuelve un dict de PII vacío con razón de skip explícita."""
    return {
        "total_hallazgos": 0,
        "hallazgos": [],
        "por_categoria": {},
        "por_nivel": {},
        "skipped_reason": (
            f"Detección de PII omitida — la respuesta no es JSON "
            f"(Content-Type: {content_type!r}). Para auditar endpoints "
            f"que devuelven HTML/texto plano, primero envolvélos en un "
            f"proxy que devuelva JSON."
        ),
    }


def detectar_pii(data: Any, content_type: str = None) -> Dict:
    """
    Recorre todos los valores y detecta datos sensibles.
    Primero por regex sobre el valor (agnóstico), luego por nombre.
    Aplica normalización previa para evitar evasión.

    Args:
        data: estructura JSON parseada (dict, list o valor simple).
        content_type: Content-Type HTTP de la respuesta. Si NO empieza
            con 'application/json', se skipea la detección de PII para
            evitar falsos positivos en respuestas HTML, XML o texto plano
            (donde palabras como 'dni' pueden aparecer como copy de
            marketing sin ser datos sensibles reales).
    """
    # Guard contra falsos positivos en respuestas no-JSON.
    # Caso real: el explorador contra clientes.credicuotas.com.ar detectó
    # "dni" en el HTML del home (formulario de login) como PII nivel ALTO.
    if content_type is not None:
        ct_lower = content_type.lower()
        if not ct_lower.startswith("application/json"):
            return _resultado_skipped(content_type)

    reglas = _cargar_reglas()
    patrones = reglas.get("patrones_pii", {})
    campos_nombre = reglas.get("campos_nombre_personal", [])
    campos_salud = reglas.get("campos_salud", [])
    campos_responsable = reglas.get("campos_responsable", [])

    hallazgos: List[Dict] = []
    muestras = _aplanar_con_path(data)

    # Palabras que indican campos con FECHAS OPERATIVAS (no son PII)
    _FECHAS_OPERATIVAS = (
        "prestamo", "devolucion", "vencimiento", "alta", "baja",
        "evento", "clase", "turno", "pago", "factura", "compra",
    )

    for muestra in muestras:
        path = muestra["path"]
        valor_original = muestra["valor"]
        nombre_campo = path.split(".")[-1].split("[")[0].lower()

        # Valor normalizado para comparar contra regex
        valor_norm = normalizar_para_pii(valor_original)

        # ---------- 1) DETECCIÓN POR VALOR (AGNÓSTICA) ----------
        valor_detectado = False
        for nombre_patron, cfg in patrones.items():
            regex = cfg.get("regex", "")
            if not regex:
                continue

            # No marcar fecha_nacimiento en campos operativos
            if nombre_patron == "fecha_nacimiento" and any(
                kw in nombre_campo for kw in _FECHAS_OPERATIVAS
            ):
                continue

            # Comparar primero contra el valor original; si no matchea,
            # intentar contra el normalizado.
            match = re.search(regex, valor_original, re.IGNORECASE)
            metodo = "valor_directo"
            if not match and valor_norm != valor_original:
                match = re.search(regex, valor_norm, re.IGNORECASE)
                if match:
                    metodo = "valor_normalizado"

            if match:
                hallazgos.append({
                    "path": path,
                    "campo": nombre_campo,
                    "tipo_pii": nombre_patron,
                    "categoria": cfg.get("categoria", "desconocida"),
                    "nivel_sensibilidad": cfg.get("nivel_sensibilidad", "medio"),
                    "metodo": metodo,
                    "muestra_truncada": (
                        valor_original[:30] + "..."
                        if len(valor_original) > 30 else valor_original
                    ),
                })
                valor_detectado = True

        # ---------- 2) DETECCIÓN POR NOMBRE (REFUERZO) ----------
        if not valor_detectado:
            if _coincide_por_nombre_campo(nombre_campo, campos_salud):
                hallazgos.append({
                    "path": path,
                    "campo": nombre_campo,
                    "tipo_pii": "salud_por_nombre",
                    "categoria": "salud",
                    "nivel_sensibilidad": "critico",
                    "metodo": "nombre_campo",
                    "muestra_truncada": (
                        valor_original[:30] + "..."
                        if len(valor_original) > 30 else valor_original
                    ),
                })
            elif _coincide_por_nombre_campo(nombre_campo, campos_nombre):
                hallazgos.append({
                    "path": path,
                    "campo": nombre_campo,
                    "tipo_pii": "identidad_por_nombre",
                    "categoria": "identidad",
                    "nivel_sensibilidad": "medio",
                    "metodo": "nombre_campo",
                    "muestra_truncada": (
                        valor_original[:30] + "..."
                        if len(valor_original) > 30 else valor_original
                    ),
                })
            elif _coincide_por_nombre_campo(nombre_campo, campos_responsable):
                hallazgos.append({
                    "path": path,
                    "campo": nombre_campo,
                    "tipo_pii": "responsable_por_nombre",
                    "categoria": "responsable",
                    "nivel_sensibilidad": "alto",
                    "metodo": "nombre_campo",
                    "muestra_truncada": (
                        valor_original[:30] + "..."
                        if len(valor_original) > 30 else valor_original
                    ),
                })

    # ---------- Deduplicar y resumir ----------
    vistos = set()
    filtrados = []
    for h in hallazgos:
        key = (h["path"], h["tipo_pii"])
        if key not in vistos:
            vistos.add(key)
            filtrados.append(h)

    por_categoria: Dict[str, int] = {}
    por_nivel: Dict[str, int] = {}
    for h in filtrados:
        por_categoria[h["categoria"]] = por_categoria.get(h["categoria"], 0) + 1
        por_nivel[h["nivel_sensibilidad"]] = por_nivel.get(h["nivel_sensibilidad"], 0) + 1

    return {
        "total_hallazgos": len(filtrados),
        "hallazgos": filtrados,
        "por_categoria": por_categoria,
        "por_nivel": por_nivel,
    }


def _calcular_edad(fecha_str: str) -> int | None:
    """Intenta parsear la fecha y devolver la edad en años cumplidos."""
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]
    for fmt in formatos:
        try:
            d = datetime.strptime(
                fecha_str[:10] if len(fecha_str) > 10 else fecha_str,
                fmt[:10] if "T" not in fecha_str else "%Y-%m-%d",
            )
            hoy = date.today()
            return hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
        except ValueError:
            continue
    return None


def evaluar_menores(data: Any, pii: Dict, tipo: str) -> Dict:
    """
    Si hay fecha_nacimiento, calcula edad. Devuelve lista de menores detectados
    y los campos de responsable que faltan.
    """
    reglas = _cargar_reglas()
    mayoria = reglas.get("reglas_menores", {}).get("mayoria_edad_default", 18)
    campos_responsable_req = reglas.get("reglas_menores", {}).get(
        "campos_requeridos_para_menor", []
    )

    muestras = _aplanar_con_path(data)
    registros_con_edad = []
    campos_presentes = set()

    for m in muestras:
        nombre = m["path"].split(".")[-1].split("[")[0].lower()
        if "nacimiento" in nombre or "fecha_nac" in nombre:
            edad = _calcular_edad(m["valor"])
            if edad is not None:
                registros_con_edad.append({
                    "path": m["path"],
                    "edad": edad,
                    "valor_fecha": m["valor"],
                })
        campos_presentes.add(nombre)

    total_menores = sum(1 for r in registros_con_edad if r["edad"] < mayoria)
    campos_responsable_faltantes = [
        c for c in campos_responsable_req if c not in campos_presentes
    ]

    return {
        "mayoria_edad_aplicada": mayoria,
        "registros_con_fecha_nacimiento": len(registros_con_edad),
        "total_menores": total_menores,
        "muestra_edades": registros_con_edad[:10],
        "campos_responsable_requeridos": campos_responsable_req,
        "campos_responsable_faltantes": campos_responsable_faltantes,
        "alerta_menores": total_menores > 0 and len(campos_responsable_faltantes) > 0,
    }