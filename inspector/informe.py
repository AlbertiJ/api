"""
informe.py — Genera el informe en texto plano (consola).
"""
from typing import Dict


def generar_informe(auditoria: Dict) -> str:
    resumen = auditoria["resumen"]
    faltantes = auditoria["faltantes_reportados"]
    pii = auditoria["pii_detectado"]
    menores = auditoria["reglas_menores"]

    lineas = []
    sep = "═" * 70
    lineas.append(sep)
    lineas.append("  INFORME DE AUDITORÍA DE MIGRACIÓN DE DATOS")
    lineas.append(sep)
    lineas.append(f"  URL:              {auditoria['url']}")
    lineas.append(f"  Fecha (UTC):      {auditoria['timestamp_utc']}")
    lineas.append(f"  Responsable:      {auditoria['responsable']}")
    lineas.append(f"  Cliente:          {auditoria['cliente']}")
    lineas.append(f"  Tipo detectado:   {auditoria['tipo_detectado']}  (confianza {auditoria['confianza_deteccion']})")
    lineas.append(f"  Pistas:           {', '.join(auditoria['pistas_deteccion']) or '(ninguna)'}")
    lineas.append("")
    lineas.append(f"  HASH SHA-256:     {auditoria['hash_sha256']}")
    lineas.append(sep)
    lineas.append("  RESUMEN")
    lineas.append(sep)
    lineas.append(f"   • Registros:                 {resumen['total_registros']}")
    lineas.append(f"   • Campos únicos:             {resumen['total_campos']}")
    lineas.append(f"   • Campos faltantes:          {resumen['campos_faltantes']}")
    lineas.append(f"   • Datos sensibles (PII):     {resumen['datos_sensibles_encontrados']}")
    lineas.append(f"   • Menores detectados:        {resumen['menores_detectados']}")

    if pii.get("por_nivel"):
        lineas.append("")
        lineas.append("  PII por nivel de sensibilidad:")
        for nivel, cant in pii["por_nivel"].items():
            icono = {"critico": "🔴", "alto": "🟠", "medio": "🟡"}.get(nivel, "⚪")
            lineas.append(f"     {icono} {nivel}: {cant}")

    if menores.get("alerta_menores"):
        lineas.append("")
        lineas.append("  ⚠ ALERTA: Se detectaron menores de edad y faltan campos de responsable:")
        for c in menores["campos_responsable_faltantes"]:
            lineas.append(f"     - {c}")

    lineas.append("")
    lineas.append(sep)
    lineas.append("  CAMPOS FALTANTES (lo que el cliente omitió)")
    lineas.append(sep)
    if not faltantes:
        lineas.append("   ✓ Sin faltantes respecto al patrón del tipo detectado")
    else:
        for f_ in faltantes:
            marca = "[OBLIGATORIO]" if f_["obligatorio"] else "[opcional]"
            lineas.append(f"   {marca} {f_['seccion']}.{f_['campo_esperado']}")

    lineas.append("")
    lineas.append(sep)
    lineas.append("  DATOS SENSIBLES DETECTADOS (PII)")
    lineas.append(sep)
    if not pii["hallazgos"]:
        lineas.append("   ✓ Sin datos sensibles detectados")
    else:
        # agrupar por nivel
        for nivel in ["critico", "alto", "medio"]:
            hs = [h for h in pii["hallazgos"] if h["nivel_sensibilidad"] == nivel]
            if not hs:
                continue
            icono = {"critico": "🔴", "alto": "🟠", "medio": "🟡"}[nivel]
            lineas.append(f"   {icono} {nivel.upper()} ({len(hs)} hallazgos):")
            for h in hs[:20]:  # cap visual
                lineas.append(f"      - {h['path']} → {h['tipo_pii']}  ({h['metodo']})")
            if len(hs) > 20:
                lineas.append(f"      ... y {len(hs) - 20} más (ver archivo completo)")

    lineas.append("")
    lineas.append(sep)
    lineas.append(f"  Archivos generados:")
    lineas.append(sep)
    for ruta in auditoria.get("_rutas_generadas", []):
        lineas.append(f"   📄 {ruta}")
    lineas.append("")
    lineas.append(f"  Firma digital: hash SHA-256 de la auditoría completa.")
    lineas.append(f"  El cliente y el auditor conservan copia. Cualquier modificación rompe el hash.")
    lineas.append(sep)
    return "\n".join(lineas)
