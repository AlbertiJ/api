"""
sensibles.py — Detecta PII y aplica reglas de menores de edad.
"""
import re
from typing import Any, Dict, List
from datetime import datetime, date
from pathlib import Path
import json


def _cargar_reglas() -> Dict:
    ruta = Path(__file__).parent.parent / "reglas" / "sensibles.json"
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _aplanar_con_path(data: Any, path: str = "") -> List[Dict]:
    """Genera lista de {path, valor} para todo valor de la estructura."""
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


def detectar_pii(data: Any) -> Dict:
    """
    Recorre todos los valores y detecta datos sensibles por regex + por nombre de campo.
    """
    reglas = _cargar_reglas()
    patrones = reglas.get("patrones_pii", {})
    campos_nombre = reglas.get("campos_nombre_personal", [])
    campos_salud = reglas.get("campos_salud", [])
    campos_responsable = reglas.get("campos_responsable", [])

    hallazgos: List[Dict] = []
    muestras = _aplanar_con_path(data)

    for muestra in muestras:
        path = muestra["path"]
        valor = muestra["valor"]
        nombre_campo = path.split(".")[-1].split("[")[0].lower()

        # Si el campo ya es PII obvio por nombre (DNI, email, telefono, etc.) saltamos la regex
        # para no re-clasificar el mismo valor en categorías equivocadas.
        campo_obvio = None
        if "dni" in nombre_campo and "responsable" not in nombre_campo:
            campo_obvio = "dni"
        elif "email" in nombre_campo or "mail" in nombre_campo:
            campo_obvio = "email"
        elif "telefono" in nombre_campo or "phone" in nombre_campo or "celular" in nombre_campo:
            campo_obvio = "telefono"
        elif "cuit" in nombre_campo or "cuil" in nombre_campo:
            campo_obvio = "cuit_cuil"
        elif "nacimiento" in nombre_campo or "fecha_nac" in nombre_campo:
            campo_obvio = "fecha_nacimiento"
        elif "prestamo" in nombre_campo or "devolucion" in nombre_campo or "vencimiento" in nombre_campo or "fecha_evento" in nombre_campo:
            campo_obvio = None  # fechas operativas, NO son PII por sí mismas

        # 1) Por regex (solo si el campo NO es obvio por nombre)
        if campo_obvio is None:
            for nombre_patron, cfg in patrones.items():
                regex = cfg.get("regex", "")
                if not regex:
                    continue
                # No aplicar regex de fecha a campos que sean fechas operativas
                if nombre_patron == "fecha_nacimiento" and any(
                    kw in nombre_campo for kw in ["prestamo", "devolucion", "vencimiento", "alta", "baja", "evento", "clase", "turno"]
                ):
                    continue
                if re.search(regex, valor, re.IGNORECASE):
                    hallazgos.append({
                        "path": path,
                        "campo": nombre_campo,
                        "tipo_pii": nombre_patron,
                        "categoria": cfg.get("categoria", "desconocida"),
                        "nivel_sensibilidad": cfg.get("nivel_sensibilidad", "medio"),
                        "metodo": "regex_valor",
                        "muestra_truncada": (valor[:30] + "...") if len(valor) > 30 else valor,
                    })
        else:
            # Reportar por nombre con categoría específica
            cfg = patrones.get(campo_obvio, {"categoria": "desconocida", "nivel_sensibilidad": "medio"})
            hallazgos.append({
                "path": path,
                "campo": nombre_campo,
                "tipo_pii": campo_obvio,
                "categoria": cfg.get("categoria", "desconocida"),
                "nivel_sensibilidad": cfg.get("nivel_sensibilidad", "medio"),
                "metodo": "nombre_campo_explicito",
                "muestra_truncada": (valor[:30] + "...") if len(valor) > 30 else valor,
            })

        # 2) Por nombre de campo (incluso si el valor está vacío)
        if _coincide_por_nombre_campo(nombre_campo, campos_salud):
            hallazgos.append({
                "path": path,
                "campo": nombre_campo,
                "tipo_pii": "salud_por_nombre",
                "categoria": "salud",
                "nivel_sensibilidad": "critico",
                "metodo": "nombre_campo",
                "muestra_truncada": (valor[:30] + "...") if len(valor) > 30 else valor,
            })
        elif _coincide_por_nombre_campo(nombre_campo, campos_nombre):
            hallazgos.append({
                "path": path,
                "campo": nombre_campo,
                "tipo_pii": "identidad_por_nombre",
                "categoria": "identidad",
                "nivel_sensibilidad": "medio",
                "metodo": "nombre_campo",
                "muestra_truncada": (valor[:30] + "...") if len(valor) > 30 else valor,
            })
        elif _coincide_por_nombre_campo(nombre_campo, campos_responsable):
            hallazgos.append({
                "path": path,
                "campo": nombre_campo,
                "tipo_pii": "responsable_por_nombre",
                "categoria": "responsable",
                "nivel_sensibilidad": "alto",
                "metodo": "nombre_campo",
                "muestra_truncada": (valor[:30] + "...") if len(valor) > 30 else valor,
            })

    # quitar duplicados por (path, tipo_pii)
    vistos = set()
    filtrados = []
    for h in hallazgos:
        key = (h["path"], h["tipo_pii"])
        if key not in vistos:
            vistos.add(key)
            filtrados.append(h)

    # categorizar para resumen
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
    """Intenta parsear la fecha y calcular edad."""
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]
    for fmt in formatos:
        try:
            d = datetime.strptime(fecha_str[:10] if len(fecha_str) > 10 else fecha_str, fmt[:10] if "T" not in fecha_str else "%Y-%m-%d")
            hoy = date.today()
            return hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
        except ValueError:
            continue
    return None


def evaluar_menores(data: Any, pii: Dict, tipo: str) -> Dict:
    """
    Si hay fecha_nacimiento + nombres que parecen personas, calcula edad.
    Devuelve lista de menores detectados y campos de responsable faltantes.
    """
    reglas = _cargar_reglas()
    mayoria = reglas.get("reglas_menores", {}).get("mayoria_edad_default", 18)
    campos_responsable_req = reglas.get("reglas_menores", {}).get("campos_requeridos_para_menor", [])

    muestras = _aplanar_con_path(data)
    registros_con_edad = []
    campos_presentes = set()

    for m in muestras:
        nombre = m["path"].split(".")[-1].split("[")[0].lower()
        if "nacimiento" in nombre or "fecha_nac" in nombre:
            edad = _calcular_edad(m["valor"])
            if edad is not None:
                registros_con_edad.append({"path": m["path"], "edad": edad, "valor_fecha": m["valor"]})
        campos_presentes.add(nombre)

    total_menores = sum(1 for r in registros_con_edad if r["edad"] < mayoria)

    # Qué campos de responsable faltan
    campos_responsable_faltantes = [c for c in campos_responsable_req if c not in campos_presentes]

    return {
        "mayoria_edad_aplicada": mayoria,
        "registros_con_fecha_nacimiento": len(registros_con_edad),
        "total_menores": total_menores,
        "muestra_edades": registros_con_edad[:10],
        "campos_responsable_requeridos": campos_responsable_req,
        "campos_responsable_faltantes": campos_responsable_faltantes,
        "alerta_menores": total_menores > 0 and len(campos_responsable_faltantes) > 0,
    }
