"""
exportar.py — Genera los archivos JSON / CSV / HTML.
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict


def _ruta(nombre: str, ext: str, directorio: str) -> Path:
    Path(directorio).mkdir(parents=True, exist_ok=True)
    return Path(directorio) / f"{nombre}.{ext}"


def _timestamp_corto() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def exportar_json(auditoria: Dict, directorio: str = "salidas") -> str:
    nombre = f"auditoria-{_timestamp_corto()}-{auditoria['hash_sha256'][:8]}"
    ruta = _ruta(nombre, "json", directorio)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(auditoria, f, indent=2, ensure_ascii=False, default=str)
    return str(ruta)


def exportar_csv(auditoria: Dict, directorio: str = "salidas") -> str:
    nombre = f"auditoria-{_timestamp_corto()}-{auditoria['hash_sha256'][:8]}"
    ruta = _ruta(nombre, "csv", directorio)

    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["SECCIÓN", "CAMPO", "VALOR"])
        w.writerow(["metadatos", "url", auditoria["url"]])
        w.writerow(["metadatos", "timestamp_utc", auditoria["timestamp_utc"]])
        w.writerow(["metadatos", "responsable", auditoria["responsable"]])
        w.writerow(["metadatos", "cliente", auditoria["cliente"]])
        w.writerow(["metadatos", "tipo_detectado", auditoria["tipo_detectado"]])
        w.writerow(["metadatos", "confianza", auditoria["confianza_deteccion"]])
        w.writerow(["metadatos", "hash_sha256", auditoria["hash_sha256"]])
        w.writerow([])
        w.writerow(["RESUMEN"])
        for k, v in auditoria["resumen"].items():
            w.writerow(["resumen", k, v])
        w.writerow([])
        w.writerow(["FALTANTES"])
        for f_ in auditoria["faltantes_reportados"]:
            w.writerow(["faltante", f_["campo_esperado"], f"{f_['seccion']} | obligatorio={f_['obligatorio']}"])
        w.writerow([])
        w.writerow(["PII"])
        for h in auditoria["pii_detectado"]["hallazgos"]:
            w.writerow(["pii", h["path"], f"{h['tipo_pii']} | {h['nivel_sensibilidad']} | {h['metodo']}"])
        w.writerow([])
        w.writerow(["MENORES"])
        w.writerow(["menores", "total_menores", auditoria["reglas_menores"]["total_menores"]])
        w.writerow(["menores", "alerta_menores", auditoria["reglas_menores"]["alerta_menores"]])
        for c in auditoria["reglas_menores"]["campos_responsable_faltantes"]:
            w.writerow(["menores", "FALTA_responsable", c])
    return str(ruta)


def _html_escape(s) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def exportar_html(auditoria: Dict, directorio: str = "salidas") -> str:
    nombre = f"auditoria-{_timestamp_corto()}-{auditoria['hash_sha256'][:8]}"
    ruta = _ruta(nombre, "html", directorio)

    resumen = auditoria["resumen"]
    faltantes = auditoria["faltantes_reportados"]
    pii = auditoria["pii_detectado"]
    menores = auditoria["reglas_menores"]

    filas_faltantes = "".join(
        f"<tr class='{'critico' if f_['obligatorio'] else 'suave'}'>"
        f"<td>{_html_escape(f_['campo_esperado'])}</td>"
        f"<td>{_html_escape(f_['seccion'])}</td>"
        f"<td>{'SÍ' if f_['obligatorio'] else 'no'}</td>"
        f"<td>NO TRAÍDO</td></tr>"
        for f_ in faltantes
    ) or "<tr><td colspan='4'>Sin faltantes</td></tr>"

    filas_pii = "".join(
        f"<tr class='{_html_escape(h['nivel_sensibilidad'])}'>"
        f"<td>{_html_escape(h['path'])}</td>"
        f"<td>{_html_escape(h['campo'])}</td>"
        f"<td>{_html_escape(h['tipo_pii'])}</td>"
        f"<td>{_html_escape(h['categoria'])}</td>"
        f"<td>{_html_escape(h['nivel_sensibilidad'])}</td>"
        f"<td>{_html_escape(h['metodo'])}</td></tr>"
        for h in pii["hallazgos"]
    ) or "<tr><td colspan='6'>Sin hallazgos PII</td></tr>"

    alerta_menores = ""
    if menores.get("alerta_menores"):
        alerta_menores = f"""
        <div class='alerta'>
          ⚠ Se detectaron <b>{menores['total_menores']}</b> posible(s) menor(es) de edad,
          y faltan los siguientes campos de responsable obligatorio:
          <ul>{''.join(f'<li>{_html_escape(c)}</li>' for c in menores['campos_responsable_faltantes'])}</ul>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<title>Auditoría {_html_escape(auditoria['hash_sha256'][:16])}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 2rem; color: #1d1d1f; background: #fafafa; }}
  h1 {{ color: #1d1d1f; border-bottom: 2px solid #0071e3; padding-bottom: .3rem; }}
  h2 {{ margin-top: 2rem; color: #0071e3; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; background: white; }}
  th, td {{ border: 1px solid #e0e0e0; padding: .5rem .75rem; text-align: left; }}
  th {{ background: #f5f5f7; }}
  .critico {{ background: #ffe5e5; }}
  .critico, .salud, .alto {{ background: #ffe5e5; }}
  .medio {{ background: #fff4e0; }}
  .suave {{ background: #fff8d0; }}
  .hash {{ font-family: monospace; background: #1d1d1f; color: #5ac8fa; padding: .75rem 1rem; border-radius: 8px; word-break: break-all; }}
  .alerta {{ background: #ffe5e5; border-left: 4px solid #ff3b30; padding: 1rem; margin: 1rem 0; border-radius: 4px; }}
  .meta {{ background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e0e0e0; }}
  .meta p {{ margin: .25rem 0; }}
  .resumen-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1rem 0; }}
  .resumen-card {{ background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e0e0e0; }}
  .resumen-card .numero {{ font-size: 2rem; font-weight: 600; color: #0071e3; }}
  .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; color: #6e6e73; font-size: .85rem; }}
</style>
</head><body>
<h1>Informe de Auditoría de Migración</h1>

<div class='meta'>
  <p><b>URL inspeccionada:</b> {_html_escape(auditoria['url'])}</p>
  <p><b>Fecha y hora (UTC):</b> {_html_escape(auditoria['timestamp_utc'])}</p>
  <p><b>Responsable de la auditoría:</b> {_html_escape(auditoria['responsable'])}</p>
  <p><b>Cliente:</b> {_html_escape(auditoria['cliente'])}</p>
  <p><b>Tipo de API detectado:</b> {_html_escape(auditoria['tipo_detectado'])} (confianza {auditoria['confianza_deteccion']})</p>
  <p><b>Pistas que dispararon la detección:</b> {_html_escape(', '.join(auditoria['pistas_deteccion']))}</p>
</div>

<h2>Hash de integridad SHA-256</h2>
<div class='hash'>{auditoria['hash_sha256']}</div>

<h2>Resumen</h2>
<div class='resumen-grid'>
  <div class='resumen-card'><div class='numero'>{resumen['total_registros']}</div>registros</div>
  <div class='resumen-card'><div class='numero'>{resumen['total_campos']}</div>campos</div>
  <div class='resumen-card'><div class='numero'>{resumen['campos_faltantes']}</div>faltantes</div>
  <div class='resumen-card'><div class='numero'>{resumen['datos_sensibles_encontrados']}</div>PII</div>
</div>

{alerta_menores}

<h2>Campos faltantes (lo que el cliente NO trajo)</h2>
<table>
  <thead><tr><th>Campo esperado</th><th>Sección</th><th>Obligatorio</th><th>Estado</th></tr></thead>
  <tbody>{filas_faltantes}</tbody>
</table>

<h2>Datos sensibles detectados (PII)</h2>
<table>
  <thead><tr><th>Path</th><th>Campo</th><th>Tipo</th><th>Categoría</th><th>Nivel</th><th>Método</th></tr></thead>
  <tbody>{filas_pii}</tbody>
</table>

<div class='footer'>
  Generado por api-inspector. Este informe es la prueba forense de lo auditado.
  El hash SHA-256 garantiza que ni el contenido ni el momento han sido alterados.
</div>
</body></html>"""

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    return str(ruta)
