"""
informe.py — Genera el informe legible por humanos (consola).
"""
from __future__ import annotations

from typing import Dict, List


def generar_informe(exploracion: Dict) -> str:
    resumen = exploracion["resumen"]
    faltantes = exploracion["faltantes_reportados"]
    pii = exploracion["pii_detectado"]
    menores = exploracion["reglas_menores"]
    pag = exploracion.get("metadata_paginacion", {})

    lineas: List[str] = []
    sep = "═" * 70
    lineas.append(sep)
    lineas.append("  INFORME DE EXPLORACIÓN DE API")
    lineas.append(sep)
    lineas.append(f"  URL:              {exploracion['url']}")
    lineas.append(f"  Fecha (UTC):      {exploracion['timestamp_utc']}")
    lineas.append(f"  Responsable:      {exploracion['responsable']}")
    lineas.append(f"  Cliente:          {exploracion['cliente']}")
    lineas.append(
        f"  Tipo detectado:   {exploracion['tipo_detectado']}  "
        f"(confianza {exploracion['confianza_deteccion']})"
    )
    pistas = exploracion["pistas_deteccion"]
    lineas.append(f"  Pistas:           {', '.join(pistas) or '(ninguna)'}")
    lineas.append("")
    lineas.append(f"  HASH SHA-256:     {exploracion['hash_sha256']}")
    lineas.append(sep)
    lineas.append("  RESUMEN")
    lineas.append(sep)
    lineas.append(f"   • Registros reales:           {resumen.get('total_registros_reales', '?')}")
    lineas.append(f"   • Registros analizados:       {resumen.get('total_registros_analizados', '?')}")
    lineas.append(f"   • Campos únicos:              {resumen['total_campos']}")
    lineas.append(f"   • Campos faltantes:           {resumen['campos_faltantes']}")
    lineas.append(f"   • Datos sensibles (PII):      {resumen['datos_sensibles_encontrados']}")
    lineas.append(f"   • Menores detectados:         {resumen['menores_detectados']}")
    lineas.append(f"   • Fuente de paginación:       {resumen.get('fuente_paginacion', 'ninguna')}")
    lineas.append(f"   • Pausa entre requests:       {resumen.get('pausa_entre_requests', '?')}s")

    if pag.get("max_alcanzado"):
        lineas.append("   ⚠ Tope de registros alcanzado — exploración parcial.")

    if pii.get("por_nivel"):
        lineas.append("")
        lineas.append("  PII por nivel de sensibilidad:")
        for nivel, cant in pii["por_nivel"].items():
            icono = {"critico": "🔴", "alto": "🟠", "medio": "🟡"}.get(nivel, "⚪")
            lineas.append(f"     {icono} {nivel}: {cant}")

    if menores.get("alerta_menores"):
        lineas.append("")
        lineas.append("  ⚠ ALERTA: Se detectaron menores y faltan campos de responsable:")
        for c in menores["campos_responsable_faltantes"]:
            lineas.append(f"     - {c}")

    lineas.append("")
    lineas.append(sep)
    lineas.append("  CAMPOS FALTANTES")
    lineas.append(sep)
    if not faltantes:
        lineas.append("   ✓ Sin faltantes respecto al patrón del tipo detectado")
    else:
        for f_ in faltantes:
            marca = "[OBLIGATORIO]" if f_["obligatorio"] else "[opcional]"
            lineas.append(f"   {marca} {f_['seccion']}.{f_['campo_esperado']}")

    lineas.append("")
    lineas.append(sep)
    lineas.append("  DATOS SENSIBLES DETECTADOS")
    lineas.append(sep)
    if not pii["hallazgos"]:
        lineas.append("   ✓ Sin datos sensibles detectados")
    else:
        for nivel in ["critico", "alto", "medio"]:
            hs = [h for h in pii["hallazgos"] if h["nivel_sensibilidad"] == nivel]
            if not hs:
                continue
            icono = {"critico": "🔴", "alto": "🟠", "medio": "🟡"}[nivel]
            lineas.append(f"   {icono} {nivel.upper()} ({len(hs)} hallazgos):")
            for h in hs[:20]:
                lineas.append(f"      - {h['path']} → {h['tipo_pii']}  ({h['metodo']})")
            if len(hs) > 20:
                lineas.append(f"      ... y {len(hs) - 20} más (ver archivo completo)")

    lineas.append("")
    lineas.append(sep)
    lineas.append("  ARCHIVOS GENERADOS")
    lineas.append(sep)
    for ruta in exploracion.get("_rutas_generadas", []):
        lineas.append(f"   📄 {ruta}")

    lineas.append("")
    lineas.append(sep)
    lineas.append("  Firma: hash SHA-256 de toda la exploración.")
    lineas.append("  Si el archivo cambia, el hash cambia.")
    lineas.append(sep)
    return "\n".join(lineas)