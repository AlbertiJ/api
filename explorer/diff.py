"""
diff.py — Compara dos exploraciones de la misma API y reporta cambios.

Caso de uso: el dueño de la API agrega un campo, saca otro, cambia el
tipo de un tercero. La semana pasada auditaste; esta semana volvés a
auditar. diff_forense() te dice qué cambió sin tener que abrir los
dos JSON a mano.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def diff_forense(actual: Dict, previa: Dict) -> Dict[str, Any]:
    """
    Compara dos payloads de exploración.

    Devuelve un dict con:
      - campos_nuevos / campos_eliminados / campos_tipo_cambiado
      - pii_nuevos / pii_eliminados
      - faltantes_resueltos / faltantes_nuevos
      - cambios_paginacion (si la API pasó a paginar, o dejó de hacerlo)
      - resumen (cifras agregadas)

    Si querés encadenar hashes para detectar manipulación, llamá a
    encadenar_hash() después.
    """
    est_actual = actual.get("estructura", {})
    est_previa = previa.get("estructura", {})

    campos_actual = set(est_actual.get("campos", {}).keys())
    campos_prev = set(est_previa.get("campos", {}).keys())

    pii_actual = {
        (h["path"], h["tipo_pii"])
        for h in actual.get("pii_detectado", {}).get("hallazgos", [])
    }
    pii_prev = {
        (h["path"], h["tipo_pii"])
        for h in previa.get("pii_detectado", {}).get("hallazgos", [])
    }

    faltantes_actual = {
        f["campo_esperado"]
        for f in actual.get("faltantes_reportados", [])
    }
    faltantes_prev = {
        f["campo_esperado"]
        for f in previa.get("faltantes_reportados", [])
    }

    tipos_actual = {
        k: v.get("tipo_mayoritario")
        for k, v in est_actual.get("campos", {}).items()
    }
    tipos_prev = {
        k: v.get("tipo_mayoritario")
        for k, v in est_previa.get("campos", {}).items()
    }

    cambios_tipo = {
        k: {"antes": tipos_prev.get(k), "ahora": tipos_actual.get(k)}
        for k in (campos_prev & campos_actual)
        if tipos_prev.get(k) != tipos_actual.get(k)
    }

    # Paginación
    pag_actual = actual.get("metadata_paginacion", {})
    pag_prev = previa.get("metadata_paginacion", {})

    cambios_pag = {}
    if pag_actual.get("fuente_paginacion") != pag_prev.get("fuente_paginacion"):
        cambios_pag["fuente_paginacion"] = {
            "antes": pag_prev.get("fuente_paginacion"),
            "ahora": pag_actual.get("fuente_paginacion"),
        }
    if pag_actual.get("total_registros_reales") != pag_prev.get("total_registros_reales"):
        cambios_pag["total_registros_reales"] = {
            "antes": pag_prev.get("total_registros_reales"),
            "ahora": pag_actual.get("total_registros_reales"),
        }

    return {
        "auditoria_previa_hash": previa.get("hash_sha256"),
        "auditoria_actual_hash": actual.get("hash_sha256"),
        "campos_nuevos": sorted(campos_actual - campos_prev),
        "campos_eliminados": sorted(campos_prev - campos_actual),
        "campos_tipo_cambiado": cambios_tipo,
        "pii_nuevos": sorted(pii_actual - pii_prev),
        "pii_eliminados": sorted(pii_prev - pii_actual),
        "faltantes_resueltos": sorted(faltantes_prev - faltantes_actual),
        "faltantes_nuevos": sorted(faltantes_actual - faltantes_prev),
        "cambios_paginacion": cambios_pag,
        "resumen": {
            "score_cambios": (
                len(campos_actual - campos_prev)
                + len(campos_prev - campos_actual)
                + len(cambios_tipo)
            ),
            "delta_pii": len(pii_actual - pii_prev) - len(pii_prev - pii_actual),
            "delta_faltantes": (
                len(faltantes_prev - faltantes_actual)
                - len(faltantes_actual - faltantes_prev)
            ),
        },
    }


def encadenar_hash(actual: Dict, hash_previo: str) -> str:
    """
    Devuelve un nuevo hash SHA-256 que incorpora el hash anterior.
    Si alguien edita el informe viejo, este hash también cambia.
    Útil para una cadena forense temporal.
    """
    import hashlib
    import json

    payload = json.dumps(actual, sort_keys=True, ensure_ascii=False, default=str)
    cadena = (hash_previo or "") + "|" + payload
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def formatear_diff_texto(diff: Dict) -> str:
    """Devuelve una versión en texto plano del diff, para consola."""
    lineas = []
    sep = "─" * 70

    lineas.append(sep)
    lineas.append("  CAMBIOS DESDE LA EXPLORACIÓN ANTERIOR")
    lineas.append(sep)

    if diff["auditoria_previa_hash"]:
        lineas.append(f"  Hash previo:  {diff['auditoria_previa_hash'][:16]}…")
    if diff["auditoria_actual_hash"]:
        lineas.append(f"  Hash actual:  {diff['auditoria_actual_hash'][:16]}…")
    lineas.append("")

    if diff["campos_nuevos"]:
        lineas.append(f"  + Campos nuevos ({len(diff['campos_nuevos'])}):")
        for c in diff["campos_nuevos"]:
            lineas.append(f"      + {c}")
    if diff["campos_eliminados"]:
        lineas.append(f"  - Campos eliminados ({len(diff['campos_eliminados'])}):")
        for c in diff["campos_eliminados"]:
            lineas.append(f"      - {c}")
    if diff["campos_tipo_cambiado"]:
        lineas.append(f"  ↻ Tipo cambiado ({len(diff['campos_tipo_cambiado'])}):")
        for c, cambio in diff["campos_tipo_cambiado"].items():
            lineas.append(f"      {c}: {cambio['antes']} → {cambio['ahora']}")

    if diff["pii_nuevos"]:
        lineas.append(f"  ⚠ PII nuevos ({len(diff['pii_nuevos'])}):")
        for p in diff["pii_nuevos"]:
            lineas.append(f"      + {p[0]} → {p[1]}")
    if diff["pii_eliminados"]:
        lineas.append(f"  PII eliminados ({len(diff['pii_eliminados'])}):")
        for p in diff["pii_eliminados"]:
            lineas.append(f"      - {p[0]} → {p[1]}")

    if diff["faltantes_resueltos"]:
        lineas.append(f"  ✓ Faltantes resueltos ({len(diff['faltantes_resueltos'])}):")
        for c in diff["faltantes_resueltos"]:
            lineas.append(f"      ✓ {c}")
    if diff["faltantes_nuevos"]:
        lineas.append(f"  ✗ Faltantes nuevos ({len(diff['faltantes_nuevos'])}):")
        for c in diff["faltantes_nuevos"]:
            lineas.append(f"      ✗ {c}")

    if diff["cambios_paginacion"]:
        lineas.append("  Paginación:")
        for k, v in diff["cambios_paginacion"].items():
            lineas.append(f"      {k}: {v['antes']} → {v['ahora']}")

    r = diff["resumen"]
    lineas.append("")
    lineas.append(f"  Score de cambios: {r['score_cambios']}")
    lineas.append(f"  Δ PII: {r['delta_pii']:+d}")
    lineas.append(f"  Δ Faltantes: {r['delta_faltantes']:+d}")
    lineas.append(sep)
    return "\n".join(lineas)


# Compatibilidad con el nombre que proponía INGENIERIA.md
comparar_auditorias = diff_forense